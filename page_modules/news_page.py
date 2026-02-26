# -*- coding: utf-8 -*-
"""Página: 📰 News — Noticias Financieras en Tiempo Real."""
import streamlit as st
from datetime import datetime

from core.news import obtener_noticias_financieras


def render(ticker_symbol, **kwargs):
    st.markdown("### 📰 Noticias Financieras en Tiempo Real")

    # --- CONTROLES ---
    col_load, col_refresh = st.columns([1, 1])

    with col_load:
        cargar_noticias_btn = st.button(
            "📡 Cargar Noticias" if not st.session_state.noticias_data else "📡 Recargar Todo",
            type="primary",
            use_container_width=True,
            key="btn_cargar_noticias_main",
        )
    with col_refresh:
        refresh_noticias_btn = st.button(
            "🔄 Refrescar",
            use_container_width=True,
            key="btn_refresh_noticias",
            disabled=not st.session_state.noticias_data,
        )

    # --- CARGAR / REFRESCAR ---
    if cargar_noticias_btn or refresh_noticias_btn:
        with st.spinner("📡 Obteniendo noticias de múltiples fuentes..."):
            noticias = obtener_noticias_financieras()
            if noticias:
                st.session_state.noticias_data = noticias
                st.session_state.noticias_last_refresh = datetime.now()
                st.session_state.noticias_filtro = "Todas"
                st.rerun()

    # --- CONTENIDO ---
    if not st.session_state.noticias_data:
        st.info(
            "👆 Presiona **Cargar Noticias** para obtener las últimas noticias financieras "
            "de Yahoo Finance, MarketWatch, CNBC, Reuters e Investing.com."
        )
    else:
        # Última actualización
        st.metric("🕐 Última actualización", st.session_state.noticias_last_refresh.strftime('%H:%M:%S'))

        # Distribución por categoría
        cat_counts = {}
        for n in st.session_state.noticias_data:
            cat = n["categoria"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:6]

        # Botones de filtro por categoría
        if top_cats:
            filtro_actual = st.session_state.get("noticias_filtro", "Todas")
            btn_labels = [("Todas", len(st.session_state.noticias_data))] + top_cats
            filter_cols = st.columns(len(btn_labels))
            for i, (cat_name, cat_count) in enumerate(btn_labels):
                with filter_cols[i]:
                    is_active = filtro_actual == cat_name
                    label_text = f"{'✅ ' if is_active else ''}{cat_name} ({cat_count})"
                    if st.button(label_text, key=f"filtro_cat_{i}", use_container_width=True,
                                 type="primary" if is_active else "secondary"):
                        st.session_state.noticias_filtro = cat_name
                        st.rerun()

        st.divider()

        # Aplicar filtro activo
        filtro_activo = st.session_state.get("noticias_filtro", "Todas")
        if filtro_activo == "Todas":
            noticias_mostrar = st.session_state.noticias_data
        else:
            noticias_mostrar = [n for n in st.session_state.noticias_data if n["categoria"] == filtro_activo]

        titulo_filtro = f" — {filtro_activo}" if filtro_activo != "Todas" else ""
        st.markdown(f"#### 📋 {len(noticias_mostrar)} noticias{titulo_filtro}")

        cat_emoji_map = {
            "Earnings": "💰",
            "Fed / Tasas": "🏛️",
            "Economía": "📊",
            "Trading": "📈",
            "Crypto": "₿",
            "Commodities": "🛢️",
            "Geopolítica": "🌍",
            "Top Stories": "⭐",
            "Mercados": "📈",
        }

        for n in noticias_mostrar:
            cat = n["categoria"]
            emoji = cat_emoji_map.get(cat, "📰")

            with st.container():
                col_noticia, col_cat = st.columns([5, 1])
                with col_noticia:
                    if n["url"]:
                        st.markdown(f"**[{n['titulo']}]({n['url']})**")
                    else:
                        st.markdown(f"**{n['titulo']}**")

                    if n["descripcion"]:
                        st.caption(n["descripcion"])

                    meta_parts = []
                    if n["fuente"]:
                        meta_parts.append(f"📰 {n['fuente']}")
                    if n["tiempo"]:
                        meta_parts.append(f"🕐 {n['tiempo']}")
                    if meta_parts:
                        st.caption(" · ".join(meta_parts))

                with col_cat:
                    st.markdown(f"**{emoji} {cat}**")

                st.divider()
