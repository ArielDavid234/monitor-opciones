# -*- coding: utf-8 -*-
"""
SidebarUserBlock — componente reutilizable de UI para el bloque de usuario
al fondo del sidebar.

Responsabilidades:
  - Renderiza avatar circular con iniciales (HTML, siempre redondo)
  - Muestra nombre y rol del usuario con estilos dark-theme
  - Botón "Mi Perfil" → navega vía ``_nav_pending``
  - Botón "Cerrar Sesión" → llama ``auth.logout()``

Principio de diseño: este componente **recibe datos, no los obtiene**.
La lógica de auth y el usuario actual los provee el llamador (app_web.py).
Cero lógica de negocio aquí.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from domain.entities import User

if TYPE_CHECKING:
    from core.protocols import AuthProvider

# ── CSS inyectado una sola vez por sesión ─────────────────────────────────
_SIDEBAR_CSS = """
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
"""

_AVATAR_TEMPLATE = """
<div style="text-align:center;padding:0.5rem 0 0.3rem 0;">
    <div style="width:46px;height:46px;border-radius:50%;
                background:linear-gradient(135deg,#00ff88,#10b981);
                display:inline-flex;align-items:center;justify-content:center;
                font-size:17px;font-weight:800;color:#0f172a;
                box-shadow:0 0 14px rgba(0,255,136,0.25);
                margin-bottom:5px;">
        {initials}
    </div><br>
    <span style="color:white;font-weight:600;font-size:0.85rem;">{name}</span><br>
    <span style="color:#64748b;font-size:0.72rem;">{role_label}</span>
</div>
"""


def render_sidebar_user_block(user: User, auth: "AuthProvider") -> None:
    """Renderiza el bloque de usuario en el sidebar.

    Args:
        user: entidad ``User`` del usuario autenticado.
        auth: proveedor de auth (``SupabaseAuth``) para cerrar sesión.

    Side-effects:
        - Si el usuario pulsa "Mi Perfil", escribe ``_nav_pending`` en
          session_state y llama ``st.rerun()``.
        - Si el usuario pulsa "Cerrar Sesión", llama ``auth.logout()``
          y ``st.rerun()``.
    """
    st.markdown(_SIDEBAR_CSS, unsafe_allow_html=True)
    st.markdown('<div class="sidebar-user-block">', unsafe_allow_html=True)

    # ── Avatar + info ─────────────────────────────────────────────────────
    st.markdown(
        _AVATAR_TEMPLATE.format(
            initials=user.initials,
            name=user.name,
            role_label=user.role_label,
        ),
        unsafe_allow_html=True,
    )

    # ── Botones de acción ─────────────────────────────────────────────────
    if st.button("\U0001f464 Mi Perfil", use_container_width=True, key="btn_go_profile"):
        st.session_state["_nav_pending"] = "\U0001f464 Mi Perfil"
        st.rerun()

    if st.button("\U0001f6aa Cerrar Sesión", use_container_width=True, key="btn_logout"):
        auth.logout()
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
