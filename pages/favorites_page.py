# -*- coding: utf-8 -*-
"""Página: ⭐ Favorites — Contratos Favoritos."""
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.formatters import (
    _fmt_monto, _fmt_lado, _fmt_oi_chg,
)
from utils.favorites import _eliminar_favorito, _guardar_favoritos
from ui.components import (
    render_metric_card, render_metric_row, render_pro_table,
    _sentiment_badge, _type_badge,
)
from core.scanner import obtener_historial_contrato


def render(ticker_symbol, **kwargs):
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
