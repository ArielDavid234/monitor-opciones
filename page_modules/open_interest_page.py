# -*- coding: utf-8 -*-
"""Página: 📊 Open Interest — Top Cambios OI de Barchart + OI Heatmap interactivo."""
import streamlit as st
import pandas as pd

from utils.helpers import _fetch_barchart_oi, _inyectar_oi_chg_barchart
from ui.components import render_metric_card, render_metric_row, render_oi_heatmap, render_bias_gauge, render_pro_table
from core.scanner import get_oi_matrix, calculate_call_put_bias


def render(ticker_symbol, **kwargs):
    st.markdown("### 📊 Open Interest")

    # ================================================================
    #  TOP OI CHANGES (Barchart) — Auto-cargado al escanear
    # ================================================================
    st.markdown("#### 🔥 Top Cambios en OI — Barchart")
    st.caption("Se actualiza automáticamente con cada escaneo • Fuente: Barchart.com")

    # Botón para recarga manual
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        bc_refresh = st.button("🔄 Actualizar OI", key="bc_refresh")

    if bc_refresh:
        sim_bc = st.session_state.get("ticker_anterior", "SPY")
        progress_bar = st.progress(0, text="Cargando datos...")
        _fetch_barchart_oi(sim_bc, progress_bar=progress_bar)
        _inyectar_oi_chg_barchart()
        progress_bar.empty()
        # Registrar ticker del OI cargado para rastrear caché
        st.session_state["oi_last_ticker"] = sim_bc

    # Mostrar error
    if st.session_state.barchart_error:
        st.warning(f"⚠️ {st.session_state.barchart_error}")

    # Mostrar datos
    if st.session_state.barchart_data is not None and not st.session_state.barchart_data.empty:
        df_bc_all = st.session_state.barchart_data.copy()

        n_total = len(df_bc_all)

        if n_total == 0:
            st.info("Sin contratos que cumplan los filtros seleccionados.")
        else:
            # Separar positivos y negativos
            df_positivos = df_bc_all[df_bc_all["OI_Chg"] > 0].sort_values("OI_Chg", ascending=False).reset_index(drop=True)
            df_negativos = df_bc_all[df_bc_all["OI_Chg"] < 0].sort_values("OI_Chg", ascending=True).reset_index(drop=True)

            n_pos = len(df_positivos)
            n_neg = len(df_negativos)
            n_calls = len(df_bc_all[df_bc_all["Tipo"] == "CALL"]) if "Tipo" in df_bc_all.columns else 0
            n_puts = len(df_bc_all[df_bc_all["Tipo"] == "PUT"]) if "Tipo" in df_bc_all.columns else 0

            # Calcular contratos cerrados (OI_Chg negativo)
            contratos_cerrados_total = int(df_negativos["OI_Chg"].sum()) if n_neg > 0 else 0
            calls_cerrados = int(df_negativos[df_negativos["Tipo"] == "CALL"]["OI_Chg"].sum()) if n_neg > 0 and "Tipo" in df_negativos.columns else 0
            puts_cerrados = int(df_negativos[df_negativos["Tipo"] == "PUT"]["OI_Chg"].sum()) if n_neg > 0 and "Tipo" in df_negativos.columns else 0

            # Calcular contratos abiertos (OI_Chg positivo)
            contratos_abiertos_total = int(df_positivos["OI_Chg"].sum()) if n_pos > 0 else 0
            calls_abiertos = int(df_positivos[df_positivos["Tipo"] == "CALL"]["OI_Chg"].sum()) if n_pos > 0 and "Tipo" in df_positivos.columns else 0
            puts_abiertos = int(df_positivos[df_positivos["Tipo"] == "PUT"]["OI_Chg"].sum()) if n_pos > 0 and "Tipo" in df_positivos.columns else 0

            # Métricas rápidas
            _pos_pct = (n_pos / n_total * 100) if n_total else 0
            _neg_pct = (n_neg / n_total * 100) if n_total else 0
            st.markdown(render_metric_row([
                render_metric_card("Total Contratos", f"{n_total:,}"),
                render_metric_card("CALLs", f"{n_calls:,}", delta=(n_calls / n_total * 100) if n_total else 0),
                render_metric_card("PUTs", f"{n_puts:,}", delta=(n_puts / n_total * 100) if n_total else 0, color_override="#ef4444"),
                render_metric_card("Señales Positivas", f"{n_pos:,}", delta=_pos_pct),
                render_metric_card("Señales Negativas", f"{n_neg:,}", delta=_neg_pct, color_override="#ef4444"),
            ]), unsafe_allow_html=True)

            # Segunda fila: Contratos abiertos vs cerrados
            st.markdown("---")
            st.markdown("##### 📈 Flujo de Contratos")
            _open_spk = [max(0, v) for v in df_positivos["OI_Chg"].head(10).tolist()] if n_pos > 1 else None
            _close_spk = [abs(v) for v in df_negativos["OI_Chg"].head(10).tolist()] if n_neg > 1 else None
            st.markdown(render_metric_row([
                render_metric_card("Contratos Abiertos", f"{contratos_abiertos_total:,}", delta="Nuevas posiciones", sparkline_data=_open_spk),
                render_metric_card("CALLs Abiertos", f"{calls_abiertos:,}"),
                render_metric_card("PUTs Abiertos", f"{puts_abiertos:,}"),
                render_metric_card("Contratos Cerrados", f"{contratos_cerrados_total:,}", delta="Posiciones cerradas", sparkline_data=_close_spk, color_override="#ef4444"),
                render_metric_card("CALLs Cerrados", f"{calls_cerrados:,}"),
                render_metric_card("PUTs Cerrados", f"{puts_cerrados:,}"),
            ]), unsafe_allow_html=True)

            st.markdown("---")

            # Filtros
            col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
            with col_f1:
                bc_tipo_filtro = st.radio(
                    "Filtrar por tipo", ["Todos", "📞 CALL", "📋 PUT"],
                    horizontal=True, key="bc_tipo_filtro", index=0,
                )
            with col_f2:
                bc_min_chg = st.number_input(
                    "OI Chg mínimo (absoluto)", value=0, step=5, min_value=0, key="bc_min_chg",
                )
            with col_f3:
                bc_orden = st.radio(
                    "Ordenar OI_Chg", ["Mayor → Menor", "Menor → Mayor"],
                    horizontal=True, key="bc_orden", index=0,
                )

            # Re-aplicar filtros
            if bc_tipo_filtro == "📞 CALL":
                df_positivos = df_positivos[df_positivos["Tipo"] == "CALL"].reset_index(drop=True)
                df_negativos = df_negativos[df_negativos["Tipo"] == "CALL"].reset_index(drop=True)
            elif bc_tipo_filtro == "📋 PUT":
                df_positivos = df_positivos[df_positivos["Tipo"] == "PUT"].reset_index(drop=True)
                df_negativos = df_negativos[df_negativos["Tipo"] == "PUT"].reset_index(drop=True)
            if bc_min_chg > 0:
                df_positivos = df_positivos[df_positivos["OI_Chg"] >= bc_min_chg].reset_index(drop=True)
                df_negativos = df_negativos[df_negativos["OI_Chg"].abs() >= bc_min_chg].reset_index(drop=True)
            _asc = (bc_orden == "Menor → Mayor")
            df_positivos = df_positivos.sort_values("OI_Chg", ascending=_asc).reset_index(drop=True)
            df_negativos = df_negativos.sort_values("OI_Chg", ascending=not _asc).reset_index(drop=True)
            n_pos = len(df_positivos)
            n_neg = len(df_negativos)

            st.markdown("---")

            # --- Columnas de tabla ---
            display_cols = ["Tipo", "Ticker", "Strike", "Vencimiento", "DTE",
                            "Volumen", "OI", "OI_Chg", "IV", "Delta", "Último"]

            def _formatear_tabla_oi(df_raw):
                """Formatea un DataFrame de OI para mostrar."""
                cols = [c for c in display_cols if c in df_raw.columns]
                df_fmt = df_raw[cols].copy()
                df_fmt["OI_Chg"] = df_fmt["OI_Chg"].apply(
                    lambda x: f"+{int(x):,}" if pd.notna(x) and x > 0 else f"{int(x):,}" if pd.notna(x) and x < 0 else "0"
                )
                df_fmt["Volumen"] = df_fmt["Volumen"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "-")
                df_fmt["OI"] = df_fmt["OI"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "-")
                df_fmt["IV"] = df_fmt["IV"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) and x > 0 else "-")
                df_fmt["Delta"] = df_fmt["Delta"].apply(lambda x: f"{x:.3f}" if pd.notna(x) and x != 0 else "-")
                df_fmt["Último"] = df_fmt["Último"].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "-")
                df_fmt["Strike"] = df_fmt["Strike"].apply(lambda x: f"${x:,.1f}" if pd.notna(x) else "-")
                return df_fmt

            def _mostrar_tabla_paginada(df_raw, df_fmt, key_prefix, emoji_func):
                """Muestra tabla con paginación y emojis."""
                n = len(df_fmt)
                if n == 0:
                    st.info("Sin contratos en esta categoría.")
                    return

                df_show = df_fmt.copy()
                df_show.insert(0, "", df_raw["OI_Chg"].apply(emoji_func))

                contratos_por_grupo = 20
                if n > contratos_por_grupo:
                    rangos = []
                    for i in range(0, n, contratos_por_grupo):
                        inicio_r = i + 1
                        fin_r = min(i + contratos_por_grupo, n)
                        rangos.append(f"{inicio_r}-{fin_r}")
                    rango_sel = st.selectbox(
                        f"Rango de contratos (Total: {n:,})",
                        rangos, key=f"{key_prefix}_rango",
                    )
                    inicio_idx, fin_idx = map(int, rango_sel.split("-"))
                else:
                    inicio_idx, fin_idx = 1, n

                df_pagina = df_show.iloc[inicio_idx - 1 : fin_idx]
                st.markdown(
                    render_pro_table(
                        df_pagina,
                        badge_count=f"{inicio_idx}-{fin_idx} de {n:,}",
                        max_height=min(500, 35 * len(df_pagina) + 50),
                    ),
                    unsafe_allow_html=True,
                )
                st.caption(f"Mostrando {inicio_idx}-{fin_idx} de {n:,} contratos")

            # ========================================
            # TABLA 1: OI Chg POSITIVO
            # ========================================
            st.markdown("#### 🟢 OI Chg Positivo — Abriendo Posiciones")

            if n_pos > 0:
                df_pos_fmt = _formatear_tabla_oi(df_positivos)
                _mostrar_tabla_paginada(
                    df_positivos, df_pos_fmt, "oi_pos",
                    lambda x: "🔥" if x >= 50 else ("🟢" if x >= 20 else "")
                )
            else:
                st.info("Sin contratos con OI Chg positivo.")

            st.markdown("---")

            # ========================================
            # TABLA 2: OI Chg NEGATIVO
            # ========================================
            st.markdown("#### 🔴 OI Chg Negativo — Cerrando Posiciones")

            if n_neg > 0:
                df_neg_fmt = _formatear_tabla_oi(df_negativos)
                _mostrar_tabla_paginada(
                    df_negativos, df_neg_fmt, "oi_neg",
                    lambda x: "🔥" if x <= -50 else ("🔴" if x <= -20 else "")
                )
            else:
                st.info("Sin contratos con OI Chg negativo.")

        # ================================================================
        #  GAUGE DE SESGO CALL/PUT — Lectura instantánea
        # ================================================================
        if st.session_state.datos_completos:
            st.markdown("---")
            st.markdown("#### 🎯 Sesgo del Mercado de Opciones")
            st.caption(
                "Resume el balance entre Calls y Puts del Open Interest total. "
                "Ayuda a identificar rápidamente si el posicionamiento institucional "
                "es alcista, bajista o neutral."
            )

            bias_data = calculate_call_put_bias(st.session_state.datos_completos)

            _gauge_col, _stats_col = st.columns([3, 1])
            with _gauge_col:
                render_bias_gauge(
                    bias_data["bias_score"],
                    oi_calls=bias_data["oi_calls"],
                    oi_puts=bias_data["oi_puts"],
                    ticker=st.session_state.get("ticker_anterior", ""),
                    key_suffix="_oi_page",
                )
            with _stats_col:
                st.markdown("##### Desglose")
                st.metric("OI Calls", f"{bias_data['oi_calls']:,}")
                st.metric("OI Puts", f"{bias_data['oi_puts']:,}")
                _raw = bias_data["ratio_raw"]
                _raw_fmt = f"{_raw:.3f}" if _raw != float('inf') else "∞"
                st.metric("Ratio C/P", _raw_fmt,
                          delta=f"{bias_data['bias_score'] - 1.0:+.2f} vs neutral")
                st.metric("OI Total", f"{bias_data['total_oi']:,}")

        # ================================================================
        #  OI HEATMAP INTERACTIVO — Strike × Vencimiento (px.imshow)
        # ================================================================
        if st.session_state.datos_completos:
            st.markdown("---")
            st.markdown("#### \U0001f50d Heatmap Interactivo de Open Interest")
            st.caption(
                "Detecta clusters de OI institucional, niveles de soporte/resistencia "
                "gamma y pin risk por expiración. Hover: OI · Volumen · Delta · Gamma · IV · Prima."
            )

            hm_col_oi1, hm_col_oi2, hm_col_oi3 = st.columns([1, 1, 2])
            with hm_col_oi1:
                hm_tipo_oi = st.radio(
                    "Tipo", ["ALL", "CALL", "PUT"],
                    horizontal=True, key="oi_hm_tipo", index=0,
                )
            with hm_col_oi2:
                # Filtro por expiración
                _exps = sorted({d["Vencimiento"] for d in st.session_state.datos_completos
                                if "Vencimiento" in d})
                _exp_options = ["Todas"] + _exps
                hm_exp_sel = st.selectbox(
                    "Expiración", _exp_options, key="oi_hm_exp", index=0,
                )
            with hm_col_oi3:
                min_oi = st.slider(
                    "Umbral mínimo OI", 0, 50_000, 1_000, step=500,
                    key="oi_hm_min",
                    help="Filtra contratos con OI menor a este valor para eliminar ruido retail.",
                )

            # Obtener datos filtrados via get_oi_matrix
            _exp_filter = None if hm_exp_sel == "Todas" else hm_exp_sel
            _oi_matrix, _oi_df = get_oi_matrix(
                st.session_state.datos_completos,
                expiration_filter=_exp_filter,
                min_oi=min_oi,
            )

            if not _oi_df.empty:
                render_oi_heatmap(
                    _oi_df,
                    min_oi_threshold=min_oi,
                    tipo_filter=hm_tipo_oi,
                    key_suffix="_oi_page",
                )
                st.caption(
                    "🔴 Rojo = alto OI (muro de resistencia/soporte) · "
                    "🟢 Verde = bajo OI (sin resistencia, precio se mueve libre) · "
                    "Hover: OI + Volumen + Delta + Gamma + IV + Prima"
                )
            else:
                st.info("Sin datos suficientes del escaneo para generar el heatmap.")

    elif st.session_state.scan_count == 0:
        st.info("⏳ **Ejecuta un escaneo** en 🔍 Live Scanning para cargar los datos de Open Interest automáticamente.")
