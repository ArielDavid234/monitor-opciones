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
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import scipy.stats  # noqa: F401 – presence check for greeks guard
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

from config.constants import MAX_EXPIRATION_DATES, RISK_FREE_RATE
from infrastructure.data.async_fetcher import get_multiple_chains_fast
from infrastructure.data.yahoo_finance_client import (
    _cached_history,
    _cached_option_chain,
    _cached_options_dates,
    cache_chain,
    crear_sesion_nueva,
    fetch_options_dates,
    fetch_single_chain,
    get_cached_chain,
    limpiar_cache_ticker,
    obtener_historial_contrato,
    obtener_precio_actual,
)

# Compatibilidad hacia atrás para imports existentes
_fetch_single_chain = fetch_single_chain


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
    _cache_hits = 0
    _async_downloaded = 0
    _fallback_sync_used = 0

    def _log_scan_telemetry() -> None:
        _elapsed = time.perf_counter() - _scan_start_ts
        logger.info(
            "scan telemetry | ticker=%s | total_time=%.2fs | cache_chains=%d | async_chains=%d | fallback_sync_chains=%d",
            ticker_sym,
            _elapsed,
            _cache_hits,
            _async_downloaded,
            _fallback_sync_used,
        )

    alertas = []
    datos = []
    perfil = "cached"

    # Obtener precio subyacente una vez para cálculo de delta
    _precio_sub, _ = obtener_precio_actual(ticker_sym)
    _today = datetime.now()

    # Obtener fechas de expiracion via capa de infraestructura
    try:
        options_dates = fetch_options_dates(ticker_sym)
    except Exception as e:
        _log_scan_telemetry()
        return [], [], str(e), perfil, []

    if not options_dates:
        _log_scan_telemetry()
        return [], [], "No se encontraron fechas de vencimiento", perfil, []

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
        _, chain_data, error = _fetch_single_chain(ticker_sym, exp_date)
        if chain_data:
            chains_map[exp_date] = chain_data
        elif error:
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
    _log_scan_telemetry()
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
