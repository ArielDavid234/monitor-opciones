"""
Scanner de opciones: sesiones anti-ban, escaneo de cadenas,
construcción de símbolos y persistencia CSV.

Incluye sistema de caché TTL para evitar rate-limiting de Yahoo Finance.
"""
import os
import time
import logging
from collections import deque
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

from config.constants import MAX_EXPIRATION_DATES, RISK_FREE_RATE
from config.settings import get_settings
from core.scanner_analysis import calculate_call_put_bias, get_oi_matrix
from core.scanner_greeks import (
    _HAS_SCIPY,
    _calcular_greeks,
    _calcular_greeks_batch,
    _clasificar_lado,
    _safe_num,
)
from core.scanner_storage import guardar_alerta_csv
from infrastructure.data.async_fetcher import get_multiple_chains_fast
from infrastructure.data.provider_runtime import (
    get_budget_manager,
    get_provider_metrics,
    record_scan_metadata,
    request_channel,
)
from infrastructure.platform.health import global_health_status
from infrastructure.data.yahoo_finance_client import (
    _cached_history,
    _cached_option_chain,
    _cached_options_dates,
    cache_chain,
    crear_sesion_nueva,
    fetch_options_dates,
    fetch_single_chain,
    get_cached_chain,
    get_active_provider,
    limpiar_cache_ticker,
    obtener_historial_contrato,
    obtener_precio_actual,
)

# Compatibilidad hacia atrás para imports existentes
_fetch_single_chain = fetch_single_chain
_SCAN_METRICS_WINDOW = deque(maxlen=100)
_SCAN_COUNTER = 0
_LAST_SCAN_RUNTIME_META: dict[str, float | int | str] = {}

__all__ = [
    "_cached_history",
    "_cached_option_chain",
    "_cached_options_dates",
    "crear_sesion_nueva",
    "limpiar_cache_ticker",
    "obtener_historial_contrato",
    "obtener_precio_actual",
    "construir_simbolo_contrato",
    "fetch_with_cache",
    "ejecutar_escaneo",
    "get_oi_matrix",
    "calculate_call_put_bias",
    "guardar_alerta_csv",
    "_safe_num",
    "_calcular_greeks",
    "_calcular_greeks_batch",
    "_clasificar_lado",
    "get_last_scan_runtime_meta",
]


def get_last_scan_runtime_meta() -> dict[str, float | int | str]:
    return dict(_LAST_SCAN_RUNTIME_META)


def _friendly_scan_error(raw_error: str | None, has_cached_snapshot: bool = False) -> str:
    text = str(raw_error or "").lower()
    if any(tok in text for tok in ["429", "rate limit", "quota", "too many", "límite"]):
        base = "datos parciales: el proveedor alcanzó una cuota temporal"
        if has_cached_snapshot:
            return f"{base}; mostrando último snapshot en cache; reintentar en 60 segundos"
        return f"{base}; reintentar en 60 segundos"
    if "timeout" in text:
        return "datos parciales: timeout temporal del proveedor; reintentar en 30 segundos"
    if has_cached_snapshot:
        return "datos parciales: mostrando último snapshot en cache"
    return "datos parciales: servicio de datos temporalmente no disponible; reintentar en 30 segundos"


def _log_periodic_scan_summary() -> None:
    global _SCAN_COUNTER
    cfg = get_settings()
    every_n = max(int(getattr(cfg, "scan_summary_every_n", 10)), 1)
    if _SCAN_COUNTER <= 0 or _SCAN_COUNTER % every_n != 0:
        return

    samples = list(_SCAN_METRICS_WINDOW)
    if not samples:
        return

    scan_ms = np.array([s["scan_total_time_ms"] for s in samples], dtype=float)
    hit_ratio = np.array([s["cache_hit_ratio"] for s in samples], dtype=float)
    p50_ms = float(np.percentile(scan_ms, 50)) if len(scan_ms) > 1 else float(scan_ms[0])
    p90_ms = float(np.percentile(scan_ms, 90)) if len(scan_ms) > 1 else float(scan_ms[0])
    p99_ms = float(np.percentile(scan_ms, 99)) if len(scan_ms) > 1 else float(scan_ms[0])
    avg_hit = float(np.mean(hit_ratio))
    metrics = get_provider_metrics()
    m = metrics.snapshot()
    budget = get_budget_manager().snapshot()
    recent_429 = metrics.get_429_last_5m()

    logger.info(
        "slo summary | scans=%d | scan_latency_ms_p50=%.0f | scan_latency_ms_p90=%.0f | scan_latency_ms_p99=%.0f | cache_hit_ratio=%.3f | snapshot_hit_ratio=%.3f | provider_calls_per_min=%d | provider_429_count=%d | provider_429_5m=%d | chain_fetch_failures=%d | degraded_mode_activations=%d",
        _SCAN_COUNTER,
        p50_ms,
        p90_ms,
        p99_ms,
        avg_hit,
        float(m.get("snapshot_hit_ratio", 0.0)),
        int(budget.get("used_total", 0)),
        m.get("provider_429_count", 0),
        recent_429,
        m.get("chain_fetch_failures", 0),
        m.get("degraded_mode_activations", 0),
    )

    if p90_ms > float(getattr(cfg, "scan_alert_p90_ms", 60000)):
        logger.error("ALERT scan_p90_high | p90_ms=%.0f | threshold_ms=%s", p90_ms, getattr(cfg, "scan_alert_p90_ms", 60000))
    if recent_429 > int(getattr(cfg, "scan_alert_429_5m", 25)):
        logger.error("ALERT provider_429_high | count_5m=%d | threshold=%s", recent_429, getattr(cfg, "scan_alert_429_5m", 25))
    if avg_hit < float(getattr(cfg, "scan_alert_cache_hit_ratio_min", 0.35)):
        logger.error(
            "ALERT cache_hit_ratio_low | ratio=%.3f | threshold=%s",
            avg_hit,
            getattr(cfg, "scan_alert_cache_hit_ratio_min", 0.35),
        )

    health = global_health_status()
    logger.info(
        "platform health summary | overall=%s | provider=%s | cache=%s | repository=%s",
        health.get("overall", "unknown"),
        next((c.get("status") for c in health.get("checks", []) if c.get("name") == "provider"), "unknown"),
        next((c.get("status") for c in health.get("checks", []) if c.get("name") == "cache"), "unknown"),
        next((c.get("status") for c in health.get("checks", []) if c.get("name") == "repository"), "unknown"),
    )


def construir_simbolo_contrato(ticker_sym, exp_date, opt_type, strike):
    """Construye el símbolo del contrato de opción en formato Yahoo Finance.
    Ej: SPY260220C00600000 = SPY, 2026-02-20, CALL, strike 600"""
    parts = exp_date.split("-")
    fecha_fmt = parts[0][2:] + parts[1] + parts[2]  # YYMMDD
    tipo_letra = "C" if opt_type == "CALL" else "P"
    strike_fmt = f"{int(strike * 1000):08d}"
    return f"{ticker_sym}{fecha_fmt}{tipo_letra}{strike_fmt}"


def fetch_with_cache(ticker_sym: str, exp_date: str):
    """Compat wrapper mantenido para integraciones legacy."""
    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return exp_date, cached, None
    result = _fetch_single_chain(ticker_sym, exp_date)
    _exp, chain_data, _error = result
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
    _scan_start_ts = time.perf_counter()
    _provider_before = get_provider_metrics().snapshot()
    _cache_hits = 0
    _cache_misses = 0
    _async_downloaded = 0
    _fallback_sync_used = 0
    _expirations_processed = 0
    _provider = get_active_provider()

    def _log_scan_telemetry() -> None:
        global _SCAN_COUNTER
        global _LAST_SCAN_RUNTIME_META
        _elapsed = time.perf_counter() - _scan_start_ts
        _elapsed_ms = _elapsed * 1000.0
        _ratio = _cache_hits / max(_cache_hits + _cache_misses, 1)
        _provider_metrics = get_provider_metrics().snapshot()
        _provider_calls_delta = int(_provider_metrics.get("provider_request_count", 0)) - int(
            _provider_before.get("provider_request_count", 0)
        )
        _snapshot_hits_delta = int(_provider_metrics.get("snapshot_hits", 0)) - int(
            _provider_before.get("snapshot_hits", 0)
        )
        _snapshot_misses_delta = int(_provider_metrics.get("snapshot_misses", 0)) - int(
            _provider_before.get("snapshot_misses", 0)
        )
        _source = "cache" if _cache_misses == 0 else "live"
        _market_schema_version = os.getenv("MARKET_SCHEMA_VERSION", "v1").strip() or "v1"
        _snapshot_schema_version = os.getenv("SNAPSHOT_SCHEMA_VERSION", "v1").strip() or "v1"
        record_scan_metadata(
            ticker=ticker_sym,
            provider=_provider,
            market_schema_version=_market_schema_version,
            snapshot_schema_version=_snapshot_schema_version,
            source=_source,
            latency_ms=_elapsed_ms,
        )
        logger.info(
            "scan telemetry | provider=%s | ticker=%s | schema_market=%s | schema_snapshot=%s | source=%s | scan_total_time_ms=%.0f | scan_latency_ms=%.0f | cache_hits=%d | cache_misses=%d | cache_hit_ratio=%.3f | async_chains=%d | expirations_processed=%d | fallbacks_used=%d | provider_request_count=%d | provider_429_count=%d | chain_fetch_failures=%d | snapshot_hit_ratio=%.3f | degraded_mode_activations=%d",
            _provider,
            ticker_sym,
            _market_schema_version,
            _snapshot_schema_version,
            _source,
            _elapsed_ms,
            _elapsed_ms,
            _cache_hits,
            _cache_misses,
            _ratio,
            _async_downloaded,
            _expirations_processed,
            _fallback_sync_used,
            _provider_metrics.get("provider_request_count", 0),
            _provider_metrics.get("provider_429_count", 0),
            _provider_metrics.get("chain_fetch_failures", 0),
            float(_provider_metrics.get("snapshot_hit_ratio", 0.0)),
            _provider_metrics.get("degraded_mode_activations", 0),
        )
        _SCAN_COUNTER += 1
        _LAST_SCAN_RUNTIME_META = {
            "provider_calls": max(_provider_calls_delta, 0),
            "cache_hits": max(_snapshot_hits_delta, 0),
            "cache_misses": max(_snapshot_misses_delta, 0),
            "cpu_seconds": round(_elapsed, 4),
            "source": _source,
            "provider": _provider,
            "latency_ms": round(_elapsed_ms, 2),
        }
        _SCAN_METRICS_WINDOW.append(
            {
                "scan_total_time_ms": _elapsed_ms,
                "cache_hit_ratio": _ratio,
            }
        )
        _log_periodic_scan_summary()

    alertas = []
    datos = []
    perfil = "cached"

    # Obtener precio subyacente una vez para cálculo de delta
    with request_channel("live_scanning"):
        _precio_sub, _ = obtener_precio_actual(ticker_sym)
    _today = datetime.now()

    # Obtener fechas de expiracion via capa de infraestructura
    try:
        with request_channel("live_scanning"):
            options_dates = fetch_options_dates(ticker_sym)
    except Exception as e:
        _log_scan_telemetry()
        return [], [], _friendly_scan_error(str(e)), perfil, []

    if not options_dates:
        _log_scan_telemetry()
        return [], [], _friendly_scan_error("no expiration dates"), perfil, []

    # Limitar fechas para evitar rate-limiting y mejorar performance
    dates_to_scan = list(options_dates)[:MAX_EXPIRATION_DATES]
    
    # Fetch de cadenas: cache primero, luego bulk async para fechas faltantes
    chains_map = {}  # {exp_date: chain_data}
    missing_dates = []
    for exp_date in dates_to_scan:
        cached = get_cached_chain(ticker_sym, exp_date)
        if cached is not None:
            chains_map[exp_date] = cached
            _cache_hits += 1
        else:
            missing_dates.append(exp_date)
            _cache_misses += 1

    if missing_dates:
        try:
            logger.info(
                "Escaneo async bulk para %d fechas faltantes (%s)",
                len(missing_dates),
                ticker_sym,
            )
            async_chains = get_multiple_chains_fast(ticker_sym, missing_dates)
            for exp_date, chain_data in async_chains.items():
                if not isinstance(chain_data, dict):
                    continue
                _calls = chain_data.get("calls")
                _puts = chain_data.get("puts")
                if _calls is None or _puts is None:
                    continue
                chains_map[exp_date] = chain_data
                _async_downloaded += 1
                if not (_calls.empty and _puts.empty):
                    cache_chain(ticker_sym, exp_date, chain_data)
        except Exception as e:
            logger.warning("Fallo async bulk %s: %s", ticker_sym, e)

    # Fallback puntual para fechas que aun no se pudieron obtener
    still_missing = [d for d in dates_to_scan if d not in chains_map]
    for idx, exp_date in enumerate(still_missing):
        _fallback_sync_used += 1
        # Sleep removido para evitar estrangulamiento pasivo del fallback sync.
        with request_channel("live_scanning"):
            _, chain_data, error = _fetch_single_chain(ticker_sym, exp_date)
        if chain_data:
            chains_map[exp_date] = chain_data
        elif error:
            get_provider_metrics().record_chain_failure()
            logger.warning("Error fallback %s: %s", exp_date, error)
    
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
    _expirations_processed = len(fechas_procesadas)
    if not fechas_procesadas and not datos:
        _log_scan_telemetry()
        return alertas, datos, _friendly_scan_error("empty chains", has_cached_snapshot=False), perfil, fechas_procesadas
    _log_scan_telemetry()
    return alertas, datos, None, perfil, fechas_procesadas


