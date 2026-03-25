"""Detail view — single alert card expander and scan data viewer."""
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from core.scanner import obtener_historial_contrato
from ui.components import render_pro_table
from utils.favorites import _es_favorito, _agregar_favorito
from utils.formatters import (
    _fmt_delta, _fmt_gamma, _fmt_theta, _fmt_rho, _fmt_lado,
    _fmt_iv, _fmt_monto, _fmt_oi, _fmt_oi_chg, _fmt_entero,
    determinar_sentimiento,
)

logger = logging.getLogger(__name__)


def render_alert_detail(alerta, i, ticker_symbol, css_class, sentimiento_txt,
                        sentimiento_emoji, sentimiento_color, emoji, etiqueta,
                        prima_vol_fmt, contract_sym_card, razon_html):
    """Render the inner content of a single alert expander."""
    # Star button
    if contract_sym_card:
        ya_fav_top = _es_favorito(contract_sym_card)
        star_icon = "⭐" if ya_fav_top else "☆"
        star_label = f"{star_icon} Favorito" if ya_fav_top else f"{star_icon} Marcar Favorito"
        col_star, _ = st.columns([1, 4])
        with col_star:
            if st.button(star_label, key=f"star_top_{i}_{contract_sym_card}", disabled=ya_fav_top, use_container_width=True):
                fav_data_top = {
                    "Contrato": contract_sym_card,
                    "Ticker": alerta.get("Ticker", ticker_symbol),
                    "Tipo_Opcion": alerta["Tipo_Opcion"],
                    "Strike": alerta["Strike"],
                    "Vencimiento": alerta["Vencimiento"],
                    "Volumen": alerta["Volumen"],
                    "OI": alerta["OI"],
                    "OI_Chg": alerta.get("OI_Chg", 0),
                    "Ask": alerta["Ask"],
                    "Bid": alerta["Bid"],
                    "Ultimo": alerta["Ultimo"],
                    "Lado": alerta.get("Lado", "N/A"),
                    "IV": alerta.get("IV", 0),
                    "Prima_Volumen": alerta["Prima_Volumen"],
                    "Tipo_Alerta": alerta["Tipo_Alerta"],
                }
                if _agregar_favorito(fav_data_top):
                    st.rerun()

    # HTML card with details
    st.markdown(
        f"""
        <div class="{css_class}" style="margin-bottom: 0; border-left: 5px solid {sentimiento_color} !important;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{emoji} {etiqueta}</strong> —
                    <b>{alerta['Tipo_Opcion']}</b> |
                    Strike: <b>${alerta['Strike']}</b> |
                    Venc: <b>{alerta['Vencimiento']}</b>
                </div>
                <div style="padding: 4px 12px; border-radius: 8px; background: {sentimiento_color}20; border: 1px solid {sentimiento_color}; font-size: 0.75rem; font-weight: 700;">
                    {sentimiento_emoji} {sentimiento_txt}
                </div>
            </div>
            Vol: <b>{alerta['Volumen']:,}</b> |
            Prima Total: <b>{prima_vol_fmt}</b> |
            Ask: ${alerta['Ask']} | Bid: ${alerta['Bid']} | Último: ${alerta['Ultimo']} |
            <b>Lado: {_fmt_lado(alerta.get('Lado', 'N/A'))}</b><br>
            Δ: <b>{_fmt_delta(alerta.get('Delta'))}</b> |
            Γ: <b>{_fmt_gamma(alerta.get('Gamma'))}</b> |
            Θ: <b>{_fmt_theta(alerta.get('Theta'))}</b> |
            ρ: <b>{_fmt_rho(alerta.get('Rho'))}</b><br>
            <span class="razon-alerta">📌 {razon_html}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if contract_sym_card:
        col_chart, col_details = st.columns([3, 1])

        with col_details:
            st.markdown("**Detalles del contrato:**")
            st.markdown(f"- **Símbolo:** `{contract_sym_card}`")
            st.markdown(f"- **Tipo:** {alerta['Tipo_Opcion']}")
            st.markdown(f"- **Strike:** ${alerta['Strike']}")
            st.markdown(f"- **Vencimiento:** {alerta['Vencimiento']}")
            st.markdown(f"- **Volumen:** {alerta['Volumen']:,}")
            st.markdown(f"- **Ask:** ${alerta['Ask']}")
            st.markdown(f"- **Bid:** ${alerta['Bid']}")
            st.markdown(f"- **Último:** ${alerta['Ultimo']}")
            st.markdown(f"- **Lado:** {_fmt_lado(alerta.get('Lado', 'N/A'))}")
            st.markdown(f"- **Delta:** {_fmt_delta(alerta.get('Delta'))}")
            st.markdown(f"- **Gamma:** {_fmt_gamma(alerta.get('Gamma'))}")
            st.markdown(f"- **Theta:** {_fmt_theta(alerta.get('Theta'))}")
            st.markdown(f"- **Rho:** {_fmt_rho(alerta.get('Rho'))}")
            st.markdown(f"- **Prima Total:** ${alerta['Prima_Volumen']:,.0f}")

            ya_fav = _es_favorito(contract_sym_card)
            btn_label = "⭐ Ya en Favoritos" if ya_fav else "☆ Guardar en Favoritos"
            if st.button(btn_label, key=f"fav_btn_{i}_{contract_sym_card}", disabled=ya_fav, use_container_width=True):
                fav_data = {
                    "Contrato": contract_sym_card,
                    "Ticker": alerta.get("Ticker", ticker_symbol),
                    "Tipo_Opcion": alerta["Tipo_Opcion"],
                    "Strike": alerta["Strike"],
                    "Vencimiento": alerta["Vencimiento"],
                    "Volumen": alerta["Volumen"],
                    "OI": alerta["OI"],
                    "OI_Chg": alerta.get("OI_Chg", 0),
                    "Ask": alerta["Ask"],
                    "Bid": alerta["Bid"],
                    "Ultimo": alerta["Ultimo"],
                    "Lado": alerta.get("Lado", "N/A"),
                    "IV": alerta.get("IV", 0),
                    "Prima_Volumen": alerta["Prima_Volumen"],
                    "Tipo_Alerta": alerta["Tipo_Alerta"],
                }
                if _agregar_favorito(fav_data):
                    st.success(f"⭐ {contract_sym_card} guardado en Favoritos")
                    st.rerun()

        with col_chart:
            with st.spinner("Cargando gráfica..."):
                hist_df_card, hist_err_card = obtener_historial_contrato(contract_sym_card)

            if hist_err_card:
                st.warning(f"⚠️ Error al cargar historial: {hist_err_card}")
            elif hist_df_card.empty:
                st.info("ℹ️ No hay datos históricos disponibles para este contrato.")
            else:
                st.markdown(f"**Precio del contrato** — `{contract_sym_card}`")
                chart_price = hist_df_card[["Close"]].copy()
                chart_price.columns = ["Precio"]
                st.line_chart(chart_price, height=300)

                if "Volume" in hist_df_card.columns:
                    chart_vol = hist_df_card[["Volume"]].copy()
                    chart_vol.columns = ["Volumen"]
                    st.bar_chart(chart_vol, height=180)

                with st.expander("🗓️ Datos históricos completos"):
                    _ht = hist_df_card.copy()
                    cols_to_drop = [c for c in ["Dividends", "Stock Splits", "Capital Gains"] if c in _ht.columns]
                    if cols_to_drop:
                        _ht = _ht.drop(columns=cols_to_drop)
                    try:
                        fecha_vals = _ht.index.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        fecha_vals = _ht.index.astype(str)
                    _ht = _ht.reset_index(drop=True)
                    _ht.insert(0, "Fecha", fecha_vals)
                    for col in ["Open", "High", "Low", "Close"]:
                        if col in _ht.columns:
                            _ht[col] = _ht[col].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "-")
                    if "Volume" in _ht.columns:
                        _ht["Volume"] = _ht["Volume"].apply(
                            lambda x: f"{int(x):,}" if pd.notna(x) and x > 0 else "-"
                        )
                    _tbl_html = render_pro_table(_ht, title="📅 Datos Históricos del Contrato", max_height=420)
                    if _tbl_html:
                        st.markdown(_tbl_html, unsafe_allow_html=True)
                    else:
                        st.dataframe(_ht, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No se encontró el símbolo del contrato.")


def render_scan_data_viewer(datos_df, datos_enriquecidos_cache, umbral_delta, min_sm_flow_score):
    """Render the ── Datos del Último Escaneo ── expander and clusters table."""
    st.markdown("---")
    st.markdown("#### 📊 Datos del Último Escaneo")

    _a_calls = len(datos_df[datos_df["Tipo"] == "CALL"])
    _a_puts = len(datos_df[datos_df["Tipo"] == "PUT"])
    _a_total = len(datos_df)
    _a_alertas = len(st.session_state.alertas_actuales)
    _a_clusters = len(st.session_state.clusters_detectados)
    _a_cpct = (_a_calls / _a_total * 100) if _a_total else 0
    _a_ppct = (_a_puts / _a_total * 100) if _a_total else 0
    _a_spk = sorted(datos_df["Volumen"].dropna().tail(12).tolist()) if "Volumen" in datos_df.columns else None

    from ui.components import render_metric_card, render_metric_row
    st.markdown(render_metric_row([
        render_metric_card("Opciones", f"{_a_total:,}", sparkline_data=_a_spk),
        render_metric_card("Calls", f"{_a_calls:,}", delta=_a_cpct),
        render_metric_card("Puts", f"{_a_puts:,}", delta=_a_ppct, color_override="#ef4444"),
        render_metric_card("Alertas", f"{_a_alertas}"),
        render_metric_card("Clusters", f"{_a_clusters}"),
    ]), unsafe_allow_html=True)

    with st.expander("🔍 Ver todas las opciones escaneadas", expanded=False):
        datos_enriquecidos = datos_enriquecidos_cache or []
        display_scan = pd.DataFrame(datos_enriquecidos) if datos_enriquecidos else pd.DataFrame()

        if "Prima_Vol" in display_scan.columns:
            display_scan["Prima Total"] = display_scan["Prima_Vol"].apply(_fmt_monto)
        if "IV" in display_scan.columns:
            display_scan["IV_F"] = display_scan["IV"].apply(_fmt_iv)
        if "Spread_Pct" in display_scan.columns:
            display_scan["Spread_%"] = display_scan["Spread_Pct"].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) and x > 0 else "N/D"
            )
        if "Liquidity_Score" in display_scan.columns:
            display_scan["Liquidez"] = display_scan["Liquidity_Score"].apply(
                lambda x: f"{x:.0f}" if pd.notna(x) else "-"
            )
        if "Lado" in display_scan.columns:
            display_scan["Lado_F"] = display_scan["Lado"].apply(_fmt_lado)
        if "Ask" in display_scan.columns:
            display_scan["Ask_F"] = display_scan["Ask"].apply(
                lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "N/D"
            )
        if "Bid" in display_scan.columns:
            display_scan["Bid_F"] = display_scan["Bid"].apply(
                lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "N/D"
            )
        if "OI" in display_scan.columns:
            display_scan["OI_F"] = display_scan["OI"].apply(_fmt_oi)
        if "OI_Chg" in display_scan.columns:
            display_scan["OI_Chg_F"] = display_scan["OI_Chg"].apply(_fmt_oi_chg)
        if "Delta" in display_scan.columns:
            display_scan["Delta"] = display_scan["Delta"].apply(_fmt_delta)
        if "Gamma" in display_scan.columns:
            display_scan["Gamma"] = display_scan["Gamma"].apply(_fmt_gamma)
        if "Theta" in display_scan.columns:
            display_scan["Theta"] = display_scan["Theta"].apply(_fmt_theta)
        if "Rho" in display_scan.columns:
            display_scan["Rho"] = display_scan["Rho"].apply(_fmt_rho)
        if "Tipo" in display_scan.columns and "Lado" in display_scan.columns:
            display_scan["Sentimiento"] = display_scan.apply(
                lambda row: (
                    f"{determinar_sentimiento(row['Tipo'], row.get('Lado', 'N/A'))[1]} "
                    f"{determinar_sentimiento(row['Tipo'], row.get('Lado', 'N/A'))[0]}"
                ),
                axis=1,
            )
        if "sm_flow_score" in display_scan.columns:
            display_scan["SM Flow"] = display_scan["sm_flow_score"].apply(
                lambda x: f"{float(x):.1f}" if pd.notna(x) else "-"
            )
        if "smart_money_tier" in display_scan.columns:
            display_scan["SM Tier"] = display_scan["smart_money_tier"]
        if "inst_flow_score" in display_scan.columns:
            display_scan["Inst Flow"] = display_scan["inst_flow_score"].apply(
                lambda x: f"{float(x):.1f}" if pd.notna(x) else "-"
            )
        if "inst_tier" in display_scan.columns:
            display_scan["Inst Tier"] = display_scan["inst_tier"]

        _min_sm = int(st.session_state.get("min_sm_flow_score", 0))
        if _min_sm > 0 and "sm_flow_score" in display_scan.columns:
            import numpy as np
            _scores = pd.to_numeric(display_scan["sm_flow_score"], errors="coerce").fillna(0)
            display_scan = display_scan[_scores >= _min_sm]

        _min_inst = int(st.session_state.get("min_inst_flow_score", 0))
        if _min_inst > 0 and "inst_flow_score" in display_scan.columns:
            _iscores = pd.to_numeric(display_scan["inst_flow_score"], errors="coerce").fillna(0)
            display_scan = display_scan[_iscores >= _min_inst]
        if st.session_state.get("ck_inst_whale") and "inst_tier" in display_scan.columns:
            display_scan = display_scan[display_scan["inst_tier"].isin(["Institutional", "Whale"])]
        if st.session_state.get("ck_delta_60_80") and "abs_delta" in display_scan.columns:
            _ad = pd.to_numeric(display_scan["abs_delta"], errors="coerce").fillna(0)
            display_scan = display_scan[(_ad >= 0.60) & (_ad <= 0.80)]
        if st.session_state.get("ck_stock_sub") and "abs_delta" in display_scan.columns:
            _ad2 = pd.to_numeric(display_scan["abs_delta"], errors="coerce").fillna(0)
            display_scan = display_scan[_ad2 >= 0.80]

        if display_scan.empty:
            st.info("⚠️ Sin opciones con los filtros actuales. Reduce los umbrales para ver resultados.")

        cols_mostrar = [
            "Sentimiento", "Inst Flow", "Inst Tier", "SM Flow", "SM Tier",
            "Flow_Type", "Hedge_Alert", "Tipo", "Strike", "Vencimiento",
            "Volumen", "OI_F", "OI_Chg_F", "Delta", "Gamma", "Theta", "Rho",
            "Ask_F", "Bid_F", "Spread_%", "Ultimo", "Lado_F", "IV_F",
            "Moneyness", "Prima Total", "Liquidez",
        ]
        cols_disponibles = [c for c in cols_mostrar if c in display_scan.columns]
        st.markdown(
            render_pro_table(
                display_scan[cols_disponibles] if cols_disponibles else display_scan,
                title="📊 Opciones Escaneadas",
                badge_count=f"{len(display_scan):,}",
                max_height=400,
            ),
            unsafe_allow_html=True,
        )

        csv_enriquecido = pd.DataFrame(datos_enriquecidos).to_csv(index=False).encode("utf-8")
        st.download_button(
            "📈 Descargar Datos Enriquecidos (CSV)",
            csv_enriquecido,
            f"opciones_enriquecidas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            key="dl_datos_enriquecidos_escaneo",
            help="Incluye métricas adicionales: spread, moneyness, liquidez, ratios, etc.",
        )

    if st.session_state.clusters_detectados:
        st.markdown("##### 🔗 Clusters de Compra Continua")
        clusters_table_esc = [
            {
                "Tipo": c["Tipo_Opcion"],
                "Vencimiento": c["Vencimiento"],
                "Contratos": c["Contratos"],
                "Rango Strikes": f"${c['Strike_Min']} - ${c['Strike_Max']}",
                "Prima Total": _fmt_monto(c["Prima_Total"]),
                "Prima Prom.": _fmt_monto(c["Prima_Promedio"]),
                "Vol Total": _fmt_entero(c["Vol_Total"]),
                "OI Total": _fmt_entero(c["OI_Total"]),
                "OI Chg": _fmt_oi_chg(c.get("OI_Chg_Total", 0)),
            }
            for c in st.session_state.clusters_detectados
        ]
        st.markdown(
            render_pro_table(
                pd.DataFrame(clusters_table_esc),
                title="🔗 Clusters de Compra Continua",
                badge_count=f"{len(clusters_table_esc)}",
            ),
            unsafe_allow_html=True,
        )
