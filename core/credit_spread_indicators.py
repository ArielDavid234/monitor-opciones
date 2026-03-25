# -*- coding: utf-8 -*-
"""Credit Spread — ticker-level IV rank/percentile and trend indicators."""
from __future__ import annotations

import logging
import numpy as np

from core.scanner import _cached_history

logger = logging.getLogger(__name__)

def compute_iv_rank_percentile(ticker: str, current_atm_iv: float | None = None) -> dict:
    """Calcula IV Rank / Percentile usando el historial cacheado.

    Usa _cached_history(ticker, "1y") — reutiliza el caché TTL del scanner
    y evita un download adicional de yfinance por ticker.

    Args:
        current_atm_iv: IV implícita ATM real de la cadena de opciones (decimal).
            Si se proporciona, se usa como nivel actual de IV en lugar del HV20.
            Las plataformas oficiales usan la IV ATM, no la HV histórica.

    Returns keys: iv_current, iv_rank, iv_percentile, iv_1y_high, iv_1y_low
    """
    _default = {
        "iv_current": 0.0, "iv_rank": 0.0, "iv_percentile": 0.0,
        "iv_1y_high": 0.0, "iv_1y_low": 0.0,
    }
    try:
        hist = _cached_history(ticker, "1y")
        if hist is None or hist.empty or len(hist) < 30:
            _cached_history.cache_invalidate(ticker, "1y")
            return _default
        close = hist["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        log_ret = np.log(close / close.shift(1))
        hv = log_ret.rolling(20).std() * np.sqrt(252) * 100
        hv = hv.dropna()
        if hv.empty:
            return _default
        hv_current = round(float(hv.iloc[-1]), 2)   # HV20 anualizada (%)
        iv_max = round(float(hv.max()), 2)
        iv_min = round(float(hv.min()), 2)
        iv_range = iv_max - iv_min
        # Si se proporcionó IV ATM real de la cadena de opciones, úsarla como
        # nivel actual; de lo contrario caer al HV20 como proxy.
        if current_atm_iv is not None and current_atm_iv > 0.01:
            iv_current = round(current_atm_iv * 100, 2)  # decimal → %
        else:
            iv_current = hv_current
        iv_rank = round((iv_current - iv_min) / iv_range * 100, 1) if iv_range > 0 else 0.0
        iv_pct = round(float((hv < iv_current).mean() * 100), 1)
        return {
            "iv_current": iv_current,
            "hv_current": hv_current,   # HV20 siempre disponible (proxy histórico)
            "iv_rank": iv_rank,
            "iv_percentile": iv_pct,
            "iv_1y_high": iv_max,
            "iv_1y_low": iv_min,
        }
    except Exception as _e:
        logger.warning("compute_iv_rank_percentile(%s): %s", ticker, _e)
        return _default


# ────────────────────────────────────────────────────────────────────────────
#  Indicadores de tendencia: VWAP, EMA9, EMA21
# ────────────────────────────────────────────────────────────────────────────

def compute_trend(ticker: str) -> dict:
    """Calcula VWAP (del día), EMA9 y EMA21 para determinar tendencia.

    Returns
    -------
    dict con keys: vwap, ema9, ema21, trend, spot
        trend: "Alcista" | "Bajista" | "Neutral"
        preferred_type: "Bull Put" | "Bear Call" | None
    """
    default = {
        "vwap": 0.0,
        "ema9": 0.0,
        "ema21": 0.0,
        "trend": "Neutral",
        "preferred_type": None,
    }
    try:
        # Historial de 3 meses para EMAs robustas (~60 trading days)
        hist = _cached_history(ticker, "3mo")
        if hist is None or hist.empty or len(hist) < 10:
            _cached_history.cache_invalidate(ticker, "3mo")
            return default

        close = hist["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()

        # EMA 9 y 21
        ema9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])

        # VWAP aproximado (usando datos diarios del último mes)
        # Usamos típico = (H+L+C)/3 * Volume / cumSum(Volume)
        # Solo usar las últimas ~21 barras para VWAP (periodo mensual)
        hist_vwap = hist.tail(21)
        high = hist_vwap["High"]
        low = hist_vwap["Low"]
        vol = hist_vwap["Volume"]
        if hasattr(high, "squeeze"):
            high = high.squeeze()
            low = low.squeeze()
            vol = vol.squeeze()
        close_vwap = hist_vwap["Close"]
        if hasattr(close_vwap, "squeeze"):
            close_vwap = close_vwap.squeeze()

        typical = (high + low + close_vwap) / 3
        cum_vol = vol.cumsum()
        cum_tp_vol = (typical * vol).cumsum()
        vwap_series = cum_tp_vol / cum_vol.replace(0, np.nan)
        vwap = float(vwap_series.iloc[-1]) if not vwap_series.empty else 0.0

        spot = float(close.iloc[-1])

        # Determinar tendencia
        above_vwap = spot > vwap if vwap > 0 else False
        ema_bullish = ema9 > ema21

        if above_vwap and ema_bullish:
            trend = "Alcista"
            preferred = "Bull Put"
        elif not above_vwap and not ema_bullish:
            trend = "Bajista"
            preferred = "Bear Call"
        else:
            trend = "Neutral"
            preferred = None

        return {
            "vwap": round(vwap, 2),
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "trend": trend,
            "preferred_type": preferred,
        }
    except Exception as exc:
        logger.warning("Error calculando tendencia para %s: %s", ticker, exc)
        return default


# ────────────────────────────────────────────────────────────────────────────
#  Construcción de spreads para una fecha de expiración
