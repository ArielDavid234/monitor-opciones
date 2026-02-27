# -*- coding: utf-8 -*-
"""
Administrar Usuarios — Panel de administración de OptionsKing Analytics.

Solo visible para usuarios con rol 'admin'.
Permite ver, filtrar y modificar perfiles de usuarios.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from core.auth import SupabaseAuth


def render(**kwargs) -> None:
    """Renderiza la página de administración de usuarios."""

    auth = SupabaseAuth()

    # ── Gate de admin ────────────────────────────────────────────────────
    if not auth.is_admin():
        st.error("⛔ No tienes permisos para acceder a esta sección.")
        st.stop()

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#1e293b,#0f172a);
                    border:1px solid #334155;border-radius:16px;
                    padding:1.5rem 2rem;margin-bottom:1.5rem;">
            <h2 style="color:#00ff88;margin:0 0 0.3rem 0;">
                👑 Administrar Usuarios
            </h2>
            <p style="color:#94a3b8;margin:0;font-size:0.9rem;">
                Gestión de perfiles, roles y estado de los usuarios de la plataforma.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Obtener perfiles ─────────────────────────────────────────────────
    profiles = auth.fetch_all_profiles()

    if not profiles:
        st.info("No se encontraron perfiles de usuarios.")
        return

    # ── Contadores para los botones ──────────────────────────────────────
    total     = len(profiles)
    activos   = sum(1 for p in profiles if p.get("is_active", True))
    inactivos = total - activos
    admins    = sum(1 for p in profiles if p.get("role") == "admin")

    # ── Sección de acciones ──────────────────────────────────────────────
    st.markdown("#### ⚙️ Acciones Rápidas")

    user_options = {
        f"{row.get('name', 'Sin nombre')} ({row.get('role', 'user')}) · {row['id']}": row["id"]
        for row in profiles
    }

    selected_label = st.selectbox(
        "Seleccionar usuario",
        list(user_options.keys()),
        key="admin_select_user",
    )
    selected_id = user_options[selected_label]
    selected_profile = next((p for p in profiles if p["id"] == selected_id), {})

    current_user = auth.get_current_user()
    target_is_admin = selected_profile.get("role") == "admin"
    target_is_self = selected_id == current_user.get("id")

    if target_is_admin and not target_is_self:
        st.warning("⚠️ No puedes modificar a otro administrador.")
    elif target_is_self:
        st.info("ℹ️ Este eres tú — no puedes cambiar tu propio rol ni desactivarte.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            new_role = st.selectbox(
                "Cambiar rol",
                ["user", "admin"],
                index=0 if selected_profile.get("role") == "user" else 1,
                key="admin_new_role",
            )
            if st.button("💾 Guardar Rol", use_container_width=True, key="btn_save_role"):
                if auth.update_profile(selected_id, {"role": new_role}):
                    st.success(f"Rol actualizado a '{new_role}'.")
                    st.rerun()
                else:
                    st.error("Error al actualizar el rol.")

        with col_b:
            is_active = selected_profile.get("is_active", True)
            action_label = "🚫 Desactivar" if is_active else "✅ Activar"
            if st.button(action_label, use_container_width=True, key="btn_toggle_active"):
                if auth.update_profile(selected_id, {"is_active": not is_active}):
                    st.success(f"Usuario {'activado' if not is_active else 'desactivado'}.")
                    st.rerun()
                else:
                    st.error("Error al cambiar el estado.")

    st.markdown("---")

    st.markdown("#### 👥 Usuarios")

    # ── Botones de métrica / filtro rápido ───────────────────────────────
    filtro_metrica = st.session_state.get("admin_metric_filter", "Todos")

    btn_defs = [
        ("Todos",     total,     "Todos"),
        ("Activos",   activos,   "activos"),
        ("Inactivos", inactivos, "inactivos"),
        ("Admins",    admins,    "admins"),
    ]

    cols = st.columns(4)
    for i, (label, count, key) in enumerate(btn_defs):
        with cols[i]:
            is_sel = filtro_metrica == key
            btn_label = f"{'✅ ' if is_sel else ''}{label} ({count})"
            if st.button(btn_label, key=f"admin_metric_btn_{i}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state["admin_metric_filter"] = key
                st.rerun()

    st.markdown("")

    df = pd.DataFrame(profiles)

    # ── Aplicar filtro de botón ──────────────────────────────────────────
    filtro_metrica = st.session_state.get("admin_metric_filter", "Todos")
    if filtro_metrica == "activos":
        df = df[df["is_active"] == True]   # noqa: E712
    elif filtro_metrica == "inactivos":
        df = df[df["is_active"] == False]  # noqa: E712
    elif filtro_metrica == "admins":
        df = df[df["role"] == "admin"]
    # "Todos" — sin filtros adicionales, muestra todos

    # ── Formatear para mostrar ───────────────────────────────────────────
    df_display = df.copy()

    col_map = {
        "id": "ID",
        "name": "Nombre",
        "role": "Rol",
        "is_active": "Activo",
    }
    df_display = df_display.rename(columns=col_map)

    df_display["Rol"] = df_display["Rol"].map({"admin": "👑 Admin", "user": "👤 Usuario"}).fillna("👤 Usuario")
    df_display["Activo"] = df_display["Activo"].map({True: "✅ Sí", False: "❌ No"}).fillna("✅ Sí")

    # ── Tabla de usuarios ────────────────────────────────────────────────
    display_cols = [c for c in ["ID", "Nombre", "Rol", "Activo"] if c in df_display.columns]
    st.dataframe(
        df_display[display_cols],
        use_container_width=True,
        hide_index=True,
        height=min(400, 40 + len(df_display) * 35),
    )
