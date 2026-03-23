from __future__ import annotations

from typing import Any


def compute_intelligence_roi(
    *,
    useful_signal_improvement_pct: float,
    retention_improvement_pct: float,
    conversion_improvement_pct: float,
    incremental_monthly_cost_usd: float,
    baseline_monthly_revenue_usd: float,
) -> dict[str, Any]:
    uplift_revenue = baseline_monthly_revenue_usd * (
        (useful_signal_improvement_pct + retention_improvement_pct + conversion_improvement_pct) / 100.0
    )
    net_gain = uplift_revenue - incremental_monthly_cost_usd
    roi_pct = (net_gain / max(incremental_monthly_cost_usd, 1e-6)) * 100.0
    return {
        "uplift_revenue_usd": round(float(uplift_revenue), 4),
        "incremental_cost_usd": round(float(incremental_monthly_cost_usd), 4),
        "net_gain_usd": round(float(net_gain), 4),
        "roi_pct": round(float(roi_pct), 4),
    }
