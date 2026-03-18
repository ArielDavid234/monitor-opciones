"""Yahoo Finance data client (Infrastructure layer).

This module centralizes network access, retries, sessions, and caching.
Core business modules should consume these helpers and avoid direct network logic.
"""

from __future__ import annotations

import logging
import threading
import time
from functools import wraps
from random import choice, uniform

import pandas as pd
import streamlit as st
import yfinance as yf
from tenacity import RetryError

from infrastructure.caching import get_cache as _get_cache
from utils.retry_utils import (
    CircuitOpenError,
    RateLimitError,
    cb_yfinance,
    retry_yfinance,
    rl_yfinance,
)

logger = logging.getLogger(__name__)

try:
    from curl_cffi.requests import Session as CurlSession

    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False
    import requests as _fallback_requests

    logger.warning(
        "curl_cffi no disponible - usando requests estandar (sin TLS fingerprint)"
    )


_cache = _get_cache()


def get_cached_chain(ticker: str, expiration: str):
    """Devuelve chain cacheado o None si no existe/expiro."""
    return _cache.get(f"chain:{ticker}:{expiration}")


def cache_chain(ticker: str, expiration: str, chain_df, ttl_seconds: int = 720):
    """Guarda el chain en cache."""
    _cache.set(f"chain:{ticker}:{expiration}", chain_df, ttl=ttl_seconds)


def ttl_cache(ttl_seconds=300, maxsize=128, should_cache=None):
    """Decorador de cache con TTL (time-to-live)."""

    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = args + tuple(sorted(kwargs.items()))
            now = time.time()
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    logger.debug("Cache HIT para %s%s", func.__name__, args)
                    return result

            logger.debug("Cache MISS para %s%s", func.__name__, args)
            result = func(*args, **kwargs)

            if should_cache is None or should_cache(result):
                cache[key] = (result, now)
                if len(cache) > maxsize:
                    oldest = min(cache, key=lambda k: cache[k][1])
                    del cache[oldest]
            else:
                logger.debug("Cache SKIP (should_cache=False) para %s%s", func.__name__, args)
            return result

        def cache_clear():
            cache.clear()

        def cache_invalidate(*args, **kwargs):
            key = args + tuple(sorted(kwargs.items()))
            cache.pop(key, None)

        wrapper.cache_clear = cache_clear
        wrapper.cache_invalidate = cache_invalidate
        wrapper.cache_info = lambda: {
            "size": len(cache),
            "maxsize": maxsize,
            "ttl": ttl_seconds,
        }
        return wrapper

    return decorator


_RETRIABLE_KEYWORDS = (
    "429",
    "rate limit",
    "too many",
    "timeout",
    "timed out",
    "connection",
    "503",
    "502",
    "504",
    "curl",
    "failure writing",
    "failed to perform",
)


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
    """Obtiene y cachea fechas de expiracion con retry interno anti-rate-limit."""
    last_exc = None
    for _attempt in range(4):
        if _attempt > 0:
            _wait = uniform(3.0, 5.0) * _attempt
            logger.warning(
                "_cached_options_dates: reintento %d/4 para %s - esperando %.1fs",
                _attempt + 1,
                ticker_sym,
                _wait,
            )
            time.sleep(_wait)
        try:
            rl_yfinance.acquire(timeout=15)
            session, _ = crear_sesion_nueva()
            ticker = yf.Ticker(ticker_sym, session=session)
            return tuple(ticker.options)
        except Exception as _e:
            last_exc = _e
            _msg = str(_e).lower()
            if not any(kw in _msg for kw in _RETRIABLE_KEYWORDS):
                raise
            logger.warning("Error transitorio obteniendo fechas (%s): %s", ticker_sym, _e)
    raise last_exc


@ttl_cache(ttl_seconds=300, maxsize=256, should_cache=_chain_is_cacheable)
def _cached_option_chain(ticker_sym, exp_date):
    """Obtiene y cachea la cadena de opciones con retry anti-rate-limit."""
    last_exc = None
    for _attempt in range(4):
        if _attempt > 0:
            _wait = uniform(3.0, 5.0) * _attempt
            logger.warning(
                "_cached_option_chain: reintento %d/4 para %s %s - esperando %.1fs",
                _attempt + 1,
                ticker_sym,
                exp_date,
                _wait,
            )
            time.sleep(_wait)
        try:
            rl_yfinance.acquire(timeout=15)
            session, _ = crear_sesion_nueva()
            ticker = yf.Ticker(ticker_sym, session=session)
            chain = ticker.option_chain(exp_date)
            result = {"calls": chain.calls.copy(), "puts": chain.puts.copy()}
            if result["puts"].empty and result["calls"].empty:
                logger.warning(
                    "_cached_option_chain: cadena vacia para %s %s (intento %d/4)",
                    ticker_sym,
                    exp_date,
                    _attempt + 1,
                )
                continue
            return result
        except KeyboardInterrupt:
            last_exc = RuntimeError(f"curl interrupt for {ticker_sym} {exp_date}")
            logger.warning(
                "KeyboardInterrupt (curl_cffi) cadena (%s %s) - reintentando",
                ticker_sym,
                exp_date,
            )
        except Exception as _e:
            last_exc = _e
            _msg = str(_e).lower()
            if not any(kw in _msg for kw in _RETRIABLE_KEYWORDS):
                raise
            logger.warning("Error transitorio cadena (%s %s): %s", ticker_sym, exp_date, _e)
    if last_exc:
        raise last_exc
    logger.warning(
        "_cached_option_chain: cadena vacia persistente para %s %s tras 4 intentos",
        ticker_sym,
        exp_date,
    )
    return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}


@ttl_cache(ttl_seconds=300, maxsize=32, should_cache=_history_is_cacheable)
def _cached_history(ticker_sym, period="1d"):
    """Obtiene y cachea el historial de precios."""
    rl_yfinance.acquire(timeout=15)
    session, _ = crear_sesion_nueva()
    ticker = yf.Ticker(ticker_sym, session=session)
    return ticker.history(period=period)


def limpiar_cache_ticker(ticker_sym=None):
    """Limpia el cache de un ticker especifico o de todo."""
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
    """Obtiene el precio actual usando cache TTL."""
    try:
        hist = _cached_history(ticker_sym, "1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1]), None
        return None, "Sin datos de precio"
    except Exception as e:
        return None, str(e)


BROWSER_PROFILES = [
    "chrome110",
    "chrome116",
    "chrome119",
    "chrome120",
    "chrome123",
    "chrome124",
    "edge99",
    "edge101",
    "safari15_3",
    "safari15_5",
    "safari17_0",
]


_SESSION_POOL: list = []
_SESSION_POOL_SIZE = 4
_SESSION_POOL_LOCK = threading.Lock()


def crear_sesion_nueva():
    """Crea sesion HTTP con perfil TLS anti-ban."""
    if _HAS_CURL_CFFI:
        perfil = choice(BROWSER_PROFILES)
        session = CurlSession(impersonate=perfil)
        return session, perfil

    session = _fallback_requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session, "requests-fallback"


def _get_pooled_session():
    with _SESSION_POOL_LOCK:
        if _SESSION_POOL:
            return _SESSION_POOL.pop()
    return crear_sesion_nueva()


def _return_session(session, perfil):
    with _SESSION_POOL_LOCK:
        if len(_SESSION_POOL) < _SESSION_POOL_SIZE:
            _SESSION_POOL.append((session, perfil))


@st.cache_data(ttl=300, show_spinner=False)
def obtener_historial_contrato(contract_symbol):
    """Obtiene historial de contrato con retry y circuit breaker."""
    try:
        cb_yfinance.check()
    except CircuitOpenError as e:
        return pd.DataFrame(), str(e)

    try:
        hist = _yf_fetch_contract_history(contract_symbol)
        cb_yfinance.record_success()
        return hist, None
    except (RetryError, Exception) as e:
        cb_yfinance.record_failure()
        logger.warning("Historial %s fallo tras retries: %s", contract_symbol, e)
        return pd.DataFrame(), str(e)


@retry_yfinance(max_attempts=4, min_wait=2, max_wait=40)
def _yf_fetch_contract_history(contract_symbol):
    session, perfil = _get_pooled_session()
    try:
        contract = yf.Ticker(contract_symbol, session=session)
        hist = contract.history(period="1mo")
        if hist.empty:
            hist = contract.history(period="5d")
        _return_session(session, perfil)
        return hist
    except Exception as e:
        _maybe_raise_rate_limit(e)
        raise


def fetch_single_chain(ticker_sym, exp_date, max_retries=3):
    """Obtiene una sola cadena de opciones con retries y cache."""
    try:
        chain_data = _cached_option_chain(ticker_sym, exp_date)
        return exp_date, chain_data, None
    except Exception:
        pass

    try:
        cb_yfinance.check()
    except CircuitOpenError as e:
        return exp_date, None, str(e)

    try:
        chain_data = _yf_fetch_chain_attempt(ticker_sym, exp_date)
        cb_yfinance.record_success()
        return exp_date, chain_data, None
    except (RetryError, Exception) as e:
        cb_yfinance.record_failure()
        return exp_date, None, str(e)


@retry_yfinance(max_attempts=5, min_wait=4, max_wait=60)
def _yf_fetch_chain_attempt(ticker_sym, exp_date):
    time.sleep(uniform(0.5, 1.8))
    rl_yfinance.acquire(timeout=15)
    session, perfil = _get_pooled_session()
    try:
        ticker = yf.Ticker(ticker_sym, session=session)
        raw_chain = ticker.option_chain(exp_date)
        chain_data = {"calls": raw_chain.calls.copy(), "puts": raw_chain.puts.copy()}
        _return_session(session, perfil)
        return chain_data
    except Exception as e:
        _maybe_raise_rate_limit(e)
        raise


def _maybe_raise_rate_limit(exc: Exception) -> None:
    msg = str(exc).lower()
    if any(kw in msg for kw in ["429", "rate limit", "too many requests"]):
        raise RateLimitError(str(exc)) from exc


@retry_yfinance(max_attempts=3, min_wait=3, max_wait=30)
def _yf_fetch_options_dates(ticker_sym):
    session, _perfil = crear_sesion_nueva()
    try:
        ticker = yf.Ticker(ticker_sym, session=session)
        return tuple(ticker.options)
    except Exception as e:
        _maybe_raise_rate_limit(e)
        raise


def fetch_options_dates(ticker_sym):
    """Obtiene fechas con cache + retry + circuit breaker encapsulados."""
    try:
        return _cached_options_dates(ticker_sym)
    except Exception:
        try:
            cb_yfinance.check()
            options_dates = _yf_fetch_options_dates(ticker_sym)
            cb_yfinance.record_success()
            return options_dates
        except Exception:
            cb_yfinance.record_failure()
            raise


def fetch_with_cache(ticker_sym: str, exp_date: str):
    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return exp_date, cached, None

    result = fetch_single_chain(ticker_sym, exp_date)
    exp_date, chain_data, error = result
    if chain_data is not None:
        cache_chain(ticker_sym, exp_date, chain_data)
    return result
