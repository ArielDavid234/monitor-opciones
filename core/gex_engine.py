# -*- coding: utf-8 -*-
"""Gamma Exposure (GEX) y Volatility Engine.

Implementa calculos institucionales para:
1) Perfil GEX por strike (Call GEX, Put GEX, Net GEX)
2) Gamma Walls y nivel Zero Gamma
3) Volatility Skew (Puts 10% OTM vs Calls 10% OTM)
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from config.constants import DAYS_PER_YEAR, RISK_FREE_RATE

try:
    from scipy.stats import norm
except Exception:  # pragma: no cover
    norm = None  # type: ignore[assignment]


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convierte a float de forma segura."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _infer_option_type(row: pd.Series) -> str:
    """Devuelve 'call' o 'put' en base a columnas comunes."""
    raw = str(
        row.get("option_type", row.get("Tipo", row.get("type", row.get("contractType", "call"))))
    ).lower()
    return "put" if "put" in raw else "call"


def _norm_pdf(x: float) -> float:
    """PDF normal estandar con fallback si scipy no esta disponible."""
    if norm is not None:
        try:
            return float(norm.pdf(x))
        except Exception:
            pass
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _approx_gamma_black_scholes(
    spot_price: float,
    strike: float,
    iv_decimal: float,
    dte_days: int,
    r: float = RISK_FREE_RATE,
) -> float:
    """Aproxima gamma con Black-Scholes cuando API no trae gamma.

    Gamma = N'(d1) / (S * sigma * sqrt(T))
    """
    s = max(_safe_float(spot_price), 0.0)
    k = max(_safe_float(strike), 0.0)
    sigma = max(_safe_float(iv_decimal), 1e-6)
    t = max(_safe_float(dte_days) / DAYS_PER_YEAR, 1.0 / DAYS_PER_YEAR)

    if s <= 0 or k <= 0 or sigma <= 0 or t <= 0:
        return 0.0

    try:
        vol_term = sigma * math.sqrt(t)
        if vol_term <= 0:
            return 0.0
        d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / vol_term
        gamma = _norm_pdf(d1) / (s * vol_term)
        return max(0.0, float(gamma))
    except Exception:
        return 0.0


def calculate_gex_by_strike(gamma: float, open_interest: float, spot_price: float) -> float:
    """Calcula GEX por strike.

    Formula institucional:
        GEX = Gamma * OpenInterest * 100 * (SpotPrice**2) * 0.01
    """
    g = _safe_float(gamma)
    oi = max(_safe_float(open_interest), 0.0)
    s = max(_safe_float(spot_price), 0.0)
    return float(g * oi * 100.0 * (s ** 2) * 0.01)


def _infer_spot_price(chain_dataframe: pd.DataFrame) -> float:
    """Infiere spot desde columnas comunes; fallback a mediana de strike."""
    for col in ("Spot", "spot", "underlyingPrice", "underlying_price"):
        if col in chain_dataframe.columns:
            val = _safe_float(chain_dataframe[col].iloc[0], 0.0)
            if val > 0:
                return val
    strike_col = "strike" if "strike" in chain_dataframe.columns else "Strike"
    if strike_col in chain_dataframe.columns:
        med = _safe_float(chain_dataframe[strike_col].median(), 0.0)
        if med > 0:
            return med
    return 0.0


def build_gex_profile(chain_dataframe: pd.DataFrame, spot_price: float) -> dict[str, Any]:
    """Construye perfil GEX por strike, gamma walls y nivel zero-gamma.

    Returns:
        {
            "profile": DataFrame[strike, Call GEX, Put GEX, Net GEX, OI Total],
            "zero_gamma_level": float,
            "call_wall": {"strike": float, "gex": float},
            "put_wall": {"strike": float, "gex": float},
        }
    """
    if chain_dataframe is None or chain_dataframe.empty:
        return {
            "profile": pd.DataFrame(),
            "zero_gamma_level": 0.0,
            "call_wall": {"strike": 0.0, "gex": 0.0},
            "put_wall": {"strike": 0.0, "gex": 0.0},
        }

    df = chain_dataframe.copy()
    strike_col = "strike" if "strike" in df.columns else "Strike"
    oi_col = "openInterest" if "openInterest" in df.columns else ("OI" if "OI" in df.columns else "oi")
    gamma_col = "gamma" if "gamma" in df.columns else ("Gamma" if "Gamma" in df.columns else None)
    iv_col = (
        "impliedVolatility"
        if "impliedVolatility" in df.columns
        else ("IV" if "IV" in df.columns else ("iv" if "iv" in df.columns else None))
    )
    dte_col = "dte" if "dte" in df.columns else ("DTE" if "DTE" in df.columns else None)

    if strike_col not in df.columns or oi_col not in df.columns:
        return {
            "profile": pd.DataFrame(),
            "zero_gamma_level": 0.0,
            "call_wall": {"strike": 0.0, "gex": 0.0},
            "put_wall": {"strike": 0.0, "gex": 0.0},
        }

    spot = _safe_float(spot_price, 0.0)
    if spot <= 0:
        spot = _infer_spot_price(df)

    rows: list[dict[str, float]] = []
    for _, row in df.iterrows():
        strike = _safe_float(row.get(strike_col, 0.0), 0.0)
        oi = max(_safe_float(row.get(oi_col, 0.0), 0.0), 0.0)
        if strike <= 0 or oi <= 0 or spot <= 0:
            continue

        gamma_raw = _safe_float(row.get(gamma_col, 0.0), 0.0) if gamma_col else 0.0
        if gamma_raw <= 0:
            iv_raw = _safe_float(row.get(iv_col, 0.0), 0.0) if iv_col else 0.0
            iv_dec = iv_raw / 100.0 if iv_raw > 1.0 else iv_raw
            dte_days = int(_safe_float(row.get(dte_col, 30), 30.0)) if dte_col else 30
            gamma_eff = _approx_gamma_black_scholes(
                spot_price=spot,
                strike=strike,
                iv_decimal=max(iv_dec, 0.05),
                dte_days=max(dte_days, 1),
            )
        else:
            gamma_eff = gamma_raw

        gex_abs = calculate_gex_by_strike(gamma_eff, oi, spot)
        opt_type = _infer_option_type(row)
        call_gex = gex_abs if opt_type == "call" else 0.0
        put_gex = -gex_abs if opt_type == "put" else 0.0

        rows.append(
            {
                "strike": strike,
                "Call GEX": call_gex,
                "Put GEX": put_gex,
                "Net GEX": call_gex + put_gex,
                "OI Total": oi,
            }
        )

    if not rows:
        return {
            "profile": pd.DataFrame(),
            "zero_gamma_level": 0.0,
            "call_wall": {"strike": 0.0, "gex": 0.0},
            "put_wall": {"strike": 0.0, "gex": 0.0},
        }

    profile = (
        pd.DataFrame(rows)
        .groupby("strike", as_index=False)
        .agg({"Call GEX": "sum", "Put GEX": "sum", "Net GEX": "sum", "OI Total": "sum"})
        .sort_values("strike")
        .reset_index(drop=True)
    )

    # Gamma Walls
    pos = profile[profile["Net GEX"] > 0]
    neg = profile[profile["Net GEX"] < 0]
    if not pos.empty:
        call_row = pos.loc[pos["Net GEX"].idxmax()]
        call_wall = {"strike": float(call_row["strike"]), "gex": float(call_row["Net GEX"])}
    else:
        call_wall = {"strike": 0.0, "gex": 0.0}

    if not neg.empty:
        put_row = neg.loc[neg["Net GEX"].abs().idxmax()]
        put_wall = {"strike": float(put_row["strike"]), "gex": float(put_row["Net GEX"])}
    else:
        put_wall = {"strike": 0.0, "gex": 0.0}

    # Zero Gamma Level (interpolacion donde cumulative net cruza 0)
    profile["Cum Net GEX"] = profile["Net GEX"].cumsum()
    zero_gamma = 0.0
    strikes = profile["strike"].tolist()
    cum = profile["Cum Net GEX"].tolist()

    found_cross = False
    for i in range(1, len(cum)):
        y1, y2 = cum[i - 1], cum[i]
        if y1 == 0:
            zero_gamma = float(strikes[i - 1])
            found_cross = True
            break
        if (y1 < 0 <= y2) or (y1 > 0 >= y2):
            x1, x2 = strikes[i - 1], strikes[i]
            if y2 != y1:
                zero_gamma = float(x1 + (0 - y1) * (x2 - x1) / (y2 - y1))
            else:
                zero_gamma = float(x1)
            found_cross = True
            break

    if not found_cross:
        idx_min = int((profile["Cum Net GEX"].abs()).idxmin())
        zero_gamma = float(profile.loc[idx_min, "strike"])

    return {
        "profile": profile,
        "zero_gamma_level": float(zero_gamma),
        "call_wall": call_wall,
        "put_wall": put_wall,
    }


def calculate_volatility_skew(chain_dataframe: pd.DataFrame) -> dict[str, float | str]:
    """Calcula skew de IV entre puts 10% OTM y calls 10% OTM.

    Skew = IV_put_10pct_OTM - IV_call_10pct_OTM
    """
    if chain_dataframe is None or chain_dataframe.empty:
        return {
            "put_iv_10otm": 0.0,
            "call_iv_10otm": 0.0,
            "skew": 0.0,
            "regime": "Sin datos",
        }

    df = chain_dataframe.copy()
    strike_col = "strike" if "strike" in df.columns else "Strike"
    iv_col = (
        "impliedVolatility"
        if "impliedVolatility" in df.columns
        else ("IV" if "IV" in df.columns else ("iv" if "iv" in df.columns else None))
    )
    if strike_col not in df.columns or iv_col is None:
        return {
            "put_iv_10otm": 0.0,
            "call_iv_10otm": 0.0,
            "skew": 0.0,
            "regime": "Sin datos",
        }

    spot = _infer_spot_price(df)
    if spot <= 0:
        return {
            "put_iv_10otm": 0.0,
            "call_iv_10otm": 0.0,
            "skew": 0.0,
            "regime": "Sin datos",
        }

    df["_strike"] = df[strike_col].apply(_safe_float)
    df["_iv"] = df[iv_col].apply(_safe_float)
    df["_iv"] = df["_iv"].apply(lambda v: v * 100.0 if 0 < v <= 1.0 else v)
    df["_type"] = df.apply(_infer_option_type, axis=1)

    put_target = spot * 0.90
    call_target = spot * 1.10

    puts_otm = df[(df["_type"] == "put") & (df["_strike"] <= put_target)]
    calls_otm = df[(df["_type"] == "call") & (df["_strike"] >= call_target)]

    # Fallback: usar strikes mas cercanos al 10% OTM si no hay suficientes.
    if puts_otm.empty:
        puts_otm = df[df["_type"] == "put"].copy()
        puts_otm["_dist"] = (puts_otm["_strike"] - put_target).abs()
        puts_otm = puts_otm.nsmallest(8, "_dist")
    if calls_otm.empty:
        calls_otm = df[df["_type"] == "call"].copy()
        calls_otm["_dist"] = (calls_otm["_strike"] - call_target).abs()
        calls_otm = calls_otm.nsmallest(8, "_dist")

    put_iv = float(puts_otm["_iv"].mean()) if not puts_otm.empty else 0.0
    call_iv = float(calls_otm["_iv"].mean()) if not calls_otm.empty else 0.0
    skew = put_iv - call_iv

    if skew > 1.0:
        regime = "Prima defensiva (Puts > Calls)"
    elif skew < -1.0:
        regime = "Prima especulativa (Calls > Puts)"
    else:
        regime = "Skew neutral"

    return {
        "put_iv_10otm": put_iv,
        "call_iv_10otm": call_iv,
        "skew": float(skew),
        "regime": regime,
    }
