from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core.autonomy.feedback_loop import FeedbackLoopEngine
from core.autonomy.drift_monitor import DriftMonitor
from core.autonomy.model_registry import ModelRegistry
from core.autonomy.recalibration import RecalibrationEngine
from core.autonomy.roi import compute_intelligence_roi
from core.autonomy.walk_forward import WalkForwardEvaluator
from infrastructure.platform.audit import record_audit_event
from infrastructure.platform.business_value_experiments import (
    assign_ab_variant,
    build_conversion_funnel,
    evaluate_ab_experiment,
    record_ab_assignment,
    record_ab_conversion,
    record_product_event,
)
from infrastructure.platform.business_value_shared import (
    PLAN_ENTERPRISE,
    PLAN_FREE,
    PLAN_PRO,
    _PLAN_ORDER,
    _plan_monthly_price,
    _resolve_tenant_id,
    _safe_load_dict,
    _safe_load_dict_tenant,
    _safe_load_list,
    _safe_load_list_tenant,
    _safe_save_tenant,
    _today_key,
    _utc_now,
    check_scan_limit,
    check_watchlist_limit,
    estimate_refresh_priority_score,
    get_plan_policy,
    get_plan_sla,
    get_rollout_cohort,
    get_user_plan,
    has_feature_access,
    is_feature_enabled_for_user,
)
from infrastructure.platform.governance import record_model_promoted
from infrastructure.platform.tenant import normalize_tenant_id

logger = logging.getLogger(__name__)

__all__ = [
    "PLAN_FREE",
    "PLAN_PRO",
    "PLAN_ENTERPRISE",
    "get_plan_policy",
    "get_user_plan",
    "has_feature_access",
    "get_rollout_cohort",
    "is_feature_enabled_for_user",
    "get_plan_sla",
    "estimate_refresh_priority_score",
    "check_scan_limit",
    "check_watchlist_limit",
    "record_scan_metering",
    "record_intelligence_snapshot",
    "run_autonomy_cycle",
    "rollback_model_version",
    "record_product_event",
    "assign_ab_variant",
    "record_ab_assignment",
    "record_ab_conversion",
    "build_conversion_funnel",
    "evaluate_ab_experiment",
    "aggregate_business_metrics",
    "export_executive_summary",
    "export_daily_business_summary",
]

_feedback_engine = FeedbackLoopEngine()
_recalibration_engine = RecalibrationEngine()
_walk_forward_engine = WalkForwardEvaluator()
_drift_monitor = DriftMonitor()
_model_registry = ModelRegistry()


def _persist_daily_usage(auth: Any, user_id: str, day_key: str, daily_row: dict[str, Any]) -> None:
    store = _safe_load_dict(auth, user_id, "business_usage_daily")
    store[day_key] = daily_row
    auth.save_user_data(user_id, "business_usage_daily", store)


def _persist_daily_usage_tenant(auth: Any, user_id: str, day_key: str, daily_row: dict[str, Any], tenant_id: str) -> None:
    store = _safe_load_dict_tenant(auth, user_id, "business_usage_daily", tenant_id)
    store[day_key] = daily_row
    _safe_save_tenant(auth, user_id, "business_usage_daily", store, tenant_id)


def record_scan_metering(auth: Any, user_id: str, plan: str, scan_runtime: dict[str, Any], tenant_id: str | None = None) -> dict[str, Any]:
    day_key = _today_key()
    policy = get_plan_policy(plan)
    tenant = _resolve_tenant_id(auth, user_id, tenant_id)

    provider_call_cost = float(os.getenv("COST_PROVIDER_CALL_USD", "0.0025"))
    cpu_second_cost = float(os.getenv("COST_CPU_SECOND_USD", "0.0008"))
    cache_miss_penalty = float(os.getenv("COST_CACHE_MISS_USD", "0.0004"))

    provider_calls = int(scan_runtime.get("provider_calls", 0))
    cache_hits = int(scan_runtime.get("cache_hits", 0))
    cache_misses = int(scan_runtime.get("cache_misses", 0))
    cpu_seconds = float(scan_runtime.get("cpu_seconds", 0.0))

    scan_cost = (
        (provider_calls * provider_call_cost)
        + (cpu_seconds * cpu_second_cost)
        + (cache_misses * cache_miss_penalty)
    )

    daily = _safe_load_dict_tenant(auth, user_id, "business_usage_daily", tenant).get(day_key, {})
    if not isinstance(daily, dict):
        daily = {}

    daily.setdefault("plan", policy.name)
    daily["plan"] = policy.name
    daily["scans"] = int(daily.get("scans", 0)) + 1
    daily["provider_calls"] = int(daily.get("provider_calls", 0)) + provider_calls
    daily["cache_hits"] = int(daily.get("cache_hits", 0)) + cache_hits
    daily["cache_misses"] = int(daily.get("cache_misses", 0)) + cache_misses
    daily["cpu_seconds"] = round(float(daily.get("cpu_seconds", 0.0)) + cpu_seconds, 3)
    daily["estimated_cost_usd"] = round(float(daily.get("estimated_cost_usd", 0.0)) + scan_cost, 6)

    daily_revenue = _plan_monthly_price(policy.name) / 30.0
    daily["revenue_estimate_usd"] = round(daily_revenue, 6)
    daily["updated_at"] = _utc_now().isoformat()

    daily["tenant_id"] = tenant
    _persist_daily_usage_tenant(auth, user_id, day_key, daily, tenant)

    usage_stats = _safe_load_dict_tenant(auth, user_id, "usage_stats", tenant)
    usage_stats["last_scan_at"] = _utc_now().isoformat()
    _safe_save_tenant(auth, user_id, "usage_stats", usage_stats, tenant)

    return {
        "scan_cost_usd": round(scan_cost, 6),
        "daily_cost_usd": daily["estimated_cost_usd"],
        "daily_revenue_usd": daily_revenue,
        "provider_calls": provider_calls,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cpu_seconds": cpu_seconds,
    }


def record_intelligence_snapshot(
    auth: Any,
    user_id: str,
    plan: str,
    snapshot: dict[str, Any],
    tenant_id: str | None = None,
) -> dict[str, Any]:
    day_key = _today_key()
    tenant = _resolve_tenant_id(auth, user_id, tenant_id)
    store = _safe_load_dict_tenant(auth, user_id, "intelligence_daily", tenant)
    row = store.get(day_key, {})
    if not isinstance(row, dict):
        row = {}

    row["plan"] = get_plan_policy(plan).name
    row["scans"] = int(row.get("scans", 0)) + 1
    row["rows_seen"] = int(row.get("rows_seen", 0)) + int(snapshot.get("rows_seen", 0))
    row["high_score_rows"] = int(row.get("high_score_rows", 0)) + int(snapshot.get("high_score_rows", 0))
    row["avg_score_acc"] = float(row.get("avg_score_acc", 0.0)) + float(snapshot.get("avg_score", 0.0))
    row["risk_conservadora"] = int(row.get("risk_conservadora", 0)) + int(snapshot.get("risk_conservadora", 0))
    row["risk_balanceada"] = int(row.get("risk_balanceada", 0)) + int(snapshot.get("risk_balanceada", 0))
    row["risk_agresiva"] = int(row.get("risk_agresiva", 0)) + int(snapshot.get("risk_agresiva", 0))
    row["decision_time_seconds_sum"] = float(row.get("decision_time_seconds_sum", 0.0)) + float(snapshot.get("decision_time_seconds", 0.0))
    row["decision_events"] = int(row.get("decision_events", 0)) + int(snapshot.get("decision_events", 0))
    row["tenant_id"] = tenant
    row["updated_at"] = _utc_now().isoformat()

    store[day_key] = row
    _safe_save_tenant(auth, user_id, "intelligence_daily", store, tenant)
    return row


def run_autonomy_cycle(
    auth: Any,
    user_id: str,
    plan: str,
    tenant_id: str | None = None,
    *,
    promote_threshold_pct: float = 2.0,
) -> dict[str, Any]:
    """Run closed-loop autonomy cycle: recalibration, validation, registry, drift, and ROI."""
    tenant = _resolve_tenant_id(auth, user_id, tenant_id)
    dataset = _feedback_engine.load_incremental_dataset(auth, user_id)
    walk = _walk_forward_engine.evaluate(dataset)
    recalibration = _recalibration_engine.run_recalibration(
        auth,
        user_id,
        dataset,
        promote_threshold_pct=promote_threshold_pct,
    )

    baseline_key = "autonomy_baseline_dataset"
    baseline_rows = auth.load_user_data(user_id, baseline_key)
    baseline_df = pd.DataFrame(baseline_rows) if isinstance(baseline_rows, list) else pd.DataFrame()
    drift_alerts = _drift_monitor.monitor(baseline_df if not baseline_df.empty else dataset, dataset)
    drift_summary = _drift_monitor.summarize(drift_alerts)

    if baseline_df.empty and dataset is not None and not dataset.empty:
        auth.save_user_data(user_id, baseline_key, dataset.tail(5000).to_dict("records"))

    version = f"autonomy-{_utc_now().strftime('%Y%m%d%H%M%S')}"
    validation_metrics = {
        "topk_precision": walk.topk_precision,
        "regime_stability": walk.regime_stability,
        "informative_drawdown": walk.informative_drawdown,
        "false_positive_rate": walk.false_positive_rate,
        "false_negative_rate": walk.false_negative_rate,
        "recalibration_improvement_pct": recalibration.improvement_pct,
    }
    status = "canary" if recalibration.promoted else "shadow"
    _model_registry.register(
        version=version,
        dataset_ref=f"user:{user_id}:incremental",
        validation_metrics=validation_metrics,
        status=status,
        params={"weights": recalibration.candidate_weights.__dict__, "plan": plan},
    )
    if recalibration.promoted:
        _model_registry.set_status(version, "prod")
        record_audit_event(
            "model_promote",
            user_id=user_id,
            tenant_id=tenant,
            status="success",
            metadata={"version": version, "plan": plan, "improvement_pct": recalibration.improvement_pct},
        )
        record_model_promoted(user_id=user_id, tenant_id=tenant, version=version)

    roi = compute_intelligence_roi(
        useful_signal_improvement_pct=max(recalibration.improvement_pct, 0.0),
        retention_improvement_pct=3.0,
        conversion_improvement_pct=2.0,
        incremental_monthly_cost_usd=12.0,
        baseline_monthly_revenue_usd=_plan_monthly_price(get_plan_policy(plan).name),
    )

    cycle = {
        "version": version,
        "status": "prod" if recalibration.promoted else "shadow",
        "walk_forward": validation_metrics,
        "drift": drift_summary,
        "recalibration": {
            "promoted": recalibration.promoted,
            "improvement_pct": recalibration.improvement_pct,
            "reason": recalibration.reason,
        },
        "roi": roi,
        "tenant_id": tenant,
        "run_at": _utc_now().isoformat(),
    }
    _safe_save_tenant(auth, user_id, "autonomy_last_cycle", cycle, tenant)
    return cycle


def rollback_model_version(target_version: str, *, actor_user_id: str = "system", tenant_id: str = "platform") -> bool:
    ok = _model_registry.rollback(target_version)
    record_audit_event(
        "model_rollback",
        user_id=actor_user_id,
        tenant_id=tenant_id,
        status="success" if ok else "failed",
        metadata={"target_version": target_version},
    )
    return ok


def aggregate_business_metrics(auth: Any, lookback_days: int = 7, tenant_id: str | None = None) -> dict[str, Any]:
    tenant_filter = normalize_tenant_id(tenant_id) if tenant_id else None
    profiles = auth.fetch_all_profiles() if hasattr(auth, "fetch_all_profiles") else []
    active_users = 0
    totals = {
        "cost": 0.0,
        "revenue": 0.0,
        "scans": 0,
        "cache_hits": 0,
        "cache_misses": 0,
    }
    plan_rows: dict[str, dict[str, float | int]] = {
        p: {"cost": 0.0, "revenue": 0.0, "scans": 0, "cache_hits": 0, "cache_misses": 0, "users": 0}
        for p in _PLAN_ORDER
    }

    upgrades_week = 0
    scans_started = 0
    scans_completed = 0
    conversion_events: list[dict[str, Any]] = []
    ab_rows: list[dict[str, Any]] = []
    ab_assignments_rows: list[dict[str, Any]] = []
    active_days: set[tuple[str, str]] = set()
    high_score_total = 0
    opportunities_total = 0
    avg_score_acc = 0.0
    avg_score_count = 0
    decision_time_sum = 0.0
    decision_events = 0
    risk_dist = {"Conservadora": 0, "Balanceada": 0, "Agresiva": 0}
    plan_scan_started = {p: 0 for p in _PLAN_ORDER}
    plan_upgrades = {p: 0 for p in _PLAN_ORDER}
    autonomy_versions = {"shadow": 0, "canary": 0, "prod": 0, "retired": 0}
    drift_high = 0
    drift_medium = 0
    wf_topk_samples: list[float] = []
    roi_samples: list[float] = []

    since_day = (_utc_now() - timedelta(days=max(lookback_days, 1) - 1)).strftime("%Y-%m-%d")
    for profile in profiles:
        user_id = str(profile.get("id") or "")
        if not user_id:
            continue

        user_tenant = normalize_tenant_id(str(profile.get("tenant_id") or "default"))
        if tenant_filter and user_tenant != tenant_filter:
            continue

        active_users += 1
        plan = get_plan_policy(profile.get("role", PLAN_FREE)).name
        plan_rows.setdefault(plan, {"cost": 0.0, "revenue": 0.0, "scans": 0, "cache_hits": 0, "cache_misses": 0, "users": 0})
        plan_rows[plan]["users"] = int(plan_rows[plan].get("users", 0)) + 1

        usage_store = (
            _safe_load_dict_tenant(auth, user_id, "business_usage_daily", user_tenant)
            if tenant_filter or hasattr(auth, "load_user_data_tenant")
            else _safe_load_dict(auth, user_id, "business_usage_daily")
        )
        for day_key, row in usage_store.items():
            if str(day_key) < since_day or not isinstance(row, dict):
                continue
            active_days.add((user_id, str(day_key)))
            cost = float(row.get("estimated_cost_usd", 0.0))
            revenue = float(row.get("revenue_estimate_usd", _plan_monthly_price(plan) / 30.0))
            scans = int(row.get("scans", 0))
            cache_hits = int(row.get("cache_hits", 0))
            cache_misses = int(row.get("cache_misses", 0))

            totals["cost"] += cost
            totals["revenue"] += revenue
            totals["scans"] += scans
            totals["cache_hits"] += cache_hits
            totals["cache_misses"] += cache_misses

            plan_rows[plan]["cost"] = float(plan_rows[plan]["cost"]) + cost
            plan_rows[plan]["revenue"] = float(plan_rows[plan]["revenue"]) + revenue
            plan_rows[plan]["scans"] = int(plan_rows[plan]["scans"]) + scans
            plan_rows[plan]["cache_hits"] = int(plan_rows[plan]["cache_hits"]) + cache_hits
            plan_rows[plan]["cache_misses"] = int(plan_rows[plan]["cache_misses"]) + cache_misses

        intelligence_store = (
            _safe_load_dict_tenant(auth, user_id, "intelligence_daily", user_tenant)
            if tenant_filter or hasattr(auth, "load_user_data_tenant")
            else _safe_load_dict(auth, user_id, "intelligence_daily")
        )
        for day_key, row in intelligence_store.items():
            if str(day_key) < since_day or not isinstance(row, dict):
                continue
            opportunities_total += int(row.get("rows_seen", 0))
            high_score_total += int(row.get("high_score_rows", 0))
            avg_score_acc += float(row.get("avg_score_acc", 0.0))
            avg_score_count += int(row.get("scans", 0))
            risk_dist["Conservadora"] += int(row.get("risk_conservadora", 0))
            risk_dist["Balanceada"] += int(row.get("risk_balanceada", 0))
            risk_dist["Agresiva"] += int(row.get("risk_agresiva", 0))
            decision_time_sum += float(row.get("decision_time_seconds_sum", 0.0))
            decision_events += int(row.get("decision_events", 0))

        events = (
            _safe_load_list_tenant(auth, user_id, "product_events", user_tenant)
            if tenant_filter or hasattr(auth, "load_user_data_tenant")
            else _safe_load_list(auth, user_id, "product_events")
        )
        for ev in events:
            ts = str(ev.get("ts") or "")
            if ts[:10] < since_day:
                continue
            conversion_events.append(ev)
            if ev.get("event") == "user_upgraded_plan":
                upgrades_week += 1
                plan_upgrades[plan] = int(plan_upgrades.get(plan, 0)) + 1
            if ev.get("event") == "user_scan_started":
                scans_started += 1
                plan_scan_started[plan] = int(plan_scan_started.get(plan, 0)) + 1
            if ev.get("event") == "user_scan_completed":
                scans_completed += 1

        ab_events = _safe_load_list_tenant(auth, user_id, "ab_conversions", user_tenant)
        for row in ab_events:
            ts = str(row.get("ts") or "")
            if ts[:10] >= since_day:
                ab_rows.append(row)

        ab_assignments = _safe_load_dict_tenant(auth, user_id, "ab_assignments", user_tenant)
        for exp_name, payload in ab_assignments.items():
            if not isinstance(payload, dict):
                continue
            ab_assignments_rows.append(
                {
                    "experiment": exp_name,
                    "variant": payload.get("variant", "A"),
                    "assigned_at": payload.get("assigned_at", ""),
                }
            )

        autonomy_cycle = _safe_load_dict_tenant(auth, user_id, "autonomy_last_cycle", user_tenant)
        if autonomy_cycle:
            drift = autonomy_cycle.get("drift", {}) if isinstance(autonomy_cycle.get("drift"), dict) else {}
            drift_high += int(drift.get("high", 0))
            drift_medium += int(drift.get("medium", 0))
            walk_forward = autonomy_cycle.get("walk_forward", {}) if isinstance(autonomy_cycle.get("walk_forward"), dict) else {}
            wf_topk_samples.append(float(walk_forward.get("topk_precision", 0.0)))
            roi = autonomy_cycle.get("roi", {}) if isinstance(autonomy_cycle.get("roi"), dict) else {}
            roi_samples.append(float(roi.get("roi_pct", 0.0)))

    for row in _model_registry.all_versions():
        st = str(row.get("status", "shadow"))
        if st in autonomy_versions:
            autonomy_versions[st] += 1

    cache_den = max(totals["cache_hits"] + totals["cache_misses"], 1)
    arpu = totals["revenue"] / max(active_users, 1)
    cost_per_user = totals["cost"] / max(active_users, 1)
    dau = len({u for u, _d in active_days})
    scans_per_user = totals["scans"] / max(active_users, 1)
    high_score_rate = high_score_total / max(opportunities_total, 1)
    avg_score_trend = avg_score_acc / max(avg_score_count, 1)
    avg_decision_time = decision_time_sum / max(decision_events, 1)
    cost_per_scan = totals["cost"] / max(totals["scans"], 1)
    conversion_by_plan = {
        p: round(plan_upgrades.get(p, 0) / max(plan_scan_started.get(p, 0), 1), 4)
        for p in _PLAN_ORDER
    }

    funnel = build_conversion_funnel(conversion_events)

    ab_eval = evaluate_ab_experiment(
        ab_rows,
        experiment_name="upgrade_prompt_copy_v1",
        assignment_rows=ab_assignments_rows,
    )

    per_plan_out: dict[str, Any] = {}
    for plan, row in plan_rows.items():
        rev = float(row.get("revenue", 0.0))
        cost = float(row.get("cost", 0.0))
        hits = int(row.get("cache_hits", 0))
        misses = int(row.get("cache_misses", 0))
        denom = max(hits + misses, 1)
        per_plan_out[plan] = {
            "users": int(row.get("users", 0)),
            "scans": int(row.get("scans", 0)),
            "revenue_usd": round(rev, 4),
            "cost_usd": round(cost, 4),
            "gross_margin_pct": round(((rev - cost) / rev) * 100.0, 2) if rev > 0 else 0.0,
            "cache_hit_ratio": round(hits / denom, 4),
        }

    return {
        "lookback_days": lookback_days,
        "tenant_id": tenant_filter or "all",
        "active_users": active_users,
        "arpu_technical_estimated_usd": round(arpu, 4),
        "cost_per_active_user_usd": round(cost_per_user, 4),
        "gross_margin_global_pct": round(((totals["revenue"] - totals["cost"]) / totals["revenue"]) * 100.0, 2)
        if totals["revenue"] > 0
        else 0.0,
        "cache_hit_ratio_global": round(totals["cache_hits"] / cache_den, 4),
        "scans_daily_by_segment": {plan: row["scans"] for plan, row in per_plan_out.items()},
        "weekly_upgrade_rate": round(upgrades_week / max(scans_started, 1), 4),
        "executive_dashboard": {
            "dau": dau,
            "scans_per_user": round(scans_per_user, 3),
            "high_score_rate": round(high_score_rate, 4),
            "avg_score_trend": round(avg_score_trend, 3),
            "decision_time_seconds": round(avg_decision_time, 2),
            "conversion_by_plan": conversion_by_plan,
            "cost_per_scan_usd": round(cost_per_scan, 6),
            "margin_pct": round(((totals["revenue"] - totals["cost"]) / totals["revenue"] * 100.0), 2)
            if totals["revenue"] > 0
            else 0.0,
            "risk_profile_distribution": risk_dist,
            "scans_completed": scans_completed,
        },
        "plans": per_plan_out,
        "funnel": funnel,
        "ab_tests": [ab_eval],
        "autonomy": {
            "model_registry": autonomy_versions,
            "drift_high": drift_high,
            "drift_medium": drift_medium,
            "walk_forward_topk_precision": round(float(sum(wf_topk_samples) / max(len(wf_topk_samples), 1)), 4),
            "intelligence_roi_pct": round(float(sum(roi_samples) / max(len(roi_samples), 1)), 4),
        },
    }


def export_executive_summary(auth: Any, period: str = "daily", output_dir: str = "reports/executive") -> Path:
    now = _utc_now()
    lookback = 7 if period == "weekly" else 1
    metrics = aggregate_business_metrics(auth=auth, lookback_days=lookback)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"executive_{period}_{now.strftime('%Y%m%d')}.md"

    exec_metrics = metrics.get("executive_dashboard", {})
    lines = [
        "# Executive Intelligence Summary",
        "",
        f"- period: {period}",
        f"- generated_at_utc: {now.isoformat()}",
        f"- dau: {exec_metrics.get('dau', 0)}",
        f"- scans_per_user: {exec_metrics.get('scans_per_user', 0)}",
        f"- high_score_rate: {exec_metrics.get('high_score_rate', 0)}",
        f"- decision_time_seconds: {exec_metrics.get('decision_time_seconds', 0)}",
        f"- cost_per_scan_usd: {exec_metrics.get('cost_per_scan_usd', 0)}",
        f"- margin_pct: {exec_metrics.get('margin_pct', 0)}",
        "",
        "## Conversion By Plan",
        "```json",
        json.dumps(exec_metrics.get("conversion_by_plan", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Risk Profile Distribution",
        "```json",
        json.dumps(exec_metrics.get("risk_profile_distribution", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Plans",
        "```json",
        json.dumps(metrics.get("plans", {}), indent=2, sort_keys=True),
        "```",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_daily_business_summary(auth: Any, output_dir: str = "reports/daily_business") -> Path:
    now = _utc_now()
    metrics = aggregate_business_metrics(auth=auth, lookback_days=7)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"business_summary_{now.strftime('%Y%m%d')}.md"

    lines = [
        "# Daily Business Summary",
        "",
        f"- generated_at_utc: {now.isoformat()}",
        f"- active_users: {metrics['active_users']}",
        f"- arpu_technical_estimated_usd: {metrics['arpu_technical_estimated_usd']}",
        f"- cost_per_active_user_usd: {metrics['cost_per_active_user_usd']}",
        f"- gross_margin_global_pct: {metrics['gross_margin_global_pct']}",
        f"- cache_hit_ratio_global: {metrics['cache_hit_ratio_global']}",
        f"- weekly_upgrade_rate: {metrics['weekly_upgrade_rate']}",
        "",
        "## Plans",
        "```json",
        json.dumps(metrics["plans"], indent=2, sort_keys=True),
        "```",
        "",
        "## Funnel",
        "```json",
        json.dumps(metrics["funnel"], indent=2, sort_keys=True),
        "```",
        "",
        "## A/B",
        "```json",
        json.dumps(metrics["ab_tests"], indent=2, sort_keys=True),
        "```",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
