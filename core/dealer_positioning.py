# -*- coding: utf-8 -*-
"""Dealer Positioning Engine y Gamma Squeeze Detector.

Este modulo modela, de forma probabilistica, la posicion estructural de
market makers (dealers) a partir de volumen/opciones y flujo direccional.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convierte valor a float de forma segura."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    """Acota valor en rango [low, high]."""
    return max(low, min(high, value))


def infer_dealer_position(
    call_volume: float,
    put_volume: float,
    bullish_flow: float,
    bearish_flow: float,
) -> dict[str, float | str]:
    """Infiere posicion de dealers (Long/Short Gamma) usando flujo agregado.

    Intuicion institucional:
    - Si el flujo comprador/agresivo en calls domina (y el flujo alcista supera
      al bajista), los dealers suelen quedar short gamma (deben perseguir precio).
    - Si domina flujo vendedor de calls y/o comprador de puts, los dealers tienden
      a quedar long gamma (hedging estabilizador).

    Returns:
        dict con:
          regime: "Short Gamma" | "Long Gamma" | "Neutral Gamma"
          pressure_score: [-100, 100]
          confidence: [0, 100]
          flow_imbalance: [-1, 1]
          volume_imbalance: [-1, 1]
    """
    cvol = max(_safe_float(call_volume), 0.0)
    pvol = max(_safe_float(put_volume), 0.0)
    bull = max(_safe_float(bullish_flow), 0.0)
    bear = max(_safe_float(bearish_flow), 0.0)

    vol_total = cvol + pvol
    flow_total = bull + bear

    volume_imbalance = ((cvol - pvol) / vol_total) if vol_total > 0 else 0.0
    flow_imbalance = ((bull - bear) / flow_total) if flow_total > 0 else 0.0

    # Mayor peso al flujo monetario que al conteo de contratos.
    pressure = 0.55 * flow_imbalance + 0.45 * volume_imbalance
    pressure = _clamp(pressure, -1.0, 1.0)
    pressure_score = pressure * 100.0
    confidence = _clamp(abs(pressure_score), 0.0, 100.0)

    if pressure >= 0.12:
        regime = "Short Gamma"
    elif pressure <= -0.12:
        regime = "Long Gamma"
    else:
        regime = "Neutral Gamma"

    return {
        "regime": regime,
        "pressure_score": float(pressure_score),
        "confidence": float(confidence),
        "flow_imbalance": float(flow_imbalance),
        "volume_imbalance": float(volume_imbalance),
    }


def detect_gamma_squeeze_conditions(
    gex_total: float,
    bullish_flow_ratio: float,
    current_iv: float,
    short_interest_proxy: float,
) -> dict[str, float | bool | str]:
    """Calcula score de probabilidad de Gamma Squeeze (0-100).

    Marco de reglas:
      1) GEX profundamente negativo  -> dealers short gamma.
      2) Presion compradora de calls -> bullish_flow_ratio alto.
      3) short_interest_proxy alto   -> mas combustible de cobertura.
      4) IV actual relativamente baja/moderada deja espacio para expansion.

    Args:
      gex_total: Net GEX agregado (negativo favorece squeeze alcista).
      bullish_flow_ratio: bullish_flow / total_flow en [0,1].
      current_iv: IV actual (0-1 o 0-100).
      short_interest_proxy: proxy de sobrecorto (ej. put/call OI ratio u otro).

    Returns:
      dict con score, alert flag y texto explicativo.
    """
    gex = _safe_float(gex_total)
    bfr = _clamp(_safe_float(bullish_flow_ratio, 0.5), 0.0, 1.0)
    iv_raw = _safe_float(current_iv)
    iv_pct = iv_raw * 100.0 if 0 < iv_raw <= 1.0 else iv_raw
    si = max(_safe_float(short_interest_proxy), 0.0)

    # Escalado heuristico institucional.
    neg_gex_factor = _clamp((-gex) / 500_000_000.0, 0.0, 1.0)
    flow_factor = _clamp((bfr - 0.50) / 0.50, 0.0, 1.0)
    iv_factor = _clamp((80.0 - iv_pct) / 80.0, 0.0, 1.0)
    short_factor = _clamp(si / 1.5, 0.0, 1.0)

    score = (
        neg_gex_factor * 45.0
        + flow_factor * 30.0
        + iv_factor * 10.0
        + short_factor * 15.0
    )
    score = _clamp(score, 0.0, 100.0)

    if score >= 80:
        regime = "Alerta Alta"
        explanation = (
            "Dealers short gamma con fuerte sesgo comprador. Riesgo elevado "
            "de cobertura forzosa y movimiento violento."
        )
    elif score >= 60:
        regime = "Vigilancia"
        explanation = "Condiciones parcialmente favorables para squeeze."
    else:
        regime = "Bajo"
        explanation = "No hay evidencia suficiente de squeeze inminente."

    return {
        "score": float(score),
        "squeeze_alert": bool(score >= 80.0),
        "regime": regime,
        "explanation": explanation,
    }


def detect_liquidity_magnet(
    chain_dataframe: pd.DataFrame,
    spot_price: float,
    move_pct: float = 0.01,
) -> dict[str, float | str]:
    """Detecta strike OTM magnetico para hedging forzoso con movimiento +/-1%.

    Metodo:
      - Objetivo alcista: spot*(1+move_pct), buscar Call OTM mas cercano.
      - Objetivo bajista: spot*(1-move_pct), buscar Put OTM mas cercano.
      - Selecciona magneto primario por menor distancia relativa al spot.
    """
    if chain_dataframe is None or chain_dataframe.empty:
        return {
            "up_magnet": 0.0,
            "down_magnet": 0.0,
            "primary_magnet": 0.0,
            "direction": "N/A",
        }

    s = max(_safe_float(spot_price), 0.0)
    if s <= 0:
        return {
            "up_magnet": 0.0,
            "down_magnet": 0.0,
            "primary_magnet": 0.0,
            "direction": "N/A",
        }

    df = chain_dataframe.copy()
    strike_col = "strike" if "strike" in df.columns else ("Strike" if "Strike" in df.columns else None)
    if strike_col is None:
        return {
            "up_magnet": 0.0,
            "down_magnet": 0.0,
            "primary_magnet": 0.0,
            "direction": "N/A",
        }

    df["_strike"] = df[strike_col].apply(_safe_float)
    df["_type"] = df.apply(
        lambda r: "put"
        if "put" in str(r.get("option_type", r.get("Tipo", r.get("type", "call")))).lower()
        else "call",
        axis=1,
    )

    up_target = s * (1.0 + move_pct)
    dn_target = s * (1.0 - move_pct)

    calls_otm = df[(df["_type"] == "call") & (df["_strike"] >= s)].copy()
    puts_otm = df[(df["_type"] == "put") & (df["_strike"] <= s)].copy()

    up_magnet = 0.0
    if not calls_otm.empty:
        calls_otm["_dist"] = (calls_otm["_strike"] - up_target).abs()
        up_magnet = float(calls_otm.loc[calls_otm["_dist"].idxmin(), "_strike"])

    down_magnet = 0.0
    if not puts_otm.empty:
        puts_otm["_dist"] = (puts_otm["_strike"] - dn_target).abs()
        down_magnet = float(puts_otm.loc[puts_otm["_dist"].idxmin(), "_strike"])

    if up_magnet > 0 and down_magnet > 0:
        up_dist = abs(up_magnet - s)
        dn_dist = abs(s - down_magnet)
        primary = up_magnet if up_dist <= dn_dist else down_magnet
    else:
        primary = up_magnet if up_magnet > 0 else down_magnet

    if primary == up_magnet and primary > 0:
        direction = "Up Magnet"
    elif primary == down_magnet and primary > 0:
        direction = "Down Magnet"
    else:
        direction = "N/A"

    return {
        "up_magnet": float(up_magnet),
        "down_magnet": float(down_magnet),
        "primary_magnet": float(primary),
        "direction": direction,
    }
