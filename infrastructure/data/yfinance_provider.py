"""Proveedor de datos de mercado usando Yahoo Finance (yfinance).

Implementa las firmas estándar del proveedor de mercado
vía yahoo_finance_client._provider_impls().
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from infrastructure.data._chain_utils import CHAIN_REQUIRED_COLUMNS as CHAIN_COLUMNS, normalize_chain_df as _normalize_chain_df

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Fechas de expiración
# ─────────────────────────────────────────────────────────

def fetch_options_dates(ticker_sym: str) -> tuple:
    """Retorna fechas de expiración futuras disponibles para el ticker."""
    try:
        ticker = yf.Ticker(ticker_sym)
        raw_dates = ticker.options  # tuple de strings "YYYY-MM-DD"
        if not raw_dates:
            return tuple()
        today = datetime.now(timezone.utc).date()
        future_dates = sorted(
            d for d in raw_dates
            if datetime.strptime(d, "%Y-%m-%d").date() >= today
        )
        return tuple(future_dates)
    except Exception as exc:
        logger.warning("YFinance expiraciones fallo (%s): %s", ticker_sym, exc)
        return tuple()


# ─────────────────────────────────────────────────────────
# Cadena de opciones (chain)
# ─────────────────────────────────────────────────────────

def fetch_single_chain(ticker_sym: str, exp_date: str):
    """Retorna (exp_date, {"calls": df, "puts": df}, error | None)."""
    empty = {
        "calls": pd.DataFrame(columns=CHAIN_COLUMNS),
        "puts": pd.DataFrame(columns=CHAIN_COLUMNS),
    }
    try:
        ticker = yf.Ticker(ticker_sym)
        chain = ticker.option_chain(exp_date)
        calls_df = _normalize_chain_df(chain.calls)
        puts_df = _normalize_chain_df(chain.puts)
        return exp_date, {"calls": calls_df, "puts": puts_df}, None
    except Exception as exc:
        logger.warning("YFinance chain fallo (%s, %s): %s", ticker_sym, exp_date, exc)
        return exp_date, empty, str(exc)


# ─────────────────────────────────────────────────────────
# Precio spot
# ─────────────────────────────────────────────────────────

def obtener_precio_actual(ticker_sym: str):
    """Retorna (precio: float, None) o (None, error: str)."""
    try:
        ticker = yf.Ticker(ticker_sym)
        price = ticker.fast_info.last_price
        if price is None or float(price) <= 0:
            return None, "Precio no disponible"
        return float(price), None
    except Exception as exc:
        logger.warning("YFinance precio actual fallo (%s): %s", ticker_sym, exc)
        return None, str(exc)


# ─────────────────────────────────────────────────────────
# Historial de precios
# ─────────────────────────────────────────────────────────

def get_price_history(ticker_sym: str, period: str = "1y") -> pd.DataFrame:
    """Retorna historial OHLCV con columnas Open/High/Low/Close/Volume."""
    try:
        df = yf.download(ticker_sym, period=period, auto_adjust=True, progress=False)
        # yfinance devuelve MultiIndex cuando llama con un solo ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as exc:
        logger.warning("YFinance historial fallo (%s): %s", ticker_sym, exc)
        return pd.DataFrame()


def get_contract_history(contract_symbol: str, period: str = "1mo") -> pd.DataFrame:
    """Retorna historial de precios para un contrato de opciones."""
    try:
        ticker = yf.Ticker(contract_symbol)
        return ticker.history(period=period)
    except Exception as exc:
        logger.warning("YFinance contract history fallo (%s): %s", contract_symbol, exc)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────
# Detalles del ticker
# ─────────────────────────────────────────────────────────

def get_ticker_details(ticker_sym: str):
    """Retorna dict con info del ticker o None si falla."""
    try:
        return yf.Ticker(ticker_sym).info
    except Exception as exc:
        logger.warning("YFinance detalles fallo (%s): %s", ticker_sym, exc)
        return None
