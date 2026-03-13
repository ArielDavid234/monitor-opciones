# -*- coding: utf-8 -*-
"""OPTIONSKING Analytics - entrypoint principal de Streamlit.

Orquestador limpio:
  1) Configuración de página + CSS
  2) Auth gate
  3) Inicialización centralizada de session_state
  4) Sidebar (navegación + estado del background updater + user block)
  5) Header + ticker
  6) Dispatcher de páginas con manejo global de errores
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import streamlit as st

from core.auth import SupabaseAuth
from core.container import get_container
from domain.entities import User
from page_modules import login_page
from page_modules import (
    admin_users_page,
    calendar_page,
    credit_spread_page,
    data_analysis_page,
    favorites_page,
    important_companies_page,
    live_scanning_page,
    mi_perfil_page,
    news_page,
    oka_sentiment_page,
    open_interest_page,
    optionkings_page,
    range_page,
    reports_page,
    watchlist_page,
)
from presentation.components import render_sidebar_user_block
from presentation.layouts import build_sidebar_nav, render_main_header
from ui.shared import inject_all_css, render_footer, render_sidebar_logo
from utils.background_updater import get_updater_state, start_background_updater
from utils.state import initialize_session_state, persist_shared_state

logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="OPTIONSKING Analytics",
    page_icon="\U0001f451",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _bootstrap_auth() -> tuple[SupabaseAuth, User]:
    """Resuelve autenticación o detiene la app mostrando login."""
    auth = SupabaseAuth()

    if auth.handle_email_callback():
        pass

    if not auth.is_authenticated() and not auth.try_restore_session():
        login_page.render(auth=auth)
        st.stop()

    raw_user = auth.get_current_user()
    return auth, User.from_auth_dict(raw_user)


def _sync_user_lists_once(user_id: str, user_service) -> None:
    """Sincroniza favoritos/watchlist desde Supabase una sola vez por sesión."""
    if st.session_state.get("_favs_synced"):
        return

    favorites = user_service.load_favorites(user_id)
    watchlist = user_service.load_watchlist(user_id)

    if favorites:
        st.session_state["favoritos"] = favorites
    if watchlist:
        st.session_state["watchlist"] = watchlist

    st.session_state["_favs_synced"] = True


def _start_background_once() -> None:
    """Inicia updater de background (idempotente a nivel de proceso)."""
    bg_state = get_updater_state()
    # Si ya corre a nivel de proceso, solo marcar la sesión sin tocar el lock
    if bg_state.running and bg_state._thread and bg_state._thread.is_alive():
        st.session_state.setdefault("background_running", True)
        return
    start_background_updater()
    st.session_state["background_running"] = True
    st.session_state["background_started_at"] = time.time()


def _render_sidebar(current_user: User, auth: SupabaseAuth) -> str:
    """Renderiza sidebar y retorna página seleccionada."""
    with st.sidebar:
        render_sidebar_logo()
        effective_page = build_sidebar_nav(current_user)

        bg_state = get_updater_state()
        if bg_state.running:
            if bg_state.last_update > 0:
                age_seconds = max(0, int(time.time() - bg_state.last_update))
                age_txt = f"Datos actualizados hace {age_seconds}s"
            else:
                age_txt = "Cargando datos de mercado..."

            st.markdown(
                f'<div style="padding:0.45rem 0.6rem;margin:0.35rem 0;'
                f'background:#0d1117;border:1px solid #1e293b;border-radius:8px;'
                f'font-size:0.76rem;color:#94a3b8;">'
                f'\U0001f4e1 Top {bg_state.tickers_loaded} S&P 500<br>'
                f'{age_txt}</div>',
                unsafe_allow_html=True,
            )

        render_sidebar_user_block(current_user, auth)

    return effective_page


def _resolve_ticker(scan_service) -> str:
    """Resuelve ticker activo, sincroniza estado y reinicia datos si cambió."""
    redirect = st.session_state.get("_redirect", {})
    redirect_ticker = st.query_params.get("t", "")
    if redirect_ticker:
        del st.query_params["t"]

    default_ticker = redirect_ticker or st.session_state.get("ticker_anterior", "") or "SPY"

    if redirect.get("page") or redirect_ticker:
        st.session_state["_redirect"] = {"page": None, "ticker": None}
        if redirect_ticker:
            st.session_state["ticker_anterior"] = redirect_ticker

    ticker_preview = redirect_ticker or st.session_state.get("ticker_anterior", "SPY") or "SPY"
    render_main_header(ticker_preview)

    ticker_symbol = st.text_input(
        "\U0001f50d S\u00edmbolo del Ticker",
        value=default_ticker,
        max_chars=10,
        help="Ingresa el s\u00edmbolo de la acci\u00f3n (ej: SPY, AAPL, TSLA, QQQ)",
        placeholder="Escribe un ticker... (SPY, AAPL, TSLA, QQQ)",
        label_visibility="collapsed",
    ).strip().upper()

    previous_ticker = st.session_state.get("ticker_anterior")
    if ticker_symbol and ticker_symbol != previous_ticker:
        # Evita rerun extra manual; el cambio de widget ya dispara rerun.
        scan_service.reset_for_ticker(ticker_symbol)

    persist_shared_state(ticker_symbol)
    return ticker_symbol


def _render_page(page_name: str, ticker_symbol: str, page_kwargs: dict) -> None:
    """Dispatcher principal de páginas con firmas compatibles."""
    page_map: dict[str, Callable[[], None]] = {
        "\U0001f50d Live Scanning": lambda: live_scanning_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4ca Open Interest": lambda: open_interest_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4c8 Data Analysis": lambda: data_analysis_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4d0 Range": lambda: range_page.render(ticker_symbol, **page_kwargs),
        "\u2b50 Favorites": lambda: favorites_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4cc Watchlist": lambda: watchlist_page.render(ticker_symbol, **page_kwargs),
        "\U0001f3e2 Important Companies": lambda: important_companies_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4f0 News": lambda: news_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4c5 Calendar": lambda: calendar_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4cb Reports": lambda: reports_page.render(ticker_symbol, **page_kwargs),
        "\U0001f4b0 Venta de Prima": lambda: credit_spread_page.render(**page_kwargs),
        "\U0001f464 Mi Perfil": lambda: mi_perfil_page.render(**page_kwargs),
        "\U0001f3c6 OptionKings Analytic": lambda: optionkings_page.render(**page_kwargs),
        "\U0001f30a OKA Sentiment Index": lambda: oka_sentiment_page.render(**page_kwargs),
        "\U0001f451 Administrar Usuarios": lambda: admin_users_page.render(**page_kwargs),
    }

    render_fn = page_map.get(page_name)
    if not render_fn:
        st.warning(f"P\u00e1gina no registrada: {page_name}")
        return

    try:
        render_fn()
    except Exception as page_exc:
        exc_name = type(page_exc).__name__
        if "CircuitOpen" in exc_name:
            st.error(
                "\U0001f50c **API pausada** - demasiados fallos consecutivos. "
                "Los datos se recuperar\u00e1n autom\u00e1ticamente en unos minutos.",
                icon="\U0001f50c",
            )
        elif "RetryError" in exc_name or "RateLimit" in exc_name:
            st.warning(
                "\u26a0\ufe0f **Datos retrasados** - l\u00edmite de API alcanzado tras "
                "varios reintentos. Intenta de nuevo en unos minutos.",
                icon="\u23f3",
            )
        else:
            logger.error(
                "Error no manejado en p\u00e1gina %s: %s",
                page_name,
                page_exc,
                exc_info=True,
            )
            st.error(f"\u274c Error inesperado: {page_exc}", icon="\u274c")


def main() -> None:
    """Pipeline principal de la app."""
    inject_all_css()
    initialize_session_state()

    auth, current_user = _bootstrap_auth()
    container = get_container(auth=auth)

    # _start_background_once()

    if st.session_state.pop("_show_welcome_splash", False):
        from page_modules.login_page import show_welcome_splash
        show_welcome_splash(auth.get_current_user())

    _sync_user_lists_once(current_user.id, container.user_service)

    effective_page = _render_sidebar(current_user, auth)
    st.session_state["current_page"] = effective_page

    ticker_symbol = _resolve_ticker(container.scan_service)
    page_kwargs = container.scan_service.get_thresholds()
    _render_page(effective_page, ticker_symbol, page_kwargs)

    render_footer()


if __name__ == "__main__":
    main()

