# -*- coding: utf-8 -*-
"""
ScanService — capa de servicio para el scanner principal (Live Scanning /
Open Interest / Data Analysis).

Desacopla la lógica de escaneo de opciones de la capa de presentación.
Todas las llamadas a yfinance y parseo de cadenas suceden aquí.

Nota de diseño: este servicio todavía usa ``st.session_state`` para el
estado transiente de UI (alertas en curso, trigger_scan, etc.).  Esto es
intencional — Streamlit requiere session_state para persistir datos entre
reruns.  La clave es que **las páginas delegan en este servicio** en vez
de manipular session_state directamente.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import streamlit as st

from core.scanner import (
    limpiar_cache_ticker,
    obtener_precio_actual,
)
from config.constants import (
    DEFAULT_MIN_VOLUME,
    DEFAULT_MIN_OI,
    DEFAULT_MIN_PRIMA,
)

logger = logging.getLogger(__name__)


class ScanService:
    """Gestiona el estado de escaneo y la obtención de datos de opciones.

    Encapsula el session_state necesario para el escaneo activo, de manera
    que las páginas no manipulen session_state de scan directamente.

    Este es el **único punto de contacto** entre business logic y
    ``st.session_state`` para datos de escaneo.
    """

    # Claves de session_state que gestiona este servicio
    _LIST_KEYS: tuple[str, ...] = (
        "alertas_actuales",
        "datos_completos",
        "datos_anteriores",
        "clusters_detectados",
        "fechas_escaneadas",
    )
    _NULLABLE_KEYS: tuple[str, ...] = (
        "oi_cambios",
        "barchart_data",
        "barchart_error",
        "rango_resultado",
        "rango_error",
        "scan_error",
        "last_full_scan",   # resetear al cambiar ticker para que auto-trigger no choque con cooldown
        # Claves de metadatos de página — se anulan al cambiar de ticker
        "live_last_ticker",
        "oi_last_ticker",
        "rng_last_ticker",
    )

    def get_price(self, ticker: str) -> Optional[float]:
        """Obtiene el precio actual del subyacente con manejo de errores.

        Args:
            ticker: símbolo del subyacente (e.g. "SPY").

        Returns:
            Precio float o None si hay error.
        """
        try:
            price, _err = obtener_precio_actual(ticker)
            return price
        except Exception as exc:
            logger.warning("Error obteniendo precio de %s: %s", ticker, exc)
            return None

    def reset_for_ticker(self, ticker: str) -> None:
        """Limpia todo el estado de scan y la caché cuando cambia el ticker.

        Llamar este método en lugar de manipular session_state directamente.

        Args:
            ticker: nuevo símbolo seleccionado por el usuario.
        """
        for key in self._LIST_KEYS:
            st.session_state[key] = []
        for key in self._NULLABLE_KEYS:
            st.session_state[key] = None
        st.session_state["trigger_scan"] = True
        st.session_state["ticker_anterior"] = ticker
        limpiar_cache_ticker(ticker)
        logger.info("Estado limpiado para ticker %s", ticker)

    @staticmethod
    def get_thresholds() -> dict[str, Any]:
        """Devuelve los umbrales de escaneo configurados en session_state.

        Returns:
            dict con keys: umbral_vol, umbral_oi, umbral_prima, umbral_delta.
        """
        return {
            "umbral_vol": st.session_state.get("umbral_vol", DEFAULT_MIN_VOLUME),
            "umbral_oi": st.session_state.get("umbral_oi", DEFAULT_MIN_OI),
            "umbral_prima": st.session_state.get("umbral_prima", DEFAULT_MIN_PRIMA),
            "umbral_delta": st.session_state.get("umbral_delta", 0.0),
        }
