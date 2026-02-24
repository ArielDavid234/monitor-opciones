# -*- coding: utf-8 -*-
"""
Inicialización del Session State.
Extraído de app_web.py — cero cambios de lógica.
"""
import streamlit as st

from utils.favorites import _cargar_favoritos

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
    "eventos_economicos": [],
    "eventos_last_refresh": None,
    "_wl_consolidadas_shown_hash": None,
    "_wl_emergentes_shown_hash": None,
}


def initialize_session_state():
    """Inicializa todos los valores por defecto del session_state y carga favoritos."""
    for _key, _val in _DEFAULTS.items():
        if _key not in st.session_state:
            st.session_state[_key] = _val
    # Cargar favoritos desde disco al inicio
    if not st.session_state.favoritos:
        st.session_state.favoritos = _cargar_favoritos()
