from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WalkForwardMetrics:
    topk_precision: float
    regime_stability: float
    informative_drawdown: float
    false_positive_rate: float
    false_negative_rate: float


class WalkForwardEvaluator:
    """Temporal walk-forward evaluator to reduce overfitting risk."""

    def evaluate(
        self,
        dataset: pd.DataFrame,
        *,
        top_k: int = 10,
        train_window: int = 120,
        test_window: int = 30,
    ) -> WalkForwardMetrics:
        if dataset is None or dataset.empty:
            return WalkForwardMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

        df = dataset.copy()
        if "emitted_at" in df.columns:
            df["_ts"] = pd.to_datetime(df["emitted_at"], errors="coerce", utc=True)
        else:
            df["_ts"] = pd.to_datetime(df.get("recorded_at"), errors="coerce", utc=True)
        df = df.dropna(subset=["_ts"]).sort_values("_ts").reset_index(drop=True)
        if df.empty:
            return WalkForwardMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

        for col in ["score_unificado", "realized_pnl", "expected_pnl"]:
            if col not in df.columns:
                df[col] = 0.0
        y_true = (pd.to_numeric(df["realized_pnl"], errors="coerce").fillna(0.0) > 0).astype(int)
        y_pred = (pd.to_numeric(df["score_unificado"], errors="coerce").fillna(0.0) >= 70).astype(int)

        topk_scores: list[float] = []
        regime_stability_samples: list[float] = []
        drawdowns: list[float] = []

        n = len(df)
        i = train_window
        while i + test_window <= n:
            test = df.iloc[i : i + test_window].copy()
            if test.empty:
                break

            ranked = test.sort_values("score_unificado", ascending=False).head(max(1, min(top_k, len(test))))
            topk_precision = float((pd.to_numeric(ranked["realized_pnl"], errors="coerce").fillna(0.0) > 0).mean())
            topk_scores.append(topk_precision)

            # Stability by regime uses profile/risk buckets if available.
            if "perfil_riesgo" in test.columns:
                grp = test.groupby("perfil_riesgo")["score_unificado"].mean()
                regime_stability_samples.append(float(1.0 / (1.0 + grp.std(ddof=0))))

            pnl = pd.to_numeric(test["realized_pnl"], errors="coerce").fillna(0.0).cumsum()
            dd = float((pnl.cummax() - pnl).max()) if not pnl.empty else 0.0
            drawdowns.append(dd)

            i += test_window

        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        tn = int(((y_true == 0) & (y_pred == 0)).sum())

        fpr = fp / max(fp + tn, 1)
        fnr = fn / max(fn + tp, 1)

        return WalkForwardMetrics(
            topk_precision=round(float(np.mean(topk_scores)) if topk_scores else 0.0, 4),
            regime_stability=round(float(np.mean(regime_stability_samples)) if regime_stability_samples else 0.0, 4),
            informative_drawdown=round(float(np.mean(drawdowns)) if drawdowns else 0.0, 4),
            false_positive_rate=round(float(fpr), 4),
            false_negative_rate=round(float(fnr), 4),
        )
