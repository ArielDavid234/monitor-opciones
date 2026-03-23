from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from infrastructure.caching import get_cache
from infrastructure.platform.event_bus import InternalEventBus, get_event_bus
from infrastructure.platform.health import global_health_status
from infrastructure.platform.rbac import (
    CAP_REPORT_VIEW,
    CAP_SCAN_EXECUTE,
    ROLE_VIEWER,
    authorize,
)
from infrastructure.platform.schema_registry import SchemaRegistry
from infrastructure.platform.security import sanitize_error_for_user
from infrastructure.platform.tenant import assert_tenant_access, normalize_tenant_id, tenant_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiIdentity:
    token: str
    user_id: str
    tenant_id: str
    plan: str
    role: str


class PublicApiV1:
    """Public API v1 internal adapter with token auth and per-plan rate limiting."""

    def __init__(self, auth: Any) -> None:
        self._auth = auth
        self._cache = get_cache()
        self._schema = SchemaRegistry()
        self._bus: InternalEventBus = get_event_bus()
        self._plan_limits = {
            "free": 60,
            "pro": 240,
            "enterprise": 1200,
        }

    def _load_tokens(self) -> dict[str, dict[str, str]]:
        raw = os.getenv("PUBLIC_API_TOKENS_JSON", "{}")
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def authenticate(self, token: str) -> ApiIdentity | None:
        token_value = str(token or "").strip()
        if not token_value:
            return None
        tokens = self._load_tokens()
        row = tokens.get(token_value)
        if not isinstance(row, dict):
            return None
        return ApiIdentity(
            token=token_value,
            user_id=str(row.get("user_id") or ""),
            tenant_id=normalize_tenant_id(str(row.get("tenant_id") or "default")),
            plan=str(row.get("plan") or "free").lower(),
            role=str(row.get("role") or ROLE_VIEWER).lower(),
        )

    def _rate_limit(self, identity: ApiIdentity, route: str) -> tuple[bool, int, int]:
        per_min_limit = int(self._plan_limits.get(identity.plan, 60))
        minute_bucket = int(time.time() // 60)
        key = tenant_key(
            identity.tenant_id,
            f"api:v1:ratelimit:{identity.user_id}:{identity.plan}:{route}:{minute_bucket}",
        )
        current = self._cache.get(key)
        used = int(current or 0)
        if used >= per_min_limit:
            return False, used, per_min_limit
        self._cache.set(key, used + 1, ttl=70)
        return True, used + 1, per_min_limit

    def _response(self, *, path: str, status: str, data: dict[str, Any], code: int = 200) -> tuple[int, dict[str, Any]]:
        return code, {
            "api_version": "v1",
            "route": path,
            "status": status,
            "data": data,
        }

    def _load_tenant_payload(self, user_id: str, tenant_id: str, key: str, default: Any) -> Any:
        if hasattr(self._auth, "load_user_data_tenant"):
            data = self._auth.load_user_data_tenant(user_id, tenant_id, key)
        else:
            data = self._auth.load_user_data(user_id, key)
        return data if data is not None else default

    def _degraded_contract_response(self, path: str, reason: str) -> tuple[int, dict[str, Any]]:
        return self._response(
            path=path,
            status="degraded",
            data={"message": "contract_validation_failed", "reason": reason},
            code=200,
        )

    def handle_request(
        self,
        *,
        path: str,
        token: str,
        tenant_id: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        req_path = str(path or "").strip()
        req_tenant = normalize_tenant_id(tenant_id)
        identity = self.authenticate(token)
        if identity is None:
            return self._response(path=req_path, status="error", data={"message": "unauthorized"}, code=401)

        try:
            assert_tenant_access(actor_tenant_id=identity.tenant_id, requested_tenant_id=req_tenant)
            allowed, used, limit = self._rate_limit(identity, req_path)
            if not allowed:
                return self._response(
                    path=req_path,
                    status="error",
                    data={"message": "rate_limited", "plan": identity.plan, "used": used, "limit": limit},
                    code=429,
                )

            route_cap = {
                "/api/v1/opportunities": CAP_SCAN_EXECUTE,
                "/api/v1/score-explainable": CAP_REPORT_VIEW,
                "/api/v1/alerts-smart": CAP_REPORT_VIEW,
                "/api/v1/health": CAP_REPORT_VIEW,
            }
            cap = route_cap.get(req_path)
            if not cap:
                return self._response(path=req_path, status="error", data={"message": "not_found"}, code=404)

            decision = authorize(user={"id": identity.user_id, "role": identity.role, "tenant_id": identity.tenant_id}, capability=cap, tenant_id=req_tenant)
            if not decision.allowed:
                return self._response(path=req_path, status="error", data={"message": "forbidden", "reason": decision.reason}, code=403)

            if req_path == "/api/v1/opportunities":
                self._bus.publish(
                    "scan_requested",
                    {
                        "event_id": f"scan-requested-{int(time.time())}",
                        "ticker": str((payload or {}).get("ticker") or "SPY"),
                        "score_unificado": float((payload or {}).get("score_unificado") or 0.0),
                        "severity": "info",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    schema_name="alert_event",
                )
                rows = self._load_tenant_payload(identity.user_id, req_tenant, "latest_scan_opportunities", [])
                if rows and isinstance(rows[0], dict):
                    sample = rows[0]
                    contract_payload = {
                        "ticker": str(sample.get("Ticker") or sample.get("ticker") or ""),
                        "spot": float(sample.get("Spot") or sample.get("spot") or 0.0),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "provider": str(sample.get("provider") or "unknown"),
                    }
                    valid = self._schema.validate_before_publish("market_snapshot", "v1", contract_payload)
                    if not valid.ok:
                        return self._degraded_contract_response(req_path, valid.message)
                self._bus.publish(
                    "scan_completed",
                    {
                        "event_id": f"scan-completed-{int(time.time())}",
                        "ticker": str((payload or {}).get("ticker") or "SPY"),
                        "score_unificado": float((payload or {}).get("score_unificado") or 0.0),
                        "severity": "info",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    schema_name="alert_event",
                )
                return self._response(path=req_path, status="ok", data={"items": rows, "count": len(rows)})

            if req_path == "/api/v1/score-explainable":
                score = self._load_tenant_payload(identity.user_id, req_tenant, "latest_score_explainability", {})
                if score:
                    contract_payload = {
                        "ticker": str((score or {}).get("ticker") or (score or {}).get("Ticker") or ""),
                        "score_unificado": float((score or {}).get("score_unificado") or (score or {}).get("Score Unificado") or 0.0),
                        "perfil_riesgo": str((score or {}).get("perfil_riesgo") or (score or {}).get("Perfil Riesgo") or ""),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    valid = self._schema.validate_before_publish("scoring_output", "v1", contract_payload)
                    if not valid.ok:
                        return self._degraded_contract_response(req_path, valid.message)
                self._bus.publish(
                    "score_updated",
                    {
                        "event_id": f"score-updated-{int(time.time())}",
                        "ticker": str((score or {}).get("ticker") or "SPY"),
                        "score_unificado": float((score or {}).get("score_unificado") or 0.0),
                        "severity": "info",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    schema_name="alert_event",
                )
                return self._response(path=req_path, status="ok", data={"score": score})

            if req_path == "/api/v1/alerts-smart":
                alerts = self._load_tenant_payload(identity.user_id, req_tenant, "latest_smart_alerts", [])
                first = alerts[0] if alerts and isinstance(alerts[0], dict) else {}
                if first:
                    contract_payload = {
                        "event_id": f"alert-emitted-{int(time.time())}",
                        "ticker": str(first.get("Ticker") or first.get("ticker") or ""),
                        "score_unificado": float(first.get("Score Unificado") or first.get("score_unificado") or 0.0),
                        "severity": "info",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    valid = self._schema.validate_before_publish("alert_event", "v1", contract_payload)
                    if not valid.ok:
                        return self._degraded_contract_response(req_path, valid.message)
                self._bus.publish(
                    "alert_emitted",
                    {
                        "event_id": f"alert-emitted-{int(time.time())}",
                        "ticker": str((alerts[0] if alerts else {}).get("Ticker") or "SPY"),
                        "score_unificado": float((alerts[0] if alerts else {}).get("Score Unificado") or 0.0),
                        "severity": "info",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    schema_name="alert_event",
                )
                return self._response(path=req_path, status="ok", data={"alerts": alerts, "count": len(alerts)})

            health = global_health_status()
            return self._response(path=req_path, status="ok", data={"health": health})
        except Exception as exc:
            logger.exception("api_v1_error | path=%s", req_path)
            return self._response(
                path=req_path,
                status="error",
                data={"message": sanitize_error_for_user(exc)},
                code=500,
            )
