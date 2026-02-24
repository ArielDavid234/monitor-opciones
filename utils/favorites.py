# -*- coding: utf-8 -*-
"""
Sistema de Favoritos — persistencia JSON.
Extraído de app_web.py — cero cambios de lógica.
"""
import json
import logging
import os
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)

_FAVORITOS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "favoritos.json")


def _cargar_favoritos():
    """Carga favoritos desde archivo JSON. Purga contratos expirados."""
    try:
        if os.path.exists(_FAVORITOS_PATH):
            with open(_FAVORITOS_PATH, "r", encoding="utf-8") as f:
                favoritos = json.load(f)
            # Purgar contratos expirados
            hoy = datetime.now().strftime("%Y-%m-%d")
            favoritos = [fav for fav in favoritos if fav.get("Vencimiento", "9999-12-31") >= hoy]
            _guardar_favoritos(favoritos)  # persistir la limpieza
            return favoritos
    except Exception as e:
        logger.warning("Error cargando favoritos: %s", e)
    return []


def _guardar_favoritos(favoritos):
    """Guarda la lista de favoritos en archivo JSON."""
    try:
        os.makedirs(os.path.dirname(_FAVORITOS_PATH), exist_ok=True)
        with open(_FAVORITOS_PATH, "w", encoding="utf-8") as f:
            json.dump(favoritos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error guardando favoritos: %s", e)


def _agregar_favorito(contrato_data):
    """Agrega un contrato a favoritos si no existe ya."""
    favoritos = st.session_state.get("favoritos", [])
    contrato_id = contrato_data.get("Contrato", "")
    if not contrato_id:
        return False
    # Verificar que no exista ya
    if any(f.get("Contrato") == contrato_id for f in favoritos):
        return False
    # Agregar timestamp de cuando se marcó
    contrato_data["Guardado_En"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    favoritos.append(contrato_data)
    st.session_state.favoritos = favoritos
    _guardar_favoritos(favoritos)
    return True


def _eliminar_favorito(contrato_id):
    """Elimina un contrato de favoritos por su símbolo."""
    favoritos = st.session_state.get("favoritos", [])
    favoritos = [f for f in favoritos if f.get("Contrato") != contrato_id]
    st.session_state.favoritos = favoritos
    _guardar_favoritos(favoritos)


def _es_favorito(contrato_id):
    """Verifica si un contrato ya está en favoritos."""
    favoritos = st.session_state.get("favoritos", [])
    return any(f.get("Contrato") == contrato_id for f in favoritos)


# ============================================================================
#                    WATCHLIST DE COMPAÑÍAS
# ============================================================================
_WATCHLIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "watchlist.json"
)


def _cargar_watchlist():
    """Carga la watchlist de compañías desde archivo JSON."""
    try:
        if os.path.exists(_WATCHLIST_PATH):
            with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Error cargando watchlist: %s", e)
    return []


def _guardar_watchlist(watchlist):
    """Guarda la watchlist de compañías en archivo JSON."""
    try:
        os.makedirs(os.path.dirname(_WATCHLIST_PATH), exist_ok=True)
        with open(_WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error guardando watchlist: %s", e)


def _agregar_a_watchlist(ticker, nombre=""):
    """Agrega una compañía a la watchlist. Devuelve (ok: bool, mensaje: str)."""
    watchlist = st.session_state.get("watchlist", [])
    ticker = ticker.strip().upper()
    if not ticker:
        return False, "El ticker no puede estar vacío"
    if any(w["ticker"] == ticker for w in watchlist):
        return False, f"{ticker} ya está en la Watchlist"
    watchlist.append({
        "ticker": ticker,
        "nombre": nombre.strip(),
        "agregado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    st.session_state.watchlist = watchlist
    _guardar_watchlist(watchlist)
    return True, f"{ticker} agregado a la Watchlist"


def _eliminar_de_watchlist(ticker):
    """Elimina una compañía de la watchlist por su ticker."""
    watchlist = st.session_state.get("watchlist", [])
    watchlist = [w for w in watchlist if w["ticker"] != ticker.upper()]
    st.session_state.watchlist = watchlist
    _guardar_watchlist(watchlist)


def _en_watchlist(ticker):
    """Verifica si un ticker ya está en la watchlist."""
    watchlist = st.session_state.get("watchlist", [])
    return any(w["ticker"] == ticker.upper() for w in watchlist)
