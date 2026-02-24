# -*- coding: utf-8 -*-
"""Página: 🏢 Important Companies — Proyecciones de crecimiento a 10 años."""
import streamlit as st


from config.watchlists import WATCHLIST_EMPRESAS, WATCHLIST_EMERGENTES
from utils.helpers import (
    _cargar_watchlist_consolidadas_dinamica,
    _cargar_watchlist_emergentes_dinamica,
)
from ui.components import (
    render_metric_card, render_metric_row, render_pro_table,
    render_empresa_card, render_tabla_comparativa,
    analizar_watchlist, render_watchlist_preview, render_analisis_completo,
)


def render(ticker_symbol, **kwargs):
    st.markdown("### 🏢 Proyecciones de Crecimiento a 10 Años")

    # ==============================================================
    #  SECCIÓN 1: EMPRESAS CONSOLIDADAS
    # ==============================================================
    st.markdown("---")
    st.markdown("## 🏢 Empresas Consolidadas — Top Corporations")
    st.caption("Grandes corporaciones con historial probado y proyección de crecimiento sostenido a 10 años.")

    with st.spinner("Actualizando ranking por capitalización..."):
        _wl_consolidadas = _cargar_watchlist_consolidadas_dinamica()

    _tickers_dinamicos = list(_wl_consolidadas.keys())
    _tickers_estaticos = list(WATCHLIST_EMPRESAS.keys())
    _nuevas = [t for t in _tickers_dinamicos if t not in _tickers_estaticos]
    _salieron = [t for t in _tickers_estaticos if t not in _tickers_dinamicos]
    if _nuevas or _salieron:
        _hash_c = frozenset(_nuevas + _salieron)
        if st.session_state._wl_consolidadas_shown_hash != _hash_c:
            st.session_state._wl_consolidadas_shown_hash = _hash_c
            _cambios_txt = []
            if _nuevas:
                _cambios_txt.append(f"**Entraron:** {', '.join(_nuevas)}")
            if _salieron:
                _cambios_txt.append(f"**Salieron:** {', '.join(_salieron)}")
            st.info(f"🔄 Ranking actualizado por market cap — {' | '.join(_cambios_txt)}")

    col_btn_c, col_info_c = st.columns([1, 3])
    with col_btn_c:
        analizar_consol_btn = st.button(
            "📊 Analizar Consolidadas en Vivo",
            type="primary",
            use_container_width=True,
            key="btn_analizar_consolidadas",
        )
    with col_info_c:
        if "proyecciones_resultados" in st.session_state and st.session_state.proyecciones_resultados:
            st.success(f"✅ Datos en vivo cargados — {len(st.session_state.proyecciones_resultados)} empresas analizadas")

    if analizar_consol_btn:
        st.session_state.scanning_active = True
        analizar_watchlist(_wl_consolidadas, "proyecciones_resultados", "consolidadas")
        st.session_state.scanning_active = False

    if "proyecciones_resultados" in st.session_state and st.session_state.proyecciones_resultados:
        resultados = st.session_state.proyecciones_resultados

        alta_count = sum(1 for r in resultados if r["clasificacion"] == "ALTA")
        media_count = sum(1 for r in resultados if r["clasificacion"] == "MEDIA")
        baja_count = sum(1 for r in resultados if r["clasificacion"] == "BAJA")
        st.markdown(render_metric_row([
            render_metric_card("Proyección Alta", f"{alta_count}"),
            render_metric_card("Proyección Media", f"{media_count}", color_override="#f59e0b"),
            render_metric_card("Proyección Baja", f"{baja_count}", color_override="#ef4444"),
        ]), unsafe_allow_html=True)

        for r in resultados:
            info_emp = _wl_consolidadas.get(r["symbol"])
            st.html(render_empresa_card(r, info_emp, _wl_consolidadas))

        st.markdown("#### 📋 Tabla Comparativa")
        df_tabla = render_tabla_comparativa(resultados)
        st.markdown(
            render_pro_table(df_tabla, title="📋 Tabla Comparativa Consolidadas", badge_count=f"{len(df_tabla)}"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown("#### 🏛️ Top Empresas Consolidadas")
        render_watchlist_preview(_wl_consolidadas)

    if "proyecciones_resultados" in st.session_state and st.session_state.proyecciones_resultados:
        with st.expander("📊 Análisis de las Empresas Consolidadas", expanded=False):
            render_analisis_completo(st.session_state.proyecciones_resultados, _wl_consolidadas)

    # ==============================================================
    #  SECCIÓN 2: EMPRESAS EMERGENTES
    # ==============================================================
    st.markdown("---")
    st.markdown("## 🚀 Empresas Emergentes — Futuras Transnacionales")
    st.caption("Empresas de menor capitalización con tecnologías disruptivas y potencial de convertirse en gigantes. Mayor riesgo, mayor recompensa.")

    _wl_emergentes = _cargar_watchlist_emergentes_dinamica()
    if set(_wl_emergentes.keys()) != set(WATCHLIST_EMERGENTES.keys()):
        entraron = set(_wl_emergentes.keys()) - set(WATCHLIST_EMERGENTES.keys())
        salieron = set(WATCHLIST_EMERGENTES.keys()) - set(_wl_emergentes.keys())
        _hash_e = frozenset(entraron | salieron)
        if st.session_state._wl_emergentes_shown_hash != _hash_e:
            st.session_state._wl_emergentes_shown_hash = _hash_e
            partes = ["🔄 Ranking actualizado por momentum"]
            if entraron:
                partes.append(f"Entraron: {', '.join(sorted(entraron))}")
            if salieron:
                partes.append(f"Salieron: {', '.join(sorted(salieron))}")
            st.info(" | ".join(partes))

    col_btn_e, col_info_e = st.columns([1, 3])
    with col_btn_e:
        analizar_emerg_btn = st.button(
            "🚀 Analizar Emergentes en Vivo",
            type="primary",
            use_container_width=True,
            key="btn_analizar_emergentes",
        )
    with col_info_e:
        if "emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados:
            st.success(f"✅ Datos en vivo cargados — {len(st.session_state.emergentes_resultados)} empresas analizadas")

    if analizar_emerg_btn:
        st.session_state.scanning_active = True
        analizar_watchlist(_wl_emergentes, "emergentes_resultados", "emergentes")
        st.session_state.scanning_active = False

    if "emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados:
        resultados_em = st.session_state.emergentes_resultados

        alta_em = sum(1 for r in resultados_em if r["clasificacion"] == "ALTA")
        media_em = sum(1 for r in resultados_em if r["clasificacion"] == "MEDIA")
        baja_em = sum(1 for r in resultados_em if r["clasificacion"] == "BAJA")
        st.markdown(render_metric_row([
            render_metric_card("Proyección Alta", f"{alta_em}"),
            render_metric_card("Proyección Media", f"{media_em}", color_override="#f59e0b"),
            render_metric_card("Proyección Baja", f"{baja_em}", color_override="#ef4444"),
        ]), unsafe_allow_html=True)

        for r in resultados_em:
            info_emp = _wl_emergentes.get(r["symbol"])
            st.html(render_empresa_card(r, info_emp, _wl_emergentes, es_emergente=True))

        st.markdown("#### 📋 Tabla Comparativa Emergentes")
        df_emerg = render_tabla_comparativa(resultados_em, es_emergente=True)
        st.markdown(
            render_pro_table(df_emerg, title="📋 Tabla Comparativa Emergentes", badge_count=f"{len(df_emerg)}"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown("#### 🚀 Top Empresas Emergentes")
        render_watchlist_preview(_wl_emergentes)

    if "emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados:
        with st.expander("📊 Análisis de las Empresas Emergentes", expanded=False):
            render_analisis_completo(st.session_state.emergentes_resultados, _wl_emergentes, es_emergente=True)
