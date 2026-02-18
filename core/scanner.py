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
import pandas as pd
import yfinance as yf
from datetime import datetime
from functools import wraps
from random import uniform, choice
from curl_cffi.requests import Session as CurlSession

from config.constants import SCAN_SLEEP_RANGE, MAX_EXPIRATION_DATES
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# ============================================================================
#                    CACHE TTL (evita rate-limiting)
# ============================================================================
# Basado en lru_cache pero con expiración temporal.
# Si los datos ya fueron descargados en los últimos `ttl` segundos,
# se devuelven desde memoria sin hacer una nueva petición a Yahoo Finance.

def ttl_cache(ttl_seconds=300, maxsize=128):
    """Decorador de caché con TTL (time-to-live).

    Similar a @lru_cache pero los datos expiran después de `ttl_seconds`.
    - maxsize: máximo de entradas en caché (evita memory leaks)
    - Cada entrada guarda (resultado, timestamp)
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
            cache[key] = (result, now)
            # Evictar entradas viejas si el cache crece mucho
            if len(cache) > maxsize:
                oldest = min(cache, key=lambda k: cache[k][1])
                del cache[oldest]
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

@ttl_cache(ttl_seconds=300, maxsize=64)
def _cached_options_dates(ticker_sym):
    """Obtiene y cachea las fechas de expiración por 5 min."""
    session, _ = crear_sesion_nueva()
    ticker = yf.Ticker(ticker_sym, session=session)
    return tuple(ticker.options)  # tuple para ser hashable


@ttl_cache(ttl_seconds=300, maxsize=256)
def _cached_option_chain(ticker_sym, exp_date):
    """Obtiene y cachea la cadena de opciones por 5 min."""
    session, _ = crear_sesion_nueva()
    ticker = yf.Ticker(ticker_sym, session=session)
    chain = ticker.option_chain(exp_date)
    # Convertir a dict para almacenar en caché
    return {"calls": chain.calls.copy(), "puts": chain.puts.copy()}


@ttl_cache(ttl_seconds=300, maxsize=32)
def _cached_history(ticker_sym, period="1d"):
    """Obtiene y cachea el historial de precios por 5 min."""
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
        _cached_history.cache_invalidate(ticker_sym, "5d")
        logger.info("Cache limpiado para ticker: %s", ticker_sym)


def obtener_precio_actual(ticker_sym):
    """Obtiene el precio actual usando caché TTL (evita rate-limiting).

    Returns: (precio_float, None) o (None, str_error)
    """
    try:
        hist = _cached_history(ticker_sym, "1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1]), None
        return None, "Sin datos de precio"
    except Exception as e:
        return None, str(e)


def _safe_num(value, default=0):
    """Retorna el valor si no es NaN/None, o el default."""
    return value if pd.notna(value) else default


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


def crear_sesion_nueva():
    """Crea sesión curl_cffi con perfil TLS aleatorio.
    
    curl_cffi con impersonate= ya configura automáticamente:
    - TLS fingerprint del navegador real
    - User-Agent correcto para ese navegador
    - Headers HTTP consistentes (Accept, Accept-Language, etc.)
    
    NO sobrescribimos headers para evitar inconsistencias TLS↔HTTP
    que Yahoo Finance detecta como bot.
    """
    perfil = choice(BROWSER_PROFILES)
    session = CurlSession(impersonate=perfil)
    return session, perfil


def construir_simbolo_contrato(ticker_sym, exp_date, opt_type, strike):
    """Construye el símbolo del contrato de opción en formato Yahoo Finance.
    Ej: SPY260220C00600000 = SPY, 2026-02-20, CALL, strike 600"""
    parts = exp_date.split("-")
    fecha_fmt = parts[0][2:] + parts[1] + parts[2]  # YYMMDD
    tipo_letra = "C" if opt_type == "CALL" else "P"
    strike_fmt = f"{int(strike * 1000):08d}"
    return f"{ticker_sym}{fecha_fmt}{tipo_letra}{strike_fmt}"


def obtener_historial_contrato(contract_symbol):
    """Obtiene el historial de precios de un contrato de opción."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            session, _ = crear_sesion_nueva()
            contract = yf.Ticker(contract_symbol, session=session)
            hist = contract.history(period="1mo")
            if hist.empty:
                hist = contract.history(period="5d")
            return hist, None
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = any(
                kw in error_msg
                for kw in ["429", "rate limit", "too many requests"]
            )
            if attempt < max_retries - 1:
                wait = 2 * (2 ** attempt) if is_rate_limit else uniform(0.8, 1.5)
                logger.warning(
                    "Error en historial %s (intento %d/%d): %s. Esperando %.1fs...",
                    contract_symbol, attempt + 1, max_retries, e, wait,
                )
                time.sleep(wait)
            else:
                return pd.DataFrame(), str(e)


def _fetch_single_chain(ticker_sym, exp_date, max_retries=3):
    """Obtiene una sola cadena de opciones con retries y caché.
    
    Función auxiliar para paralelización. Retorna (exp_date, chain_data, error).
    """
    # Intentar del caché primero
    try:
        chain_data = _cached_option_chain(ticker_sym, exp_date)
        return exp_date, chain_data, None
    except Exception:
        pass
    
    # Cache miss — fetch con retries
    for attempt in range(max_retries):
        try:
            session, _ = crear_sesion_nueva()
            ticker = yf.Ticker(ticker_sym, session=session)
            raw_chain = ticker.option_chain(exp_date)
            chain_data = {"calls": raw_chain.calls.copy(), "puts": raw_chain.puts.copy()}
            return exp_date, chain_data, None
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = any(
                kw in error_msg for kw in ["429", "rate limit", "too many requests"]
            )
            if attempt < max_retries - 1:
                wait = 2 * (2 ** attempt) if is_rate_limit else uniform(0.8, 1.5)
                time.sleep(wait)
            else:
                return exp_date, None, str(e)


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

    # Obtener fechas de expiración (cacheado 5 min)
    try:
        options_dates = _cached_options_dates(ticker_sym)
    except Exception as e:
        # Si falla el caché, intentar directo con retries
        options_dates = None
        for attempt in range(3):
            try:
                session, perfil = crear_sesion_nueva()
                ticker = yf.Ticker(ticker_sym, session=session)
                options_dates = tuple(ticker.options)
                break
            except Exception as e2:
                if attempt < 2:
                    time.sleep(5 * (3 ** attempt))
                else:
                    return [], [], str(e2), perfil, []
        if not options_dates:
            return [], [], str(e), perfil, []

    if not options_dates:
        return [], [], "No se encontraron fechas de vencimiento", perfil, []

    # Limitar fechas para evitar rate-limiting y mejorar performance
    dates_to_scan = list(options_dates)[:MAX_EXPIRATION_DATES]
    
    # Fetch de cadenas de opciones (paralelo o secuencial)
    chains_map = {}  # {exp_date: chain_data}
    
    if paralelo and len(dates_to_scan) > 2:
        # Modo paralelo: fetch múltiples fechas simultáneamente
        logger.info("Escaneo paralelo activado para %d fechas", len(dates_to_scan))
        with ThreadPoolExecutor(max_workers=min(4, len(dates_to_scan))) as executor:
            future_to_date = {
                executor.submit(_fetch_single_chain, ticker_sym, exp_date): exp_date
                for exp_date in dates_to_scan
            }
            
            for future in as_completed(future_to_date):
                exp_date, chain_data, error = future.result()
                if chain_data:
                    chains_map[exp_date] = chain_data
                elif error:
                    logger.warning("Error fetch paralelo %s: %s", exp_date, error)
    else:
        # Modo secuencial (original) — fallback para pocas fechas
        max_retries = 3
        for idx, exp_date in enumerate(dates_to_scan):
            if idx > 0:
                time.sleep(uniform(*SCAN_SLEEP_RANGE))

            # Intentar obtener del caché primero
            chain_data = None
            try:
                chain_data = _cached_option_chain(ticker_sym, exp_date)
            except Exception:
                # Cache miss o error — retry con backoff
                for attempt in range(max_retries):
                    try:
                        session, perfil = crear_sesion_nueva()
                        ticker_retry = yf.Ticker(ticker_sym, session=session)
                        raw_chain = ticker_retry.option_chain(exp_date)
                        chain_data = {"calls": raw_chain.calls.copy(), "puts": raw_chain.puts.copy()}
                        break
                    except Exception as e:
                        error_msg = str(e).lower()
                        is_rate_limit = any(
                            kw in error_msg
                            for kw in ["429", "rate limit", "too many requests"]
                        )
                        if attempt < max_retries - 1:
                            wait = 2 * (2 ** attempt) if is_rate_limit else uniform(0.8, 1.5)
                            logger.warning(
                                "Error en %s (intento %d/%d). Esperando %.0fs...",
                                exp_date, attempt + 1, max_retries, wait,
                            )
                            time.sleep(wait)
                        else:
                            logger.warning(
                                "Falló después de %d intentos en %s: %s",
                                max_retries, exp_date, e,
                            )

            if chain_data:
                chains_map[exp_date] = chain_data
    
    # Procesar todas las cadenas obtenidas
    for exp_date in dates_to_scan:
        chain_data = chains_map.get(exp_date)
        if chain_data is None:
            continue

        try:
            for opt_type, df in [("CALL", chain_data["calls"]), ("PUT", chain_data["puts"])]:
                # Filtrado rápido: eliminar filas con volumen=0 antes de iterar
                df_filtered = df[df["volume"].notna() & (df["volume"] > 0)].copy()
                
                for _, row in df_filtered.iterrows():
                    vol = int(_safe_num(row["volume"]))
                    oi = int(_safe_num(row["openInterest"]))

                    iv = _safe_num(row.get("impliedVolatility", 0))
                    ask_val = _safe_num(row.get("ask", 0))
                    bid_val = _safe_num(row.get("bid", 0))
                    last_val = _safe_num(row.get("lastPrice", 0))
                    price_volume = (
                        ask_val if ask_val > 0 else (last_val if last_val > 0 else 0)
                    )

                    volume_premium = vol * price_volume * 100

                    lado = _clasificar_lado(last_val, bid_val, ask_val)

                    datos.append(
                        {
                            "Vencimiento": exp_date,
                            "Tipo": opt_type,
                            "Strike": row["strike"],
                            "Volumen": vol,
                            "OI": oi,
                            "Ask": round(ask_val, 2),
                            "Bid": round(bid_val, 2),
                            "Ultimo": round(last_val, 2),
                            "IV": round(iv * 100, 2) if iv else 0,
                            "Prima_Volumen": round(volume_premium, 0),
                            "Lado": lado,
                        }
                    )

                    # Filtrar por los tres umbrales: volumen, OI y prima
                    if vol < u_vol or oi < u_oi or volume_premium < u_prima:
                        continue

                    # Si llega aquí, pasó todos los umbrales → es alerta PRINCIPAL
                    tipo_alerta = "PRINCIPAL"

                    if tipo_alerta:
                        contract_sym = construir_simbolo_contrato(
                            ticker_sym, exp_date, opt_type, row["strike"]
                        )
                        alerta = {
                            "Fecha_Hora": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "Ticker": ticker_sym,
                            "Tipo_Alerta": tipo_alerta,
                            "Tipo_Opcion": opt_type,
                            "Vencimiento": exp_date,
                            "Strike": row["strike"],
                            "Volumen": vol,
                            "OI": oi,
                            "Prima_Volumen": round(volume_premium, 0),
                            "Ask": round(ask_val, 2),
                            "Bid": round(bid_val, 2),
                            "Ultimo": round(last_val, 2),
                            "IV": round(iv * 100, 2) if iv else 0,
                            "Contrato": contract_sym,
                            "Lado": lado,
                        }
                        alertas.append(alerta)

                        if guardar:
                            guardar_alerta_csv(carpeta_csv, ticker_sym, alerta)

        except Exception:
            continue

    return alertas, datos, None, perfil, list(options_dates)


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


def cargar_historial_csv(carpeta):
    """Carga todos los archivos CSV de alertas históricas."""
    if not os.path.exists(carpeta):
        return pd.DataFrame()

    archivos = glob.glob(os.path.join(carpeta, "alertas_*.csv"))
    if not archivos:
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            df = pd.read_csv(archivo, encoding="utf-8")
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            logger.warning("Error leyendo CSV %s: %s", archivo, e)
            continue

    if not dfs:
        return pd.DataFrame()
    
    result_df = pd.concat(dfs, ignore_index=True)
    
    # Compatibilidad: renombrar Prima_Volumen a Prima_Total si existe (CSVs antiguos)
    if "Prima_Volumen" in result_df.columns:
        result_df = result_df.rename(columns={"Prima_Volumen": "Prima_Total"})
    
    return result_df
