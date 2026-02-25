# -*- coding: utf-8 -*-
"""
Inicialización del Session State.
Extraído de app_web.py — cero cambios de lógica.
"""
import streamlit as st

from config.constants import (
    DEFAULT_MIN_VOLUME, DEFAULT_MIN_OI, DEFAULT_MIN_PRIMA,
    DEFAULT_TARGET_DELTA,
)
from utils.favorites import _cargar_favoritos, _cargar_watchlist

# ============================================================================
#                    VALORES POR DEFECTO DEL SESSION STATE
# ============================================================================
_DEFAULTS = {
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
    "ticker_anterior": "SPY",
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
}


def initialize_session_state():
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
