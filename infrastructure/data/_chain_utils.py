"""Shared helpers for option-chain DataFrames."""
from __future__ import annotations

import pandas as pd

CHAIN_REQUIRED_COLUMNS: list[str] = [
    "strike",
    "lastPrice",
    "bid",
    "ask",
    "volume",
    "openInterest",
    "impliedVolatility",
]


def normalize_chain_df(df: pd.DataFrame | None) -> pd.DataFrame:
    """Normalize a raw yfinance options-chain DataFrame to the standard column schema."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=CHAIN_REQUIRED_COLUMNS)

    out = df.copy()
    for col in CHAIN_REQUIRED_COLUMNS:
        if col not in out.columns:
            out[col] = 0

    out["strike"] = pd.to_numeric(out["strike"], errors="coerce").fillna(0.0).astype(float)
    out["lastPrice"] = pd.to_numeric(out["lastPrice"], errors="coerce").fillna(0.0).astype(float)
    out["bid"] = pd.to_numeric(out["bid"], errors="coerce").fillna(0.0).astype(float)
    out["ask"] = pd.to_numeric(out["ask"], errors="coerce").fillna(0.0).astype(float)
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype(int)
    out["openInterest"] = pd.to_numeric(out["openInterest"], errors="coerce").fillna(0).astype(int)
    out["impliedVolatility"] = pd.to_numeric(out["impliedVolatility"], errors="coerce").fillna(0.0).astype(float)
    return out[CHAIN_REQUIRED_COLUMNS]
