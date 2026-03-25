# -*- coding: utf-8 -*-
"""Credit Spread — pure options math helpers and pre-filter utilities."""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from datetime import datetime, date

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from config.constants import (
    RISK_FREE_RATE, DAYS_PER_YEAR,
    CS_MIN_PRICE, CS_MIN_AVG_VOLUME, CS_MAX_BID_ASK_PCT,
)
from core.option_greeks import OptionGreeks, quick_probability_of_touch
from core.scanner import (
    _cached_options_dates, _cached_option_chain, _cached_history,
)

logger = logging.getLogger(__name__)

def _dte_from_expiry(exp_str: str) -> int:
    """Calcula días hasta el vencimiento desde una fecha YYYY-MM-DD."""
    try:
        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        # Usar fecha de mercado (US/Eastern) evita desfases de ±1 día cuando
        # el servidor está en otra zona horaria (UTC/latam/eu).
        if ZoneInfo is not None:
            today = datetime.now(ZoneInfo("America/New_York")).date()
        else:
            today = date.today()
        return max((exp_date - today).days, 0)
    except Exception:
        return 0


def _bsm_delta(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> float:
    """Calcula delta preciso usando Black-Scholes-Merton.

    Falls back a estimación por moneyness si los inputs no son válidos.
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25  # fallback IV 25 %
    try:
        greeks = OptionGreeks(S=spot, K=strike, T=T, r=RISK_FREE_RATE, sigma=sigma)
        d = greeks.delta()
        return float(d.get(option_type, 0.0))
    except Exception:
        # Fallback simple
        if option_type == "put":
            m = (spot - strike) / spot
            return max(-0.50, min(-0.01, -0.50 + m * 3))
        m = (strike - spot) / spot
        return max(0.01, min(0.50, 0.50 - m * 3))


def _bsm_greeks(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> dict[str, float]:
    """Calcula gamma y theta via BSM para un contrato individual.

    Returns dict con claves: gamma, theta.  Ambos por unidad/día.
    Gamma es idéntico para calls y puts; theta depende del tipo.
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    try:
        g = OptionGreeks(S=spot, K=strike, T=T, r=RISK_FREE_RATE, sigma=sigma)
        return {
            "gamma": g.gamma(),
            "theta": g.theta().get(option_type, 0.0),
        }
    except Exception:
        return {"gamma": 0.0, "theta": 0.0}


def _pop_from_delta(delta: float) -> float:
    """Probabilidad de ganancia estimada = 1 - |delta| del strike vendido."""
    return round(1.0 - abs(delta), 4)


def _pop_from_breakeven(
    spot: float,
    breakeven: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> float:
    """POP basado en breakeven real del spread (BSM con IV del strike).

    Para Bull Put: breakeven = strike_vendido - crédito
        POP = P(S_T > breakeven) = N(d2)  con K = breakeven
    Para Bear Call: breakeven = strike_vendido + crédito
        POP = P(S_T < breakeven) = N(-d2) con K = breakeven

    Más preciso que 1-|Δ| porque usa el breakeven real del spread.
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    try:
        g = OptionGreeks(S=spot, K=breakeven, T=T, r=RISK_FREE_RATE, sigma=sigma)
        d2 = g._d2
        from scipy.stats import norm as _norm
        if option_type == "put":
            return float(_norm.cdf(d2))       # P(S_T > breakeven)
        return float(_norm.cdf(-d2))          # P(S_T < breakeven)
    except Exception:
        return 0.70


def calculate_probability_of_touch(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> float:
    """Probability of Touch (PoT) del strike vendido — fórmula BSM exacta.

    Usa la fórmula de primer toque de barrera (first-passage time)
    en vez de la aproximación 2×|Δ| de tastytrade.

    La fórmula exacta captura el efecto del drift y es más precisa
    para strikes OTM con skew alto.

    Args:
        spot:        precio actual del subyacente
        strike:      strike vendido
        dte:         días hasta vencimiento
        iv:          implied volatility del strike (decimal, ej 0.25)
        option_type: "put" o "call"

    Returns:
        Probabilidad de toque en porcentaje (0.0 – 99.0).
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    prob = quick_probability_of_touch(
        S=spot, K=strike, T=T, iv=sigma,
        option_type=option_type, r=RISK_FREE_RATE,
    )
    return round(min(prob * 100.0, 99.0), 1)


def _pot_approx_2delta(delta: float) -> float:
    """PoT aproximado tastytrade (2×|Δ|) — solo para columna debug."""
    return round(min(2.0 * abs(delta) * 100.0, 99.0), 1)


def _bid_ask_spread(bid: float, ask: float) -> float:
    """Spread bid-ask en dólares."""
    if ask > 0 and bid >= 0:
        return round(ask - bid, 2)
    return 0.0


def _strike_distance_pct(spot: float, strike: float) -> float:
    """% de distancia entre spot y strike vendido."""
    if spot <= 0:
        return 0.0
    return round(abs(spot - strike) / spot * 100, 2)


# ────────────────────────────────────────────────────────────────────────────
#  Helpers de pre-filtro (underlying y liquidez)
# ────────────────────────────────────────────────────────────────────────────

def _avg_daily_volume(ticker: str, days: int = 20) -> float:
    """Volumen diario promedio (acciones) de los últimos *days* días."""
    try:
        hist = _cached_history(ticker, "1mo")
        if hist is None or hist.empty:
            return 0.0
        vol = hist["Volume"]
        if hasattr(vol, "squeeze"):
            vol = vol.squeeze()
        return float(vol.tail(days).mean())
    except Exception:
        return 0.0


def _avg_chain_oi(ticker: str) -> float:
    """OI promedio en los strikes más cercanos (ATM ±5) de la primera expiración."""
    try:
        dates = _cached_options_dates(ticker)
        if not dates:
            return 0.0
        chain = _cached_option_chain(ticker, dates[0])
        puts = chain.get("puts", pd.DataFrame())
        calls = chain.get("calls", pd.DataFrame())
        oi_vals = []
        for df_chain in (puts, calls):
            if not df_chain.empty and "openInterest" in df_chain.columns:
                oi_vals.extend(df_chain["openInterest"].dropna().tolist())
        if not oi_vals:
            return 0.0
        # Tomar strikes centrales (ordenar por OI y promediar top-10)
        oi_vals.sort(reverse=True)
        return float(np.mean(oi_vals[: min(10, len(oi_vals))]))
    except Exception:
        return 0.0


def _passes_underlying_filter(ticker: str, spot: float) -> tuple[bool, str]:
    """Filtro 1 — verifica precio y volumen promedio del subyacente.

    Returns (passed, reason).

    Nota: si avg_vol == 0 (rate-limit / error de red) el ticker pasa con
    beneficio de la duda. Solo se rechaza cuando hay un valor real positivo
    menor al umbral.
    """
    if spot < CS_MIN_PRICE:
        return False, f"Precio ${spot:.2f} < ${CS_MIN_PRICE}"
    avg_vol = _avg_daily_volume(ticker)
    # avg_vol == 0 → dato no disponible (rate-limit/error) → no rechazar
    if avg_vol > 0 and avg_vol < CS_MIN_AVG_VOLUME:
        return False, f"Vol prom {avg_vol:,.0f} < {CS_MIN_AVG_VOLUME:,}"
    return True, ""


def _passes_bid_ask_filter(bid: float, ask: float) -> bool:
    """Filtro 9c — Bid-Ask Spread ≤ 10% del mid price."""
    if ask <= 0 or bid < 0:
        return False
    mid = (bid + ask) / 2
    if mid <= 0:
        return False
    return (ask - bid) / mid <= CS_MAX_BID_ASK_PCT

