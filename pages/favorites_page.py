# -*- coding: utf-8 -*-
"""Página: ⭐ Favorites — Watchlist de Compañías + Contratos Favoritos."""
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.formatters import (
    _fmt_monto, _fmt_lado, _fmt_oi_chg,
)
from utils.favorites import (
    _eliminar_favorito, _guardar_favoritos,
    _agregar_a_watchlist, _eliminar_de_watchlist,
)
from ui.components import (
    render_metric_card, render_metric_row, render_pro_table,
    _sentiment_badge, _type_badge,
)
from core.scanner import obtener_historial_contrato


# ─── Estilos para las tarjetas de Watchlist ─────────────────────────────────
_WL_CARD_CSS = """
<style>
.wl-card{
    border:1px solid #2a2a3a;
    border-radius:10px;
    padding:16px 18px;
    background:#0d1117;
    margin-bottom:8px;
    transition: border-color 0.2s;
}
.wl-card:hover{ border-color:#00ff88; }
.wl-ticker{
    font-size:1.5rem;
    font-weight:800;
    color:#00ff88;
    letter-spacing:1px;
}
.wl-nombre{
    color:#ccc;
    font-size:0.9rem;
    margin-top:2px;
}
.wl-fecha{
    color:#555;
    font-size:0.72rem;
    margin-top:6px;
}
</style>
"""


def render(ticker_symbol, **kwargs):
    st.markdown(_WL_CARD_CSS, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    #  SECCIÓN 1 — WATCHLIST DE COMPAÑÍAS
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("### 📌 Watchlist")
    st.caption(
        "Guarda las compañías que más te interesan. "
        "Haz clic en **🔍 Analizar** para ir directo a Live Scanning y ejecutar el escaneo automáticamente."
    )

    # ── Formulario para agregar ──────────────────────────────────────────────
    with st.form("form_add_watchlist", clear_on_submit=True):
        col_t, col_n, col_btn = st.columns([1, 2, 1])
        with col_t:
            wl_new_ticker = st.text_input(
                "Ticker", placeholder="AAPL", max_chars=10,
                label_visibility="visible",
            )
        with col_n:
            wl_new_nombre = st.text_input(
                "Nombre (opcional)", placeholder="Apple Inc.",
                label_visibility="visible",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            wl_submitted = st.form_submit_button("➕ Agregar", use_container_width=True)

        if wl_submitted:
            ok, msg = _agregar_a_watchlist(wl_new_ticker, wl_new_nombre)
            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.warning(f"⚠️ {msg}")

    # ── Grid de tarjetas ─────────────────────────────────────────────────────
    watchlist = st.session_state.get("watchlist", [])

    if not watchlist:
        st.info("Sin compañías en la Watchlist. Usa el formulario de arriba para agregar una.")
    else:
        COLS_PER_ROW = 3
        for row_start in range(0, len(watchlist), COLS_PER_ROW):
            row_items = watchlist[row_start : row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col, item in zip(cols, row_items):
                with col:
                    wl_tk = item["ticker"]
                    wl_nm = item.get("nombre", "")
                    wl_dt = item.get("agregado", "")[:10]

                    nombre_html = (
                        f'<div class="wl-nombre">{wl_nm}</div>'
                        if wl_nm else ""
                    )
                    st.markdown(
                        f"""<div class="wl-card">
                            <div class="wl-ticker">{wl_tk}</div>
                            {nombre_html}
                            <div class="wl-fecha">Agregado: {wl_dt}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                    btn_a, btn_d = st.columns([3, 1])
                    with btn_a:
                        if st.button(
                            "🔍 Analizar",
                            key=f"wl_analyze_{wl_tk}",
                            use_container_width=True,
                            type="primary",
                        ):
                            # Redirigir a Live Scanning con este ticker
                            st.session_state["ticker_input"] = wl_tk
                            st.session_state["nav_radio"] = "🔍 Live Scanning"
                            st.session_state.ticker_anterior = ""  # fuerza detección de cambio
                            st.session_state.trigger_scan = True
                            # Limpiar datos del scan anterior
                            st.session_state.alertas_actuales = []
                            st.session_state.datos_completos = []
                            st.session_state.clusters_detectados = []
                            st.session_state.barchart_data = None
                            st.session_state.scan_error = None
                            st.rerun()
                    with btn_d:
                        if st.button(
                            "🗑️",
                            key=f"wl_del_{wl_tk}",
                            use_container_width=True,
                            help=f"Eliminar {wl_tk} de la Watchlist",
                        ):
                            _eliminar_de_watchlist(wl_tk)
                            st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    #  SECCIÓN 2 — CONTRATOS FAVORITOS
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### ⭐ Contratos Favoritos")

    favoritos = st.session_state.get("favoritos", [])

    if not favoritos:
        st.info("No hay contratos en favoritos. Ejecuta un escaneo y usa el botón ☆ **Guardar en Favoritos** en cualquier alerta.")
    else:
        # Métricas rápidas
        n_calls_fav = sum(1 for f in favoritos if f.get("Tipo_Opcion") == "CALL")
        n_puts_fav = sum(1 for f in favoritos if f.get("Tipo_Opcion") == "PUT")
        prima_total_fav = sum(f.get("Prima_Volumen", 0) for f in favoritos)
        st.markdown(render_metric_row([
            render_metric_card("Total Favoritos", f"{len(favoritos)}"),
            render_metric_card("Calls", f"{n_calls_fav}"),
            render_metric_card("Puts", f"{n_puts_fav}"),
            render_metric_card("Prima Total", _fmt_monto(prima_total_fav)),
        ]), unsafe_allow_html=True)

        # Tabla resumen
        fav_df = pd.DataFrame(favoritos)
        cols_tabla_fav = ["Contrato", "Ticker", "Tipo_Opcion", "Strike", "Vencimiento",
                          "Volumen", "OI", "Ask", "Bid", "Ultimo", "Lado", "Prima_Volumen"]
        cols_disp_fav = [c for c in cols_tabla_fav if c in fav_df.columns]
        display_fav_df = fav_df[cols_disp_fav].copy()
        if "Tipo_Opcion" in display_fav_df.columns and "Lado" in display_fav_df.columns:
            display_fav_df.insert(0, "Sentimiento", display_fav_df.apply(
                lambda row: _sentiment_badge(row["Tipo_Opcion"], row.get("Lado", "N/A")), axis=1
            ))
        if "Tipo_Opcion" in display_fav_df.columns:
            display_fav_df["Tipo_Opcion"] = display_fav_df["Tipo_Opcion"].apply(_type_badge)
        if "Lado" in display_fav_df.columns:
            display_fav_df["Lado"] = display_fav_df["Lado"].apply(_fmt_lado)
        if "Prima_Volumen" in display_fav_df.columns:
            display_fav_df = display_fav_df.rename(columns={"Prima_Volumen": "Prima Total"})
            display_fav_df["Prima Total"] = display_fav_df["Prima Total"].apply(_fmt_monto)
        st.markdown(
            render_pro_table(display_fav_df, title="⭐ Favoritos", badge_count=f"{len(favoritos)}"),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Detalle individual de cada favorito
        st.markdown("#### 🔍 Detalle de Contratos")
        for idx_fav, fav in enumerate(favoritos):
            fav_sym = fav.get("Contrato", "N/A")
            fav_tipo = fav.get("Tipo_Opcion", "N/A")
            fav_strike = fav.get("Strike", 0)
            fav_venc = fav.get("Vencimiento", "N/A")
            fav_prima = fav.get("Prima_Volumen", 0)

            # Calcular días para vencimiento
            try:
                dias_venc = (datetime.strptime(fav_venc, "%Y-%m-%d") - datetime.now()).days
                dias_str = f"{dias_venc}d" if dias_venc >= 0 else "EXPIRADO"
            except Exception:
                dias_str = "N/A"

            fav_label = (
                f"⭐ {fav_tipo} ${fav_strike} | Venc: {fav_venc} ({dias_str}) | "
                f"Prima: ${fav_prima:,.0f} | {fav_sym}"
            )

            with st.expander(fav_label, expanded=False):
                col_fav_info, col_fav_chart = st.columns([1, 2])

                with col_fav_info:
                    st.markdown("**📄 Información del Contrato**")
                    st.markdown(f"- **Símbolo:** `{fav_sym}`")
                    st.markdown(f"- **Ticker:** {fav.get('Ticker', 'N/A')}")
                    st.markdown(f"- **Tipo:** {fav_tipo}")
                    st.markdown(f"- **Strike:** ${fav_strike}")
                    st.markdown(f"- **Vencimiento:** {fav_venc} ({dias_str})")
                    st.markdown(f"- **Volumen:** {fav.get('Volumen', 0):,}")
                    st.markdown(f"- **OI:** {fav.get('OI', 0):,}")
                    oi_chg_val = fav.get('OI_Chg', 0)
                    st.markdown(f"- **OI Chg:** {_fmt_oi_chg(oi_chg_val)}")
                    st.markdown(f"- **Ask:** ${fav.get('Ask', 0)}")
                    st.markdown(f"- **Bid:** ${fav.get('Bid', 0)}")
                    st.markdown(f"- **Último:** ${fav.get('Ultimo', 0)}")
                    st.markdown(f"- **Lado:** {_fmt_lado(fav.get('Lado', 'N/A'))}")
                    iv_fav = fav.get('IV', 0)
                    st.markdown(f"- **IV:** {iv_fav:.1f}%" if iv_fav > 0 else "- **IV:** N/A")
                    st.markdown(f"- **Prima Total:** {_fmt_monto(fav.get('Prima_Volumen', 0))}")
                    st.markdown(f"- **Tipo Alerta:** {fav.get('Tipo_Alerta', 'N/A')}")
                    st.markdown(f"- **Guardado:** {fav.get('Guardado_En', 'N/A')}")

                    # Botón eliminar
                    if st.button("🗑️ Eliminar de Favoritos", key=f"del_fav_{idx_fav}_{fav_sym}", use_container_width=True):
                        _eliminar_favorito(fav_sym)
                        st.success(f"🗑️ {fav_sym} eliminado de Favoritos")
                        st.rerun()

                with col_fav_chart:
                    if fav_sym and fav_sym != "N/A":
                        with st.spinner("Cargando gráfica del contrato..."):
                            hist_fav, err_fav = obtener_historial_contrato(fav_sym)

                        if err_fav:
                            st.warning(f"⚠️ Error al cargar historial: {err_fav}")
                        elif hist_fav.empty:
                            st.info("ℹ️ No hay datos históricos disponibles.")
                        else:
                            st.markdown(f"**Precio del contrato** — `{fav_sym}`")
                            chart_fav_price = hist_fav[["Close"]].copy()
                            chart_fav_price.columns = ["Precio"]
                            st.line_chart(chart_fav_price, height=280)

                            if "Volume" in hist_fav.columns:
                                chart_fav_vol = hist_fav[["Volume"]].copy()
                                chart_fav_vol.columns = ["Volumen"]
                                st.bar_chart(chart_fav_vol, height=160)

        # Botón limpiar todos
        st.markdown("---")
        col_limpiar, _ = st.columns([1, 3])
        with col_limpiar:
            if st.button("🗑️ Limpiar todos los favoritos", use_container_width=True, type="secondary"):
                st.session_state.favoritos = []
                _guardar_favoritos([])
                st.success("Se eliminaron todos los favoritos")
                st.rerun()


    favoritos = st.session_state.get("favoritos", [])

    if not favoritos:
        st.info("No hay contratos en favoritos. Ejecuta un escaneo y usa el botón ☆ **Guardar en Favoritos** en cualquier alerta.")
    else:
        # Métricas rápidas
        n_calls_fav = sum(1 for f in favoritos if f.get("Tipo_Opcion") == "CALL")
        n_puts_fav = sum(1 for f in favoritos if f.get("Tipo_Opcion") == "PUT")
        prima_total_fav = sum(f.get("Prima_Volumen", 0) for f in favoritos)
        st.markdown(render_metric_row([
            render_metric_card("Total Favoritos", f"{len(favoritos)}"),
            render_metric_card("Calls", f"{n_calls_fav}"),
            render_metric_card("Puts", f"{n_puts_fav}"),
            render_metric_card("Prima Total", _fmt_monto(prima_total_fav)),
        ]), unsafe_allow_html=True)

        # Tabla resumen
        fav_df = pd.DataFrame(favoritos)
        cols_tabla_fav = ["Contrato", "Ticker", "Tipo_Opcion", "Strike", "Vencimiento",
                          "Volumen", "OI", "Ask", "Bid", "Ultimo", "Lado", "Prima_Volumen"]
        cols_disp_fav = [c for c in cols_tabla_fav if c in fav_df.columns]
        display_fav_df = fav_df[cols_disp_fav].copy()
        if "Tipo_Opcion" in display_fav_df.columns and "Lado" in display_fav_df.columns:
            display_fav_df.insert(0, "Sentimiento", display_fav_df.apply(
                lambda row: _sentiment_badge(row["Tipo_Opcion"], row.get("Lado", "N/A")), axis=1
            ))
        if "Tipo_Opcion" in display_fav_df.columns:
            display_fav_df["Tipo_Opcion"] = display_fav_df["Tipo_Opcion"].apply(_type_badge)
        if "Lado" in display_fav_df.columns:
            display_fav_df["Lado"] = display_fav_df["Lado"].apply(_fmt_lado)
        if "Prima_Volumen" in display_fav_df.columns:
            display_fav_df = display_fav_df.rename(columns={"Prima_Volumen": "Prima Total"})
            display_fav_df["Prima Total"] = display_fav_df["Prima Total"].apply(_fmt_monto)
        st.markdown(
            render_pro_table(display_fav_df, title="⭐ Favoritos", badge_count=f"{len(favoritos)}"),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Detalle individual de cada favorito
        st.markdown("#### 🔍 Detalle de Contratos")
        for idx_fav, fav in enumerate(favoritos):
            fav_sym = fav.get("Contrato", "N/A")
            fav_tipo = fav.get("Tipo_Opcion", "N/A")
            fav_strike = fav.get("Strike", 0)
            fav_venc = fav.get("Vencimiento", "N/A")
            fav_prima = fav.get("Prima_Volumen", 0)

            # Calcular días para vencimiento
            try:
                dias_venc = (datetime.strptime(fav_venc, "%Y-%m-%d") - datetime.now()).days
                dias_str = f"{dias_venc}d" if dias_venc >= 0 else "EXPIRADO"
            except Exception:
                dias_str = "N/A"

            fav_label = (
                f"⭐ {fav_tipo} ${fav_strike} | Venc: {fav_venc} ({dias_str}) | "
                f"Prima: ${fav_prima:,.0f} | {fav_sym}"
            )

            with st.expander(fav_label, expanded=False):
                col_fav_info, col_fav_chart = st.columns([1, 2])

                with col_fav_info:
                    st.markdown("**📄 Información del Contrato**")
                    st.markdown(f"- **Símbolo:** `{fav_sym}`")
                    st.markdown(f"- **Ticker:** {fav.get('Ticker', 'N/A')}")
                    st.markdown(f"- **Tipo:** {fav_tipo}")
                    st.markdown(f"- **Strike:** ${fav_strike}")
                    st.markdown(f"- **Vencimiento:** {fav_venc} ({dias_str})")
                    st.markdown(f"- **Volumen:** {fav.get('Volumen', 0):,}")
                    st.markdown(f"- **OI:** {fav.get('OI', 0):,}")
                    oi_chg_val = fav.get('OI_Chg', 0)
                    st.markdown(f"- **OI Chg:** {_fmt_oi_chg(oi_chg_val)}")
                    st.markdown(f"- **Ask:** ${fav.get('Ask', 0)}")
                    st.markdown(f"- **Bid:** ${fav.get('Bid', 0)}")
                    st.markdown(f"- **Último:** ${fav.get('Ultimo', 0)}")
                    st.markdown(f"- **Lado:** {_fmt_lado(fav.get('Lado', 'N/A'))}")
                    iv_fav = fav.get('IV', 0)
                    st.markdown(f"- **IV:** {iv_fav:.1f}%" if iv_fav > 0 else "- **IV:** N/A")
                    st.markdown(f"- **Prima Total:** {_fmt_monto(fav.get('Prima_Volumen', 0))}")
                    st.markdown(f"- **Tipo Alerta:** {fav.get('Tipo_Alerta', 'N/A')}")
                    st.markdown(f"- **Guardado:** {fav.get('Guardado_En', 'N/A')}")

                    # Botón eliminar
                    if st.button("🗑️ Eliminar de Favoritos", key=f"del_fav_{idx_fav}_{fav_sym}", use_container_width=True):
                        _eliminar_favorito(fav_sym)
                        st.success(f"🗑️ {fav_sym} eliminado de Favoritos")
                        st.rerun()

                with col_fav_chart:
                    if fav_sym and fav_sym != "N/A":
                        with st.spinner("Cargando gráfica del contrato..."):
                            hist_fav, err_fav = obtener_historial_contrato(fav_sym)

                        if err_fav:
                            st.warning(f"⚠️ Error al cargar historial: {err_fav}")
                        elif hist_fav.empty:
                            st.info("ℹ️ No hay datos históricos disponibles.")
                        else:
                            st.markdown(f"**Precio del contrato** — `{fav_sym}`")
                            chart_fav_price = hist_fav[["Close"]].copy()
                            chart_fav_price.columns = ["Precio"]
                            st.line_chart(chart_fav_price, height=280)

                            if "Volume" in hist_fav.columns:
                                chart_fav_vol = hist_fav[["Volume"]].copy()
                                chart_fav_vol.columns = ["Volumen"]
                                st.bar_chart(chart_fav_vol, height=160)

        # Botón limpiar todos
        st.markdown("---")
        col_limpiar, _ = st.columns([1, 3])
        with col_limpiar:
            if st.button("🗑️ Limpiar todos los favoritos", use_container_width=True, type="secondary"):
                st.session_state.favoritos = []
                _guardar_favoritos([])
                st.success("Se eliminaron todos los favoritos")
                st.rerun()
