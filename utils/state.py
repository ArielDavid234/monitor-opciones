# -*- coding: utf-8 -*-
"""
Inicialización y gestión centralizada del Session State.

Provee:
  - _DEFAULTS: valores iniciales de todas las claves, organizadas por página.
  - initialize_session_state(): inicializa _DEFAULTS + carga favoritos/watchlist.
  - save_page_data(page_key, data_dict): persiste datos de una página con prefijo.
  - load_page_data(page_key, keys): lee datos de una página desde session_state.
  - persist_shared_state(current_ticker): valida coherencia del estado entre páginas.
"""
import streamlit as st

from config.constants import (
    DEFAULT_MIN_VOLUME, DEFAULT_MIN_OI, DEFAULT_MIN_PRIMA,
    DEFAULT_TARGET_DELTA, DEFAULT_TICKER,
)
from utils.favorites import _cargar_favoritos, _cargar_watchlist

# ============================================================================
#                    VALORES POR DEFECTO DEL SESSION STATE
# ============================================================================
_DEFAULTS = {
    # ── Core de escaneo (Live Scanning) ── prefijo: sin prefijo (legado) ──
    "alertas_actuales": [],
    "datos_completos": [],
    "scan_count": 0,
    "last_scan_time": None,
    "last_perfil": None,
    "scan_error": None,
    "datos_anteriores": [],
    "oi_cambios": None,
    "fechas_escaneadas": [],
    "auto_scan": False,
    "clusters_detectados": [],
    "ticker_anterior": DEFAULT_TICKER,
    "trigger_scan": False,
    "todas_las_fechas": [],
    "rango_resultado": None,
    "rango_error": None,
    "scanning_active": False,
    "noticias_data": [],
    "noticias_last_refresh": None,
    "barchart_data": None,
    "barchart_error": None,
    "noticias_auto_refresh": False,
    "noticias_filtro": "Todas",
    "favoritos": [],
    "watchlist": [],
    "eventos_economicos": [],
    "eventos_last_refresh": None,
    "_wl_consolidadas_shown_hash": None,
    "_wl_emergentes_shown_hash": None,
    # Umbrales del escáner (configurables en Live Scanning)
    "umbral_vol": DEFAULT_MIN_VOLUME,
    "umbral_oi": DEFAULT_MIN_OI,
    "umbral_prima": DEFAULT_MIN_PRIMA,
    "umbral_delta": 0.0,
    "min_sm_flow_score": 60,
    "min_inst_flow_score": 65,
    # Navegación y estado de precio
    "current_page": "\U0001f50d Live Scanning",
    "rango_delta": DEFAULT_TARGET_DELTA,
    "precio_subyacente": None,
    "last_full_scan": None,
    # Resultados de análisis de empresas
    "proyecciones_resultados": None,
    "emergentes_resultados": None,
    # Redirect container (mutable dict — avoids widget-key conflicts)
    "_redirect": {"page": None, "ticker": None},

    # ── Venta de Prima / Credit Spread ── prefijo: cs_ ───────────────────
    # Resultados del scanner (persisten aunque cambie el ticker del subyacente
    # porque el CS elige sus propios tickers de forma independiente).
    "cs_results": None,           # DataFrame con todos los spreads encontrados
    "cs_alerts": None,            # DataFrame de alertas (10 reglas)
    "cs_scan_time": None,         # timestamp del último scan ("YYYY-MM-DD HH:MM:SS")
    "cs_ticker_indicators": {},   # dict {ticker: {iv_rank, trend, ...}}
    "cs_filters": {},             # snapshot de filtros usados en el último scan
    "bt_results": None,           # dict {spread_key: BacktestResult} del backtester Fase 3

    # ── OKA Sentiment Index ── prefijo: oka_ ─────────────────────────────
    # Cache por sesión (reemplaza @st.cache_data global para evitar mezcla
    # entre usuarios distintos en un despliegue multi-tenant).
    "oka_last_result": None,      # dict completo devuelto por compute_oka_index
    "oka_last_symbol": None,      # símbolo del último cálculo cacheado
    "oka_last_lookback": 60,      # ventana en minutos del último cálculo
    "oka_last_gamma": False,      # gamma weighting del último cálculo
    "oka_last_refresh": None,     # timestamp float (time.time()) del último fetch

    # ── Live Scanning ── prefijo: live_ ──────────────────────────────────
    # Ticker del que provienen los datos de scan actualmente en memoria.
    # Se escribe tras cada scan exitoso; se anula al cambiar de ticker.
    "live_last_ticker": None,

    # ── Open Interest ── prefijo: oi_ ────────────────────────────────────
    # Ticker del que proviene barchart_data actualmente en memoria.
    "oi_last_ticker": None,

    # ── Range ── prefijo: rng_ ────────────────────────────────────────────
    # Ticker del último cálculo de rango guardado en rango_resultado.
    "rng_last_ticker": None,

    # ── Admin page ───────────────────────────────────────────────────────
    "admin_metric_filter": "Todos",

    # ── Flags internos de sincronización ─────────────────────────────────
    "_favs_synced": False,
    "_show_welcome_splash": False,
}

# Claves ligadas a un ticker específico.
# Estas claves se invalidan (≠ None o []) al cambiar de ticker — ver scan_service.
# Las claves cs_ NO están aquí porque el credit spread elige sus propios tickers.
_TICKER_SCOPED_KEYS: frozenset[str] = frozenset({
    "alertas_actuales",
    "datos_completos",
    "datos_anteriores",
    "clusters_detectados",
    "fechas_escaneadas",
    "oi_cambios",
    "barchart_data",
    "barchart_error",
    "rango_resultado",
    "rango_error",
    "scan_error",
    "precio_subyacente",
    "last_scan_time",
    "last_perfil",
    "scan_count",
    "last_full_scan",
    "proyecciones_resultados",
    "emergentes_resultados",
    "live_last_ticker",
    "oi_last_ticker",
    "rng_last_ticker",
})


def initialize_session_state() -> None:
    """Inicializa todos los valores por defecto del session_state y carga favoritos."""
    for _key, _val in _DEFAULTS.items():
        if _key not in st.session_state:
            st.session_state[_key] = _val
    # Cargar favoritos desde disco al inicio
    if not st.session_state.favoritos:
        st.session_state.favoritos = _cargar_favoritos()
    # Cargar watchlist desde disco al inicio
    if not st.session_state.watchlist:
        st.session_state.watchlist = _cargar_watchlist()


def save_page_data(page_key: str, data_dict: dict) -> None:
    """Persiste datos de una página en session_state con prefijo.

    Convierte cada entrada en una clave `{page_key}_{nombre}` dentro de
    st.session_state, lo que garantiza espacio de nombres aislado por página.

    Uso::

        save_page_data("cs", {
            "results": df,
            "scan_time": "2026-03-01 10:00",
            "filters": {"min_pop": 70, "tickers": ["SPY"]},
        })
        # Produce: st.session_state["cs_results"], ["cs_scan_time"], ["cs_filters"]

    Args:
        page_key:  prefijo corto de la página (ej: ``"cs"``, ``"live"``, ``"oka"``).
        data_dict: mapping nombre_corto → valor a guardar.
    """
    for k, v in data_dict.items():
        st.session_state[f"{page_key}_{k}"] = v


def load_page_data(page_key: str, keys: list) -> dict:
    """Lee datos de una página desde session_state con prefijo.

    Uso::

        d = load_page_data("cs", ["results", "scan_time", "filters"])
        df = d["results"]   # None si aún no se ha escaneado

    Args:
        page_key: prefijo corto de la página.
        keys:     lista de nombres cortos (sin prefijo).

    Returns:
        dict ``{nombre_corto: valor}``; valor es ``None`` si la clave no existe.
    """
    return {k: st.session_state.get(f"{page_key}_{k}") for k in keys}


def persist_shared_state(current_ticker: str) -> None:
    """Valida y actualiza claves de estado compartido entre páginas.

    Llamar en app_web.py después de resolver ``ticker_symbol``, antes de
    renderizar la página activa.  No limpia datos (eso es trabajo de
    ``scan_service.reset_for_ticker``); solo garantiza consistencia.

    Casos que maneja:
    - Asegura que ``ticker_anterior`` esté siempre actualizado.
    - Detecta datos live/OI de un ticker distinto al activo y los marca
      como obsoletos (no los borra para no interferir con reset_for_ticker).

    Args:
        current_ticker: símbolo seleccionado en el input principal (ya
                        en mayúsculas y sin espacios).
    """
    if not current_ticker:
        return

    # Garantizar que ticker_anterior refleje el ticker activo.
    st.session_state["ticker_anterior"] = current_ticker

    # Si los datos live pertenecen a otro ticker y aún no han sido limpiados
    # por reset_for_ticker (puede ocurrir en redirects o en primer carga),
    # simplemente indicamos que el live_last_ticker no coincide.
    # La limpieza real ocurre en scan_service.reset_for_ticker().
    live_lt = st.session_state.get("live_last_ticker")
    if live_lt and live_lt != current_ticker:
        # Marcar que los datos live son de otro ticker (sin borrar por seguridad).
        st.session_state["live_last_ticker"] = None
