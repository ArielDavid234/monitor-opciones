# -*- coding: utf-8 -*-
"""
Monitor de Opciones — Punto de entrada para Streamlit Cloud.
Orquesta la UI importando lógica desde config/, core/, ui/ y page_modules/.
"""
import streamlit as st

# ============================================================================
#                    PAGE CONFIG  (debe ir ANTES de cualquier widget)
# ============================================================================
st.set_page_config(
    page_title="OPTIONSKING Analytics",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
#                    AUTH GATE — bloquea TODO si no hay sesión
# ============================================================================
from core.auth import SupabaseAuth  # noqa: E402
from page_modules import login_page  # noqa: E402
from ui.shared import inject_all_css, render_sidebar_logo, render_sidebar_avatar, render_footer  # noqa: E402

inject_all_css()

_auth = SupabaseAuth()

# ── Callback de confirmación por email ───────────────────────────────────
# Si el usuario viene de clicar el enlace de confirmación, intentar
# autenticarlo automáticamente (PKCE / implicit tokens en query params).
if _auth.handle_email_callback():
    pass  # Ya autenticado — continúa al dashboard

if not _auth.is_authenticated():
    # Intentar restaurar sesión persistente ("Recordarme")
    if not _auth.try_restore_session():
        login_page.render()
        st.stop()  # No renderizar nada más

# ── A partir de aquí, el usuario ESTÁ autenticado ────────────────────────
_current_user = _auth.get_current_user()  # {id, email, name}

from core.scanner import limpiar_cache_ticker  # noqa: E402
from utils.state import initialize_session_state  # noqa: E402

# --- Pages ---
from page_modules import (  # noqa: E402
    live_scanning_page,
    open_interest_page,
    data_analysis_page,
    range_page,
    favorites_page,
    watchlist_page,
    important_companies_page,
    news_page,
    reports_page,
    calendar_page,
)

# ============================================================================
#                    CSS + SESSION STATE
# ============================================================================
initialize_session_state()  # Inicializa TODOS los defaults incluyendo umbrales y navegación

# ── Sincronizar favoritos de Supabase → session_state (una vez por sesión) ──
if not st.session_state.get("_favs_synced"):
    cloud_favs = _auth.load_user_data(_current_user["id"], "favoritos")
    if cloud_favs and isinstance(cloud_favs, list):
        st.session_state.favoritos = cloud_favs
    cloud_wl = _auth.load_user_data(_current_user["id"], "watchlist")
    if cloud_wl and isinstance(cloud_wl, list):
        st.session_state.watchlist = cloud_wl
    st.session_state["_favs_synced"] = True

# ============================================================================
#                    SIDEBAR
# ============================================================================
# Precalcular initials antes del bloque sidebar
_user_initials = "".join(
    w[0].upper() for w in (_current_user["name"] or "U").split()[:2]
)

with st.sidebar:
    render_sidebar_logo()

    # ── CSS: flex column para empujar usuario al fondo ───────────────────
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] > div:first-child {
            display: flex !important;
            flex-direction: column !important;
            height: 100vh !important;
            padding-bottom: 0 !important;
        }
        .sidebar-nav-area { flex: 1 1 auto; }
        .sidebar-user-block {
            padding: 0.6rem 0 0.8rem 0;
            border-top: 1px solid #1e293b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Navegación ───────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-nav-area">', unsafe_allow_html=True)

    _NAV_OPTIONS = [
        "🔍 Live Scanning",
        "📊 Open Interest",
        "📈 Data Analysis",
        "📐 Range",
        "⭐ Favorites",
        "📌 Watchlist",
        "🏢 Important Companies",
        "📰 News",
        "📅 Calendar",
        "📋 Reports",
    ]
    # Handle page redirect from Watchlist / other pages
    _redir = st.session_state.get("_redirect", {})
    _redirect_page = _redir.get("page")
    # Force radio to show the redirect page by pre-writing the widget key
    # BEFORE the widget is created (Streamlit allows this for unrendered widgets)
    if _redirect_page and _redirect_page in _NAV_OPTIONS:
        st.session_state["nav_radio"] = _redirect_page

    pagina = st.radio(
        "Navegación",
        _NAV_OPTIONS,
        label_visibility="collapsed",
        key="nav_radio",
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Info de usuario — al fondo del sidebar ───────────────────────────
    st.markdown('<div class="sidebar-user-block">', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center;padding:0.4rem 0 0.6rem 0;">'
        f'<div style="width:42px;height:42px;border-radius:50%;'
        f'background:linear-gradient(135deg,#00ff88,#10b981);'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:16px;font-weight:700;color:#0f172a;'
        f'margin-bottom:4px;box-shadow:0 0 12px rgba(0,255,136,0.2);">{_user_initials}</div>'
        f'<div style="color:white;font-weight:600;font-size:0.85rem;">{_current_user["name"]}</div>'
        f'<div style="color:#64748b;font-size:0.72rem;margin-top:1px;">● Pro Plan</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout"):
        _auth.logout()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.session_state.current_page = pagina

# ============================================================================
#                    HEADER + TICKER INPUT
# ============================================================================

# Handle redirect from Watchlist / other pages
_redir = st.session_state.get("_redirect", {})
_redirect_ticker = st.query_params.get("t", "")  # carry ticker via query_params
if _redirect_ticker:
    # consume it immediately so it doesn't persist in the URL
    del st.query_params["t"]
_default_ticker = _redirect_ticker or st.session_state.get("ticker_anterior", "") or "SPY"
# Clear page redirect flag
if _redir.get("page") or _redirect_ticker:
    st.session_state["_redirect"] = {"page": None, "ticker": None}
    if _redirect_ticker:
        st.session_state.ticker_anterior = _redirect_ticker

# Placeholder ticker for header before input is rendered
_ticker_preview = _redirect_ticker or st.session_state.get("ticker_anterior", "SPY") or "SPY"
st.markdown(
    f"""
<div class="scanner-header">
    <h1>👑 OPTIONS<span style="color: #00ff88;">KING</span> Analytics</h1>
    <p class="subtitle">
        Escáner institucional de actividad inusual en opciones — <b style="color: #00ff88;">{_ticker_preview}</b>
    </p>
    <span class="badge">● LIVE • Análisis Avanzado</span>
</div>
""",
    unsafe_allow_html=True,
)

ticker_symbol = st.text_input(
    "🔍 Símbolo del Ticker",
    value=_default_ticker,
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
elif pagina == "📌 Watchlist":
    watchlist_page.render(ticker_symbol, **_page_kwargs)
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
