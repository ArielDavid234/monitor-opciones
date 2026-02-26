# -*- coding: utf-8 -*-
"""
Página de Login / Registro — OptionsKing Analytics.

Renderiza la UI de autenticación con el mismo dark theme
del resto de la app.  Se muestra ANTES del dashboard principal
cuando el usuario no está autenticado.
"""
from __future__ import annotations

import time
import streamlit as st

from core.auth import SupabaseAuth


# ============================================================================
#                    CSS LOGIN (dark theme matching the app)
# ============================================================================
_LOGIN_CSS = """
<style>
/* ── Contenedor central ────────────────────────────────────────────────── */
.login-container {
    max-width: 460px;
    margin: 0 auto;
    padding: 2.5rem 2rem 2rem 2rem;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border-radius: 20px;
    border: 1px solid #334155;
    box-shadow: 0 8px 32px rgba(0,0,0,0.45), 0 0 60px rgba(0,255,136,0.04);
}
.login-logo {
    text-align: center;
    margin-bottom: 1.5rem;
}
.login-logo h1 {
    color: #00ff88;
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin: 0.5rem 0 0 0;
}
.login-logo .sub {
    color: #94a3b8;
    font-size: 0.95rem;
    margin: 0;
}
/* ── Welcome splash ────────────────────────────────────────────────────── */
.welcome-splash {
    text-align: center;
    padding: 4rem 1rem;
}
.welcome-splash h1 {
    font-size: 2.8rem;
    font-weight: 800;
    color: #00ff88;
    margin-bottom: 0.5rem;
}
.welcome-splash p {
    color: #94a3b8;
    font-size: 1.1rem;
}
/* ── Links ─────────────────────────────────────────────────────────────── */
.auth-link {
    color: #00ff88;
    text-decoration: none;
    cursor: pointer;
    font-weight: 600;
}
.auth-link:hover { text-decoration: underline; }
</style>
"""


def _render_logo_html() -> str:
    """HTML del logo para la pantalla de login (sin SVG — máxima compatibilidad)."""
    return (
        '<div style="text-align:center;padding:1.2rem 0 1.6rem 0;">'
        '<div style="font-size:3rem;margin-bottom:4px;">&#x1F451;</div>'
        '<div style="font-size:2rem;font-weight:800;color:#00ff88;'
        'letter-spacing:-0.02em;line-height:1.1;">OPTIONSKING</div>'
        '<div style="color:#94a3b8;font-size:0.9rem;margin-top:4px;">Analytics v5.0</div>'
        '</div>'
    )


# ============================================================================
#                    RENDER PRINCIPAL
# ============================================================================
def render() -> bool:
    """Renderiza la pantalla de login/registro.

    Returns True si el usuario quedó autenticado (para que app_web.py
    sepa que puede continuar). False = seguir mostrando login.
    """
    auth = SupabaseAuth()

    # ── Intentar restaurar sesión ("Recordarme") ─────────────────────────
    if auth.try_restore_session():
        return True
    if auth.is_authenticated():
        return True

    # ── Inyectar CSS ─────────────────────────────────────────────────────
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # ── Columnas para centrar ────────────────────────────────────────────
    _, col_center, _ = st.columns([1, 2, 1])

    with col_center:
        # Logo (un solo st.markdown — no se pueden abrir/cerrar divs entre calls)
        st.markdown(_render_logo_html(), unsafe_allow_html=True)

        # ── Tabs: Login / Registro ───────────────────────────────────────
        tab_login, tab_register = st.tabs(["🔐 Iniciar Sesión", "📝 Crear Cuenta"])

        # ────────────────── TAB: LOGIN ──────────────────────────────────
        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                login_email = st.text_input(
                    "Correo electrónico",
                    placeholder="tu@email.com",
                    key="login_email",
                )
                login_password = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="••••••••",
                    key="login_password",
                )
                login_remember = st.checkbox("Recordarme (30 días)", key="login_remember")
                login_submit = st.form_submit_button(
                    "🔐 Iniciar Sesión",
                    use_container_width=True,
                    type="primary",
                )

            if login_submit:
                ok, msg = auth.login(login_email, login_password, login_remember)
                if ok:
                    _show_welcome_and_redirect(auth)
                    return True  # nunca se alcanza por el rerun, pero por consistencia
                else:
                    st.error(msg)

            # ── Olvidé mi contraseña ─────────────────────────────────────
            st.markdown("")
            with st.expander("¿Olvidaste tu contraseña?"):
                reset_email = st.text_input(
                    "Ingresa tu correo",
                    placeholder="tu@email.com",
                    key="reset_email",
                )
                if st.button("Enviar enlace de recuperación", use_container_width=True):
                    ok, msg = auth.send_password_reset(reset_email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        # ────────────────── TAB: REGISTRO ───────────────────────────────
        with tab_register:
            with st.form("register_form", clear_on_submit=False):
                reg_name = st.text_input(
                    "Nombre",
                    placeholder="Tu nombre",
                    key="reg_name",
                )
                reg_email = st.text_input(
                    "Correo electrónico",
                    placeholder="tu@email.com",
                    key="reg_email",
                )
                reg_password = st.text_input(
                    "Contraseña (mín. 8 caracteres)",
                    type="password",
                    placeholder="••••••••",
                    key="reg_password",
                )
                reg_confirm = st.text_input(
                    "Confirmar contraseña",
                    type="password",
                    placeholder="••••••••",
                    key="reg_confirm",
                )
                reg_submit = st.form_submit_button(
                    "📝 Crear Cuenta",
                    use_container_width=True,
                    type="primary",
                )

            if reg_submit:
                ok, msg = auth.register(reg_email, reg_password, reg_name, reg_confirm)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    return False


# ============================================================================
#                    WELCOME SPLASH (3 sec → redirect)
# ============================================================================
def _show_welcome_and_redirect(auth: SupabaseAuth) -> None:
    """Muestra pantalla de bienvenida por 3 segundos y hace rerun."""
    user = auth.get_current_user()
    name = user["name"] if user else "Usuario"

    placeholder = st.empty()
    placeholder.markdown(
        f"""
        <div class="welcome-splash">
            <h1>👑 ¡Bienvenido!</h1>
            <h2 style="color: white; font-weight: 700;">{name}</h2>
            <p>Preparando tu dashboard...</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(3)
    placeholder.empty()
    st.rerun()
