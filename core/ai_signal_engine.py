# -*- coding: utf-8 -*-
"""AI Signal Engine — institutional signal aggregation.

ES:
    Orquesta señales de flujo, GEX, posicionamiento dealer y edge/Monte Carlo
    para producir una conclusion operativa unica.

EN:
    Aggregates flow, GEX, dealer positioning and edge/Monte Carlo dimensions
    into a single actionable signal score and critical alerts.
"""
from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safe float conversion."""
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp helper."""
    return max(low, min(high, value))


def _normalize_gex_score(gex_total: float) -> float:
    """Maps aggregated GEX to a directional score [0,100].

    Positive GEX -> more stabilizing regime (higher score for premium selling).
    Negative GEX -> unstable/short-gamma regime (lower score unless other
    components dominate).
    """
    g = _safe_float(gex_total)
    # Smooth saturation around +/- 1B notional gamma exposure.
    scaled = _clamp(g / 1_000_000_000.0, -1.0, 1.0)
    return 50.0 + scaled * 50.0


def generate_master_signal(
    oka_sentiment: dict[str, Any],
    gex_data: dict[str, Any],
    dealer_positioning: dict[str, Any],
    mc_results: dict[str, Any],
) -> dict[str, Any]:
    """Generate Master Signal by weighting 4 institutional dimensions.

    Weights / Pesos:
      - 40% Institutional Flow (OKA sentiment)
      - 30% GEX regime
      - 20% Monte Carlo / Edge quality
      - 10% Liquidity quality

    Critical alerts:
      a) Flow Z-score > 3
      b) Gamma Flip (spot crosses zero gamma with meaningful move)
      c) IV Spike (IV >= 1.3 * HV20)
    """
    flow_score = _clamp(_safe_float(oka_sentiment.get("score", 50.0), 50.0), 0.0, 100.0)

    gex_score = _safe_float(gex_data.get("gex_score", -1.0), -1.0)
    if gex_score < 0:
        gex_score = _normalize_gex_score(_safe_float(gex_data.get("gex_total", 0.0), 0.0))
    gex_score = _clamp(gex_score, 0.0, 100.0)

    edge_score = _safe_float(mc_results.get("edge_score", 50.0), 50.0)
    edge_score = _clamp(edge_score, 0.0, 100.0)

    liquidity_score = _safe_float(mc_results.get("liquidity_score", dealer_positioning.get("liquidity_score", 60.0)), 60.0)
    liquidity_score = _clamp(liquidity_score, 0.0, 100.0)

    signal_score = (
        0.40 * flow_score
        + 0.30 * gex_score
        + 0.20 * edge_score
        + 0.10 * liquidity_score
    )
    signal_score = _clamp(signal_score, 0.0, 100.0)

    flow_zscore = _safe_float(oka_sentiment.get("flow_zscore", 0.0), 0.0)
    flow_z_alert = abs(flow_zscore) > 3.0

    spot_now = _safe_float(gex_data.get("spot", 0.0), 0.0)
    spot_prev = _safe_float(gex_data.get("prev_spot", spot_now), spot_now)
    zero_gamma = _safe_float(gex_data.get("zero_gamma_level", 0.0), 0.0)
    gamma_flip_alert = False
    if zero_gamma > 0 and spot_now > 0 and spot_prev > 0:
        crossed = (spot_prev - zero_gamma) * (spot_now - zero_gamma) < 0
        move_pct = abs((spot_now - spot_prev) / max(spot_prev, 1e-9))
        gamma_flip_alert = crossed and move_pct >= 0.005

    current_iv = _safe_float(oka_sentiment.get("current_iv", 0.0), 0.0)
    hv20 = _safe_float(oka_sentiment.get("hv_20d", 0.0), 0.0)
    iv_spike_alert = hv20 > 0 and current_iv >= hv20 * 1.30

    squeeze_alert = bool(dealer_positioning.get("squeeze_alert", False))

    alerts = {
        "flow_zscore_alert": flow_z_alert,
        "gamma_flip_alert": gamma_flip_alert,
        "iv_spike_alert": iv_spike_alert,
        "squeeze_alert": squeeze_alert,
    }

    if signal_score >= 72:
        regime = "Bullish Conviction"
    elif signal_score <= 35:
        regime = "Bearish Conviction"
    elif 45 <= signal_score <= 60:
        regime = "Range / Neutral"
    else:
        regime = "Tactical / Mixed"

    result = {
        "signal_score": float(round(signal_score, 2)),
        "regime": regime,
        "components": {
            "flow_score": float(round(flow_score, 2)),
            "gex_score": float(round(gex_score, 2)),
            "edge_score": float(round(edge_score, 2)),
            "liquidity_score": float(round(liquidity_score, 2)),
        },
        "alerts": alerts,
        "inputs": {
            "flow_zscore": float(round(flow_zscore, 3)),
            "spot": float(spot_now),
            "zero_gamma_level": float(zero_gamma),
            "current_iv": float(current_iv),
            "hv_20d": float(hv20),
        },
    }
    result["recommendation"] = translate_signals_to_text(result)
    return result


def translate_signals_to_text(signals_dict: dict[str, Any]) -> str:
    """Translate binary alerts + score into human strategy guidance.

    ES/EN recommendation paragraph for the desk.
    """
    score = _safe_float(signals_dict.get("signal_score", 50.0), 50.0)
    regime = str(signals_dict.get("regime", "Tactical / Mixed"))
    alerts = signals_dict.get("alerts", {}) or {}

    squeeze = bool(alerts.get("squeeze_alert", False))
    gamma_flip = bool(alerts.get("gamma_flip_alert", False))
    iv_spike = bool(alerts.get("iv_spike_alert", False))
    z_alert = bool(alerts.get("flow_zscore_alert", False))

    if squeeze and score >= 70:
        strategy = "Bull Put Spread"
        tone = "⚠️ CONVICCION ALCISTA FUERTE"
    elif score <= 35:
        strategy = "Bear Call Spread"
        tone = "⚠️ CONVICCION BAJISTA FUERTE"
    elif 45 <= score <= 60:
        strategy = "Iron Condor"
        tone = "📌 REGIMEN NEUTRAL"
    else:
        strategy = "Credit Spread selectivo"
        tone = "📊 REGIMEN MIXTO"

    drivers: list[str] = []
    if squeeze:
        drivers.append("Squeeze detectado")
    if z_alert:
        drivers.append("Flow Z-score > 3")
    if gamma_flip:
        drivers.append("Gamma Flip activo")
    if iv_spike:
        drivers.append("IV Spike vs HV20")

    if not drivers:
        drivers.append("sin alertas criticas activas")

    return (
        f"{tone}: Regimen {regime} (score {score:.1f}/100). "
        f"Drivers: {', '.join(drivers)}. "
        f"Priorizar estrategia {strategy} con gestion de riesgo estricta "
        f"y ajuste tactico segun liquidez/volatilidad intradia."
    )
