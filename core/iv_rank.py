# -*- coding: utf-8 -*-
"""
IV Rank & IV Percentile — Métricas clave para opciones.

IV Rank   = (IV_actual - IV_min_52w) / (IV_max_52w - IV_min_52w) × 100
IV Percentile = % de días en el último año donde IV fue MENOR que IV actual.

Ambas van de 0 a 100.
- IV Rank > 50  → IV está en la mitad superior de su rango histórico.
- IV Percentile > 80 → IV actual supera al 80% de los días del año.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from core.scanner import crear_sesion_nueva

logger = logging.getLogger(__name__)


def _calcular_iv_historica(df_hist: pd.DataFrame, window: int = 20) -> pd.Series:
    """Calcula la volatilidad histórica (HV) anualizada rolling.

    Usa log-returns y una ventana de `window` días hábiles.
    Se usa como proxy de IV histórica cuando no hay datos de IV directa.
    """
    if df_hist.empty or "Close" not in df_hist.columns:
        return pd.Series(dtype=float)
    log_ret = np.log(df_hist["Close"] / df_hist["Close"].shift(1))
    hv = log_ret.rolling(window).std() * np.sqrt(252) * 100  # anualizada %
    return hv


def calcular_iv_rank_percentile(
    symbol: str,
    iv_actual: Optional[float] = None,
    periodo: str = "1y",
) -> dict:
    """Calcula IV Rank e IV Percentile para un símbolo.

    Si `iv_actual` no se provee, usa la volatilidad del último día como proxy.

    Args:
        symbol: Ticker del activo (e.g. "SPY").
        iv_actual: IV actual en porcentaje (e.g. 24.5 para 24.5%).
                   Si es None, se estima desde la cadena de opciones o HV.
        periodo: Periodo histórico para calcular rango ("1y", "2y", etc).

    Returns:
        dict con claves: iv_actual, iv_rank, iv_percentile, iv_high_52w,
        iv_low_52w, hv_20d, fuente ("chain" o "hv_proxy")
    """
    result = {
        "iv_actual": 0.0,
        "iv_rank": 0.0,
        "iv_percentile": 0.0,
        "iv_high_52w": 0.0,
        "iv_low_52w": 0.0,
        "hv_20d": 0.0,
        "fuente": "hv_proxy",
    }

    try:
        session, _ = crear_sesion_nueva()
        ticker = yf.Ticker(symbol, session=session)

        # Descargar histórico
        hist = ticker.history(period=periodo)
        if hist.empty or len(hist) < 30:
            logger.warning(f"{symbol}: Historial insuficiente ({len(hist)} días)")
            return result

        # Calcular HV rolling 20
        hv_series = _calcular_iv_historica(hist, window=20)
        hv_series = hv_series.dropna()
        if hv_series.empty:
            return result

        result["hv_20d"] = round(float(hv_series.iloc[-1]), 2)

        # Si no se pasó IV actual, intentar obtenerla de la cadena ATM
        if iv_actual is None:
            try:
                expirations = ticker.options
                if expirations:
                    # Tomar la primera expiración
                    chain = ticker.option_chain(expirations[0])
                    spot = hist["Close"].iloc[-1]
                    # Buscar call ATM
                    calls = chain.calls
                    if not calls.empty and "impliedVolatility" in calls.columns:
                        calls = calls.copy()
                        calls["dist"] = abs(calls["strike"] - spot)
                        atm = calls.nsmallest(1, "dist")
                        if not atm.empty:
                            iv_actual = float(atm["impliedVolatility"].iloc[0]) * 100
                            result["fuente"] = "chain"
            except Exception as e:
                logger.debug(f"{symbol}: No se pudo obtener IV de cadena: {e}")

        # Si aún no hay IV, usar HV actual como proxy
        if iv_actual is None or iv_actual <= 0:
            iv_actual = result["hv_20d"]
            result["fuente"] = "hv_proxy"

        result["iv_actual"] = round(iv_actual, 2)

        # Max/Min de la serie HV (proxy para rango de IV)
        iv_max = float(hv_series.max())
        iv_min = float(hv_series.min())
        result["iv_high_52w"] = round(iv_max, 2)
        result["iv_low_52w"] = round(iv_min, 2)

        # IV Rank
        rango = iv_max - iv_min
        if rango > 0:
            result["iv_rank"] = round(
                ((iv_actual - iv_min) / rango) * 100, 1
            )
        else:
            result["iv_rank"] = 50.0

        # IV Percentile — % de días donde HV fue menor que IV actual
        below = (hv_series < iv_actual).sum()
        result["iv_percentile"] = round((below / len(hv_series)) * 100, 1)

        # Clamp to [0, 100]
        result["iv_rank"] = max(0, min(100, result["iv_rank"]))
        result["iv_percentile"] = max(0, min(100, result["iv_percentile"]))

        logger.info(
            f"{symbol}: IV={iv_actual:.1f}%, IV Rank={result['iv_rank']:.1f}, "
            f"IV Pctile={result['iv_percentile']:.1f}, Fuente={result['fuente']}"
        )
    except Exception as e:
        logger.error(f"{symbol}: Error calculando IV Rank: {e}")

    return result


def iv_rank_label(iv_rank: float) -> tuple:
    """Retorna (etiqueta, color) según el IV Rank.

    Returns:
        (label, hex_color) — e.g. ("ALTO", "#ef4444")
    """
    if iv_rank >= 70:
        return ("ALTO", "#ef4444")
    elif iv_rank >= 40:
        return ("MEDIO", "#f59e0b")
    else:
        return ("BAJO", "#10b981")


# ============================================================================
#        DATOS HISTÓRICOS DE IV  (para predicción de volatilidad)
# ============================================================================

def get_historical_iv(
    symbol: str,
    period: str = "1y",
    hv_window: int = 20,
) -> pd.DataFrame:
    """Obtiene un DataFrame con métricas históricas de volatilidad para un ticker.

    Combina datos de precios del subyacente con VIX como proxy del miedo
    de mercado. La HV rolling se usa como proxy de IV histórica (yfinance
    no provee series históricas de IV; sólo IV puntual de la cadena actual).

    Columnas del DataFrame retornado:
      - date       : fecha (datetime)
      - close_price: precio de cierre del subyacente
      - volume     : volumen del subyacente
      - hv_20d     : volatilidad histórica anualizada rolling 20d (%)
      - vix_close  : cierre del VIX (proxy de IV de mercado)
      - iv_mean    : proxy de IV (promedio ponderado: 60% HV + 40% VIX normalizado)

    Args:
        symbol: Ticker (e.g. "AAPL", "SPY").
        period: Periodo histórico ("6mo", "1y", "2y").
        hv_window: Ventana rolling para HV (default 20 días hábiles).

    Returns:
        pd.DataFrame con las columnas descritas, o DataFrame vacío si falla.
    """
    try:
        session, _ = crear_sesion_nueva()
        ticker = yf.Ticker(symbol, session=session)

        # Histórico del subyacente
        hist = ticker.history(period=period)
        if hist.empty or len(hist) < hv_window + 5:
            logger.warning(f"{symbol}: historial insuficiente para IV histórica")
            return pd.DataFrame()

        # HV rolling anualizada
        log_ret = np.log(hist["Close"] / hist["Close"].shift(1))
        hv_series = log_ret.rolling(hv_window).std() * np.sqrt(252) * 100

        # VIX como proxy de IV de mercado
        try:
            vix = yf.Ticker("^VIX", session=session)
            vix_hist = vix.history(period=period)
            vix_close = vix_hist["Close"].reindex(hist.index, method="ffill")
        except Exception:
            logger.debug(f"{symbol}: No se pudo obtener VIX, usando HV como fallback")
            vix_close = hv_series  # fallback: usar HV como proxy de VIX

        # Construir DataFrame
        df = pd.DataFrame({
            "date": hist.index,
            "close_price": hist["Close"].values,
            "volume": hist["Volume"].values,
            "hv_20d": hv_series.values,
            "vix_close": vix_close.values,
        })

        # iv_mean: proxy ponderado (60% HV + 40% VIX-normalizado)
        # El VIX ya está en % anualizado; HV también → promedio ponderado directo
        df["iv_mean"] = df["hv_20d"] * 0.6 + df["vix_close"] * 0.4

        # Limpiar NaN de las primeras filas (rolling window)
        df = df.dropna(subset=["hv_20d", "iv_mean"]).reset_index(drop=True)

        logger.info(f"{symbol}: {len(df)} días de IV histórica obtenidos")
        return df

    except Exception as e:
        logger.error(f"{symbol}: Error obteniendo IV histórica: {e}")
        return pd.DataFrame()
