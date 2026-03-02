# -*- coding: utf-8 -*-
"""
Integraciones con APIs financieras externas — Alpha Vantage.

Proporciona datos fundamentales que yfinance no siempre ofrece:
earnings surprise history, short interest %, ROE, PEG actualizado.

Estas métricas ayudan al usuario a contextualizar datos de opciones
(OI, IV, flujo) con la salud fundamental de la empresa.

**API Key:** Se lee de st.secrets["alpha_vantage"]["api_key"]
(Streamlit Cloud) o de la variable de entorno ALPHA_VANTAGE_KEY.
"""
import logging
import os
import time
from typing import Optional

import requests
import streamlit as st

from utils.retry_utils import (
    retry_alpha_vantage, cb_alpha_vantage,
    RateLimitError, CircuitOpenError,
    notify_retry_exhausted, notify_circuit_open,
)
from tenacity import RetryError

logger = logging.getLogger(__name__)

_AV_BASE_URL = "https://www.alphavantage.co/query"

# Rate limit: Alpha Vantage free tier = 25 req/día, 5 req/min


def _get_av_api_key() -> Optional[str]:
    """Obtiene la API key de Alpha Vantage desde st.secrets o env."""
    # 1. Streamlit secrets (producción en Streamlit Cloud)
    try:
        return st.secrets["alpha_vantage"]["api_key"]
    except (KeyError, FileNotFoundError):
        pass

    # 2. Variable de entorno (desarrollo local)
    key = os.getenv("ALPHA_VANTAGE_KEY")
    if key:
        return key

    return None


@retry_alpha_vantage(max_attempts=3, min_wait=8, max_wait=60)
def _av_request(params: dict, api_key: str) -> Optional[dict]:
    """Ejecuta un request a Alpha Vantage con retry automático (tenacity).

    Backoff exponencial + jitter para respetar el rate-limit severo
    del free tier (5 req/min). Detecta rate-limit tanto por HTTP 429
    como por el campo JSON \"Note\" que AV devuelve.

    Args:
        params: Parámetros de la query (sin apikey).
        api_key: API key válida.

    Returns:
        dict con la respuesta JSON, o None si error no-transitorio.

    Raises:
        RateLimitError: Si AV devuelve rate-limit (para que tenacity reintente).
        requests.exceptions.Timeout: Timeout de red.
        requests.exceptions.HTTPError: Error 5xx del servidor.
    """
    params["apikey"] = api_key

    resp = requests.get(_AV_BASE_URL, params=params, timeout=15)

    # HTTP 429 → RateLimitError (tenacity reintentará)
    if resp.status_code == 429:
        raise RateLimitError("Alpha Vantage HTTP 429 rate limit")

    resp.raise_for_status()
    data = resp.json()

    # Alpha Vantage devuelve {"Note": "..."} cuando excedes rate limit
    if "Note" in data and "call frequency" in data.get("Note", ""):
        raise RateLimitError(
            f"Alpha Vantage rate limit (JSON Note): {data['Note'][:80]}"
        )

    # Respuesta vacía o error no-transitorio
    if "Error Message" in data:
        logger.warning(f"Alpha Vantage error: {data['Error Message']}")
        return None

    return data


def _safe_float(value, default: float = 0.0) -> float:
    """Convierte un valor a float de forma segura."""
    if value is None or value == "None" or value == "-" or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_alpha_vantage_fundamentals(ticker: str) -> dict:
    """Fetch datos fundamentales de Alpha Vantage para un ticker.

    Obtiene Company Overview (PEG, márgenes, ROE, short %, book value)
    y Earnings trimestrales (surprise %, EPS reportado vs estimado).

    Estas métricas complementan los datos de yfinance y contextualizan
    la actividad de opciones:
    - Earnings surprise positivo + IV alta → posible oportunidad post-earnings
    - Short interest alto + OI calls subiendo → posible short squeeze
    - PEG bajo + revenue growth → empresa subvalorada, calls a largo plazo

    Args:
        ticker: Símbolo del activo (e.g. "AAPL", "TSLA").

    Returns:
        dict con métricas fundamentales, o dict con "error" si falla.
    """
    api_key = _get_av_api_key()
    if not api_key:
        return {
            "error": (
                "API Key de Alpha Vantage no configurada. "
                "Agrega alpha_vantage.api_key en secrets.toml o "
                "ALPHA_VANTAGE_KEY en variables de entorno."
            ),
            "source": "Alpha Vantage",
        }

    # ── Circuit breaker: pausar si Alpha Vantage está caído ──────
    try:
        cb_alpha_vantage.check()
    except CircuitOpenError as e:
        return {"error": str(e), "source": "Alpha Vantage"}

    # ── Company Overview ─────────────────────────────────────────
    try:
        overview = _av_request({"function": "OVERVIEW", "symbol": ticker}, api_key)
        cb_alpha_vantage.record_success()
    except (RetryError, RateLimitError, Exception) as e:
        cb_alpha_vantage.record_failure()
        return {"error": f"Error obteniendo overview: {e}", "source": "Alpha Vantage"}

    # ── Earnings (quarterly) ─────────────────────────────────────
    try:
        earnings = _av_request({"function": "EARNINGS", "symbol": ticker}, api_key)
        cb_alpha_vantage.record_success()
    except (RetryError, RateLimitError, Exception) as e:
        cb_alpha_vantage.record_failure()
        earnings = None  # no bloquear si solo falla earnings
        logger.warning("Alpha Vantage earnings failed for %s: %s", ticker, e)

    # ── Parsear Overview ─────────────────────────────────────────
    if not overview or len(overview) < 5:
        # Alpha Vantage devuelve {} para tickers inválidos o sin datos
        return {
            "error": f"Sin datos de Alpha Vantage para {ticker} (ticker inválido o sin cobertura)",
            "source": "Alpha Vantage",
        }

    peg = _safe_float(overview.get("PEGRatio"))
    pe_forward = _safe_float(overview.get("ForwardPE"))
    pe_trailing = _safe_float(overview.get("TrailingPE"))
    revenue_ttm = _safe_float(overview.get("RevenueTTM"))
    eps_ttm = _safe_float(overview.get("DilutedEPSTTM"))
    profit_margin = _safe_float(overview.get("ProfitMargin"))
    roe = _safe_float(overview.get("ReturnOnEquityTTM"))
    roa = _safe_float(overview.get("ReturnOnAssetsTTM"))
    gross_margin = _safe_float(overview.get("GrossProfitTTM"))
    operating_margin = _safe_float(overview.get("OperatingMarginTTM"))
    ev_to_ebitda = _safe_float(overview.get("EVToEBITDA"))
    book_value = _safe_float(overview.get("BookValue"))
    dividend_yield = _safe_float(overview.get("DividendYield"))
    beta = _safe_float(overview.get("Beta"))
    shares_short = _safe_float(overview.get("SharesShort"))
    shares_outstanding = _safe_float(overview.get("SharesOutstanding"))
    week_52_high = _safe_float(overview.get("52WeekHigh"))
    week_52_low = _safe_float(overview.get("52WeekLow"))
    analyst_target = _safe_float(overview.get("AnalystTargetPrice"))

    # Short interest % (shares short / shares outstanding)
    short_pct = 0.0
    if shares_short > 0 and shares_outstanding > 0:
        short_pct = round((shares_short / shares_outstanding) * 100, 2)

    # Normalizar gross margin (viene como valor absoluto, no ratio)
    if gross_margin > 0 and revenue_ttm > 0:
        gross_margin_pct = round(gross_margin / revenue_ttm, 4)
    else:
        gross_margin_pct = 0.0

    # ── Parsear Earnings ─────────────────────────────────────────
    quarterly_earnings = []
    last_surprise_pct = None
    last_reported_date = "N/A"
    earnings_beat_streak = 0

    if earnings and "quarterlyEarnings" in earnings:
        raw_quarters = earnings["quarterlyEarnings"][:8]  # últimos 8 quarters
        for q in raw_quarters:
            reported = _safe_float(q.get("reportedEPS"))
            estimated = _safe_float(q.get("estimatedEPS"))
            surprise = _safe_float(q.get("surprisePercentage"))
            quarterly_earnings.append({
                "date": q.get("reportedDate", "N/A"),
                "reported_eps": reported,
                "estimated_eps": estimated,
                "surprise_pct": surprise,
            })

        if quarterly_earnings:
            last_surprise_pct = quarterly_earnings[0]["surprise_pct"]
            last_reported_date = quarterly_earnings[0]["date"]

            # Calcular racha de beats consecutivos
            for q in quarterly_earnings:
                if q["surprise_pct"] > 0:
                    earnings_beat_streak += 1
                else:
                    break

    # ── Resultado ────────────────────────────────────────────────
    result = {
        # Valuación
        "peg_ratio": round(peg, 2) if peg else None,
        "pe_forward": round(pe_forward, 2) if pe_forward else None,
        "pe_trailing": round(pe_trailing, 2) if pe_trailing else None,
        "ev_to_ebitda": round(ev_to_ebitda, 2) if ev_to_ebitda else None,
        "book_value": round(book_value, 2) if book_value else None,

        # Ingresos / Márgenes
        "revenue_ttm": revenue_ttm,
        "eps_ttm": round(eps_ttm, 2) if eps_ttm else None,
        "profit_margin": round(profit_margin * 100, 2) if profit_margin else None,
        "gross_margin_pct": round(gross_margin_pct * 100, 2),
        "operating_margin": round(operating_margin * 100, 2) if operating_margin else None,
        "roe": round(roe * 100, 2) if roe else None,
        "roa": round(roa * 100, 2) if roa else None,

        # Mercado
        "short_interest_pct": short_pct,
        "beta": round(beta, 2) if beta else None,
        "dividend_yield": round(dividend_yield * 100, 2) if dividend_yield else None,
        "analyst_target": analyst_target if analyst_target else None,
        "week_52_high": week_52_high,
        "week_52_low": week_52_low,

        # Earnings
        "last_earnings_date": last_reported_date,
        "last_surprise_pct": round(last_surprise_pct, 2) if last_surprise_pct is not None else None,
        "earnings_beat_streak": earnings_beat_streak,
        "quarterly_earnings": quarterly_earnings,

        # Meta
        "name": overview.get("Name", ticker),
        "sector": overview.get("Sector", "N/A"),
        "industry": overview.get("Industry", "N/A"),
        "description": overview.get("Description", ""),
        "source": "Alpha Vantage",
    }

    logger.info(
        f"{ticker}: Alpha Vantage OK — PEG={peg}, EPS={eps_ttm}, "
        f"Short={short_pct}%, Surprise={last_surprise_pct}%, "
        f"Beat streak={earnings_beat_streak}"
    )

    return result
