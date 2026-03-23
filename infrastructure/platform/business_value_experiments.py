from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Any

from infrastructure.platform.business_value_shared import (
    _resolve_tenant_id,
    _safe_load_dict,
    _safe_load_list,
    _safe_load_list_tenant,
    _safe_save_tenant,
    _utc_now,
)

logger = logging.getLogger(__name__)

_PRODUCT_EVENTS_ALLOWED = {
    "user_scan_started",
    "user_scan_completed",
    "smart_alert_generated",
    "scan_decision_made",
    "auto_report_generated",
    "user_hit_plan_limit",
    "user_opened_upgrade_prompt",
    "user_upgraded_plan",
}


def record_product_event(
    auth: Any,
    user_id: str,
    event_name: str,
    metadata: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> bool:
    if event_name not in _PRODUCT_EVENTS_ALLOWED:
        logger.warning("Ignored unsupported event '%s'", event_name)
        return False

    tenant = _resolve_tenant_id(auth, user_id, tenant_id)
    events = _safe_load_list_tenant(auth, user_id, "product_events", tenant)
    events.append(
        {
            "ts": _utc_now().isoformat(),
            "event": event_name,
            "tenant_id": tenant,
            "metadata": metadata or {},
        }
    )

    max_items = int(os.getenv("PRODUCT_EVENTS_MAX_ITEMS_PER_USER", "2500"))
    if len(events) > max_items:
        events = events[-max_items:]

    _safe_save_tenant(auth, user_id, "product_events", events, tenant)
    return True


def assign_ab_variant(user_id: str, experiment_name: str, variants: tuple[str, ...] = ("A", "B")) -> str:
    if not variants:
        return "A"
    digest = hashlib.sha256(f"{experiment_name}:{user_id}".encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(variants)
    return variants[idx]


def record_ab_assignment(auth: Any, user_id: str, experiment_name: str, variant: str) -> None:
    data = _safe_load_dict(auth, user_id, "ab_assignments")
    data[experiment_name] = {"variant": variant, "assigned_at": _utc_now().isoformat()}
    auth.save_user_data(user_id, "ab_assignments", data)


def record_ab_conversion(auth: Any, user_id: str, experiment_name: str, converted: bool) -> None:
    assignments = _safe_load_dict(auth, user_id, "ab_assignments")
    variant = str(assignments.get(experiment_name, {}).get("variant", "A")).upper()
    rows = _safe_load_list(auth, user_id, "ab_conversions")
    rows.append(
        {
            "experiment": experiment_name,
            "variant": variant,
            "converted": bool(converted),
            "ts": _utc_now().isoformat(),
        }
    )
    auth.save_user_data(user_id, "ab_conversions", rows[-2000:])


def build_conversion_funnel(events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = [
        "user_scan_started",
        "user_scan_completed",
        "user_hit_plan_limit",
        "user_opened_upgrade_prompt",
        "user_upgraded_plan",
    ]
    counts: dict[str, int] = {name: 0 for name in ordered}
    for row in events:
        name = row.get("event")
        if name in counts:
            counts[name] += 1

    abandonment = {}
    for idx, step in enumerate(ordered[:-1]):
        next_step = ordered[idx + 1]
        current = counts.get(step, 0)
        nxt = counts.get(next_step, 0)
        if current <= 0:
            abandonment[step] = 0.0
        else:
            abandonment[step] = round(max(0.0, (current - nxt) / current), 4)

    return {"steps": counts, "abandonment": abandonment}


def _two_prop_significance(success_a: int, total_a: int, success_b: int, total_b: int) -> dict[str, float]:
    if total_a <= 0 or total_b <= 0:
        return {"z_score": 0.0, "p_value": 1.0}

    p1 = success_a / total_a
    p2 = success_b / total_b
    pooled = (success_a + success_b) / (total_a + total_b)
    se = math.sqrt(max(pooled * (1.0 - pooled) * ((1.0 / total_a) + (1.0 / total_b)), 1e-9))
    z = (p1 - p2) / se
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return {"z_score": round(z, 4), "p_value": round(p, 6)}


def evaluate_ab_experiment(
    rows: list[dict[str, Any]],
    experiment_name: str,
    assignment_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    counts = {
        "A": {"total": 0, "converted": 0},
        "B": {"total": 0, "converted": 0},
    }
    for row in rows:
        if row.get("experiment") != experiment_name:
            continue
        variant = str(row.get("variant", "A")).upper()
        if variant not in counts:
            continue
        counts[variant]["total"] += 1
        counts[variant]["converted"] += int(bool(row.get("converted")))

    if assignment_rows:
        totals_from_assignments = {"A": 0, "B": 0}
        for row in assignment_rows:
            if row.get("experiment") != experiment_name:
                continue
            variant = str(row.get("variant", "A")).upper()
            if variant in totals_from_assignments:
                totals_from_assignments[variant] += 1

        for variant in ("A", "B"):
            counts[variant]["total"] = max(counts[variant]["total"], totals_from_assignments[variant])

    sig = _two_prop_significance(
        counts["A"]["converted"],
        counts["A"]["total"],
        counts["B"]["converted"],
        counts["B"]["total"],
    )

    rate_a = (counts["A"]["converted"] / counts["A"]["total"]) if counts["A"]["total"] else 0.0
    rate_b = (counts["B"]["converted"] / counts["B"]["total"]) if counts["B"]["total"] else 0.0
    if sig["p_value"] < 0.05 and counts["A"]["total"] >= 30 and counts["B"]["total"] >= 30:
        winner = "B" if rate_b > rate_a else "A"
        recommendation = f"Rollout variant {winner}"
    else:
        winner = "none"
        recommendation = "Keep experiment running"

    return {
        "experiment": experiment_name,
        "variant_a": counts["A"],
        "variant_b": counts["B"],
        "rate_a": round(rate_a, 4),
        "rate_b": round(rate_b, 4),
        "winner": winner,
        "recommendation": recommendation,
        **sig,
    }
