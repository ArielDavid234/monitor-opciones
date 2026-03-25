import json
import os
import unittest
from unittest.mock import patch

from infrastructure.caching.cache_manager import CacheManager
from infrastructure.platform.api_v1 import PublicApiV1
from infrastructure.platform.event_bus import InternalEventBus
from infrastructure.platform.rbac import (
    CAP_CONFIG_UPDATE,
    CAP_MODEL_PROMOTE,
    CAP_PROVIDER_SWITCH,
    CAP_REPORT_VIEW,
    CAP_SCAN_EXECUTE,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OWNER,
    ROLE_VIEWER,
    authorize,
)
from infrastructure.platform.schema_registry import SchemaRegistry


class _FakeAuth:
    def __init__(self):
        self._store = {
            ("u1", "tenant:alpha:latest_scan_opportunities"): [{"Ticker": "SPY", "Spot": 530.0, "provider": "yfinance"}],
            ("u1", "tenant:alpha:latest_score_explainability"): {
                "ticker": "SPY",
                "score_unificado": 88.5,
                "perfil_riesgo": "Balanceada",
            },
            ("u1", "tenant:alpha:latest_smart_alerts"): [{"Ticker": "SPY", "Score Unificado": 86.0}],
        }

    def load_user_data(self, user_id, key):
        return self._store.get((user_id, key))

    def load_user_data_tenant(self, user_id, tenant_id, key):
        return self._store.get((user_id, f"tenant:{tenant_id}:{key}"))


class TestStep10Enterprise(unittest.TestCase):
    def test_multi_tenant_cache_isolation(self):
        cache = CacheManager(redis_url="")
        cache.clear_all()
        cache.set_tenant("alpha", "market:SPY", {"v": 1}, ttl=60)
        cache.set_tenant("beta", "market:SPY", {"v": 2}, ttl=60)

        alpha = cache.get_tenant("alpha", "market:SPY")
        beta = cache.get_tenant("beta", "market:SPY")
        raw = cache.get("market:SPY")

        self.assertEqual(alpha["v"], 1)
        self.assertEqual(beta["v"], 2)
        self.assertIsNone(raw)

    def test_rbac_permissions(self):
        viewer = authorize(user={"id": "u", "role": ROLE_VIEWER, "tenant_id": "alpha"}, capability=CAP_REPORT_VIEW, tenant_id="alpha")
        analyst = authorize(user={"id": "u", "role": ROLE_ANALYST, "tenant_id": "alpha"}, capability=CAP_SCAN_EXECUTE, tenant_id="alpha")
        admin = authorize(user={"id": "u", "role": ROLE_ADMIN, "tenant_id": "alpha"}, capability=CAP_PROVIDER_SWITCH, tenant_id="alpha")
        owner = authorize(user={"id": "u", "role": ROLE_OWNER, "tenant_id": "alpha"}, capability=CAP_MODEL_PROMOTE, tenant_id="alpha")
        denied = authorize(user={"id": "u", "role": ROLE_ANALYST, "tenant_id": "alpha"}, capability=CAP_CONFIG_UPDATE, tenant_id="alpha")

        self.assertTrue(viewer.allowed)
        self.assertTrue(analyst.allowed)
        self.assertTrue(admin.allowed)
        self.assertTrue(owner.allowed)
        self.assertFalse(denied.allowed)

    def test_api_v1_contracts_and_version(self):
        fake_auth = _FakeAuth()
        api = PublicApiV1(fake_auth)
        token_map = {
            "tok-alpha": {
                "user_id": "u1",
                "tenant_id": "alpha",
                "plan": "enterprise",
                "role": "owner",
            }
        }

        with patch.dict(os.environ, {"PUBLIC_API_TOKENS_JSON": json.dumps(token_map)}, clear=False):
            code_opp, body_opp = api.handle_request(path="/api/v1/opportunities", token="tok-alpha", tenant_id="alpha", payload={"ticker": "SPY"})
            code_score, body_score = api.handle_request(path="/api/v1/score-explainable", token="tok-alpha", tenant_id="alpha")
            code_alert, body_alert = api.handle_request(path="/api/v1/alerts-smart", token="tok-alpha", tenant_id="alpha")
            code_health, body_health = api.handle_request(path="/api/v1/health", token="tok-alpha", tenant_id="alpha")

        self.assertEqual(code_opp, 200)
        self.assertEqual(code_score, 200)
        self.assertEqual(code_alert, 200)
        self.assertEqual(code_health, 200)
        for body in (body_opp, body_score, body_alert, body_health):
            self.assertEqual(body["api_version"], "v1")
            self.assertIn("route", body)
            self.assertIn("status", body)
            self.assertIn("data", body)

    def test_event_bus_publish_consume_and_idempotency(self):
        bus = InternalEventBus()
        captured = []

        def _handler(event):
            captured.append(event)

        bus.subscribe("scan_requested", _handler)
        payload = {
            "event_id": "evt-1",
            "ticker": "SPY",
            "score_unificado": 85.0,
            "severity": "info",
            "timestamp": "2026-03-23T00:00:00Z",
        }
        first = bus.publish("scan_requested", payload, event_id="evt-1", schema_name="alert_event")
        second = bus.publish("scan_requested", payload, event_id="evt-1", schema_name="alert_event")

        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertEqual(len(captured), 1)

    def test_schema_registry_validation(self):
        registry = SchemaRegistry()
        valid = registry.validate(
            "market_snapshot",
            "v1",
            {
                "ticker": "SPY",
                "spot": 530.0,
                "timestamp": "2026-03-23T00:00:00Z",
                "provider": "yfinance",
            },
        )
        invalid = registry.validate("market_snapshot", "v1", {"ticker": "SPY", "spot": 530.0})

        self.assertTrue(valid.ok)
        self.assertFalse(invalid.ok)
        self.assertIn("missing_field", invalid.message)


if __name__ == "__main__":
    unittest.main()
