from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from core.intelligence_layer import IntelligenceWeights


@dataclass(frozen=True)
class RecalibrationDecision:
    promoted: bool
    improvement_pct: float
    reason: str
    candidate_weights: IntelligenceWeights


class RecalibrationEngine:
    """Periodic score weight recalibration with frozen base + shadow candidate mode."""

    BASE_KEY = "autonomy_score_weights_base"
    SHADOW_KEY = "autonomy_score_weights_shadow"
    PROD_KEY = "autonomy_score_weights_prod"

    def _base_weights(self) -> IntelligenceWeights:
        return IntelligenceWeights()

    def load_weights(self, auth: Any, user_id: str, *, mode: str = "prod") -> IntelligenceWeights:
        key = {
            "base": self.BASE_KEY,
            "shadow": self.SHADOW_KEY,
            "prod": self.PROD_KEY,
        }.get(mode, self.PROD_KEY)
        row = auth.load_user_data(user_id, key)
        if not isinstance(row, dict):
            w = self._base_weights()
            auth.save_user_data(user_id, key, w.__dict__)
            return w
        try:
            return IntelligenceWeights(**row).normalized()
        except Exception:
            return self._base_weights()

    def derive_shadow_candidate(self, dataset: pd.DataFrame) -> IntelligenceWeights:
        if dataset is None or dataset.empty:
            return self._base_weights()

        # Heuristic data-driven candidate from realized performance by feature proxies.
        safe = dataset.copy()
        for col in ["score_unificado", "dte", "credito", "realized_pnl", "expected_pnl"]:
            if col not in safe.columns:
                safe[col] = 0.0
        safe["target"] = (safe["realized_pnl"] - safe["expected_pnl"]).astype(float)

        def _corr(col: str) -> float:
            s = pd.to_numeric(safe[col], errors="coerce").fillna(0.0)
            t = pd.to_numeric(safe["target"], errors="coerce").fillna(0.0)
            if s.std() <= 1e-9 or t.std() <= 1e-9:
                return 0.0
            return float(np.corrcoef(s, t)[0, 1])

        c_score = abs(_corr("score_unificado")) + 0.01
        c_credit = abs(_corr("credito")) + 0.01
        c_dte = abs(_corr("dte")) + 0.01

        # Map into weight family preserving 6-component structure.
        candidate = IntelligenceWeights(
            liquidity=0.15 + (0.10 * c_score),
            bid_ask=0.12 + (0.10 * c_credit),
            relative_iv=0.12 + (0.08 * c_score),
            oi_volume=0.15 + (0.10 * c_credit),
            strike_distance=0.12 + (0.08 * c_dte),
            estimated_risk=0.14 + (0.10 * c_dte),
        ).normalized()
        return candidate

    def evaluate_candidate_improvement(self, dataset: pd.DataFrame) -> float:
        if dataset is None or dataset.empty:
            return 0.0
        df = dataset.copy()
        for col in ["realized_pnl", "expected_pnl"]:
            if col not in df.columns:
                df[col] = 0.0
        realized = pd.to_numeric(df["realized_pnl"], errors="coerce").fillna(0.0)
        expected = pd.to_numeric(df["expected_pnl"], errors="coerce").fillna(0.0)
        baseline = float(expected.mean()) if len(expected) else 0.0
        new_perf = float(realized.mean()) if len(realized) else 0.0
        denom = abs(baseline) if abs(baseline) > 1e-6 else 1.0
        return ((new_perf - baseline) / denom) * 100.0

    def run_recalibration(
        self,
        auth: Any,
        user_id: str,
        dataset: pd.DataFrame,
        *,
        promote_threshold_pct: float = 2.0,
    ) -> RecalibrationDecision:
        base = self.load_weights(auth, user_id, mode="base")
        auth.save_user_data(user_id, self.BASE_KEY, base.__dict__)

        candidate = self.derive_shadow_candidate(dataset)
        auth.save_user_data(user_id, self.SHADOW_KEY, candidate.__dict__)

        improvement = self.evaluate_candidate_improvement(dataset)
        if improvement >= promote_threshold_pct:
            auth.save_user_data(user_id, self.PROD_KEY, candidate.__dict__)
            return RecalibrationDecision(
                promoted=True,
                improvement_pct=round(improvement, 4),
                reason="candidate exceeds promotion threshold",
                candidate_weights=candidate,
            )

        # Keep production as-is if no improvement.
        if not isinstance(auth.load_user_data(user_id, self.PROD_KEY), dict):
            auth.save_user_data(user_id, self.PROD_KEY, base.__dict__)
        return RecalibrationDecision(
            promoted=False,
            improvement_pct=round(improvement, 4),
            reason="shadow only; below threshold",
            candidate_weights=candidate,
        )
