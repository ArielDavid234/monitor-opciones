# -*- coding: utf-8 -*-
"""
Monitor de Opciones — Punto de entrada para Streamlit Cloud.

Orquestador mínimo:
  1. Configura la página (debe ser la primera llamada a st)
  2. Aplica CSS global
  3. Verifica/restaura autenticación
  4. Inicializa session_state
  5. Construye el sidebar (layout + user block)
  6. Renderiza la página activa

Toda la lógica de negocio vive en core/services/.
Toda la lógica de presentación vive en presentation/.
Infraestructura (Supabase, Redis, yfinance) vive en infrastructure/.
Configuración global vive en config/.

Arquitectura: config → core → infrastructure → presentation → app_web.py
"""
import streamlit as st

# ============================================================================
#                    PAGE CONFIG  (primera llamada st — obligatorio)
# ============================================================================
st.set_page_config(
    page_title="OPTIONSKING Analytics",
    page_icon="\U0001f451",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
#                    AUTH GATE — bloquea TODO si no hay sesión
# ============================================================================
from core.auth import SupabaseAuth  # noqa: E402
from core.container import get_container  # noqa: E402
from page_modules import login_page  # noqa: E402
from ui.shared import inject_all_css, render_sidebar_logo  # noqa: E402

inject_all_css()

_auth = SupabaseAuth()
_container = get_container(auth=_auth)

if _auth.handle_email_callback():
    pass  # autenticado via PKCE — continúa

if not _auth.is_authenticated():
    if not _auth.try_restore_session():
        login_page.render(auth=_auth)
        st.stop()

# ── A partir de aquí el usuario ESTÁ autenticado ─────────────────────────
from core.entities import User  # noqa: E402
from presentation.components import render_sidebar_user_block  # noqa: E402
from presentation.layouts import render_main_header, build_sidebar_nav  # noqa: E402

_raw_user = _auth.get_current_user()
_current_user = User.from_auth_dict(_raw_user)

_user_svc = _container.user_service
_scan_svc = _container.scan_service

# ── Splash de bienvenida (una sola vez tras login) ────────────────────────
if st.session_state.pop("_show_welcome_splash", False):
    from page_modules.login_page import show_welcome_splash  # noqa: E402
    show_welcome_splash(_raw_user)

# ============================================================================
#                    IMPORTS DE PÁGINAS + SESSION STATE
# ============================================================================
from utils.state import initialize_session_state  # noqa: E402
from page_modules import (  # noqa: E402
    live_scanning_page, open_interest_page, data_analysis_page,
    range_page, favorites_page, watchlist_page, important_companies_page,
    news_page, reports_page, calendar_page, admin_users_page,
    credit_spread_page, mi_perfil_page,
)

initialize_session_state()

# ── Sincronizar favoritos/watchlist desde Supabase (una vez por sesión) ──
if not st.session_state.get("_favs_synced"):
    _favs = _user_svc.load_favorites(_current_user.id)
    _wl = _user_svc.load_watchlist(_current_user.id)
    if _favs:
        st.session_state.favoritos = _favs
    if _wl:
        st.session_state.watchlist = _wl
    st.session_state["_favs_synced"] = True

# ============================================================================
#                    SIDEBAR
# ============================================================================
with st.sidebar:
    render_sidebar_logo()
    _effective_page = build_sidebar_nav(_current_user)
    render_sidebar_user_block(_current_user, _auth)

st.session_state.current_page = _effective_page

# ============================================================================
#                    HEADER + TICKER INPUT
# ============================================================================
_redir = st.session_state.get("_redirect", {})
_redirect_ticker = st.query_params.get("t", "")
if _redirect_ticker:
    del st.query_params["t"]

_default_ticker = _redirect_ticker or st.session_state.get("ticker_anterior", "") or "SPY"

if _redir.get("page") or _redirect_ticker:
    st.session_state["_redirect"] = {"page": None, "ticker": None}
    if _redirect_ticker:
        st.session_state.ticker_anterior = _redirect_ticker

_ticker_preview = _redirect_ticker or st.session_state.get("ticker_anterior", "SPY") or "SPY"
render_main_header(_ticker_preview)

ticker_symbol = st.text_input(
    "\U0001f50d Símbolo del Ticker",
    value=_default_ticker,
    max_chars=10,
    help="Ingresa el símbolo de la acción (ej: SPY, AAPL, TSLA, QQQ)",
    placeholder="Escribe un ticker... (SPY, AAPL, TSLA, QQQ)",
    label_visibility="collapsed",
).strip().upper()

# Detectar cambio de ticker → limpiar estado y re-escanear
if ticker_symbol and ticker_symbol != st.session_state.ticker_anterior:
    _scan_svc.reset_for_ticker(ticker_symbol)
    st.rerun()

# ============================================================================
#                    PAGE DISPATCH
# ============================================================================
_page_kwargs = _scan_svc.get_thresholds()

_PAGE_MAP: dict[str, object] = {
    "\U0001f50d Live Scanning":       lambda: live_scanning_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4ca Open Interest":       lambda: open_interest_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4c8 Data Analysis":       lambda: data_analysis_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4d0 Range":               lambda: range_page.render(ticker_symbol, **_page_kwargs),
    "\u2b50 Favorites":               lambda: favorites_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4cc Watchlist":           lambda: watchlist_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f3e2 Important Companies": lambda: important_companies_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4f0 News":                lambda: news_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4c5 Calendar":            lambda: calendar_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4cb Reports":             lambda: reports_page.render(ticker_symbol, **_page_kwargs),
    "\U0001f4b0 Venta de Prima":      lambda: credit_spread_page.render(**_page_kwargs),
    "\U0001f464 Mi Perfil":           lambda: mi_perfil_page.render(**_page_kwargs),
    "\U0001f451 Administrar Usuarios": lambda: admin_users_page.render(**_page_kwargs),
}

if _render_fn := _PAGE_MAP.get(_effective_page):
    _render_fn()

# ============================================================================
#                    FOOTER
# ============================================================================
from ui.shared import render_footer  # noqa: E402
render_footer()

