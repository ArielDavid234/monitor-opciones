from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


@dataclass(frozen=True)
class SignalOutcomeLabel:
    signal_id: str
    horizon: str
    realized_pnl: float
    expected_pnl: float
    label: str


class FeedbackLoopEngine:
    """Closed-loop pipeline for signal feedback and incremental training data."""

    SIGNALS_KEY = "autonomy_signals_emitted"
    OUTCOMES_KEY = "autonomy_signal_outcomes"
    DATASET_KEY = "autonomy_incremental_dataset"

    def emit_signal(
        self,
        auth: Any,
        user_id: str,
        *,
        signal_id: str,
        signal_payload: dict[str, Any],
        market_context: dict[str, Any],
        horizons: list[str],
    ) -> dict[str, Any]:
        rows = auth.load_user_data(user_id, self.SIGNALS_KEY)
        rows = rows if isinstance(rows, list) else []
        row = {
            "signal_id": signal_id,
            "emitted_at": _utc_now_iso(),
            "signal": signal_payload,
            "market_context": market_context,
            "horizons": list(horizons or []),
        }
        rows.append(row)
        auth.save_user_data(user_id, self.SIGNALS_KEY, rows[-5000:])
        return row

    def record_outcome(
        self,
        auth: Any,
        user_id: str,
        *,
        signal_id: str,
        horizon: str,
        realized_pnl: float,
        expected_pnl: float,
        extra_context: dict[str, Any] | None = None,
    ) -> SignalOutcomeLabel:
        rows = auth.load_user_data(user_id, self.OUTCOMES_KEY)
        rows = rows if isinstance(rows, list) else []

        realized = _to_float(realized_pnl)
        expected = _to_float(expected_pnl)
        if realized >= expected and realized > 0:
            label = "outperform"
        elif realized >= 0:
            label = "neutral"
        else:
            label = "underperform"

        outcome = {
            "signal_id": signal_id,
            "horizon": horizon,
            "realized_pnl": realized,
            "expected_pnl": expected,
            "label": label,
            "recorded_at": _utc_now_iso(),
            "context": extra_context or {},
        }
        rows.append(outcome)
        auth.save_user_data(user_id, self.OUTCOMES_KEY, rows[-10000:])

        self._rebuild_incremental_dataset(auth, user_id)
        return SignalOutcomeLabel(
            signal_id=signal_id,
            horizon=horizon,
            realized_pnl=realized,
            expected_pnl=expected,
            label=label,
        )

    def _rebuild_incremental_dataset(self, auth: Any, user_id: str) -> pd.DataFrame:
        emitted = auth.load_user_data(user_id, self.SIGNALS_KEY)
        emitted = emitted if isinstance(emitted, list) else []
        outcomes = auth.load_user_data(user_id, self.OUTCOMES_KEY)
        outcomes = outcomes if isinstance(outcomes, list) else []

        if not emitted or not outcomes:
            empty = pd.DataFrame()
            auth.save_user_data(user_id, self.DATASET_KEY, [])
            return empty

        e_df = pd.DataFrame(emitted)
        o_df = pd.DataFrame(outcomes)
        if e_df.empty or o_df.empty:
            auth.save_user_data(user_id, self.DATASET_KEY, [])
            return pd.DataFrame()

        merged = e_df.merge(o_df, on="signal_id", how="inner", suffixes=("_emit", "_outcome"))
        if merged.empty:
            auth.save_user_data(user_id, self.DATASET_KEY, [])
            return merged

        # Flatten selected fields for model-ready incremental dataset.
        merged["score_unificado"] = merged["signal"].map(lambda s: _to_float((s or {}).get("Score Unificado", (s or {}).get("Score Oportunidad", 0.0))))
        merged["perfil_riesgo"] = merged["signal"].map(lambda s: str((s or {}).get("Perfil Riesgo", "Balanceada")))
        merged["dte"] = merged["signal"].map(lambda s: _to_float((s or {}).get("DTE", 0)))
        merged["credito"] = merged["signal"].map(lambda s: _to_float((s or {}).get("Crédito", 0.0)))

        dataset_cols = [
            "signal_id",
            "emitted_at",
            "recorded_at",
            "horizon",
            "score_unificado",
            "perfil_riesgo",
            "dte",
            "credito",
            "realized_pnl",
            "expected_pnl",
            "label",
        ]
        final_df = merged[[c for c in dataset_cols if c in merged.columns]].copy()
        auth.save_user_data(user_id, self.DATASET_KEY, final_df.to_dict("records")[-20000:])
        return final_df

    def load_incremental_dataset(self, auth: Any, user_id: str) -> pd.DataFrame:
        rows = auth.load_user_data(user_id, self.DATASET_KEY)
        rows = rows if isinstance(rows, list) else []
        return pd.DataFrame(rows)
