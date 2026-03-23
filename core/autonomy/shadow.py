from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class ShadowComparison:
    quality_delta: float
    latency_delta_ms: float
    cost_delta_usd: float
    promoted: bool
    reason: str


class ShadowDeploymentEngine:
    """Run candidate model in parallel and promote with guardrails."""

    def compare(
        self,
        *,
        current_fn: Callable[[pd.DataFrame], pd.DataFrame],
        candidate_fn: Callable[[pd.DataFrame], pd.DataFrame],
        df: pd.DataFrame,
        cost_current_usd: float,
        cost_candidate_usd: float,
        min_quality_improvement: float = 0.02,
        max_latency_penalty_ms: float = 25.0,
        max_cost_penalty_usd: float = 0.003,
    ) -> ShadowComparison:
        src = pd.DataFrame() if df is None else df.copy()

        t0 = time.perf_counter()
        out_current = current_fn(src.copy())
        latency_current = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        out_candidate = candidate_fn(src.copy())
        latency_candidate = (time.perf_counter() - t1) * 1000.0

        quality_current = self._quality_proxy(out_current)
        quality_candidate = self._quality_proxy(out_candidate)
        quality_delta = quality_candidate - quality_current

        latency_delta = latency_candidate - latency_current
        cost_delta = float(cost_candidate_usd - cost_current_usd)

        promote = (
            quality_delta >= min_quality_improvement
            and latency_delta <= max_latency_penalty_ms
            and cost_delta <= max_cost_penalty_usd
        )
        reason = (
            "guardrails passed"
            if promote
            else "guardrails failed: check quality/latency/cost"
        )

        return ShadowComparison(
            quality_delta=round(float(quality_delta), 6),
            latency_delta_ms=round(float(latency_delta), 4),
            cost_delta_usd=round(float(cost_delta), 6),
            promoted=promote,
            reason=reason,
        )

    def _quality_proxy(self, df: pd.DataFrame) -> float:
        if df is None or df.empty:
            return 0.0
        col = "Score Unificado" if "Score Unificado" in df.columns else "Score Oportunidad"
        if col not in df.columns:
            return 0.0
        score = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        top = score.nlargest(min(10, len(score)))
        return float(top.mean() / 100.0)
