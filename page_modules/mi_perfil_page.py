# -*- coding: utf-8 -*-
"""Página: 👤 Mi Perfil — Información y estadísticas del usuario."""
import streamlit as st
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
#  Helpers
# ============================================================================

def _load_user_stats(auth, user_id: str) -> dict:
    """Carga estadísticas de uso desde user_data (Supabase)."""
    raw = auth.load_user_data(user_id, "usage_stats")
    defaults = {
        "scans_total": 0,
        "scans_month": 0,
        "reports_generated": 0,
        "logins_total": 0,
        "last_login": None,
        "avg_income_score": None,
    }
    if raw and isinstance(raw, dict):
        defaults.update(raw)
    return defaults


def _increment_stat(auth, user_id: str, key: str, amount: int = 1) -> None:
    """Incrementa un contador en usage_stats."""
    stats = _load_user_stats(auth, user_id)
    stats[key] = stats.get(key, 0) + amount
    auth.save_user_data(user_id, "usage_stats", stats)


def _record_login(auth, user_id: str) -> None:
    """Registra un nuevo login en las estadísticas."""
    stats = _load_user_stats(auth, user_id)
    stats["logins_total"] = stats.get("logins_total", 0) + 1
    stats["last_login"] = datetime.utcnow().isoformat()
    auth.save_user_data(user_id, "usage_stats", stats)


# ============================================================================
#  CSS
# ============================================================================
_PROFILE_CSS = """
<style>
.profile-container {
    max-width: 900px;
    margin: 0 auto;
}
.profile-hero {
    text-align: center;
    padding: 2.5rem 1rem 2rem 1rem;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-radius: 16px;
    border: 1px solid #334155;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}
.profile-avatar-big {
    width: 96px; height: 96px; border-radius: 50%;
    background: linear-gradient(135deg, #00ff88, #10b981);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 38px; font-weight: 800; color: #0f172a;
    margin-bottom: 12px;
    box-shadow: 0 0 32px rgba(0,255,136,0.25);
}
.profile-name {
    color: white; font-size: 1.6rem; font-weight: 700; margin: 0;
}
.profile-email {
    color: #64748b; font-size: 0.9rem; margin-top: 2px;
}
.profile-role-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-top: 8px;
}
.role-admin {
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: #0f172a;
}
.role-user {
    background: linear-gradient(135deg, #00ff88, #10b981);
    color: #0f172a;
}
.profile-section {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}
.profile-section h3 {
    color: #00ff88;
    font-size: 1.1rem;
    margin: 0 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #334155;
}
.info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
}
.info-item {
    padding: 0.6rem 0;
}
.info-label {
    color: #64748b;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}
.info-value {
    color: white;
    font-size: 0.95rem;
    font-weight: 600;
}
.stat-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
}
.stat-card {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
}
.stat-icon {
    font-size: 1.6rem;
    margin-bottom: 4px;
}
.stat-number {
    color: #00ff88;
    font-size: 1.5rem;
    font-weight: 800;
}
.stat-label {
    color: #94a3b8;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 2px;
}
@media (max-width: 640px) {
    .info-grid { grid-template-columns: 1fr; }
    .stat-grid { grid-template-columns: 1fr 1fr; }
}
</style>
"""


# ============================================================================
#  RENDER
# ============================================================================

def render(**kwargs):
    """Renderiza la página Mi Perfil."""
    from core.container import get_container

    st.markdown(_PROFILE_CSS, unsafe_allow_html=True)

    auth = get_container().auth
    user = auth.get_current_user()
    if not user:
        st.warning("No hay sesión activa.")
        return

    user_id = user["id"]
    user_name = user.get("name", "Usuario")
    user_email = user.get("email", "")
    user_role = user.get("role", "user")

    # ── Obtener datos adicionales del perfil ─────────────────────────────
    profile_extra = auth.fetch_profile_full(user_id)
    created_at_str = "—"
    # Intentar desde la tabla profiles
    if profile_extra and profile_extra.get("created_at"):
        try:
            dt = datetime.fromisoformat(
                profile_extra["created_at"].replace("Z", "+00:00")
            )
            created_at_str = dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            created_at_str = str(profile_extra["created_at"])[:19]

    # ── Estadísticas de uso ────────────────────────────────────────
    stats = _load_user_stats(auth, user_id)

    # Fallback: usar registered_at guardado en usage_stats durante el login
    if created_at_str == "—" and stats.get("registered_at"):
        try:
            dt = datetime.fromisoformat(stats["registered_at"].replace("Z", "+00:00"))
            created_at_str = dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            created_at_str = str(stats["registered_at"])[:19]
    n_favs = len(st.session_state.get("favoritos", []))
    n_watchlist = len(st.session_state.get("watchlist", []))

    # ── Initials ─────────────────────────────────────────────────────────
    initials = "".join(w[0].upper() for w in (user_name or "U").split()[:2])

    # ── Tema persitido ───────────────────────────────────────────────────
    saved_theme = auth.load_user_data(user_id, "theme_preference")
    if saved_theme is None:
        saved_theme = "dark"

    # ====================================================================
    #  Hero — Avatar + Info básica
    # ====================================================================
    role_badge_cls = "role-admin" if user_role == "admin" else "role-user"
    role_label = "👑 Administrador" if user_role == "admin" else "⚡ Pro Plan"

    st.markdown(
        f"""
<div class="profile-container">
<div class="profile-hero">
    <div class="profile-avatar-big">{initials}</div>
    <p class="profile-name">{user_name}</p>
    <p class="profile-email">{user_email}</p>
    <span class="profile-role-badge {role_badge_cls}">{role_label}</span>
</div>
""",
        unsafe_allow_html=True,
    )

    # ====================================================================
    #  Info de cuenta
    # ====================================================================
    last_login_display = "—"
    _ll_raw = user.get("last_login_at") or stats.get("last_login")
    if _ll_raw:
        try:
            ll = datetime.fromisoformat(_ll_raw.replace("Z", "+00:00"))
            last_login_display = ll.strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            last_login_display = str(_ll_raw)[:19]

    st.markdown(
        f"""
<div class="profile-section">
    <h3>📋 Información de la Cuenta</h3>
    <div class="info-grid">
        <div class="info-item">
            <div class="info-label">Nombre</div>
            <div class="info-value">{user_name}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Email</div>
            <div class="info-value">{user_email}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Fecha de Registro</div>
            <div class="info-value">{created_at_str}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Último Login</div>
            <div class="info-value">{last_login_display}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Rol</div>
            <div class="info-value">{role_label}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Estado</div>
            <div class="info-value">{"🟢 Activo" if user.get("is_active", True) else "🔴 Inactivo"}</div>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ====================================================================
    #  Estadísticas de uso
    # ====================================================================
    scans_total = stats.get("scans_total", 0)
    scans_month = stats.get("scans_month", 0)
    reports_gen = stats.get("reports_generated", 0)
    logins_total = stats.get("logins_total", 0)
    avg_score = stats.get("avg_income_score")
    avg_score_str = f"{avg_score:.0f}" if avg_score else "—"

    st.markdown(
        f"""
<div class="profile-section">
    <h3>📊 Estadísticas de Uso</h3>
    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-icon">🔍</div>
            <div class="stat-number">{scans_total}</div>
            <div class="stat-label">Scans Totales</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📅</div>
            <div class="stat-number">{scans_month}</div>
            <div class="stat-label">Scans Este Mes</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📋</div>
            <div class="stat-number">{reports_gen}</div>
            <div class="stat-label">Reportes Generados</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">⭐</div>
            <div class="stat-number">{n_favs}</div>
            <div class="stat-label">Favoritos</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📌</div>
            <div class="stat-number">{n_watchlist}</div>
            <div class="stat-label">Watchlist</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🔑</div>
            <div class="stat-number">{logins_total}</div>
            <div class="stat-label">Logins Totales</div>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ====================================================================
    #  Puntuación promedio
    # ====================================================================
    st.markdown(
        f"""
<div class="profile-section">
    <h3>🏆 Rendimiento</h3>
    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-number">{avg_score_str}</div>
            <div class="stat-label">Income Score Prom.</div>
        </div>
    </div>
</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ====================================================================
    #  Acciones — Editar nombre, cambiar contraseña, tema, cerrar sesión
    # ====================================================================
    st.markdown("---")
    st.markdown("### ⚙️ Configuración")

    col1, col2 = st.columns(2)

    # ── Editar nombre ────────────────────────────────────────────────────
    with col1:
        with st.expander("✏️ Editar Nombre", expanded=False):
            new_name = st.text_input(
                "Nuevo nombre",
                value=user_name,
                max_chars=60,
                key="profile_new_name",
            )
            if st.button("💾 Guardar Nombre", key="btn_save_name"):
                new_name = new_name.strip()
                if not new_name:
                    st.error("El nombre no puede estar vacío.")
                elif new_name == user_name:
                    st.info("El nombre no ha cambiado.")
                else:
                    ok = auth.update_profile(user_id, {"name": new_name})
                    if ok:
                        # Actualizar session state
                        st.session_state["_auth_user"]["name"] = new_name
                        st.session_state.pop("_profile_synced", None)
                        st.success(f"Nombre actualizado a **{new_name}**.")
                        st.rerun()
                    else:
                        st.error("Error al actualizar el nombre.")

    # ── Cambiar contraseña ───────────────────────────────────────────────
    with col2:
        with st.expander("🔑 Cambiar Contraseña", expanded=False):
            st.markdown(
                "Se enviará un enlace de restablecimiento a tu correo electrónico."
            )
            if st.button("📧 Enviar enlace de cambio", key="btn_reset_pw"):
                ok, msg = auth.send_password_reset(user_email)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    # ── Tema ─────────────────────────────────────────────────────────────
    st.markdown("")
    tcol1, tcol2 = st.columns([1, 3])
    with tcol1:
        theme_options = ["dark", "light"]
        theme_labels = {"dark": "🌙 Modo Oscuro", "light": "☀️ Modo Claro"}
        current_idx = theme_options.index(saved_theme) if saved_theme in theme_options else 0
        selected_theme = st.selectbox(
            "🎨 Tema de la aplicación",
            options=theme_options,
            format_func=lambda x: theme_labels[x],
            index=current_idx,
            key="profile_theme_select",
        )
        if selected_theme != saved_theme:
            auth.save_user_data(user_id, "theme_preference", selected_theme)
            st.success(f"Tema cambiado a **{theme_labels[selected_theme]}**")
            st.rerun()

    # ── Cerrar sesión ────────────────────────────────────────────────────
    st.markdown("---")
    _, ccol, _ = st.columns([1, 1, 1])
    with ccol:
        if st.button(
            "🚪 Cerrar Sesión",
            use_container_width=True,
            type="primary",
            key="btn_logout_profile",
        ):
            auth.logout()
            st.rerun()
