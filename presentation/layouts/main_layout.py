# -*- coding: utf-8 -*-
"""
MainLayout — encapsula la lógica de navegación del sidebar y el header
del dashboard.

Extrae toda la lógica de navegación de app_web.py para que ese archivo
sea un orquestador mínimo.
"""
from __future__ import annotations

import streamlit as st

from domain.entities import User

# Opciones de navegación en orden de aparición en el sidebar
_NAV_OPTIONS_BASE: tuple[str, ...] = (
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
    "💰 Venta de Prima",
    "🏆 OptionKings Analytic",
    "🌊 OKA Sentiment Index",
)
_ADMIN_OPTION = "👑 Administrar Usuarios"


def build_sidebar_nav(user: User) -> str:
    """Construye la navegación del sidebar y devuelve la página efectiva.

    Gestiona:
    - Lista de opciones (+ Admin si el usuario es admin)
    - Redirecciones via ``_nav_pending`` y ``_redirect``
    - Override de página (Mi Perfil, no en el radio)
    - ``on_change`` callback para limpiar el override al cambiar radio

    Args:
        user: usuario autenticado (para saber si agregar opción Admin).

    Returns:
        Nombre de la página activa (string de la lista NAV_OPTIONS o "👤 Mi Perfil").
    """
    nav_options: list[str] = list(_NAV_OPTIONS_BASE)
    if user.is_admin:
        nav_options.append(_ADMIN_OPTION)

    # ── Resolver navegación pendiente ─────────────────────────────────────
    redir_page = st.session_state.get("_redirect", {}).get("page")
    pending_nav = st.session_state.pop("_nav_pending", None)
    nav_target = pending_nav or redir_page

    def _clear_page_override() -> None:
        st.session_state.pop("_page_override", None)

    radio_kw: dict = {}
    if nav_target == "👤 Mi Perfil":
        st.session_state["_page_override"] = "👤 Mi Perfil"
    elif nav_target and nav_target in nav_options:
        st.session_state.pop("_page_override", None)
        st.session_state.pop("nav_radio", None)
        radio_kw["index"] = nav_options.index(nav_target)

    # ── Radio de navegación ───────────────────────────────────────────────
    st.markdown('<div class="sidebar-nav-area">', unsafe_allow_html=True)
    pagina = st.radio(
        "Navegación",
        nav_options,
        label_visibility="collapsed",
        key="nav_radio",
        on_change=_clear_page_override,
        **radio_kw,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Página efectiva: override (Mi Perfil) > radio
    return st.session_state.get("_page_override") or pagina


def render_main_header(ticker_preview: str) -> None:
    """Renderiza el header principal del dashboard con el ticker activo.

    Args:
        ticker_preview: el ticker a mostrar en el subtítulo del header.
    """
    st.markdown(
        f"""
<div class="scanner-header">
    <h1>👑 OPTIONS<span style="color: #00ff88;">KING</span> Analytics</h1>
    <p class="subtitle">
        Escáner institucional de actividad inusual en opciones —
        <b style="color: #00ff88;">{ticker_preview}</b>
    </p>
    <span class="badge">● LIVE • Análisis Avanzado</span>
</div>
""",
        unsafe_allow_html=True,
    )
