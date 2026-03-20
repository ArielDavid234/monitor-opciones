"""Facade de compatibilidad: backend 100% Polygon.io.

Este módulo conserva la API pública usada por el resto del sistema,
pero delega toda la data de mercado/opciones a polygon_client.
"""

from __future__ import annotations

import logging
import time
from functools import wraps

import pandas as pd
import streamlit as st

from infrastructure.caching import get_cache as _get_cache
from infrastructure.data.polygon_client import (
    fetch_options_dates as _polygon_fetch_options_dates,
    fetch_single_chain as _polygon_fetch_single_chain,
    get_contract_history as _polygon_get_contract_history,
    get_price_history as _polygon_get_price_history,
    obtener_precio_actual as _polygon_obtener_precio_actual,
)

logger = logging.getLogger(__name__)
_cache = _get_cache()


def get_cached_chain(ticker: str, expiration: str):
    return _cache.get(f"chain:{ticker}:{expiration}")


def cache_chain(ticker: str, expiration: str, chain_df, ttl_seconds: int = 720):
    _cache.set(f"chain:{ticker}:{expiration}", chain_df, ttl=ttl_seconds)


def ttl_cache(ttl_seconds=300, maxsize=128, should_cache=None):
    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = args + tuple(sorted(kwargs.items()))
            now = time.time()
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    return result

            result = func(*args, **kwargs)
            if should_cache is None or should_cache(result):
                cache[key] = (result, now)
                if len(cache) > maxsize:
                    oldest = min(cache, key=lambda k: cache[k][1])
                    del cache[oldest]
            return result

        def cache_clear():
            cache.clear()

        def cache_invalidate(*args, **kwargs):
            key = args + tuple(sorted(kwargs.items()))
            cache.pop(key, None)

        wrapper.cache_clear = cache_clear
        wrapper.cache_invalidate = cache_invalidate
        return wrapper

    return decorator


def _chain_is_cacheable(result):
    if not isinstance(result, dict):
        return False
    puts = result.get("puts")
    calls = result.get("calls")
    if puts is None or calls is None:
        return False
    return not (puts.empty and calls.empty)


def _history_is_cacheable(result):
    if result is None:
        return False
    return not result.empty


@ttl_cache(ttl_seconds=300, maxsize=64)
def _cached_options_dates(ticker_sym):
    return tuple(_polygon_fetch_options_dates(ticker_sym))


@ttl_cache(ttl_seconds=300, maxsize=256, should_cache=_chain_is_cacheable)
def _cached_option_chain(ticker_sym, exp_date):
    _, chain_data, err = _polygon_fetch_single_chain(ticker_sym, exp_date)
    if err:
        raise RuntimeError(err)
    return chain_data


@ttl_cache(ttl_seconds=300, maxsize=32, should_cache=_history_is_cacheable)
def _cached_history(ticker_sym, period="1d"):
    return _polygon_get_price_history(ticker_sym, period)


def limpiar_cache_ticker(ticker_sym=None):
    if ticker_sym is None:
        _cached_options_dates.cache_clear()
        _cached_option_chain.cache_clear()
        _cached_history.cache_clear()
        logger.info("Cache completo limpiado")
    else:
        _cached_options_dates.cache_invalidate(ticker_sym)
        _cached_history.cache_invalidate(ticker_sym, "1d")
        _cached_history.cache_invalidate(ticker_sym, "1mo")
        _cached_history.cache_invalidate(ticker_sym, "3mo")
        _cached_history.cache_invalidate(ticker_sym, "5d")
        logger.info("Cache limpiado para ticker: %s", ticker_sym)


def obtener_precio_actual(ticker_sym):
    return _polygon_obtener_precio_actual(ticker_sym)


def crear_sesion_nueva():
    """Compat: ya no existe sesión HTTP para Yahoo; backend es Polygon."""
    return None, "polygon"


@st.cache_data(ttl=300, show_spinner=False)
def obtener_historial_contrato(contract_symbol):
    try:
        hist = _polygon_get_contract_history(contract_symbol, period="1mo")
        if hist.empty:
            hist = _polygon_get_contract_history(contract_symbol, period="5d")
        return hist, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def fetch_single_chain(ticker_sym, exp_date, max_retries=3):
    return _polygon_fetch_single_chain(ticker_sym, exp_date)


def fetch_options_dates(ticker_sym):
    return _cached_options_dates(ticker_sym)


def fetch_with_cache(ticker_sym: str, exp_date: str):
    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return exp_date, cached, None

    result = fetch_single_chain(ticker_sym, exp_date)
    exp_date, chain_data, error = result
    if chain_data is not None:
        cache_chain(ticker_sym, exp_date, chain_data)
    return result
