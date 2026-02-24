# -*- coding: utf-8 -*-
"""
Monitor de Opciones — Punto de entrada para Streamlit Cloud.
Orquesta la UI importando lógica desde config/, core/, ui/ y pages/.
"""
import streamlit as st

from core.scanner import limpiar_cache_ticker

# --- UI helpers ---
from ui.shared import inject_all_css, render_sidebar_logo, render_sidebar_avatar, render_footer
from utils.state import initialize_session_state

# --- Pages ---
from pages import (
    live_scanning_page,
    open_interest_page,
    data_analysis_page,
    range_page,
    favorites_page,
    important_companies_page,
    news_page,
    reports_page,
    calendar_page,
)


# ============================================================================
#                    PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="OPTIONSKING Analytics",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
#                    CSS + SESSION STATE
# ============================================================================
inject_all_css()
initialize_session_state()  # Inicializa TODOS los defaults incluyendo umbrales y navegación

# ============================================================================
#                    SIDEBAR
# ============================================================================
with st.sidebar:
    render_sidebar_logo()

    pagina = st.radio(
        "Navegación",
        [
            "🔍 Live Scanning",
            "📊 Open Interest",
            "📈 Data Analysis",
            "📐 Range",
            "⭐ Favorites",
            "🏢 Important Companies",
            "📰 News",
            "📅 Calendar",
            "📋 Reports",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")
    render_sidebar_avatar()

st.session_state.current_page = pagina

# ============================================================================
#                    TICKER INPUT + HEADER
# ============================================================================
ticker_symbol = st.text_input(
    "🔍 Símbolo del Ticker",
    value="SPY",
    max_chars=10,
    help="Ingresa el símbolo de la acción (ej: SPY, AAPL, TSLA, QQQ)",
    placeholder="Escribe un ticker... (SPY, AAPL, TSLA, QQQ)",
    label_visibility="collapsed",
).strip().upper()

# Detectar cambio de ticker → auto-escanear
if ticker_symbol and ticker_symbol != st.session_state.ticker_anterior:
    st.session_state.ticker_anterior = ticker_symbol
    st.session_state.alertas_actuales = []
    st.session_state.datos_completos = []
    st.session_state.datos_anteriores = []
    st.session_state.oi_cambios = None
    st.session_state.barchart_data = None
    st.session_state.barchart_error = None
    st.session_state.clusters_detectados = []
    st.session_state.rango_resultado = None
    st.session_state.rango_error = None
    st.session_state.scan_error = None
    st.session_state.fechas_escaneadas = []
    limpiar_cache_ticker(ticker_symbol)
    st.session_state.trigger_scan = True
    st.rerun()

st.markdown(
    f"""
    <div class="scanner-header">
        <h1>👑 OPTIONS<span style="color: #00ff88;">KING</span> Analytics</h1>
        <p class="subtitle">
            Escáner institucional de actividad inusual en opciones — <b style="color: #00ff88;">{ticker_symbol}</b>
        </p>
        <span class="badge">● LIVE • Análisis Avanzado</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
#                    PAGE DISPATCH
# ============================================================================
_page_kwargs = dict(
    umbral_vol=st.session_state.umbral_vol,
    umbral_oi=st.session_state.umbral_oi,
    umbral_prima=st.session_state.umbral_prima,
    umbral_delta=st.session_state.umbral_delta,
)

if pagina == "🔍 Live Scanning":
    live_scanning_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "📊 Open Interest":
    open_interest_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "📈 Data Analysis":
    data_analysis_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "📐 Range":
    range_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "⭐ Favorites":
    favorites_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "🏢 Important Companies":
    important_companies_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "📰 News":
    news_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "📅 Calendar":
    calendar_page.render(ticker_symbol, **_page_kwargs)
elif pagina == "📋 Reports":
    reports_page.render(ticker_symbol, **_page_kwargs)

# ============================================================================
#                    FOOTER
# ============================================================================
render_footer()
