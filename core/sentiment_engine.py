# -*- coding: utf-8 -*-
"""Motor quant para Options Flow y OKA Sentiment Index.

Este modulo clasifica agresion de ordenes a partir de last/bid/ask, estima
flujos alcistas/bajistas y calcula un indice de sentimiento 0-100.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from config.constants import DAYS_PER_YEAR, RISK_FREE_RATE
from core.option_greeks import OptionGreeks


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convierte a float de forma segura."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    """Convierte a int de forma segura."""
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def calculate_trade_aggression(price: float, bid: float, ask: float) -> str:
    """Clasifica la agresion del trade segun posicion relativa en el spread.

    Reglas:
    - aggressive_buy:  price >= ask
    - aggressive_sell: price <= bid
    - neutral:         en cualquier otro caso
    """
    p = _to_float(price)
    b = _to_float(bid)
    a = _to_float(ask)

    if p <= 0:
        return "neutral"

    # Si no hay book valido no se puede inferir agresion con confianza.
    if b <= 0 or a <= 0:
        return "neutral"

    if p >= a:
        return "aggressive_buy"
    if p <= b:
        return "aggressive_sell"
    return "neutral"


def _estimate_delta(row: pd.Series, spot_price: float) -> float:
    """Estima delta (o usa la disponible) para ponderar premium por direccionalidad."""
    raw_delta = row.get("delta", row.get("Delta", None))
    if raw_delta is not None and not pd.isna(raw_delta):
        d = abs(_to_float(raw_delta))
        if d > 0:
            return min(d, 1.0)

    strike = _to_float(row.get("strike", row.get("Strike", 0)))
    if strike <= 0 or spot_price <= 0:
        return 0.5

    iv_raw = _to_float(row.get("impliedVolatility", row.get("iv", row.get("IV", 0.30))), 0.30)
    sigma = iv_raw / 100.0 if iv_raw > 1.0 else iv_raw
    sigma = max(0.05, min(sigma, 3.0))

    dte = _to_int(row.get("dte", row.get("DTE", 30)), 30)
    t_years = max(dte / DAYS_PER_YEAR, 1.0 / DAYS_PER_YEAR)

    option_type = str(row.get("option_type", row.get("Tipo", "call"))).lower()
    side = "put" if "put" in option_type else "call"

    try:
        model = OptionGreeks(
            S=float(spot_price),
            K=float(strike),
            T=float(t_years),
            r=float(RISK_FREE_RATE),
            sigma=float(sigma),
        )
        d_map = model.delta()
        return min(abs(float(d_map.get(side, 0.5))), 1.0)
    except Exception:
        # Fallback robusto si algun parametro invalido rompe BSM.
        moneyness = abs(spot_price - strike) / max(spot_price, 1.0)
        return max(0.1, min(0.9, 0.6 - (moneyness * 1.2)))


def calculate_flow_metrics(chain_dataframe: pd.DataFrame, spot_price: float) -> dict[str, float]:
    """Calcula metricas de flujo estimadas a partir de una cadena de opciones.

    Args:
        chain_dataframe: dataframe combinado calls/puts con al menos columnas:
            option_type, bid, ask, lastPrice, volume, impliedVolatility, strike, dte
        spot_price: precio spot actual del subyacente.

    Returns:
        Dict con DeltaWeightedPremium, BullishFlow, BearishFlow, NetFlow, TotalFlow.
    """
    if chain_dataframe is None or chain_dataframe.empty:
        return {
            "DeltaWeightedPremium": 0.0,
            "BullishFlow": 0.0,
            "BearishFlow": 0.0,
            "NetFlow": 0.0,
            "TotalFlow": 0.0,
            "AggressiveBuys": 0.0,
            "AggressiveSells": 0.0,
            "NeutralTrades": 0.0,
        }

    bullish_flow = 0.0
    bearish_flow = 0.0
    dwp_total = 0.0
    agg_buy = 0
    agg_sell = 0
    neutral = 0

    for _, row in chain_dataframe.iterrows():
        bid = _to_float(row.get("bid", 0))
        ask = _to_float(row.get("ask", 0))
        last_price = _to_float(row.get("lastPrice", row.get("last", 0)))
        volume = _to_float(row.get("volume", 0))

        if last_price <= 0 or volume <= 0:
            continue

        premium = last_price * volume * 100.0
        option_type = str(row.get("option_type", row.get("Tipo", "call"))).lower()
        aggression = calculate_trade_aggression(last_price, bid, ask)

        delta_abs = _estimate_delta(row, spot_price)
        dwp_total += premium * delta_abs

        if aggression == "aggressive_buy":
            agg_buy += 1
            if "call" in option_type:
                bullish_flow += premium
            else:
                bearish_flow += premium
        elif aggression == "aggressive_sell":
            agg_sell += 1
            if "call" in option_type:
                bearish_flow += premium
            else:
                bullish_flow += premium
        else:
            neutral += 1

    total_flow = bullish_flow + bearish_flow
    net_flow = bullish_flow - bearish_flow

    return {
        "DeltaWeightedPremium": float(dwp_total),
        "BullishFlow": float(bullish_flow),
        "BearishFlow": float(bearish_flow),
        "NetFlow": float(net_flow),
        "TotalFlow": float(total_flow),
        "AggressiveBuys": float(agg_buy),
        "AggressiveSells": float(agg_sell),
        "NeutralTrades": float(neutral),
    }


def calculate_oka_sentiment_index(bullish_flow: float, bearish_flow: float) -> dict[str, float | str]:
    """Calcula score OKA Sentiment Index en escala [0, 100] + etiqueta.

    Formula institucional:
        Sentiment = 50 + (NetFlow / TotalFlow) * 50

    Si TotalFlow = 0, devuelve 50 (neutral).
    """
    bullish = max(_to_float(bullish_flow), 0.0)
    bearish = max(_to_float(bearish_flow), 0.0)

    net_flow = bullish - bearish
    total_flow = bullish + bearish

    try:
        if total_flow <= 0:
            score = 50.0
        else:
            score = 50.0 + (net_flow / total_flow) * 50.0
    except ZeroDivisionError:
        score = 50.0

    score = max(0.0, min(100.0, score))

    if score < 30:
        label = "Extremadamente Bajista"
    elif score < 45:
        label = "Bajista"
    elif score <= 55:
        label = "Neutral"
    elif score <= 70:
        label = "Alcista"
    else:
        label = "Extremadamente Alcista"

    return {
        "score": float(score),
        "label": label,
        "net_flow": float(net_flow),
        "total_flow": float(total_flow),
    }
