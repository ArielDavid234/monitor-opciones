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

    # ── Filtros en sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔧 Filtros de Usuarios")
        solo_activos = st.toggle("Mostrar solo activos", value=True, key="admin_solo_activos")
        filtro_rol = st.selectbox(
            "Rol",
            ["Todos", "user", "admin"],
            index=0,
            key="admin_filtro_rol",
        )

    # ── Obtener perfiles ─────────────────────────────────────────────────
    profiles = auth.fetch_all_profiles()

    if not profiles:
        st.info("No se encontraron perfiles de usuarios.")
        return

    df = pd.DataFrame(profiles)

    # ── Aplicar filtros ──────────────────────────────────────────────────
    if solo_activos:
        df = df[df["is_active"] == True]  # noqa: E712
    if filtro_rol != "Todos":
        df = df[df["role"] == filtro_rol]

    # ── Formatear para mostrar ───────────────────────────────────────────
    df_display = df.copy()

    # Renombrar columnas a español
    col_map = {
        "id": "ID",
        "name": "Nombre",
        "role": "Rol",
        "is_active": "Activo",
        "created_at": "Fecha Creación",
    }
    df_display = df_display.rename(columns=col_map)

    # Formatear rol y activo
    df_display["Rol"] = df_display["Rol"].map({"admin": "👑 Admin", "user": "👤 Usuario"}).fillna("👤 Usuario")
    df_display["Activo"] = df_display["Activo"].map({True: "✅ Sí", False: "❌ No"}).fillna("✅ Sí")

    # Formatear fecha
    if "Fecha Creación" in df_display.columns:
        df_display["Fecha Creación"] = pd.to_datetime(
            df_display["Fecha Creación"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M")

    # ── Métricas rápidas ─────────────────────────────────────────────────
    total = len(profiles)
    activos = sum(1 for p in profiles if p.get("is_active", True))
    admins = sum(1 for p in profiles if p.get("role") == "admin")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Usuarios", total)
    with c2:
        st.metric("Activos", activos)
    with c3:
        st.metric("Inactivos", total - activos)
    with c4:
        st.metric("Admins", admins)

    st.markdown("")

    # ── Tabla de usuarios ────────────────────────────────────────────────
    display_cols = [c for c in ["Nombre", "Rol", "Activo", "Fecha Creación"] if c in df_display.columns]
    st.dataframe(
        df_display[display_cols],
        use_container_width=True,
        hide_index=True,
        height=min(400, 40 + len(df_display) * 35),
    )

    # ── Sección de acciones ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⚙️ Acciones Rápidas")

    # Seleccionar usuario por nombre
    user_options = {
        f"{row.get('name', 'Sin nombre')} ({row.get('role', 'user')})": row["id"]
        for row in profiles
    }
    if not user_options:
        return

    selected_label = st.selectbox(
        "Seleccionar usuario",
        list(user_options.keys()),
        key="admin_select_user",
    )
    selected_id = user_options[selected_label]
    selected_profile = next((p for p in profiles if p["id"] == selected_id), {})

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
