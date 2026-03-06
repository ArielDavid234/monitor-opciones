# -*- coding: utf-8 -*-
"""
OKA Sentiment Index v2 — Página principal.

Renderiza la pestaña completa "🌊 OKA Sentiment Index" con:
    • Selector de símbolo + configuración
    • Toggle Gamma Weighting (Phase 2)
    • Botón "Actualizar" + refresco automático cada 30s
    • Gauge + tarjetas + barra de distribución + tabla de trades
    • Cache @st.cache_data (TTL 30s) para no abusar de la API

Uso (desde app_web.py):
    from page_modules import oka_sentiment_page
    oka_sentiment_page.render()
"""
from __future__ import annotations

import logging
import time

import streamlit as st

import time

from core.oka_sentiment_v2 import compute_oka_index
from ui.oka_components import render_oka_page

logger = logging.getLogger(__name__)

# Tickers disponibles para el selector
_OKA_TICKERS = [
    "SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "AMD",
    "MSFT", "AMZN", "META", "GOOGL", "NFLX", "BA", "GLD",
]
_DEFAULT_TICKER = "SPY"

# TTL del cache por sesión: 30 segundos (idéntico al botón de refresco)
_CACHE_TTL = 30


def _get_oka_data(symbol: str, gamma: bool, lookback: int,
                  force_refresh: bool = False) -> dict:
    """Obtiene datos OKA desde session_state o recalcula si el TTL expiró.

    Reemplaza el antiguo @st.cache_data global: la caché vive en el
    session_state del usuario, por lo que no se comparte entre sesiones
    diferentes en un despliegue multi-tenant.

    Args:
        symbol:        ticker subyacente.
        gamma:         activar gamma weighting.
        lookback:      ventana en minutos.
        force_refresh: ignorar caché y forzar recalculo.

    Returns:
        dict resultado del pipeline completo.
    """
    now = time.time()
    last_refresh = st.session_state.get("oka_last_refresh") or 0

    # Verificar si los parámetros son los mismos que el último cálculo
    mismos_params = (
        st.session_state.get("oka_last_symbol") == symbol
        and st.session_state.get("oka_last_lookback") == lookback
        and st.session_state.get("oka_last_gamma") == gamma
    )
    ttl_vigente = (now - last_refresh) < _CACHE_TTL

    # Usar caché si no se fuerza refresco, los parámetros coinciden y el TTL no expiró
    if (
        not force_refresh
        and mismos_params
        and ttl_vigente
        and st.session_state.get("oka_last_result") is not None
    ):
        return st.session_state["oka_last_result"]

    # Calcular y guardar en session_state
    result = compute_oka_index(
        symbol=symbol,
        gamma_weighting=gamma,
        lookback_minutes=lookback,
    )
    st.session_state["oka_last_result"] = result
    st.session_state["oka_last_symbol"] = symbol
    st.session_state["oka_last_lookback"] = lookback
    st.session_state["oka_last_gamma"] = gamma
    st.session_state["oka_last_refresh"] = now
    return result


def render(**kwargs) -> None:
    """Renderiza la pestaña OKA Sentiment Index v2."""

    # ── Header ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#0a0a1a,#0d1f3e);
                    border:1px solid #1e3a5f;border-radius:16px;
                    padding:1.2rem 2rem;margin-bottom:1rem;">
            <h2 style="color:#a78bfa;margin:0 0 0.25rem 0;">
                🌊 OKA Sentiment Index v2
            </h2>
            <p style="color:#94a3b8;margin:0;font-size:0.85rem;">
                Flujo institucional real · Delta-Weighted Premium · Clasificación agresiva ·
                Sentimiento 0–100 con sesgo cuantificado
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Panel de configuración ────────────────────────────────────────────
    with st.expander("⚙️ Configuración del Análisis de Flujo", expanded=True):
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            symbol = st.selectbox(
                "📈 Símbolo a analizar",
                options=_OKA_TICKERS,
                index=_OKA_TICKERS.index(_DEFAULT_TICKER),
                key="oka_symbol",
                help="Subyacente cuyo flujo institucional de opciones se analizará.",
            )

        with col2:
            lookback = st.slider(
                "⏱ Ventana (minutos)",
                min_value=15,
                max_value=240,
                value=60,
                step=15,
                key="oka_lookback",
                help="Ventana temporal hacia atrás para capturar trades.",
            )

        with col3:
            gamma_on = st.toggle(
                "🔬 Gamma Weighting (Phase 2)",
                value=False,
                key="oka_gamma",
                help=(
                    "GammaAdjusted = Premium × |delta| × gamma\n"
                    "Captura el impacto de convexidad. Recomendado en earnings."
                ),
            )

        if gamma_on:
            st.markdown(
                '<div style="background:#1a0d2e;border:1px solid #5b21b6;'
                'border-radius:6px;padding:6px 12px;font-size:0.78rem;color:#c4b5fd;">'
                "⚡ <b>Phase 2 activa:</b> OKA Index calculado con GammaAdjusted "
                "(Premium × |δ| × γ) en lugar de Delta-Weighted Premium."
                "</div>",
                unsafe_allow_html=True,
            )

    # ── Controles de refresco ─────────────────────────────────────────────
    col_btn, col_auto, col_ts = st.columns([1, 1, 2])

    with col_btn:
        do_refresh = st.button(
            "🔄 Actualizar flujo en tiempo real",
            type="primary",
            use_container_width=True,
            key="oka_refresh_btn",
            help="Fuerza la recarga de datos ignorando el cache de 30 segundos.",
        )

    with col_auto:
        auto_refresh = st.toggle(
            "⏰ Auto-refresco (30s)",
            value=False,
            key="oka_auto_refresh",
            help="Refresca automáticamente cada 30 segundos.",
        )

    # ── Obtener datos (caché por sesión con TTL=30s) ─────────────────────
    with st.spinner("Analizando flujo institucional…"):
        try:
            result = _get_oka_data(
                symbol        = str(symbol),
                gamma         = bool(gamma_on),
                lookback      = int(lookback),
                force_refresh = do_refresh,
            )
        except Exception as exc:
            logger.error("Error en compute_oka_index: %s", exc, exc_info=True)
            st.error(
                f"❌ Error al obtener datos de flujo: {exc}\n\n"
                "Verifica tu `POLYGON_API_KEY` o inténtalo de nuevo.",
                icon="❌",
            )
            return

    with col_ts:
        ts     = result.get("timestamp", "—")
        total_r = result.get("total_raw_trades", 0)
        total_i = result.get("total_institutional", 0)
        api_key_set = __import__("os").environ.get("POLYGON_API_KEY", "")
        data_label = "Polygon.io" if api_key_set else "Demo (mock)"
        st.markdown(
            f'<div style="padding:4px 0;font-size:0.75rem;color:#64748b;">'
            f'🕐 {ts[:16]} &nbsp;|&nbsp; '
            f'{total_r} trades crudos → {total_i} institucionales &nbsp;|&nbsp; '
            f'Fuente: <b style="color:#a78bfa;">{data_label}</b>'
            f"{'  ·  🔬 Gamma ON' if gamma_on else ''}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Aviso si no hay API key (modo demo)
    if not __import__("os").environ.get("POLYGON_API_KEY", ""):
        st.info(
            "🧪 **Modo Demo** — Los datos mostrados son simulados (mock) para demostración.\n\n"
            "Configura la variable de entorno `POLYGON_API_KEY` con tu clave de Polygon.io "
            "para datos reales en tiempo real.",
            icon="💡",
        )

    # ── Renderizar visualizaciones ────────────────────────────────────────
    render_oka_page(result)

    # ── Auto-refresco: forzar rerun cada 30s ─────────────────────────────
    if auto_refresh:
        time.sleep(30)
        st.cache_data.clear()
        st.rerun()
