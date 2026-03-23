from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DriftAlert:
    metric: str
    value: float
    severity: str
    recommendation: str


class DriftMonitor:
    """Monitor feature/score/performance drift and produce actionable alerts."""

    def _psi_like(self, base: pd.Series, current: pd.Series, bins: int = 10) -> float:
        base = pd.to_numeric(base, errors="coerce").dropna()
        current = pd.to_numeric(current, errors="coerce").dropna()
        if base.empty or current.empty:
            return 0.0
        qs = np.linspace(0, 1, bins + 1)
        edges = np.unique(np.quantile(base, qs))
        if len(edges) <= 2:
            return 0.0
        b_hist, _ = np.histogram(base, bins=edges)
        c_hist, _ = np.histogram(current, bins=edges)
        b_pct = np.clip(b_hist / max(b_hist.sum(), 1), 1e-6, 1)
        c_pct = np.clip(c_hist / max(c_hist.sum(), 1), 1e-6, 1)
        return float(np.sum((c_pct - b_pct) * np.log(c_pct / b_pct)))

    def monitor(self, baseline_df: pd.DataFrame, current_df: pd.DataFrame) -> list[DriftAlert]:
        alerts: list[DriftAlert] = []
        if baseline_df is None or baseline_df.empty or current_df is None or current_df.empty:
            return alerts

        feature_cols = [c for c in ["DTE", "Crédito", "Bid-Ask", "Dist Strike %", "IV Rank"] if c in baseline_df.columns and c in current_df.columns]
        for col in feature_cols:
            psi = self._psi_like(baseline_df[col], current_df[col])
            if psi >= 0.3:
                alerts.append(DriftAlert(col, round(psi, 4), "high", "Recalibrar modelo y revisar proveedor de datos"))
            elif psi >= 0.15:
                alerts.append(DriftAlert(col, round(psi, 4), "medium", "Monitorear tendencia y mantener shadow mode"))

        if "Score Unificado" in baseline_df.columns and "Score Unificado" in current_df.columns:
            score_psi = self._psi_like(baseline_df["Score Unificado"], current_df["Score Unificado"])
            if score_psi >= 0.2:
                sev = "high" if score_psi >= 0.35 else "medium"
                alerts.append(DriftAlert("score_distribution", round(score_psi, 4), sev, "Auditar drift de score y activar guardrails"))

        if "realized_pnl" in baseline_df.columns and "realized_pnl" in current_df.columns:
            b = pd.to_numeric(baseline_df["realized_pnl"], errors="coerce").fillna(0.0)
            c = pd.to_numeric(current_df["realized_pnl"], errors="coerce").fillna(0.0)
            perf_delta = float(c.mean() - b.mean())
            if perf_delta < -0.25:
                alerts.append(DriftAlert("performance_post_signal", round(perf_delta, 4), "high", "Pausar promoción y ejecutar rollback de modelo"))
            elif perf_delta < -0.1:
                alerts.append(DriftAlert("performance_post_signal", round(perf_delta, 4), "medium", "Aumentar validación temporal y revisar señales"))

        return alerts

    def summarize(self, alerts: list[DriftAlert]) -> dict[str, Any]:
        return {
            "count": len(alerts),
            "high": sum(1 for a in alerts if a.severity == "high"),
            "medium": sum(1 for a in alerts if a.severity == "medium"),
            "low": sum(1 for a in alerts if a.severity == "low"),
            "alerts": [a.__dict__ for a in alerts],
        }
