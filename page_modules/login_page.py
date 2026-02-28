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

        # ── Banner si viene de confirmación de email ─────────────────────
        if st.session_state.pop("_email_just_confirmed", False):
            st.success(
                "✅ ¡Tu correo ha sido confirmado exitosamente! "
                "Ya puedes iniciar sesión con tu cuenta."
            )

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
                login_remember = st.checkbox("Recordarme (1 día)", key="login_remember")
                login_submit = st.form_submit_button(
                    "🔐 Iniciar Sesión",
                    use_container_width=True,
                    type="primary",
                )

            if login_submit:
                ok, msg = auth.login(login_email, login_password, login_remember)
                if ok:
                    st.session_state["_show_welcome_splash"] = True
                    st.rerun()
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
                    if SupabaseAuth.is_authenticated():
                        # Registro sin confirmación de email → ya autenticado
                        st.rerun()
                    else:
                        st.success(msg)
                else:
                    st.error(msg)

    return False


# ============================================================================
#                    WELCOME SPLASH (full-screen overlay → redirect)
# ============================================================================
def show_welcome_splash(user: dict | None = None) -> None:
    """Pantalla de bienvenida full-screen sobre toda la app, luego rerun.

    Se llama desde app_web.py a nivel top-level (sin columnas) para
    que el overlay cubra toda la pantalla correctamente.
    """
    name = (user or {}).get("name", "Usuario")
    initials = "".join(w[0].upper() for w in name.split()[:2]) if name else "U"

    splash = st.empty()
    splash.markdown(
        f"""
        <style>
        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"] {{ display: none !important; }}
        .ok-overlay {{
            position: fixed; inset: 0; z-index: 999999;
            background: linear-gradient(135deg, #0a0f1e 0%, #0d1b2a 50%, #0a1628 100%);
            display: flex; align-items: center; justify-content: center;
            animation: okFadeIn 0.4s ease;
        }}
        @keyframes okFadeIn {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
        .ok-card {{
            text-align: center;
            padding: 3.5rem 4rem;
            background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
            border-radius: 24px;
            border: 1px solid #1e3a5f;
            box-shadow: 0 0 80px rgba(0,255,136,0.08), 0 8px 40px rgba(0,0,0,0.6);
            max-width: 460px; width: 90%;
            animation: okSlideUp 0.45s cubic-bezier(.22,1,.36,1) both;
        }}
        @keyframes okSlideUp {{
            from {{ transform: translateY(28px); opacity:0; }}
            to   {{ transform: translateY(0);   opacity:1; }}
        }}
        .ok-av {{
            width:72px; height:72px; border-radius:50%;
            background: linear-gradient(135deg, #00ff88, #10b981);
            display:inline-flex; align-items:center; justify-content:center;
            font-size:26px; font-weight:800; color:#0f172a;
            margin-bottom:1.2rem;
            box-shadow: 0 0 24px rgba(0,255,136,0.35);
        }}
        .ok-label {{
            font-size:0.85rem; color:#64748b; font-weight:500;
            letter-spacing:0.12em; text-transform:uppercase; margin-bottom:0.3rem;
        }}
        .ok-name {{
            font-size:2rem; font-weight:800; color:#fff; line-height:1.15;
            margin-bottom:0.6rem;
        }}
        .ok-badge {{
            display:inline-block;
            background:rgba(0,255,136,0.1); border:1px solid rgba(0,255,136,0.25);
            color:#00ff88; font-size:0.78rem; font-weight:600;
            padding:0.25rem 0.9rem; border-radius:999px;
            margin-bottom:1.8rem; letter-spacing:0.06em;
        }}
        .ok-sub {{ color:#475569; font-size:0.88rem; }}
        .ok-dots {{
            display:flex; justify-content:center; gap:6px; margin-top:1.6rem;
        }}
        .ok-dots span {{
            width:7px; height:7px; border-radius:50%; background:#00ff88;
            animation: okBounce 1.2s infinite ease-in-out both;
        }}
        .ok-dots span:nth-child(1) {{ animation-delay:-0.32s; }}
        .ok-dots span:nth-child(2) {{ animation-delay:-0.16s; }}
        @keyframes okBounce {{
            0%,80%,100% {{ transform:scale(0); opacity:0.4; }}
            40%          {{ transform:scale(1); opacity:1;   }}
        }}
        </style>
        <div class="ok-overlay">
          <div class="ok-card">
            <div class="ok-av">{initials}</div>
            <div class="ok-label">&#x1F451;&ensp;Bienvenido de vuelta</div>
            <div class="ok-name">{name}</div>
            <div class="ok-badge">Pro Plan</div>
            <div class="ok-sub">Cargando&hellip;</div>
            <div class="ok-dots"><span></span><span></span><span></span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(3)
    splash.empty()
    st.rerun()
