from __future__ import annotations

import hashlib
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config.settings import get_settings
from infrastructure.platform.tenant import normalize_tenant_id

logger = logging.getLogger(__name__)

PLAN_FREE = "free"
PLAN_PRO = "pro"
PLAN_ENTERPRISE = "enterprise"
_PLAN_ORDER = (PLAN_FREE, PLAN_PRO, PLAN_ENTERPRISE)


@dataclass(frozen=True)
class PlanPolicy:
    name: str
    scans_per_day: int
    min_seconds_between_scans: int
    watchlist_max_tickers: int
    priority_queue: str
    premium_features: frozenset[str]
    commercial_weight: float


_PLAN_POLICIES: dict[str, PlanPolicy] = {
    PLAN_FREE: PlanPolicy(
        name=PLAN_FREE,
        scans_per_day=15,
        min_seconds_between_scans=180,
        watchlist_max_tickers=12,
        priority_queue="shared",
        premium_features=frozenset(),
        commercial_weight=1.0,
    ),
    PLAN_PRO: PlanPolicy(
        name=PLAN_PRO,
        scans_per_day=120,
        min_seconds_between_scans=45,
        watchlist_max_tickers=60,
        priority_queue="priority",
        premium_features=frozenset(
            {
                "advanced_alerts",
                "stress_tests",
                "extended_reports",
                "advanced_score",
                "explainability",
                "smart_alerts",
                "auto_reports",
            }
        ),
        commercial_weight=2.0,
    ),
    PLAN_ENTERPRISE: PlanPolicy(
        name=PLAN_ENTERPRISE,
        scans_per_day=1200,
        min_seconds_between_scans=15,
        watchlist_max_tickers=250,
        priority_queue="dedicated",
        premium_features=frozenset(
            {
                "advanced_alerts",
                "stress_tests",
                "extended_reports",
                "advanced_score",
                "explainability",
                "smart_alerts",
                "auto_reports",
            }
        ),
        commercial_weight=3.0,
    ),
}

_PLAN_SLA = {
    PLAN_FREE: {"queue": "shared", "latency_target_ms": 55000},
    PLAN_PRO: {"queue": "priority", "latency_target_ms": 30000},
    PLAN_ENTERPRISE: {"queue": "dedicated", "latency_target_ms": 15000},
}

_ROLLOUT_MIN_PLAN = {
    "advanced_score": PLAN_FREE,
    "explainability": PLAN_PRO,
    "smart_alerts": PLAN_PRO,
    "auto_reports": PLAN_PRO,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return _utc_now().strftime("%Y-%m-%d")


def _safe_load_dict(auth: Any, user_id: str, key: str) -> dict[str, Any]:
    raw = auth.load_user_data(user_id, key)
    return raw if isinstance(raw, dict) else {}


def _safe_load_list(auth: Any, user_id: str, key: str) -> list[dict[str, Any]]:
    raw = auth.load_user_data(user_id, key)
    return raw if isinstance(raw, list) else []


def _safe_load_dict_tenant(auth: Any, user_id: str, key: str, tenant_id: str) -> dict[str, Any]:
    try:
        raw = auth.load_user_data_tenant(user_id, tenant_id, key)
    except AttributeError:
        raw = auth.load_user_data(user_id, key)
    return raw if isinstance(raw, dict) else {}


def _safe_load_list_tenant(auth: Any, user_id: str, key: str, tenant_id: str) -> list[dict[str, Any]]:
    try:
        raw = auth.load_user_data_tenant(user_id, tenant_id, key)
    except AttributeError:
        raw = auth.load_user_data(user_id, key)
    return raw if isinstance(raw, list) else []


def _safe_save_tenant(auth: Any, user_id: str, key: str, value: Any, tenant_id: str) -> None:
    try:
        auth.save_user_data_tenant(user_id, tenant_id, key, value)
    except AttributeError:
        auth.save_user_data(user_id, key, value)


def _resolve_tenant_id(auth: Any, user_id: str, tenant_id: str | None = None) -> str:
    if tenant_id:
        return normalize_tenant_id(tenant_id)
    try:
        user = auth.get_current_user() if hasattr(auth, "get_current_user") else None
        if isinstance(user, dict) and str(user.get("id") or "") == str(user_id):
            return normalize_tenant_id(str(user.get("tenant_id") or "default"))
    except Exception:
        pass
    return "default"


def _plan_monthly_price(plan: str) -> float:
    defaults = {
        PLAN_FREE: 0.0,
        PLAN_PRO: 49.0,
        PLAN_ENTERPRISE: 299.0,
    }
    env_name = f"PLAN_PRICE_{plan.upper()}_MONTHLY_USD"
    try:
        return max(float(os.getenv(env_name, defaults.get(plan, 0.0))), 0.0)
    except ValueError:
        return defaults.get(plan, 0.0)


def get_plan_policy(plan: str | None) -> PlanPolicy:
    key = str(plan or PLAN_FREE).strip().lower()
    if key in {"admin", "owner"}:
        key = PLAN_ENTERPRISE
    if key == "user":
        key = PLAN_FREE
    return _PLAN_POLICIES.get(key, _PLAN_POLICIES[PLAN_FREE])


def get_user_plan(user: dict[str, Any] | None) -> str:
    if not user:
        return PLAN_FREE
    return get_plan_policy(str(user.get("role") or PLAN_FREE)).name


def has_feature_access(plan: str, feature_name: str) -> bool:
    policy = get_plan_policy(plan)
    return feature_name in policy.premium_features


def get_rollout_cohort(user_id: str, *, experiment: str = "feature_rollout_v1") -> int:
    if not user_id:
        return 0
    digest = hashlib.sha256(f"{experiment}:{user_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def is_feature_enabled_for_user(
    *,
    feature_name: str,
    plan: str,
    user_id: str,
    cohort: int | None = None,
) -> bool:
    settings = get_settings()
    plan_policy = get_plan_policy(plan)

    default_flag = {
        "advanced_score": bool(settings.feature_flag_advanced_score),
        "explainability": bool(settings.feature_flag_explainability),
        "smart_alerts": bool(settings.feature_flag_smart_alerts),
        "auto_reports": bool(settings.feature_flag_auto_reports),
    }.get(feature_name, False)
    if not default_flag:
        return False

    min_plan = _ROLLOUT_MIN_PLAN.get(feature_name, PLAN_FREE)
    plan_rank = _PLAN_ORDER.index(plan_policy.name) if plan_policy.name in _PLAN_ORDER else 0
    min_rank = _PLAN_ORDER.index(min_plan) if min_plan in _PLAN_ORDER else 0
    if plan_rank < min_rank:
        return False

    if feature_name in {"explainability", "smart_alerts", "auto_reports"} and not has_feature_access(plan_policy.name, feature_name):
        return False

    pct = {
        "advanced_score": int(settings.feature_rollout_advanced_score_pct),
        "explainability": int(settings.feature_rollout_explainability_pct),
        "smart_alerts": int(settings.feature_rollout_smart_alerts_pct),
        "auto_reports": int(settings.feature_rollout_auto_reports_pct),
    }.get(feature_name, 0)
    pct = max(0, min(100, pct))
    user_cohort = get_rollout_cohort(user_id) if cohort is None else max(0, min(99, int(cohort)))
    return user_cohort < pct


def get_plan_sla(plan: str) -> dict[str, Any]:
    normalized = get_plan_policy(plan).name
    return dict(_PLAN_SLA.get(normalized, _PLAN_SLA[PLAN_FREE]))


def estimate_refresh_priority_score(
    *,
    user_plan: str,
    demand_users: int,
    recent_activity_seconds: float,
    activity_count_5m: int,
) -> float:
    policy = get_plan_policy(user_plan)
    demand_score = min(max(demand_users, 1), 20) / 20.0
    recency_score = math.exp(-max(recent_activity_seconds, 0.0) / 300.0)
    activity_score = min(max(activity_count_5m, 0), 50) / 50.0
    plan_score = policy.commercial_weight / 3.0
    final = (0.4 * demand_score) + (0.25 * recency_score) + (0.2 * activity_score) + (0.15 * plan_score)
    return round(final, 4)


def check_scan_limit(auth: Any, user_id: str, plan: str) -> dict[str, Any]:
    policy = get_plan_policy(plan)
    usage_stats = _safe_load_dict(auth, user_id, "usage_stats")
    today = _today_key()
    scans_today = int(usage_stats.get("scans_today", 0)) if usage_stats.get("scans_today_date") == today else 0

    if scans_today >= policy.scans_per_day:
        return {
            "allowed": False,
            "reason": "daily_limit",
            "usage": scans_today,
            "limit": policy.scans_per_day,
            "retry_in_seconds": 3600,
            "friendly_message": (
                f"Llegaste a {scans_today}/{policy.scans_per_day} scans hoy. "
                "Puedes seguir viendo snapshots en cache y actualizar plan para aumentar capacidad."
            ),
        }

    last_scan_iso = usage_stats.get("last_scan_at")
    if isinstance(last_scan_iso, str) and last_scan_iso:
        try:
            last_scan = datetime.fromisoformat(last_scan_iso.replace("Z", "+00:00"))
            elapsed = (_utc_now() - last_scan).total_seconds()
            if elapsed < policy.min_seconds_between_scans:
                wait_seconds = int(policy.min_seconds_between_scans - elapsed)
                return {
                    "allowed": False,
                    "reason": "frequency_limit",
                    "usage": scans_today,
                    "limit": policy.scans_per_day,
                    "retry_in_seconds": max(wait_seconds, 1),
                    "friendly_message": (
                        f"Espera {wait_seconds}s para el siguiente scan en plan {policy.name.title()}. "
                        "Mientras tanto conservas acceso a datos en cache."
                    ),
                }
        except ValueError:
            pass

    return {
        "allowed": True,
        "reason": None,
        "usage": scans_today,
        "limit": policy.scans_per_day,
        "retry_in_seconds": 0,
        "friendly_message": "",
    }


def check_watchlist_limit(plan: str, current_watchlist_size: int) -> dict[str, Any]:
    policy = get_plan_policy(plan)
    if current_watchlist_size >= policy.watchlist_max_tickers:
        return {
            "allowed": False,
            "usage": current_watchlist_size,
            "limit": policy.watchlist_max_tickers,
            "friendly_message": (
                f"Tu watchlist tiene {current_watchlist_size}/{policy.watchlist_max_tickers} tickers. "
                "Haz upgrade para ampliar cobertura de simbolos."
            ),
        }

    return {
        "allowed": True,
        "usage": current_watchlist_size,
        "limit": policy.watchlist_max_tickers,
        "friendly_message": "",
    }
