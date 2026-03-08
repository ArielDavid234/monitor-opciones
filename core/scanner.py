"""
Scanner de opciones: sesiones anti-ban, escaneo de cadenas,
construcción de símbolos y persistencia CSV.

Incluye sistema de caché TTL para evitar rate-limiting de Yahoo Finance.
"""
import os
import csv
import glob
import time
import logging
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime
from functools import wraps
from random import uniform, choice

logger = logging.getLogger(__name__)

try:
    import scipy.stats  # noqa: F401 – presence check for greeks guard
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False
try:
    from curl_cffi.requests import Session as CurlSession
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False
    import requests as _fallback_requests
    logger.warning("curl_cffi no disponible — usando requests estándar (sin TLS fingerprint)")

from config.constants import SCAN_SLEEP_RANGE, MAX_EXPIRATION_DATES, RISK_FREE_RATE
from concurrent.futures import ThreadPoolExecutor, as_completed
from infrastructure.caching import get_cache as _get_cache
from utils.retry_utils import (
    retry_yfinance, cb_yfinance, RateLimitError, CircuitOpenError,
    notify_retry_exhausted, notify_circuit_open,
    rl_yfinance,
)
from tenacity import RetryError

# ── Cache helpers (delegados a CacheManager unificado) ────────────────────
_cache = _get_cache()


def get_cached_chain(ticker: str, expiration: str):
    """Devuelve chain cacheado o None si no existe/expiró."""
    return _cache.get(f"chain:{ticker}:{expiration}")


def cache_chain(ticker: str, expiration: str, chain_df, ttl_seconds: int = 720):
    """Guarda el chain en caché."""
    _cache.set(f"chain:{ticker}:{expiration}", chain_df, ttl=ttl_seconds)


# ============================================================================
#                    CACHE TTL (evita rate-limiting)
# ============================================================================
"""
    Basado en lru_cache pero con expiración temporal.
    Si los datos ya fueron descargados en los últimos `ttl` segundos,
    se devuelven desde memoria sin hacer una nueva petición a Yahoo Finance.
"""
def ttl_cache(ttl_seconds=300, maxsize=128, should_cache=None):
    """Decorador de caché con TTL (time-to-live).

    Similar a @lru_cache pero los datos expiran después de `ttl_seconds`.
    - maxsize: máximo de entradas en caché (evita memory leaks)
    - Cada entrada guarda (resultado, timestamp)
    - should_cache: callable(result) -> bool. Si devuelve False, el resultado
      NO se almacena en cache (evita envenenar el cache con respuestas vacías).
    """
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
            # Cache MISS — ejecutar función real
            logger.debug("Cache MISS para %s%s", func.__name__, args)
            result = func(*args, **kwargs)
            # Solo cachear si should_cache lo permite (o si no hay predicado)
            if should_cache is None or should_cache(result):
                cache[key] = (result, now)
                # Evictar entradas viejas si el cache crece mucho
                if len(cache) > maxsize:
                    oldest = min(cache, key=lambda k: cache[k][1])
                    del cache[oldest]
            else:
                logger.debug("Cache SKIP (should_cache=False) para %s%s", func.__name__, args)
            return result

        def cache_clear():
            """Limpia todo el caché."""
            cache.clear()

        def cache_invalidate(*args, **kwargs):
            """Invalida una entrada específica del caché."""
            key = args + tuple(sorted(kwargs.items()))
            cache.pop(key, None)

        wrapper.cache_clear = cache_clear
        wrapper.cache_invalidate = cache_invalidate
        wrapper.cache_info = lambda: {"size": len(cache), "maxsize": maxsize, "ttl": ttl_seconds}
        return wrapper
    return decorator


# --- Funciones cacheadas de Yahoo Finance ---

# Errores que justifican reintento (rate-limit, red, curl)
_RETRIABLE_KEYWORDS = (
    "429", "rate limit", "too many", "timeout", "timed out",
    "connection", "503", "502", "504",
    "curl", "failure writing", "failed to perform",
)


def _chain_is_cacheable(result):
    """Predicado: solo cachear cadenas con datos reales."""
    if not isinstance(result, dict):
        return False
    puts = result.get("puts")
    calls = result.get("calls")
    if puts is None or calls is None:
        return False
    return not (puts.empty and calls.empty)


def _history_is_cacheable(result):
    """Predicado: solo cachear historiales no vacíos."""
    if result is None:
        return False
    return not result.empty


@ttl_cache(ttl_seconds=300, maxsize=64)
def _cached_options_dates(ticker_sym):
    """Obtiene y cachea las fechas de expiración con retry interno anti-rate-limit."""
    last_exc = None
    for _attempt in range(4):
        if _attempt > 0:
            # Backoff escalonado: 4s, 10s, 20s entre reintentos
            _wait = uniform(3.0, 5.0) * _attempt
            logger.warning(
                "_cached_options_dates: reintento %d/4 para %s — esperando %.1fs",
                _attempt + 1, ticker_sym, _wait,
            )
            time.sleep(_wait)
        try:
            session, _ = crear_sesion_nueva()
            ticker = yf.Ticker(ticker_sym, session=session)
            return tuple(ticker.options)  # tuple para ser hashable
        except Exception as _e:
            last_exc = _e
            _msg = str(_e).lower()
            # Solo reintentar en errores transitorios (rate-limit, timeout, curl, etc.)
            if not any(kw in _msg for kw in _RETRIABLE_KEYWORDS):
                raise  # Error no retriable (ej. ticker inválido) — salir ya
            logger.warning("Error transitorio obteniendo fechas (%s): %s", ticker_sym, _e)
    raise last_exc


@ttl_cache(ttl_seconds=300, maxsize=256, should_cache=_chain_is_cacheable)
def _cached_option_chain(ticker_sym, exp_date):
    """Obtiene y cachea la cadena de opciones con retry anti-rate-limit.

    Reintenta hasta 4 veces tanto en excepciones como en cadenas vacías
    (rate-limit silencioso de Yahoo). Las cadenas vacías NO se cachean
    gracias al predicado should_cache del decorador ttl_cache.
    """
    last_exc = None
    for _attempt in range(4):
        if _attempt > 0:
            _wait = uniform(3.0, 5.0) * _attempt
            logger.warning(
                "_cached_option_chain: reintento %d/4 para %s %s — esperando %.1fs",
                _attempt + 1, ticker_sym, exp_date, _wait,
            )
            time.sleep(_wait)
        try:
            session, _ = crear_sesion_nueva()
            ticker = yf.Ticker(ticker_sym, session=session)
            chain = ticker.option_chain(exp_date)
            result = {"calls": chain.calls.copy(), "puts": chain.puts.copy()}
            # Si ambas tablas están vacías → posible rate-limit silencioso.
            # Reintentar (no retornar inmediatamente).
            if result["puts"].empty and result["calls"].empty:
                logger.warning(
                    "_cached_option_chain: cadena vacía para %s %s (intento %d/4)",
                    ticker_sym, exp_date, _attempt + 1,
                )
                continue  # reintentar
            return result
        except KeyboardInterrupt:
            # curl_cffi raises spurious KeyboardInterrupt from buffer_callback
            last_exc = RuntimeError(f"curl interrupt for {ticker_sym} {exp_date}")
            logger.warning("KeyboardInterrupt (curl_cffi) cadena (%s %s) — reintentando", ticker_sym, exp_date)
        except Exception as _e:
            last_exc = _e
            _msg = str(_e).lower()
            if not any(kw in _msg for kw in _RETRIABLE_KEYWORDS):
                raise
            logger.warning("Error transitorio cadena (%s %s): %s", ticker_sym, exp_date, _e)
    # Agotados los reintentos: devolver cadena vacía (no se cacheará)
    if last_exc:
        raise last_exc
    logger.warning(
        "_cached_option_chain: cadena vacía persistente para %s %s tras 4 intentos",
        ticker_sym, exp_date,
    )
    return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}


@ttl_cache(ttl_seconds=300, maxsize=32, should_cache=_history_is_cacheable)
def _cached_history(ticker_sym, period="1d"):
    """Obtiene y cachea el historial de precios por 5 min.

    Los historiales vacíos NO se cachean para evitar envenenar el cache.
    """
    session, _ = crear_sesion_nueva()
    ticker = yf.Ticker(ticker_sym, session=session)
    return ticker.history(period=period)


def limpiar_cache_ticker(ticker_sym=None):
    """Limpia el caché de un ticker específico o de todo.

    Llamar cuando el usuario cambia de ticker para forzar datos frescos.
    """
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
    """Obtiene el precio actual usando caché TTL (evita rate-limiting).

    Returns: (precio_float, None) o (None, str_error)
    """
    try:
        hist = _cached_history(ticker_sym, "1d")
        if hist is not None and not hist.empty:
            return float(hist['Close'].iloc[-1]), None
        # Resultado vacío (no se cacheó gracias a should_cache)
        return None, "Sin datos de precio"
    except Exception as e:
        return None, str(e)


def _safe_num(value, default=0):
    """Retorna el valor si no es NaN/None, o el default."""
    return value if pd.notna(value) else default


def _calcular_greeks(S, K, T, r_rate, sigma, tipo="call"):
    """Calcula Delta, Gamma, Theta y Rho usando OptionGreeks (BSM).
    Retorna dict {"Delta": .., "Gamma": .., "Theta": .., "Rho": ..} o Nones.
    """
    _nones = {"Delta": None, "Gamma": None, "Theta": None, "Rho": None}
    if not _HAS_SCIPY or T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return _nones
    try:
        from core.option_greeks import OptionGreeks
        opt = OptionGreeks(S=S, K=K, T=T, r=r_rate, sigma=sigma)
        side = "call" if tipo == "call" else "put"
        return {
            "Delta": round(opt.delta()[side], 4),
            "Gamma": round(opt.gamma(), 6),
            "Theta": round(opt.theta()[side], 4),
            "Rho":   round(opt.rho()[side], 4),
        }
    except Exception:
        return _nones


# ── Batch vectorizado de Greeks (evita instanciar OptionGreeks por fila) ──

def _calcular_greeks_batch(S, strikes, T_arr, r_rate, iv_arr, tipos):
    """Calcula Greeks para un DataFrame entero en una sola pasada vectorizada.

    Parámetros
    ----------
    S        : float — precio spot del subyacente
    strikes  : np.ndarray — strikes
    T_arr    : np.ndarray — tiempo a vencimiento (años) por fila
    r_rate   : float — tasa libre de riesgo
    iv_arr   : np.ndarray — IV (decimales, no %) por fila
    tipos    : np.ndarray de str — "call" o "put" por fila

    Retorna
    -------
    dict con arrays: Delta, Gamma, Theta, Rho (floats, NaN donde inválido)
    """
    from scipy.stats import norm as _norm_dist

    n = len(strikes)
    delta_out = np.full(n, np.nan)
    gamma_out = np.full(n, np.nan)
    theta_out = np.full(n, np.nan)
    rho_out = np.full(n, np.nan)

    # Máscara de valores válidos
    valid = (T_arr > 0) & (iv_arr > 0) & (strikes > 0) & (S > 0)
    if not valid.any():
        return {"Delta": delta_out, "Gamma": gamma_out, "Theta": theta_out, "Rho": rho_out}

    K = strikes[valid]
    T = T_arr[valid]
    sig = iv_arr[valid]
    tp = tipos[valid]

    vol_sqrt_T = sig * np.sqrt(T)
    d1 = (np.log(S / K) + (r_rate + 0.5 * sig**2) * T) / vol_sqrt_T
    d2 = d1 - vol_sqrt_T

    disc_r = np.exp(-r_rate * T)

    # — Delta —
    is_call = (tp == "call")
    delta_v = np.where(is_call, _norm_dist.cdf(d1), _norm_dist.cdf(d1) - 1)

    # — Gamma (igual para calls y puts) —
    gamma_v = _norm_dist.pdf(d1) / (S * vol_sqrt_T)

    # — Theta (por día calendario) —
    decay = -S * _norm_dist.pdf(d1) * sig / (2.0 * np.sqrt(T))
    theta_call = (decay - r_rate * K * disc_r * _norm_dist.cdf(d2)) / 365.0
    theta_put = (decay + r_rate * K * disc_r * _norm_dist.cdf(-d2)) / 365.0
    theta_v = np.where(is_call, theta_call, theta_put)

    # — Rho (por 1%) —
    rho_call = K * T * disc_r * _norm_dist.cdf(d2) / 100.0
    rho_put = -K * T * disc_r * _norm_dist.cdf(-d2) / 100.0
    rho_v = np.where(is_call, rho_call, rho_put)

    delta_out[valid] = np.round(delta_v, 4)
    gamma_out[valid] = np.round(gamma_v, 6)
    theta_out[valid] = np.round(theta_v, 4)
    rho_out[valid] = np.round(rho_v, 4)

    return {"Delta": delta_out, "Gamma": gamma_out, "Theta": theta_out, "Rho": rho_out}


def _clasificar_lado(last_price, bid, ask):
    """Clasifica si la transacción se ejecutó al Bid, Ask o Mid.
    
    - Ask  → compra agresiva (el comprador paga el precio del vendedor)
    - Bid  → venta agresiva  (el vendedor acepta el precio del comprador)
    - Mid  → ejecutado entre bid y ask
    - N/A  → sin datos suficientes
    """
    if ask <= 0 and bid <= 0:
        return "N/A"
    if last_price <= 0:
        return "N/A"
    if ask > 0 and last_price >= ask:
        return "Ask"
    if bid > 0 and last_price <= bid:
        return "Bid"
    if bid > 0 and ask > 0 and bid < last_price < ask:
        return "Mid"
    return "N/A"


# ============================================================================
#                    SISTEMA ANTI-BANEO
# ============================================================================

# Perfiles TLS para curl_cffi (cada uno impersona un navegador real completo:
# TLS fingerprint + User-Agent + headers — todo consistente automáticamente)
BROWSER_PROFILES = [
    "chrome110", "chrome116", "chrome119", "chrome120", "chrome123", "chrome124",
    "edge99", "edge101",
    "safari15_3", "safari15_5", "safari17_0",
]


# ── Session pool: reutiliza sesiones TLS para evitar handshakes repetidos ──
import threading as _threading
_SESSION_POOL: list = []     # [(session, perfil), ...]
_SESSION_POOL_SIZE = 4       # Máximo de sesiones pre-creadas
_SESSION_POOL_LOCK = _threading.Lock()


def crear_sesion_nueva():
    """Crea sesión HTTP con perfil TLS anti-ban.
    
    Si curl_cffi está disponible: usa impersonate con TLS real de navegador.
    Si no (ej. Streamlit Cloud): usa requests estándar como fallback.
    """
    if _HAS_CURL_CFFI:
        perfil = choice(BROWSER_PROFILES)
        session = CurlSession(impersonate=perfil)
        return session, perfil
    else:
        # Fallback: requests estándar con User-Agent genérico
        session = _fallback_requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session, "requests-fallback"


def _get_pooled_session():
    """Obtiene una sesión del pool o crea una nueva.

    Reutilizar sesiones evita el costo del TLS handshake (~200-500ms)
    en cada llamada a yfinance. El pool rota perfiles para anti-ban.
    """
    with _SESSION_POOL_LOCK:
        if _SESSION_POOL:
            return _SESSION_POOL.pop()
    return crear_sesion_nueva()


def _return_session(session, perfil):
    """Devuelve una sesión al pool si no está lleno."""
    with _SESSION_POOL_LOCK:
        if len(_SESSION_POOL) < _SESSION_POOL_SIZE:
            _SESSION_POOL.append((session, perfil))
    # Si el pool está lleno, la sesión se descarta (GC)


def construir_simbolo_contrato(ticker_sym, exp_date, opt_type, strike):
    """Construye el símbolo del contrato de opción en formato Yahoo Finance.
    Ej: SPY260220C00600000 = SPY, 2026-02-20, CALL, strike 600"""
    parts = exp_date.split("-")
    fecha_fmt = parts[0][2:] + parts[1] + parts[2]  # YYMMDD
    tipo_letra = "C" if opt_type == "CALL" else "P"
    strike_fmt = f"{int(strike * 1000):08d}"
    return f"{ticker_sym}{fecha_fmt}{tipo_letra}{strike_fmt}"


@st.cache_data(ttl=300, show_spinner=False)
def obtener_historial_contrato(contract_symbol):
    """Obtiene el historial de precios de un contrato de opción (cached 5 min).

    Usa tenacity para retry con backoff exponencial + jitter y circuit breaker
    para pausar si yfinance está caído.
    """
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
        logger.warning(
            "Historial %s falló tras retries: %s", contract_symbol, e,
        )
        return pd.DataFrame(), str(e)


@retry_yfinance(max_attempts=4, min_wait=2, max_wait=40)
def _yf_fetch_contract_history(contract_symbol):
    """Fetch interno con retry automático (tenacity).

    Cada intento usa una sesión del pool con TLS fingerprint distinto.
    Si falla, tenacity espera con backoff exponencial + jitter random
    antes del siguiente intento.
    """
    session, perfil = _get_pooled_session()
    try:
        contract = yf.Ticker(contract_symbol, session=session)
        hist = contract.history(period="1mo")
        if hist.empty:
            hist = contract.history(period="5d")
        _return_session(session, perfil)
        return hist
    except Exception as e:
        # Clasificar para que tenacity decida si reintentar
        _maybe_raise_rate_limit(e)
        raise


def _fetch_single_chain(ticker_sym, exp_date, max_retries=3):
    """Obtiene una sola cadena de opciones con retries y caché.

    Función auxiliar para paralelización. Retorna (exp_date, chain_data, error).
    Usa tenacity para retry con backoff exponencial + jitter.
    """
    # Intentar del caché primero
    try:
        chain_data = _cached_option_chain(ticker_sym, exp_date)
        return exp_date, chain_data, None
    except Exception:
        pass

    # Circuit breaker
    try:
        cb_yfinance.check()
    except CircuitOpenError as e:
        return exp_date, None, str(e)

    # Cache miss — fetch con tenacity retry
    try:
        chain_data = _yf_fetch_chain_attempt(ticker_sym, exp_date)
        cb_yfinance.record_success()
        return exp_date, chain_data, None
    except (RetryError, Exception) as e:
        cb_yfinance.record_failure()
        return exp_date, None, str(e)


@retry_yfinance(max_attempts=5, min_wait=4, max_wait=60)
def _yf_fetch_chain_attempt(ticker_sym, exp_date):
    """Fetch interno de cadena con retry automático (tenacity) y jitter anti-flood."""
    # Pausa aleatoria antes de cada intento — esparce requests simultáneos
    time.sleep(uniform(0.5, 1.8))
    rl_yfinance.acquire()
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
    """Convierte excepciones genéricas de yfinance a RateLimitError.

    yfinance envuelve errores HTTP en Exception genérica. Si detectamos
    keywords de rate-limit en el mensaje, convertimos a RateLimitError
    para que tenacity aplique esperas más largas y el circuit breaker
    registre el fallo correctamente.
    """
    msg = str(exc).lower()
    if any(kw in msg for kw in ["429", "rate limit", "too many requests"]):
        raise RateLimitError(str(exc)) from exc


@retry_yfinance(max_attempts=3, min_wait=3, max_wait=30)
def _yf_fetch_options_dates(ticker_sym):
    """Fetch directo de fechas de expiración con retry (tenacity)."""
    session, perfil = crear_sesion_nueva()
    try:
        ticker = yf.Ticker(ticker_sym, session=session)
        return tuple(ticker.options)
    except Exception as e:
        _maybe_raise_rate_limit(e)
        raise


def fetch_with_cache(ticker_sym: str, exp_date: str):
    """Versión con caché Redis + fallback al fetch original."""
    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return exp_date, cached, None

    # Cache miss → fetch normal (función original)
    result = _fetch_single_chain(ticker_sym, exp_date)
    exp_date, chain_data, error = result
    if chain_data is not None:
        cache_chain(ticker_sym, exp_date, chain_data)
    return result


def ejecutar_escaneo(
    ticker_sym, u_vol, u_oi, u_prima, u_filtro, carpeta_csv, guardar, paralelo=True
):
    """Ejecuta un ciclo completo de escaneo y retorna alertas + datos.

    Usa caché TTL: si los datos de una fecha ya se descargaron en los
    últimos 5 minutos, se reutilizan sin hacer nueva petición a Yahoo.
    
    Args:
        paralelo: Si True, procesa múltiples fechas simultáneamente (más rápido)
    """
    alertas = []
    datos = []
    perfil = "cached"

    # Obtener precio subyacente una vez para cálculo de delta
    _precio_sub, _ = obtener_precio_actual(ticker_sym)
    _today = datetime.now()

    # Obtener fechas de expiración (cacheado 5 min)
    try:
        options_dates = _cached_options_dates(ticker_sym)
    except Exception as e:
        # Si falla el caché, intentar directo con tenacity retry
        try:
            cb_yfinance.check()
            options_dates = _yf_fetch_options_dates(ticker_sym)
            cb_yfinance.record_success()
        except CircuitOpenError as ce:
            return [], [], str(ce), perfil, []
        except (RetryError, Exception) as e2:
            cb_yfinance.record_failure()
            return [], [], str(e2), perfil, []

    if not options_dates:
        return [], [], "No se encontraron fechas de vencimiento", perfil, []

    # Limitar fechas para evitar rate-limiting y mejorar performance
    dates_to_scan = list(options_dates)[:MAX_EXPIRATION_DATES]
    
    # Fetch de cadenas de opciones (paralelo o secuencial)
    chains_map = {}  # {exp_date: chain_data}
    
    if paralelo and len(dates_to_scan) > 2:
        # Modo paralelo: máx 2 workers simultáneos para no saturar Yahoo Finance
        logger.info("Escaneo paralelo activado para %d fechas (max_workers=2)", len(dates_to_scan))
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_date = {}
            for _i, _exp in enumerate(dates_to_scan):
                # Escalonar envíos: pequeña pausa entre cada submit
                # evita que Yahoo vea un pico de N requests simultáneos
                if _i > 0:
                    time.sleep(uniform(0.8, 1.5))
                _f = executor.submit(fetch_with_cache, ticker_sym, _exp)
                future_to_date[_f] = _exp

            for future in as_completed(future_to_date):
                exp_date, chain_data, error = future.result()
                if chain_data:
                    chains_map[exp_date] = chain_data
                elif error:
                    # Solo loguear si no es rate-limit (ya fue reintentado por tenacity)
                    _rl = any(kw in str(error).lower() for kw in ["429", "rate limit", "too many"])
                    if _rl:
                        logger.info("Rate-limit en %s (agotados reintentos) — fecha omitida", exp_date)
                    else:
                        logger.warning("Error fetch paralelo %s: %s", exp_date, error)
    else:
        # Modo secuencial — usa _fetch_single_chain que ya tiene tenacity retry
        for idx, exp_date in enumerate(dates_to_scan):
            if idx > 0:
                time.sleep(uniform(*SCAN_SLEEP_RANGE))

            _, chain_data, error = _fetch_single_chain(ticker_sym, exp_date)
            if chain_data:
                chains_map[exp_date] = chain_data
            elif error:
                logger.warning("Error secuencial %s: %s", exp_date, error)
    
    # Procesar todas las cadenas obtenidas — VECTORIZADO

    _now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for exp_date in dates_to_scan:
        chain_data = chains_map.get(exp_date)
        if chain_data is None:
            continue

        try:
            # Calcular DTE una sola vez por fecha
            try:
                exp_dt_d = datetime.strptime(exp_date, "%Y-%m-%d")
                dte_years = max((exp_dt_d - _today).total_seconds() / (365 * 86400), 1e-6)
            except Exception:
                dte_years = 1e-6

            for opt_type, df in [("CALL", chain_data["calls"]), ("PUT", chain_data["puts"])]:
                # Filtrado rápido vectorizado: eliminar filas con volumen=0
                df_f = df[df["volume"].notna() & (df["volume"] > 0)].copy()
                if df_f.empty:
                    continue

                # Extraer arrays (0 donde NaN)
                vol_arr = df_f["volume"].fillna(0).astype(int).values
                oi_arr = df_f["openInterest"].fillna(0).astype(int).values
                iv_arr = df_f["impliedVolatility"].fillna(0).values
                ask_arr = df_f["ask"].fillna(0).values
                bid_arr = df_f["bid"].fillna(0).values
                last_arr = df_f["lastPrice"].fillna(0).values
                strike_arr = df_f["strike"].values

                # Precio para calcular prima: ask si > 0, sino last, sino 0
                price_vol = np.where(ask_arr > 0, ask_arr, np.where(last_arr > 0, last_arr, 0.0))
                prima_arr = vol_arr * price_vol * 100

                # Clasificar lado vectorizado
                lado_arr = np.full(len(df_f), "N/A", dtype=object)
                has_data = (ask_arr > 0) | (bid_arr > 0)
                has_last = last_arr > 0
                lado_arr = np.where(
                    ~has_data | ~has_last, "N/A",
                    np.where(
                        (ask_arr > 0) & (last_arr >= ask_arr), "Ask",
                        np.where(
                            (bid_arr > 0) & (last_arr <= bid_arr), "Bid",
                            np.where(
                                (bid_arr > 0) & (ask_arr > 0) & (bid_arr < last_arr) & (last_arr < ask_arr),
                                "Mid", "N/A"
                            )
                        )
                    )
                )

                # Greeks vectorizados en batch
                tipo_lower = "call" if opt_type == "CALL" else "put"
                tipos_arr = np.full(len(df_f), tipo_lower)
                T_arr = np.full(len(df_f), dte_years)

                if _precio_sub and _HAS_SCIPY:
                    greeks = _calcular_greeks_batch(
                        _precio_sub, strike_arr, T_arr, RISK_FREE_RATE, iv_arr, tipos_arr
                    )
                else:
                    greeks = {
                        "Delta": np.full(len(df_f), np.nan),
                        "Gamma": np.full(len(df_f), np.nan),
                        "Theta": np.full(len(df_f), np.nan),
                        "Rho": np.full(len(df_f), np.nan),
                    }

                # Construir resultados sin iterrows — list comprehension sobre arrays
                iv_pct = np.round(iv_arr * 100, 2)
                ask_r = np.round(ask_arr, 2)
                bid_r = np.round(bid_arr, 2)
                last_r = np.round(last_arr, 2)
                prima_r = np.round(prima_arr, 0)

                for i in range(len(df_f)):
                    d_val = greeks["Delta"][i]
                    g_val = greeks["Gamma"][i]
                    t_val = greeks["Theta"][i]
                    r_val = greeks["Rho"][i]
                    delta = round(float(d_val), 4) if not np.isnan(d_val) else None
                    gamma = round(float(g_val), 6) if not np.isnan(g_val) else None
                    theta = round(float(t_val), 4) if not np.isnan(t_val) else None
                    rho = round(float(r_val), 4) if not np.isnan(r_val) else None

                    datos.append({
                        "Vencimiento": exp_date,
                        "Tipo": opt_type,
                        "Strike": strike_arr[i],
                        "Volumen": int(vol_arr[i]),
                        "OI": int(oi_arr[i]),
                        "Ask": float(ask_r[i]),
                        "Bid": float(bid_r[i]),
                        "Ultimo": float(last_r[i]),
                        "IV": float(iv_pct[i]) if iv_arr[i] else 0,
                        "Prima_Volumen": float(prima_r[i]),
                        "Lado": lado_arr[i],
                        "Delta": delta,
                        "Gamma": gamma,
                        "Theta": theta,
                        "Rho": rho,
                    })

                # Alertas: filtro vectorizado por umbrales
                mask_alerta = (vol_arr >= u_vol) & (oi_arr >= u_oi) & (prima_arr >= u_prima)
                alerta_indices = np.where(mask_alerta)[0]

                for idx in alerta_indices:
                    contract_sym = construir_simbolo_contrato(
                        ticker_sym, exp_date, opt_type, strike_arr[idx]
                    )
                    d_a = greeks["Delta"][idx]
                    g_a = greeks["Gamma"][idx]
                    t_a = greeks["Theta"][idx]
                    r_a = greeks["Rho"][idx]

                    alerta = {
                        "Fecha_Hora": _now_str,
                        "Ticker": ticker_sym,
                        "Tipo_Alerta": "PRINCIPAL",
                        "Tipo_Opcion": opt_type,
                        "Vencimiento": exp_date,
                        "Strike": strike_arr[idx],
                        "Volumen": int(vol_arr[idx]),
                        "OI": int(oi_arr[idx]),
                        "Prima_Volumen": float(prima_r[idx]),
                        "Ask": float(ask_r[idx]),
                        "Bid": float(bid_r[idx]),
                        "Ultimo": float(last_r[idx]),
                        "IV": float(iv_pct[idx]) if iv_arr[idx] else 0,
                        "Contrato": contract_sym,
                        "Lado": lado_arr[idx],
                        "Delta": round(float(d_a), 4) if not np.isnan(d_a) else None,
                        "Gamma": round(float(g_a), 6) if not np.isnan(g_a) else None,
                        "Theta": round(float(t_a), 4) if not np.isnan(t_a) else None,
                        "Rho": round(float(r_a), 4) if not np.isnan(r_a) else None,
                    }
                    alertas.append(alerta)

                    if guardar:
                        guardar_alerta_csv(carpeta_csv, ticker_sym, alerta)

        except Exception:
            continue

    # Devolver SOLO las fechas que fueron efectivamente procesadas (no todas las disponibles).
    # Antes devolvía list(options_dates) — el total disponible en yfinance — lo que mostraba
    # un número mayor al real en el status bar y ocultaba fechas que no llegaron a escanearse
    # por el límite MAX_EXPIRATION_DATES o por fallos de red en modo paralelo.
    fechas_procesadas = [d for d in dates_to_scan if d in chains_map]
    return alertas, datos, None, perfil, fechas_procesadas


def get_oi_matrix(
    datos: list[dict],
    expiration_filter: str | None = None,
    min_oi: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye la matriz OI (Strike × Expiración) para heatmap interactivo.

    Opera sobre los datos ya descargados por ``ejecutar_escaneo`` (almacenados
    en ``st.session_state.datos_completos``), sin hacer peticiones HTTP extra.

    Cómo ayuda a decisiones de inversión
    ------------------------------------
    * **Clusters de OI** → niveles donde creadores de mercado tienen
      exposición gamma significativa.  Funcionan como imanes de precio.
    * **Expiración dominante** → identifica dónde vence la mayor parte
      de la exposición institucional (pin risk).
    * **Filtro min_oi** → elimina ruido retail y deja solo niveles
      con liquidez real.

    Args:
        datos: Lista de dicts del escaneo.
        expiration_filter: Filtrar por un vencimiento específico (``None`` = todos).
        min_oi: Umbral mínimo de OI a incluir (contratos con OI < min_oi se descartan).

    Returns:
        ``(oi_matrix, df_filtered)``

        * ``oi_matrix``   — ``pd.DataFrame`` pivotado (filas = Vencimiento,
          columnas = Strike, valores = OI sumado).
        * ``df_filtered`` — ``pd.DataFrame`` plano filtrado con todas las
          columnas originales (útil para hover data: Volumen, Delta, IV …).

    Example (pytest)::

        >>> datos = [
        ...     {"Vencimiento": "2026-03-20", "Strike": 590, "OI": 5000,
        ...      "Volumen": 300, "Delta": 0.55, "Tipo": "CALL", "IV": 18.2,
        ...      "Prima_Volumen": 150000, "Ask": 5.2, "Bid": 5.0, "Ultimo": 5.1, "Lado": "Ask"},
        ...     {"Vencimiento": "2026-03-20", "Strike": 600, "OI": 800,
        ...      "Volumen": 50, "Delta": -0.30, "Tipo": "PUT", "IV": 22.1,
        ...      "Prima_Volumen": 25000, "Ask": 3.1, "Bid": 2.9, "Ultimo": 3.0, "Lado": "Bid"},
        ... ]
        >>> matrix, df_f = get_oi_matrix(datos, min_oi=1000)
        >>> assert matrix.shape == (1, 1)          # solo el strike 590 pasa el filtro
        >>> assert df_f.shape[0] == 1
    """
    if not datos:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(datos)

    # Normalizar nombre de prima
    if "Prima_Volumen" in df.columns and "Prima_Vol" not in df.columns:
        df = df.rename(columns={"Prima_Volumen": "Prima_Vol"})

    # Filtro por expiración
    if expiration_filter:
        df = df[df["Vencimiento"] == expiration_filter]

    # Filtro por OI mínimo
    if min_oi > 0 and "OI" in df.columns:
        df = df[df["OI"] >= min_oi]

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    oi_matrix = df.pivot_table(
        values="OI",
        index="Vencimiento",
        columns="Strike",
        aggfunc="sum",
    ).fillna(0)

    return oi_matrix, df


def calculate_call_put_bias(datos: list[dict]) -> dict:
    """Calcula el sesgo alcista/bajista basándose en el ratio Call/Put de OI.

    Cómo ayuda a decisiones de inversión
    ------------------------------------
    * **Score > 1.2** → Dominio de Calls → el mercado de opciones está
      posicionado para un movimiento alcista.  Considerar spreads alcistas.
    * **Score < 0.8** → Dominio de Puts → presión de cobertura/bajista.
      Precaución con posiciones largas sin protección.
    * **Score ≈ 1.0** → Equilibrio → sin sesgo claro; esperar confirmación
      de volumen o precio antes de operar.

    El score usa **Open Interest total** (no volumen) porque el OI
    refleja posiciones *abiertas* reales, no solo actividad intradía.

    Fórmula:
        ``bias_score = 2 × (OI_calls / (OI_calls + OI_puts))``

        Escala 0–2: 0=fuertemente bajista, 1=neutral, 2=fuertemente alcista.

    Args:
        datos: Lista de dicts del escaneo (``st.session_state.datos_completos``).

    Returns:
        ``dict`` con claves:
        - ``bias_score`` (float): Valor 0–2.
        - ``oi_calls`` (int): OI total de Calls.
        - ``oi_puts`` (int): OI total de Puts.
        - ``ratio_raw`` (float): OI_calls / OI_puts (o inf si 0 puts).
        - ``total_oi`` (int): OI total.

    Example (pytest)::

        >>> datos = [
        ...     {"Tipo": "CALL", "OI": 5000, "Volumen": 300},
        ...     {"Tipo": "PUT",  "OI": 3000, "Volumen": 200},
        ... ]
        >>> r = calculate_call_put_bias(datos)
        >>> assert 1.0 < r['bias_score'] < 2.0  # calls dominan
        >>> assert r['oi_calls'] == 5000
        >>> assert r['oi_puts'] == 3000
    """
    result = {
        "bias_score": 1.0,
        "oi_calls": 0,
        "oi_puts": 0,
        "ratio_raw": 1.0,
        "total_oi": 0,
    }

    if not datos:
        return result

    df = pd.DataFrame(datos)
    if "Tipo" not in df.columns or "OI" not in df.columns:
        return result

    df["OI"] = pd.to_numeric(df["OI"], errors="coerce").fillna(0)

    oi_calls = int(df.loc[df["Tipo"] == "CALL", "OI"].sum())
    oi_puts = int(df.loc[df["Tipo"] == "PUT", "OI"].sum())
    total = oi_calls + oi_puts

    if total == 0:
        return result

    ratio = oi_calls / total  # 0–1
    bias_score = round(2.0 * ratio, 2)  # 0–2
    raw = round(oi_calls / oi_puts, 3) if oi_puts > 0 else float("inf")

    return {
        "bias_score": bias_score,
        "oi_calls": oi_calls,
        "oi_puts": oi_puts,
        "ratio_raw": raw,
        "total_oi": total,
    }


def guardar_alerta_csv(carpeta, ticker_sym, alerta):
    """Guarda una alerta individual en el archivo CSV diario."""
    try:
        os.makedirs(carpeta, exist_ok=True)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        csv_path = os.path.join(carpeta, f"alertas_{ticker_sym}_{fecha_hoy}.csv")
        escribir_header = not os.path.exists(csv_path)

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Fecha_Hora", "Ticker", "Tipo_Alerta", "Tipo_Opcion",
                    "Vencimiento", "Strike", "Volumen", "OI",
                    "Prima_Total", "Ask", "Bid", "Ultimo", "Lado",
                ],
            )
            if escribir_header:
                writer.writeheader()
            # Renombrar Prima_Volumen a Prima_Total para el CSV (claridad para el usuario)
            alerta_csv = alerta.copy()
            if "Prima_Volumen" in alerta_csv:
                alerta_csv["Prima_Total"] = alerta_csv.pop("Prima_Volumen")
            writer.writerow(alerta_csv)
    except Exception as e:
        logger.error("Error guardando alerta CSV: %s", e)
