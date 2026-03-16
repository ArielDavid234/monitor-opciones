# -*- coding: utf-8 -*-
"""Gestión centralizada y robusta del ``st.session_state``.

Provee:
  - ``initialize_session_state()``: inicializa claves globales y por página.
  - ``save_page_data(page_key, data)``: persiste payload con prefijo ``{page}_``.
  - ``load_page_data(page_key, keys=None)``: carga por clave o bloque completo.
  - ``clear_page_data(page_key)``: limpia/restaura estado de una página.
  - ``persist_shared_state(current_ticker)``: sincroniza estado compartido.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import streamlit as st

from config.constants import (
    DEFAULT_MIN_OI,
    DEFAULT_MIN_PRIMA,
    DEFAULT_MIN_VOLUME,
    DEFAULT_TARGET_DELTA,
    DEFAULT_TICKER,
)
from utils.favorites import _cargar_favoritos, _cargar_watchlist


# ============================================================================
#                    VALORES POR DEFECTO DEL SESSION STATE
# ============================================================================

# Claves globales/transversales (sin prefijo de página)
_GLOBAL_DEFAULTS: dict[str, Any] = {
    # Core scanner (legacy keys usadas por múltiples módulos)
    "alertas_actuales": [],
    "datos_completos": [],
    "datos_anteriores": [],
    "clusters_detectados": [],
    "fechas_escaneadas": [],
    "todas_las_fechas": [],
    "scan_count": 0,
    "last_scan_time": None,
    "last_perfil": None,
    "scan_error": None,
    "oi_cambios": None,
    "rango_resultado": None,
    "rango_error": None,
    "precio_subyacente": None,
    "last_full_scan": None,
    "auto_scan": False,
    "scanning_active": False,
    "trigger_scan": False,

    # Datos auxiliares por página legacy
    "noticias_data": [],
    "noticias_last_refresh": None,
    "noticias_auto_refresh": False,
    "noticias_filtro": "Todas",
    "eventos_economicos": [],
    "eventos_last_refresh": None,
    "barchart_data": None,
    "barchart_error": None,
    "proyecciones_resultados": None,
    "emergentes_resultados": None,

    # Navegación/ticker
    "current_page": "Live Scanning",
    "ticker_anterior": DEFAULT_TICKER,
    "_redirect": {"page": None, "ticker": None},
    "_page_override": None,

    # Favoritos/watchlist
    "favoritos": [],
    "watchlist": [],
    "_wl_consolidadas_shown_hash": None,
    "_wl_emergentes_shown_hash": None,
    "_favs_synced": False,

    # Umbrales Live
    "umbral_vol": DEFAULT_MIN_VOLUME,
    "umbral_oi": DEFAULT_MIN_OI,
    "umbral_prima": DEFAULT_MIN_PRIMA,
    "umbral_delta": 0.0,
    "rango_delta": DEFAULT_TARGET_DELTA,
    "min_sm_flow_score": 60,
    "min_inst_flow_score": 65,

    # Flags internos
    "_show_welcome_splash": False,
    "_enrich_cache": None,
    "_enrich_cache_key": None,
    "_gex_cache": None,
    "_gex_cache_key": None,
    # Admin / OptionKings runtime keys
    "admin_metric_filter": "Todos",
    "ok_flow_history": [],

    # Background updater (arranque una sola vez por sesión)
    "background_running": False,
    "background_started_at": None,
}


# Claves por página (prefijadas con ``{page_key}_``)
_PAGE_DEFAULTS: dict[str, dict[str, Any]] = {
    "cs": {
        "results": None,
        "alerts": None,
        "scan_time": None,
        "ticker_indicators": {},
        "filters": {},
        "error": None,
    },
    "live": {
        "results": None,
        "scan_time": None,
        "filters": {},
        "last_ticker": None,
        "error": None,
    },
    "oi": {
        "results": None,
        "last_ticker": None,
        "error": None,
    },
    "oka": {
        "data": None,
        "last_result": None,
        "last_symbol": None,
        "last_lookback": 60,
        "last_gamma": False,
        "last_refresh": None,
    },
    "ok": {
        "results": None,
        "scan_time": None,
        "page": 0,
        "settings": {},
        "error": None,
    },
    "rng": {
        "results": None,
        "last_ticker": None,
        "error": None,
    },
    "bt": {
        "results": None,
    },
    "fast": {
        "data": {},
        "last_update": None,
    },
}


# Mapa explícito para compatibilidad con claves legacy sin prefijo
_LEGACY_ALIASES: dict[str, str] = {
    "bt_results": "bt_results",
    "oka_last_result": "oka_last_result",
    "oka_last_symbol": "oka_last_symbol",
    "oka_last_lookback": "oka_last_lookback",
    "oka_last_gamma": "oka_last_gamma",
    "oka_last_refresh": "oka_last_refresh",
    "live_last_ticker": "live_last_ticker",
    "oi_last_ticker": "oi_last_ticker",
    "rng_last_ticker": "rng_last_ticker",
    "ok_results": "ok_results",
    "ok_scan_time": "ok_scan_time",
    "ok_page": "ok_page",
    "ok_settings": "ok_settings",
}


# Backward-compatibility shim for legacy tooling/tests that still expects
# a flat ``_DEFAULTS`` dictionary in this module.
_DEFAULTS: dict[str, Any] = dict(_GLOBAL_DEFAULTS)
for _page_key, _defaults in _PAGE_DEFAULTS.items():
    for _k, _v in _defaults.items():
        _DEFAULTS[f"{_page_key}_{_k}"] = _v
for _legacy_key in _LEGACY_ALIASES.keys():
    _DEFAULTS.setdefault(_legacy_key, None)


def _safe_default(value: Any) -> Any:
    """Devuelve una copia segura para valores mutables."""
    if isinstance(value, (dict, list, set)):
        return deepcopy(value)
    return value


def initialize_session_state() -> None:
    """Inicializa estado global y por página con valores por defecto."""
    for key, value in _GLOBAL_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = _safe_default(value)

    # Inicializar bloques por página usando prefijo estable
    for page_key, defaults in _PAGE_DEFAULTS.items():
        for key, value in defaults.items():
            scoped_key = f"{page_key}_{key}"
            if scoped_key not in st.session_state:
                st.session_state[scoped_key] = _safe_default(value)

    # Compatibilidad con claves legacy usadas en módulos existentes
    for legacy_key, canonical_key in _LEGACY_ALIASES.items():
        if legacy_key not in st.session_state:
            st.session_state[legacy_key] = st.session_state.get(canonical_key)

    # Carga local de favoritos/watchlist (fallback cuando no hay sync remoto)
    if not st.session_state.get("favoritos"):
        st.session_state["favoritos"] = _cargar_favoritos()
    if not st.session_state.get("watchlist"):
        st.session_state["watchlist"] = _cargar_watchlist()


def save_page_data(page_key: str, data: dict[str, Any]) -> None:
    """Persiste datos de una página con namespace ``{page_key}_``."""
    for key, value in data.items():
        st.session_state[f"{page_key}_{key}"] = value


def load_page_data(page_key: str, keys: list[str] | None = None) -> dict[str, Any]:
    """Carga datos de una página.

    Compatibilidad:
    - ``load_page_data("cs")`` devuelve todo el bloque ``cs_*``.
    - ``load_page_data("cs", ["results", "scan_time"])`` devuelve subset.
    """
    prefix = f"{page_key}_"

    if keys is not None:
        return {k: st.session_state.get(f"{prefix}{k}") for k in keys}

    data: dict[str, Any] = {}
    for key in st.session_state.keys():
        if key.startswith(prefix):
            data[key[len(prefix):]] = st.session_state.get(key)

    # Si aún no existe ningún valor prefijado, devolver defaults conocidos
    if not data and page_key in _PAGE_DEFAULTS:
        return deepcopy(_PAGE_DEFAULTS[page_key])
    return data


def clear_page_data(page_key: str) -> None:
    """Limpia estado de una página y restaura defaults si existen."""
    prefix = f"{page_key}_"
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith(prefix)]
    for key in keys_to_clear:
        del st.session_state[key]

    # Restaurar defaults base del bloque para evitar KeyError posteriores
    defaults = _PAGE_DEFAULTS.get(page_key, {})
    for key, value in defaults.items():
        st.session_state[f"{page_key}_{key}"] = _safe_default(value)


def persist_shared_state(current_ticker: str) -> None:
    """Sincroniza consistencia del estado compartido entre páginas."""
    if not current_ticker:
        return

    st.session_state["ticker_anterior"] = current_ticker

    # Garantizar shape del contenedor de redirección
    if not isinstance(st.session_state.get("_redirect"), dict):
        st.session_state["_redirect"] = {"page": None, "ticker": None}

    # Si live/oi/range apuntan a otro ticker, se marcan obsoletos
    if st.session_state.get("live_last_ticker") not in (None, current_ticker):
        st.session_state["live_last_ticker"] = None
    if st.session_state.get("oi_last_ticker") not in (None, current_ticker):
        st.session_state["oi_last_ticker"] = None
    if st.session_state.get("rng_last_ticker") not in (None, current_ticker):
        st.session_state["rng_last_ticker"] = None
