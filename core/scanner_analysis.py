"""Funciones de analisis extraidas de core.scanner."""

from __future__ import annotations

import pandas as pd


def get_oi_matrix(
    datos: list[dict],
    expiration_filter: str | None = None,
    min_oi: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye la matriz OI (Strike x Expiracion) para heatmap interactivo."""
    if not datos:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(datos)

    if "Prima_Volumen" in df.columns and "Prima_Vol" not in df.columns:
        df = df.rename(columns={"Prima_Volumen": "Prima_Vol"})

    if expiration_filter:
        df = df[df["Vencimiento"] == expiration_filter]

    if min_oi > 0 and "OI" in df.columns:
        df = df[df["OI"] >= min_oi]

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    oi_matrix = df.pivot_table(
        values="OI",
        index="Vencimiento",
        columns="Strike",
        aggfunc="sum",
    ).fillna(0)

    return oi_matrix, df


def calculate_call_put_bias(datos: list[dict]) -> dict:
    """Calcula sesgo alcista/bajista a partir del ratio Call/Put de OI."""
    result = {
        "bias_score": 1.0,
        "oi_calls": 0,
        "oi_puts": 0,
        "ratio_raw": 1.0,
        "total_oi": 0,
    }

    if not datos:
        return result

    df = pd.DataFrame(datos)
    if "Tipo" not in df.columns or "OI" not in df.columns:
        return result

    df["OI"] = pd.to_numeric(df["OI"], errors="coerce").fillna(0)

    oi_calls = int(df.loc[df["Tipo"] == "CALL", "OI"].sum())
    oi_puts = int(df.loc[df["Tipo"] == "PUT", "OI"].sum())
    total = oi_calls + oi_puts

    if total == 0:
        return result

    ratio = oi_calls / total
    bias_score = round(2.0 * ratio, 2)
    raw = round(oi_calls / oi_puts, 3) if oi_puts > 0 else float("inf")

    return {
        "bias_score": bias_score,
        "oi_calls": oi_calls,
        "oi_puts": oi_puts,
        "ratio_raw": raw,
        "total_oi": total,
    }
