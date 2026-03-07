# -*- coding: utf-8 -*-
"""
Credit Spread Scanner — Escanea cadenas de opciones para encontrar
oportunidades de venta de prima (Bull Put Spreads y Bear Call Spreads).

Usa Black-Scholes (OptionGreeks) para deltas precisos y POP real.
Incluye IV Rank / IV Percentile, indicadores de tendencia (VWAP, EMA9/21)
y distancia al strike vendido.
Reutiliza las sesiones anti-ban y el caché TTL del scanner principal.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from datetime import datetime

from config.constants import (
    RISK_FREE_RATE,
    DAYS_PER_YEAR,
    INCOME_SCORE_IV_RANK_MIN,
    INCOME_SCORE_IV_PCTIL_MIN,
    INCOME_SCORE_DELTA_MAX,
    INCOME_SCORE_VOL_MIN,
    INCOME_SCORE_OI_MIN,
    INCOME_SCORE_DIST_PCT_MIN,
    INCOME_SCORE_LABEL_ALTA,
    INCOME_SCORE_LABEL_BUENA,
    # ── Filtro estricto pipeline ──
    CS_WHITELIST,
    CS_MIN_PRICE,
    CS_MIN_AVG_VOLUME,
    CS_MIN_CHAIN_OI,
    CS_MIN_IV_RANK,
    CS_DTE_MIN,
    CS_DTE_MAX,
    CS_DELTA_MIN,
    CS_DELTA_MAX,
    CS_ALLOWED_WIDTHS,
    CS_MIN_CREDIT_PCT,
    CS_MIN_DIST_PCT,
    CS_MIN_SOLD_OI,
    CS_MIN_SOLD_VOL,
    CS_MAX_BID_ASK_PCT,
    # ── Score de Oportunidad ──
    OPP_SCORE_IV_RANK_MIN,
    OPP_SCORE_DELTA_MIN,
    OPP_SCORE_DELTA_MAX,
    OPP_SCORE_CREDIT_WIDTH_PCT,
    OPP_SCORE_DIST_PCT_MIN,
    OPP_SCORE_VOL_MIN,
    OPP_SCORE_OI_MIN,
    OPP_SCORE_BA_CREDIT_PCT,
    OPP_SCORE_MIN_SHOW,
    # ── Sistema de Alertas ──
    ALERT_DEFAULT_ACCOUNT_SIZE,
    ALERT_MAX_RISK_PCT,
)
from core.option_greeks import OptionGreeks, quick_probability_of_touch
from core.backtester import (
    compute_ev_real_adjusted,
    _surface_edge,
    compute_optimized_score,
)
from core.scanner import (
    _cached_options_dates,
    _cached_option_chain,
    _cached_history,
    obtener_precio_actual,
    _safe_num,
)

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
#  Helpers internos
# ────────────────────────────────────────────────────────────────────────────

def _dte_from_expiry(exp_str: str) -> int:
    """Calcula días hasta el vencimiento desde una fecha YYYY-MM-DD."""
    try:
        exp = datetime.strptime(exp_str, "%Y-%m-%d")
        return max((exp - datetime.now()).days, 0)
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
    """Filtro 1 — verifica precio, volumen promedio y OI de cadena.

    Returns (passed, reason).
    """
    if spot < CS_MIN_PRICE:
        return False, f"Precio ${spot:.2f} < ${CS_MIN_PRICE}"
    avg_vol = _avg_daily_volume(ticker)
    if avg_vol < CS_MIN_AVG_VOLUME:
        return False, f"Vol prom {avg_vol:,.0f} < {CS_MIN_AVG_VOLUME:,}"
    avg_oi = _avg_chain_oi(ticker)
    if avg_oi < CS_MIN_CHAIN_OI:
        return False, f"OI cadena prom {avg_oi:.0f} < {CS_MIN_CHAIN_OI}"
    return True, ""


def _passes_bid_ask_filter(bid: float, ask: float) -> bool:
    """Filtro 9c — Bid-Ask Spread ≤ 10% del mid price."""
    if ask <= 0 or bid < 0:
        return False
    mid = (bid + ask) / 2
    if mid <= 0:
        return False
    return (ask - bid) / mid <= CS_MAX_BID_ASK_PCT


# ────────────────────────────────────────────────────────────────────────────
#  Income Score — puntuación única de cada spread (0–100)
# ────────────────────────────────────────────────────────────────────────────

def compute_income_score(row: dict) -> tuple[float, str]:
    """Calcula el Income Score (0–100) para un spread individual.

    Componentes (20 pts cada uno, total máximo 100):
      1. IV alto: IV Rank > 40 ó IV Percentile > 60
      2. Delta bajo: |delta vendido| ≤ 0.20
      3. Liquidez: volumen > 100 y OI > 200
      4. Tendencia alineada: Bull Put + Alcista ó Bear Call + Bajista
      5. Distancia del strike: dist_pct > 5.0 %

    Umbrales configurables en config/constants.py.

    Returns
    -------
    tuple[float, str]
        (score redondeado a 1 decimal, etiqueta en español)
    """
    score = 0.0

    # 1. IV alto
    iv_rank = row.get("IV Rank", 0) or 0
    iv_pctil = row.get("IV Pctil", 0) or 0
    if iv_rank > INCOME_SCORE_IV_RANK_MIN or iv_pctil > INCOME_SCORE_IV_PCTIL_MIN:
        score += 20

    # 2. Delta bajo
    delta = abs(row.get("Delta Vendido", 1.0) or 1.0)
    if delta <= INCOME_SCORE_DELTA_MAX:
        score += 20

    # 3. Liquidez
    vol = row.get("Volumen", 0) or 0
    oi = row.get("OI", 0) or 0
    if vol > INCOME_SCORE_VOL_MIN and oi > INCOME_SCORE_OI_MIN:
        score += 20

    # 4. Tendencia alineada con tipo de spread
    tipo = row.get("Tipo", "")
    tendencia = row.get("Tendencia", "Neutral")
    if (tipo == "Bull Put" and tendencia == "Alcista") or \
       (tipo == "Bear Call" and tendencia == "Bajista"):
        score += 20

    # 5. Distancia del strike
    dist_pct = row.get("Dist Strike %", 0) or 0
    if dist_pct > INCOME_SCORE_DIST_PCT_MIN:
        score += 20

    score = round(min(max(score, 0), 100), 1)

    # Etiqueta
    if score >= INCOME_SCORE_LABEL_ALTA:
        label = "Alta probabilidad"
    elif score >= INCOME_SCORE_LABEL_BUENA:
        label = "Buena"
    else:
        label = "Evitar"

    return score, label


# ────────────────────────────────────────────────────────────────────────────
#  Score de Oportunidad (0–100) — scoring propio de cada spread
# ────────────────────────────────────────────────────────────────────────────

def compute_opportunity_score(row: dict) -> tuple[float, str]:
    """Score de Oportunidad (0–100) para un spread individual.

    Componentes (20 pts cada uno):
      1. IV Rank > 40
      2. Delta en sweet spot (0.12–0.18)
      3. Crédito ≥ 20 % del ancho del spread
      4. Distancia al strike > 4 %
      5. Liquidez alta (vol > 100, OI > 500, B-A ≤ 10 % del crédito)

    Returns: (score, label)
    """
    score = 0.0

    # 1. IV Rank alto
    iv_rank = row.get("IV Rank", 0) or 0
    if iv_rank > OPP_SCORE_IV_RANK_MIN:
        score += 20

    # 2. Delta sweet spot
    delta = abs(row.get("Delta Vendido", 0) or 0)
    if OPP_SCORE_DELTA_MIN <= delta <= OPP_SCORE_DELTA_MAX:
        score += 20

    # 3. Crédito vs ancho
    width = abs(
        (row.get("Strike Vendido", 0) or 0) - (row.get("Strike Comprado", 0) or 0)
    )
    credit = row.get("Crédito", 0) or 0
    if width > 0 and credit >= OPP_SCORE_CREDIT_WIDTH_PCT * width:
        score += 20

    # 4. Distancia del strike
    dist_pct = row.get("Dist Strike %", 0) or 0
    if dist_pct > OPP_SCORE_DIST_PCT_MIN:
        score += 20

    # 5. Liquidez alta
    vol = row.get("Volumen", 0) or 0
    oi = row.get("OI", 0) or 0
    ba = row.get("Bid-Ask", 0) or 0
    ba_ratio = ba / max(credit, 0.01)
    if vol > OPP_SCORE_VOL_MIN and oi > OPP_SCORE_OI_MIN and ba_ratio <= OPP_SCORE_BA_CREDIT_PCT:
        score += 20

    score = round(min(max(score, 0), 100), 1)

    if score >= 80:
        label = "Excelente"
    elif score >= OPP_SCORE_MIN_SHOW:
        label = "Buena"
    else:
        label = "Baja"

    return score, label


def opportunity_score_breakdown(row: dict) -> list[dict]:
    """Desglose detallado del Score de Oportunidad para una fila.

    Devuelve una lista de dicts con criterio, detalle, puntos, máximo, cumple.
    Útil para mostrar al usuario qué criterios cumplió cada spread.
    """
    breakdown: list[dict] = []

    # 1. IV Rank
    ivr = row.get("IV Rank", 0) or 0
    p = ivr > OPP_SCORE_IV_RANK_MIN
    breakdown.append({
        "criterio": "IV Rank > 40",
        "detalle": f"IV Rank actual: {ivr:.0f}%",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 2. Delta sweet spot
    delta = abs(row.get("Delta Vendido", 0) or 0)
    p = OPP_SCORE_DELTA_MIN <= delta <= OPP_SCORE_DELTA_MAX
    breakdown.append({
        "criterio": "Delta 0.12 – 0.18 (sweet spot)",
        "detalle": f"|Δ| = {delta:.3f}",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 3. Crédito vs ancho
    width = abs(
        (row.get("Strike Vendido", 0) or 0) - (row.get("Strike Comprado", 0) or 0)
    )
    credit = row.get("Crédito", 0) or 0
    ratio = credit / width * 100 if width > 0 else 0
    p = width > 0 and credit >= OPP_SCORE_CREDIT_WIDTH_PCT * width
    breakdown.append({
        "criterio": f"Crédito ≥ {OPP_SCORE_CREDIT_WIDTH_PCT*100:.0f}% del ancho",
        "detalle": f"${credit:.2f} / ${width:.0f} = {ratio:.0f}%",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 4. Distancia
    dist = row.get("Dist Strike %", 0) or 0
    p = dist > OPP_SCORE_DIST_PCT_MIN
    breakdown.append({
        "criterio": "Distancia > 4%",
        "detalle": f"Distancia: {dist:.1f}%",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 5. Liquidez
    vol = row.get("Volumen", 0) or 0
    oi = row.get("OI", 0) or 0
    ba = row.get("Bid-Ask", 0) or 0
    ba_pct = ba / max(credit, 0.01) * 100
    cv = vol > OPP_SCORE_VOL_MIN
    co = oi > OPP_SCORE_OI_MIN
    cb = (ba_pct / 100) <= OPP_SCORE_BA_CREDIT_PCT
    p = cv and co and cb
    breakdown.append({
        "criterio": "Liquidez (Vol>100, OI>500, B-A≤10%)",
        "detalle": f"Vol:{vol:,} · OI:{oi:,} · B-A:{ba_pct:.0f}% crédito",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    return breakdown


# ────────────────────────────────────────────────────────────────────────────
#  IV Rank & IV Percentile  — delegado a core.iv_rank (fuente canónica)
# ────────────────────────────────────────────────────────────────────────────

def compute_iv_rank_percentile(ticker: str) -> dict:
    """Thin adapter around ``core.iv_rank.calcular_iv_rank_percentile``.

    Returns keys expected by the rest of this module:
        iv_current, iv_rank, iv_percentile, iv_1y_high, iv_1y_low
    """
    from core.iv_rank import calcular_iv_rank_percentile  # canonical impl

    raw = calcular_iv_rank_percentile(ticker)
    return {
        "iv_current":    raw.get("hv_20d", 0.0),
        "iv_rank":       raw.get("iv_rank", 0.0),
        "iv_percentile": raw.get("iv_percentile", 0.0),
        "iv_1y_high":    raw.get("iv_high_52w", 0.0),
        "iv_1y_low":     raw.get("iv_low_52w", 0.0),
    }


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
# ────────────────────────────────────────────────────────────────────────────

def _build_spreads_for_expiry(
    ticker: str,
    spot: float,
    exp_date: str,
    min_pop: float,
    min_credit: float,
    ticker_meta: dict | None = None,
    allowed_type: str | None = None,
    strict: bool = False,
) -> list[dict]:
    """Genera Bull Put Spreads y Bear Call Spreads para una expiración.

    Parameters
    ----------
    allowed_type : str | None
        Si se pasa "Bull Put" o "Bear Call", solo genera ese tipo (filtro 5).
    strict : bool
        Si True, aplica los 9 filtros obligatorios del pipeline.
    """
    dte = _dte_from_expiry(exp_date)
    if dte <= 0:
        return []

    # Filtro 3 — DTE estricto (solo en modo strict)
    if strict and (dte < CS_DTE_MIN or dte > CS_DTE_MAX):
        return []

    try:
        chain = _cached_option_chain(ticker, exp_date)
    except Exception as exc:
        logger.warning("Error obteniendo cadena %s %s: %s", ticker, exp_date, exc)
        return []

    puts: pd.DataFrame = chain.get("puts", pd.DataFrame())
    calls: pd.DataFrame = chain.get("calls", pd.DataFrame())

    results: list[dict] = []

    # ── Bull Put Spreads ─────────────────────────────────────────────────
    if (allowed_type is None or allowed_type == "Bull Put") and not puts.empty and len(puts) >= 2:
        otm_puts = puts[
            (puts["strike"] < spot) &
            (puts["bid"].fillna(0) > 0)
        ].sort_values("strike", ascending=False).reset_index(drop=True)

        for i in range(len(otm_puts)):
            sold = otm_puts.iloc[i]
            sold_strike = float(sold["strike"])
            sold_bid = float(_safe_num(sold.get("bid", 0)))
            sold_ask = float(_safe_num(sold.get("ask", 0)))
            sold_iv = float(_safe_num(sold.get("impliedVolatility", 0), 0))
            sold_vol = int(_safe_num(sold.get("volume", 0)))
            sold_oi = int(_safe_num(sold.get("openInterest", 0)))

            # Delta preciso vía BSM
            sold_delta = _bsm_delta(spot, sold_strike, dte, sold_iv, "put")

            # Filtro 4 — Delta del short strike (strict)
            if strict:
                abs_d = abs(sold_delta)
                if abs_d < CS_DELTA_MIN or abs_d > CS_DELTA_MAX:
                    continue

            pop = _pop_from_delta(sold_delta)
            if pop < min_pop:
                continue

            # Filtro 8 — Distancia del strike (strict)
            dist_pct = _strike_distance_pct(spot, sold_strike)
            if strict and dist_pct < CS_MIN_DIST_PCT:
                continue

            # Filtro 9a/9b — Liquidez del contrato vendido (strict)
            if strict and (sold_oi < CS_MIN_SOLD_OI or sold_vol < CS_MIN_SOLD_VOL):
                continue

            # Filtro 9c — Bid-Ask (strict)
            if strict and not _passes_bid_ask_filter(sold_bid, sold_ask):
                continue

            # Build a strike→row lookup for fast width matching
            _put_strikes = {float(r["strike"]): r for _, r in otm_puts.iterrows()}

            # In strict mode, only try allowed widths; otherwise try next 5 strikes
            if strict:
                _target_widths = CS_ALLOWED_WIDTHS
            else:
                _target_widths = None  # fallback: iterate consecutive

            _bought_candidates: list[tuple[float, pd.Series]] = []
            if _target_widths:
                for w in _target_widths:
                    target_k = round(sold_strike - w, 2)
                    if target_k in _put_strikes:
                        _bought_candidates.append((target_k, _put_strikes[target_k]))
            else:
                for j in range(i + 1, min(i + 8, len(otm_puts))):
                    _b = otm_puts.iloc[j]
                    _bought_candidates.append((float(_b["strike"]), _b))

            for bought_strike, bought in _bought_candidates:
                bought_ask = float(_safe_num(bought.get("ask", 0)))

                if bought_ask <= 0:
                    continue

                credit = round(sold_bid - bought_ask, 2)
                if credit < min_credit:
                    continue

                width = round(sold_strike - bought_strike, 2)
                if width <= 0:
                    continue

                # Filtro 6 — Ancho del spread (strict)
                if strict:
                    width_int = int(round(width))
                    if width_int not in CS_ALLOWED_WIDTHS:
                        continue

                # Filtro 7 — Crédito mínimo % del ancho (strict)
                if strict and credit < width * CS_MIN_CREDIT_PCT:
                    continue

                max_risk = round(width - credit, 2)
                if max_risk <= 0:
                    continue

                retorno_pct = round((credit / max_risk) * 100, 2)
                bought_vol = int(_safe_num(bought.get("volume", 0)))
                bought_oi = int(_safe_num(bought.get("openInterest", 0)))

                # ── Métricas Fase 1: PoT, Delta Comprado, Delta Neto ─────
                bought_iv = float(_safe_num(bought.get("impliedVolatility", sold_iv)) or sold_iv)
                bought_delta = _bsm_delta(spot, bought_strike, dte, bought_iv, "put")

                # PoT BSM exacto (barrera) vs aproximación 2×|Δ|
                pot_short = calculate_probability_of_touch(
                    spot, sold_strike, dte, sold_iv, "put",
                )
                pot_approx = _pot_approx_2delta(sold_delta)

                # Delta Neto: para Bull Put (short higher put, long lower put),
                # ambos deltas son negativos.  El spread neto es bullish (positivo).
                # Δ_spread = Δ_short + Δ_long (short = vendido, invertimos signo)
                #          = -Δ_short_put + Δ_long_put
                delta_neto = round(-sold_delta + bought_delta, 4)

                # POP basado en breakeven real del spread
                breakeven = round(sold_strike - credit, 2)
                pop_be = _pop_from_breakeven(spot, breakeven, dte, sold_iv, "put")
                pop = _pop_from_delta(sold_delta)  # mantener como referencia

                # ── Métricas Fase 2: Gamma, Theta, Liquidez ───────────────
                _g_sold = _bsm_greeks(spot, sold_strike, dte, sold_iv, "put")
                _g_bought = _bsm_greeks(spot, bought_strike, dte, bought_iv, "put")
                # Vendemos el short, compramos el long → gamma neto = -gamma_sold + gamma_bought
                gamma_neto = round(_g_bought["gamma"] - _g_sold["gamma"], 6)
                # Theta neto: short nos beneficia (+), long nos cuesta (-)
                theta_neto = round(-_g_sold["theta"] + _g_bought["theta"], 6)
                decay_7d = round(theta_neto * 7.0, 2)
                # Liquidity Score del short leg (0-100)
                _ba_mid = (sold_bid + sold_ask) / 2 if sold_ask > 0 else 0.01
                _ba_tight = (sold_ask - sold_bid) / _ba_mid if _ba_mid > 0 else 1.0
                liq_score = (
                    (40 if sold_oi > 1000 else sold_oi / 1000 * 40)
                    + (30 if sold_vol > 200 else sold_vol / 200 * 30)
                    + (30 if _ba_tight < 0.10 else max(0, 30 * (1 - _ba_tight)))
                )
                liq_score = round(min(100, max(0, liq_score)), 1)

                # ── Fase 3: EV Real Adjusted + Surface Edge ───────────────
                ev_real_adj = compute_ev_real_adjusted(
                    spot, sold_strike, dte, sold_iv, credit, max_risk, "put",
                )
                surface_edge = _surface_edge(
                    spot, sold_strike, dte, sold_iv, round(pop * 100, 1), "put",
                )

                row = {
                    "Ticker": ticker,
                    "Tipo": "Bull Put",
                    "Spot": round(spot, 2),
                    "Strike Vendido": sold_strike,
                    "Strike Comprado": bought_strike,
                    "DTE": dte,
                    "Expiración": exp_date,
                    "Delta Vendido": round(sold_delta, 4),
                    "Delta Comprado": round(bought_delta, 4),
                    "Delta Neto": delta_neto,
                    "PoT Short": pot_short,
                    "PoT 2Δ Approx": pot_approx,
                    "Gamma Neto": gamma_neto,
                    "Theta Neto": theta_neto,
                    "Decay 7d": decay_7d,
                    "POP %": round(pop * 100, 1),
                    "POP Breakeven %": round(pop_be * 100, 1),
                    "Prob OTM %": round(pop * 100, 1),
                    "Crédito": credit,
                    "Riesgo Máx": max_risk,
                    "Retorno %": retorno_pct,
                    "IV Short %": round(sold_iv * 100, 1),
                    "IV Long %": round(bought_iv * 100, 1),
                    "IV %": round(sold_iv * 100, 1),
                    "Breakeven": breakeven,
                    "Dist Strike %": dist_pct,
                    "Vol Short": sold_vol,
                    "OI Short": sold_oi,
                    "Liq Score": liq_score,
                    "EV Real Adj": ev_real_adj,
                    "Surface Edge": surface_edge,
                    "Volumen": sold_vol + bought_vol,
                    "OI": sold_oi + bought_oi,
                    "Bid-Ask": _bid_ask_spread(sold_bid, sold_ask),
                    "Liquidez": sold_vol + sold_oi + bought_vol + bought_oi,
                }
                if ticker_meta:
                    row.update(ticker_meta)
                results.append(row)

    # ── Bear Call Spreads ────────────────────────────────────────────────
    if (allowed_type is None or allowed_type == "Bear Call") and not calls.empty and len(calls) >= 2:
        otm_calls = calls[
            (calls["strike"] > spot) &
            (calls["bid"].fillna(0) > 0)
        ].sort_values("strike", ascending=True).reset_index(drop=True)

        for i in range(len(otm_calls)):
            sold = otm_calls.iloc[i]
            sold_strike = float(sold["strike"])
            sold_bid = float(_safe_num(sold.get("bid", 0)))
            sold_ask = float(_safe_num(sold.get("ask", 0)))
            sold_iv = float(_safe_num(sold.get("impliedVolatility", 0), 0))
            sold_vol = int(_safe_num(sold.get("volume", 0)))
            sold_oi = int(_safe_num(sold.get("openInterest", 0)))

            # Delta preciso vía BSM
            sold_delta = _bsm_delta(spot, sold_strike, dte, sold_iv, "call")

            # Filtro 4 — Delta del short strike (strict)
            if strict:
                abs_d = abs(sold_delta)
                if abs_d < CS_DELTA_MIN or abs_d > CS_DELTA_MAX:
                    continue

            pop = _pop_from_delta(sold_delta)
            if pop < min_pop:
                continue

            # Filtro 8 — Distancia del strike (strict)
            dist_pct = _strike_distance_pct(spot, sold_strike)
            if strict and dist_pct < CS_MIN_DIST_PCT:
                continue

            # Filtro 9a/9b — Liquidez del contrato vendido (strict)
            if strict and (sold_oi < CS_MIN_SOLD_OI or sold_vol < CS_MIN_SOLD_VOL):
                continue

            # Filtro 9c — Bid-Ask (strict)
            if strict and not _passes_bid_ask_filter(sold_bid, sold_ask):
                continue

            # Build a strike→row lookup for fast width matching
            _call_strikes = {float(r["strike"]): r for _, r in otm_calls.iterrows()}

            if strict:
                _target_widths_c = CS_ALLOWED_WIDTHS
            else:
                _target_widths_c = None

            _bought_candidates_c: list[tuple[float, pd.Series]] = []
            if _target_widths_c:
                for w in _target_widths_c:
                    target_k = round(sold_strike + w, 2)
                    if target_k in _call_strikes:
                        _bought_candidates_c.append((target_k, _call_strikes[target_k]))
            else:
                for j in range(i + 1, min(i + 8, len(otm_calls))):
                    _b = otm_calls.iloc[j]
                    _bought_candidates_c.append((float(_b["strike"]), _b))

            for bought_strike, bought in _bought_candidates_c:
                bought_ask = float(_safe_num(bought.get("ask", 0)))

                if bought_ask <= 0:
                    continue

                credit = round(sold_bid - bought_ask, 2)
                if credit < min_credit:
                    continue

                width = round(bought_strike - sold_strike, 2)
                if width <= 0:
                    continue

                # Filtro 6 — Ancho del spread (strict)
                if strict:
                    width_int = int(round(width))
                    if width_int not in CS_ALLOWED_WIDTHS:
                        continue

                # Filtro 7 — Crédito mínimo % del ancho (strict)
                if strict and credit < width * CS_MIN_CREDIT_PCT:
                    continue

                max_risk = round(width - credit, 2)
                if max_risk <= 0:
                    continue

                retorno_pct = round((credit / max_risk) * 100, 2)
                bought_vol = int(_safe_num(bought.get("volume", 0)))
                bought_oi = int(_safe_num(bought.get("openInterest", 0)))

                # ── Métricas Fase 1: PoT, Delta Comprado, Delta Neto ─────
                bought_ivbc = float(_safe_num(bought.get("impliedVolatility", sold_iv)) or sold_iv)
                bought_delta_bc = _bsm_delta(spot, bought_strike, dte, bought_ivbc, "call")

                # PoT BSM exacto (barrera) vs aproximación 2×|Δ|
                pot_short_bc = calculate_probability_of_touch(
                    spot, sold_strike, dte, sold_iv, "call",
                )
                pot_approx_bc = _pot_approx_2delta(sold_delta)

                # Delta Neto: para Bear Call (short lower call, long higher call),
                # ambos deltas son positivos.  El spread neto es bearish (negativo).
                # Δ_spread = -Δ_short_call + Δ_long_call
                delta_neto_bc = round(-sold_delta + bought_delta_bc, 4)

                # POP basado en breakeven real del spread
                breakeven_bc = round(sold_strike + credit, 2)
                pop_be_bc = _pop_from_breakeven(spot, breakeven_bc, dte, sold_iv, "call")
                pop_bc = _pop_from_delta(sold_delta)  # referencia

                # ── Métricas Fase 2: Gamma, Theta, Liquidez ───────────────
                _gc_sold = _bsm_greeks(spot, sold_strike, dte, sold_iv, "call")
                _gc_bought = _bsm_greeks(spot, bought_strike, dte, bought_ivbc, "call")
                gamma_neto_bc = round(_gc_bought["gamma"] - _gc_sold["gamma"], 6)
                theta_neto_bc = round(-_gc_sold["theta"] + _gc_bought["theta"], 6)
                decay_7d_bc = round(theta_neto_bc * 7.0, 2)
                _ba_mid_c = (sold_bid + sold_ask) / 2 if sold_ask > 0 else 0.01
                _ba_tight_c = (sold_ask - sold_bid) / _ba_mid_c if _ba_mid_c > 0 else 1.0
                liq_score_bc = (
                    (40 if sold_oi > 1000 else sold_oi / 1000 * 40)
                    + (30 if sold_vol > 200 else sold_vol / 200 * 30)
                    + (30 if _ba_tight_c < 0.10 else max(0, 30 * (1 - _ba_tight_c)))
                )
                liq_score_bc = round(min(100, max(0, liq_score_bc)), 1)

                # ── Fase 3: EV Real Adjusted + Surface Edge ───────────────
                ev_real_adj_bc = compute_ev_real_adjusted(
                    spot, sold_strike, dte, sold_iv, credit, max_risk, "call",
                )
                surface_edge_bc = _surface_edge(
                    spot, sold_strike, dte, sold_iv, round(pop_bc * 100, 1), "call",
                )

                row = {
                    "Ticker": ticker,
                    "Tipo": "Bear Call",
                    "Spot": round(spot, 2),
                    "Strike Vendido": sold_strike,
                    "Strike Comprado": bought_strike,
                    "DTE": dte,
                    "Expiración": exp_date,
                    "Delta Vendido": round(sold_delta, 4),
                    "Delta Comprado": round(bought_delta_bc, 4),
                    "Delta Neto": delta_neto_bc,
                    "PoT Short": pot_short_bc,
                    "PoT 2Δ Approx": pot_approx_bc,
                    "Gamma Neto": gamma_neto_bc,
                    "Theta Neto": theta_neto_bc,
                    "Decay 7d": decay_7d_bc,
                    "POP %": round(pop_bc * 100, 1),
                    "POP Breakeven %": round(pop_be_bc * 100, 1),
                    "Prob OTM %": round(pop_bc * 100, 1),
                    "Crédito": credit,
                    "Riesgo Máx": max_risk,
                    "Retorno %": retorno_pct,
                    "IV Short %": round(sold_iv * 100, 1),
                    "IV Long %": round(bought_ivbc * 100, 1),
                    "IV %": round(sold_iv * 100, 1),
                    "Breakeven": breakeven_bc,
                    "Dist Strike %": dist_pct,
                    "Vol Short": sold_vol,
                    "OI Short": sold_oi,
                    "Liq Score": liq_score_bc,
                    "EV Real Adj": ev_real_adj_bc,
                    "Surface Edge": surface_edge_bc,
                    "Volumen": sold_vol + bought_vol,
                    "OI": sold_oi + bought_oi,
                    "Bid-Ask": _bid_ask_spread(sold_bid, sold_ask),
                    "Liquidez": sold_vol + sold_oi + bought_vol + bought_oi,
                }
                if ticker_meta:
                    row.update(ticker_meta)
                results.append(row)

    return results


# ────────────────────────────────────────────────────────────────────────────
#  Escaneo de un ticker completo (todas las expiraciones válidas)
# ────────────────────────────────────────────────────────────────────────────

def _scan_single_ticker(
    ticker: str,
    min_pop: float,
    max_dte: int,
    min_credit: float,
    strict: bool = False,
) -> tuple[list[dict], dict]:
    """Escanea todas las expiraciones válidas de un ticker.

    Parameters
    ----------
    strict : bool
        Si True, aplica pipeline completo de 9 filtros.

    Returns
    -------
    tuple[list[dict], dict]
        (lista de spreads, metadata del ticker — IV rank, trend, etc.)
    """
    spot, err = obtener_precio_actual(ticker)
    if not spot:
        logger.warning("Sin precio para %s: %s", ticker, err)
        return [], {}

    # Calcular indicadores a nivel de ticker (una sola vez)
    iv_info = compute_iv_rank_percentile(ticker)
    trend_info = compute_trend(ticker)

    combined_meta = {"ticker": ticker, **iv_info, **trend_info}

    # ── Filtro 1 — Underlying (strict) ───────────────────────────────────
    if strict:
        ok, reason = _passes_underlying_filter(ticker, spot)
        if not ok:
            logger.info("[STRICT] %s descartado — %s", ticker, reason)
            return [], combined_meta

    # ── Filtro 2 — IV Rank mínimo (strict) ───────────────────────────────
    if strict and iv_info["iv_rank"] < CS_MIN_IV_RANK:
        logger.info(
            "[STRICT] %s descartado — IV Rank %.1f < %d",
            ticker, iv_info["iv_rank"], CS_MIN_IV_RANK,
        )
        return [], combined_meta

    # ── Filtro 5 — Dirección / Tendencia (strict) ────────────────────────
    allowed_type: str | None = None
    if strict:
        trend = trend_info["trend"]
        if trend == "Alcista":
            allowed_type = "Bull Put"
        elif trend == "Bajista":
            allowed_type = "Bear Call"
        else:
            # Neutral → no mostrar trades
            logger.info("[STRICT] %s descartado — tendencia Neutral", ticker)
            return [], combined_meta

    ticker_meta = {
        "IV Rank": iv_info["iv_rank"],
        "IV Pctil": iv_info["iv_percentile"],
        "HV 20D": iv_info["iv_current"],   # HV anualizada 20 días en % (proxy de IV histórica)
        "Tendencia": trend_info["trend"],
    }

    try:
        exp_dates = _cached_options_dates(ticker)
    except Exception as exc:
        logger.warning("Sin fechas de expiración para %s: %s", ticker, exc)
        return [], combined_meta

    all_spreads: list[dict] = []

    for exp_date in exp_dates:
        dte = _dte_from_expiry(exp_date)
        if dte <= 0 or dte > max_dte:
            continue
        spreads = _build_spreads_for_expiry(
            ticker, spot, exp_date, min_pop, min_credit, ticker_meta,
            allowed_type=allowed_type,
            strict=strict,
        )
        all_spreads.extend(spreads)

    return all_spreads, combined_meta


# ────────────────────────────────────────────────────────────────────────────
#  Datos rápidos de mercado (background updater)
# ────────────────────────────────────────────────────────────────────────────

def get_fast_market_data(tickers: list[str]) -> dict[str, dict]:
    """Obtiene datos ligeros de mercado para un batch de tickers.

    Para cada ticker recopila:
      - spot (precio actual)
      - iv_rank, iv_percentile (rango/percentil de IV)
      - trend (tendencia: Alcista/Bajista/Neutral)
      - expirations (lista de expiraciones disponibles)
      - updated_at (timestamp de actualización)

    Respeta rate limiter + circuit breaker globales de yfinance.
    Usa sleep aleatorio entre llamadas para evitar bans.

    Args:
        tickers: lista de símbolos (ej. ["AAPL", "MSFT", "NVDA"]).

    Returns:
        dict[str, dict] — {ticker: {spot, iv_rank, ...}} para los que
        se obtuvieron datos exitosamente.
    """
    import time as _time
    from random import uniform as _uniform
    from utils.retry_utils import cb_yfinance, rl_yfinance

    results: dict[str, dict] = {}

    for ticker in tickers:
        try:
            # Respetar circuit breaker
            if cb_yfinance.is_open:
                logger.warning("get_fast_market_data: circuit breaker abierto — abortando batch")
                break

            # Respetar rate limiter
            rl_yfinance.acquire(timeout=15)

            # Precio actual (usa cache TTL interno de 5 min)
            spot, err = obtener_precio_actual(ticker)
            if not spot:
                logger.debug("get_fast_market_data: sin precio para %s: %s", ticker, err)
                continue

            # IV rank + percentile + tendencia
            iv_info = compute_iv_rank_percentile(ticker)
            trend_info = compute_trend(ticker)

            # Expiraciones disponibles (usa cache TTL interno de 5 min)
            try:
                expirations = list(_cached_options_dates(ticker))
            except Exception:
                expirations = []

            results[ticker] = {
                "spot": round(spot, 2),
                "iv_rank": iv_info.get("iv_rank", 0),
                "iv_percentile": iv_info.get("iv_percentile", 0),
                "trend": trend_info.get("trend", "Neutral"),
                "expirations": expirations[:12],
                "updated_at": _time.time(),
            }

            cb_yfinance.record_success()

            # Sleep anti-ban entre tickers
            _time.sleep(_uniform(1.8, 2.5))

        except Exception as exc:
            cb_yfinance.record_failure()
            logger.warning("get_fast_market_data: error en %s — %s", ticker, exc)
            # Continuar con el siguiente ticker
            _time.sleep(_uniform(2.0, 3.5))

    logger.info("get_fast_market_data: %d/%d tickers OK", len(results), len(tickers))
    return results


# ────────────────────────────────────────────────────────────────────────────
#  Función pública principal
# ────────────────────────────────────────────────────────────────────────────

def scan_credit_spreads(
    tickers: list[str],
    min_pop: float = 0.70,
    max_dte: int = 45,
    min_credit: float = 0.30,
    progress_callback=None,
    strict: bool = False,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Escanea múltiples tickers buscando Credit Spreads óptimos.

    Parameters
    ----------
    tickers : list[str]
        Lista de símbolos a escanear.
    min_pop : float
        Probabilidad mínima de ganancia (0-1). Default 0.70.
    max_dte : int
        Máximo de días hasta vencimiento. Default 45.
    min_credit : float
        Crédito mínimo por spread en USD. Default 0.30.
    progress_callback : callable, optional
        Función(ticker, idx, total) para reportar progreso.
    strict : bool
        Si True, aplica los 9 filtros obligatorios del pipeline.
        En modo strict, solo se escanean tickers de la whitelist.

    Returns
    -------
    tuple[pd.DataFrame, dict[str, dict]]
        (DataFrame de oportunidades ordenado por Income Score,
         dict {ticker: {iv_rank, iv_percentile, trend, ...}} por ticker)
    """
    all_results: list[dict] = []
    ticker_indicators: dict[str, dict] = {}

    # En modo strict, filtrar contra whitelist
    effective_tickers = tickers
    if strict:
        effective_tickers = [t for t in tickers if t.strip().upper() in CS_WHITELIST]

    for idx, ticker in enumerate(effective_tickers):
        ticker = ticker.strip().upper()
        if not ticker:
            continue
        if progress_callback:
            progress_callback(ticker, idx, len(effective_tickers))

        try:
            spreads, t_meta = _scan_single_ticker(
                ticker, min_pop, max_dte, min_credit, strict=strict,
            )
            all_results.extend(spreads)
            if t_meta:
                ticker_indicators[ticker] = t_meta
        except Exception as exc:
            logger.error("Error escaneando %s: %s", ticker, exc)

    if not all_results:
        return pd.DataFrame(), ticker_indicators

    df = pd.DataFrame(all_results)

    # ── Income Score por cada spread ─────────────────────────────────
    scores, labels = zip(*[
        compute_income_score(row) for row in all_results
    ])
    df["Income Score"] = list(scores)
    df["Calidad"] = list(labels)

    # ── Score de Oportunidad por cada spread ──────────────────────────
    opp_scores, opp_labels = zip(*[
        compute_opportunity_score(row) for row in all_results
    ])
    df["Score Oportunidad"] = list(opp_scores)
    df["Nivel"] = list(opp_labels)

    # Filtrar: solo mostrar score ≥ 60
    df = df[df["Score Oportunidad"] >= OPP_SCORE_MIN_SHOW].reset_index(drop=True)

    if df.empty:
        return pd.DataFrame(), ticker_indicators

    # ── EV Ajustado por capital en riesgo (Fase 1) ────────────────────
    def _ev_ajustado(row: dict) -> float:
        """EV como porcentaje del capital en riesgo.

        EV = crédito × POP  -  riesgo × (1 - POP)
        ev_ajustado = EV / riesgo_máx × 100
        """
        credit_ = row.get("Crédito", 0) or 0
        risk_ = row.get("Riesgo Máx", 0) or 0
        pop_ = (row.get("POP %", 0) or 0) / 100.0
        if risk_ <= 0:
            return 0.0
        ev = credit_ * pop_ - risk_ * (1.0 - pop_)
        return round(ev / risk_ * 100.0, 2)

    df["EV Ajustado"] = [
        _ev_ajustado(r) for r in df.to_dict("records")
    ]

    # ── Score Final Optimizado (Fase 3) ────────────────────────────────
    # Usa EV Real Adj + Surface Edge + pesos optimizables por backtesting.
    # compute_optimized_score vive en core/backtester.py
    df["Score Final"] = [
        compute_optimized_score(r) for r in df.to_dict("records")
    ]

    # Ordenar por Score Final > Score Oportunidad > Income Score > Retorno
    df = df.sort_values(
        ["Score Final", "Score Oportunidad", "Income Score", "Retorno %"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    return df, ticker_indicators


# ────────────────────────────────────────────────────────────────────────────
#  Sistema de Alertas — 10 reglas obligatorias sequenciales
# ────────────────────────────────────────────────────────────────────────────

def _check_10_rules(row: dict, account_size: float) -> tuple[bool, list[dict]]:
    """Verifica las 10 reglas obligatorias sobre un spread ya construido.

    Reglas que se chequean aquí son las que NO se aplicaron en
    _build_spreads_for_expiry, o que requieren información extra
    (como account_size y alineación tendencia).

    Returns (all_pass, detalle_reglas)
    """
    rules: list[dict] = []
    all_pass = True

    ticker = row.get("Ticker", "")
    spot = row.get("Spot", 0)
    tipo = row.get("Tipo", "")
    dte = row.get("DTE", 0)
    delta = abs(row.get("Delta Vendido", 1.0))
    trend = row.get("Tendencia", "Neutral")
    width = abs(
        (row.get("Strike Vendido", 0) or 0)
        - (row.get("Strike Comprado", 0) or 0)
    )
    credit = row.get("Crédito", 0) or 0
    risk = row.get("Riesgo Máx", 0) or 0
    dist_pct = row.get("Dist Strike %", 0) or 0
    oi = row.get("OI", 0) or 0
    vol = row.get("Volumen", 0) or 0
    bid_ask = row.get("Bid-Ask", 0) or 0
    iv_rank = row.get("IV Rank", 0) or 0
    mid = credit + bid_ask / 2 if credit > 0 else 0.01

    # Regla 1 — Whitelist + Precio > $20 + Vol > 1M + OI cadena > 500
    r1 = ticker in CS_WHITELIST and spot > CS_MIN_PRICE
    rules.append({"regla": "1. Underlying (whitelist, precio>$20)", "ok": r1})
    if not r1:
        all_pass = False

    # Regla 2 — IV Rank >= 30
    r2 = iv_rank >= CS_MIN_IV_RANK
    rules.append({"regla": f"2. IV Rank ≥ {CS_MIN_IV_RANK}%", "ok": r2})
    if not r2:
        all_pass = False

    # Regla 3 — 25 <= DTE <= 45
    r3 = CS_DTE_MIN <= dte <= CS_DTE_MAX
    rules.append({"regla": f"3. DTE {CS_DTE_MIN}–{CS_DTE_MAX}", "ok": r3})
    if not r3:
        all_pass = False

    # Regla 4 — 0.10 <= |Delta| <= 0.20
    r4 = CS_DELTA_MIN <= delta <= CS_DELTA_MAX
    rules.append({"regla": f"4. Delta {CS_DELTA_MIN}–{CS_DELTA_MAX}", "ok": r4})
    if not r4:
        all_pass = False

    # Regla 5 — Tendencia alineada (Alcista→Put, Bajista→Call, Neutral→descartar)
    if trend == "Alcista":
        r5 = tipo == "Bull Put"
    elif trend == "Bajista":
        r5 = tipo == "Bear Call"
    else:
        r5 = False  # Neutral → no alertar
    rules.append({"regla": "5. Tendencia alineada", "ok": r5})
    if not r5:
        all_pass = False

    # Regla 6 — Width = 2, 3 o 5
    width_int = int(round(width))
    r6 = width_int in CS_ALLOWED_WIDTHS
    rules.append({"regla": f"6. Ancho {CS_ALLOWED_WIDTHS}", "ok": r6})
    if not r6:
        all_pass = False

    # Regla 7 — Crédito >= 15% del ancho
    r7 = width > 0 and credit >= CS_MIN_CREDIT_PCT * width
    rules.append({"regla": f"7. Crédito ≥ {CS_MIN_CREDIT_PCT*100:.0f}% ancho", "ok": r7})
    if not r7:
        all_pass = False

    # Regla 8 — Riesgo <= 5% del account size
    max_risk_allowed = account_size * ALERT_MAX_RISK_PCT
    # Riesgo es por contrato (x100)
    risk_per_contract = risk * 100
    r8 = risk_per_contract <= max_risk_allowed
    rules.append({
        "regla": f"8. Riesgo ≤ 5% cuenta (${max_risk_allowed:,.0f})",
        "ok": r8,
    })
    if not r8:
        all_pass = False

    # Regla 9 — Distancia >= 3%
    r9 = dist_pct >= CS_MIN_DIST_PCT
    rules.append({"regla": f"9. Distancia ≥ {CS_MIN_DIST_PCT}%", "ok": r9})
    if not r9:
        all_pass = False

    # Regla 10 — Liquidez (OI>500, Vol>100, Bid-Ask<=10% mid)
    ba_ok = True
    if mid > 0:
        ba_ok = bid_ask / mid <= CS_MAX_BID_ASK_PCT
    r10 = oi > CS_MIN_SOLD_OI and vol > CS_MIN_SOLD_VOL and ba_ok
    rules.append({"regla": "10. Liquidez (OI>500, Vol>100, B-A≤10%)", "ok": r10})
    if not r10:
        all_pass = False

    return all_pass, rules


def generate_alerts(
    df: pd.DataFrame,
    account_size: float = ALERT_DEFAULT_ACCOUNT_SIZE,
) -> pd.DataFrame:
    """Filtra el DataFrame de spreads aplicando las 10 reglas obligatorias.

    Solo retorna filas donde TODAS las reglas son verdaderas.
    Agrega columna 'Reglas' con el detalle de cada regla verificada.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame resultado de scan_credit_spreads (strict mode).
    account_size : float
        Tamaño de la cuenta del usuario en USD.

    Returns
    -------
    pd.DataFrame
        Solo filas que cumplen las 10 reglas. Vacío si ninguna cumple.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    alerts: list[dict] = []

    for _, row_s in df.iterrows():
        row = row_s.to_dict()
        all_pass, rules_detail = _check_10_rules(row, account_size)
        if all_pass:
            row["_rules_detail"] = rules_detail
            alerts.append(row)

    if not alerts:
        return pd.DataFrame()

    alerts_df = pd.DataFrame(alerts)
    # Ordenar por Score Oportunidad descendente
    if "Score Oportunidad" in alerts_df.columns:
        alerts_df = alerts_df.sort_values(
            "Score Oportunidad", ascending=False
        ).reset_index(drop=True)

    return alerts_df
