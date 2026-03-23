from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SanityCheckResult:
    allowed: bool
    reason: str


class SafetyGuardrails:
    """Safety checks to avoid extreme recommendations on anomalous data."""

    DISCLAIMER = "Este contenido es informativo y educativo. No constituye consejo financiero."

    def validate_row(self, row: dict[str, Any]) -> SanityCheckResult:
        score = float(row.get("Score Unificado", row.get("Score Oportunidad", 0.0)) or 0.0)
        credit = float(row.get("Crédito", 0.0) or 0.0)
        dte = float(row.get("DTE", 0.0) or 0.0)
        risk = float(row.get("Riesgo Máx", 0.0) or 0.0)
        bid_ask = float(row.get("Bid-Ask", 0.0) or 0.0)

        if score > 100 or score < 0:
            return SanityCheckResult(False, "score fuera de rango")
        if credit <= 0:
            return SanityCheckResult(False, "credito invalido")
        if dte <= 0 or dte > 365:
            return SanityCheckResult(False, "dte anomalo")
        if risk < 0:
            return SanityCheckResult(False, "riesgo invalido")
        if bid_ask < 0 or bid_ask > 5:
            return SanityCheckResult(False, "bid-ask anomalo")
        return SanityCheckResult(True, "ok")

    def enforce(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df

        keep_rows = []
        for row in df.to_dict("records"):
            chk = self.validate_row(row)
            if chk.allowed:
                row["Disclaimer"] = self.DISCLAIMER
                keep_rows.append(row)
        return pd.DataFrame(keep_rows)
