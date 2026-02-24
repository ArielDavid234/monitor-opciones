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
