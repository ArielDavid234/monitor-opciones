"""Alerts section and results display for the Live Scanning page."""
import logging

import numpy as np
import pandas as pd
import streamlit as st

from core.flow_classifier import classify_flow_type, flow_badge, detect_institutional_hedge, detect_hedge_bulk
from ui.components import render_pro_table, _sentiment_badge, _type_badge, _priority_badge
from utils.formatters import (
    _fmt_dolar, _fmt_delta, _fmt_iv, _fmt_oi, _fmt_oi_chg, _fmt_lado,
    determinar_sentimiento,
)
from page_modules.live_scanning._detail_view import render_alert_detail, render_scan_data_viewer
from page_modules.live_scanning._charts import render_net_flow_chart, render_flow_screener

logger = logging.getLogger(__name__)


def render_alerts_section(
    *,
    ticker_symbol,
    datos_df,
    datos_enriquecidos_cache,
    umbral_vol,
    umbral_oi,
    umbral_prima,
    umbral_delta,
    min_sm_flow_score,
):
    """Render the full alerts section: hedge banner, alert cards, dashboard, screener."""
    from datetime import datetime

    if st.session_state.alertas_actuales:
        st.markdown("### 🚨 Alertas Detectadas")

        # Smart Money Hedge Alert Banner
        _hedge_alerts = []
        for _a in st.session_state.alertas_actuales:
            _h = detect_institutional_hedge(_a)
            if _h:
                _h["_ticker"] = _a.get("Ticker", ticker_symbol)
                _h["_strike"] = _a.get("Strike", "")
                _h["_venc"] = _a.get("Vencimiento", "")
                _h["_prima"] = _a.get("Prima_Volumen", 0)
                _hedge_alerts.append(_h)

        if _hedge_alerts:
            _has_critical = any(h["nivel"] == "critical" for h in _hedge_alerts)
            _banner_css = "hedge-banner-critical" if _has_critical else "hedge-banner-warning"
            _banner_icon = "🚨" if _has_critical else "⚠️"
            _banner_title = (
                "ALERTA ROJA: Protección institucional pesada detectada — instituciones con miedo real al downside"
                if _has_critical
                else "Protección institucional detectada — cobertura de riesgo significativa"
            )
            _banner_details = []
            for _h in _hedge_alerts:
                _banner_details.append(
                    f"<div style='margin-top:6px;font-size:0.8rem;opacity:0.9;'>"
                    f"• <b>{_h['_ticker']}</b> PUT ${_h['_strike']} Venc {_h['_venc']} — "
                    f"Prima ${_h['_prima']:,.0f} — {_h['explicacion']}</div>"
                )
            st.markdown(
                f'<div class="hedge-banner {_banner_css}">'
                f'<div><span style="font-size:1.3rem;">{_banner_icon}</span></div>'
                f'<div><b>{_banner_title}</b>'
                f'{"".join(_banner_details)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            """
            <div class="leyenda-colores">
                <div style="font-weight: 600; color: #f1f5f9; margin-bottom: 8px; font-size: 0.9rem;">🎨 Guía de Prioridades</div>
                <span class="leyenda-item"><span class="dot-green">●</span> <b>VERDE</b> — Mayor prima detectada. Máxima atención: contrato con más dinero en juego.</span>
                <span class="leyenda-item"><span class="dot-red">●</span> <b>ROJO</b> — Actividad institucional. Vol <u>y</u> OI superan umbrales + prima alta.</span>
                <span class="leyenda-item"><span class="dot-orange">●</span> <b>NARANJA</b> — Actividad notable. Vol y OI superan umbrales.</span>
                <span class="leyenda-item"><span class="dot-purple">●</span> <b>MORADO</b> — Compra continua. Múltiples contratos similares cerca del umbral = posible mismo comprador institucional.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        alertas_sorted = sorted(
            st.session_state.alertas_actuales,
            key=lambda a: a["Prima_Volumen"],
            reverse=True,
        )
        if umbral_delta > 0:
            alertas_sorted = [
                a for a in alertas_sorted
                if a.get("Delta") is not None and abs(a["Delta"]) >= umbral_delta
            ]
        if not alertas_sorted:
            st.info(f"⚠️ Sin alertas con |Δ| ≥ {umbral_delta:.2f}. Reduce el filtro Delta en Umbrales de Filtrado.")
        max_prima = max((a["Prima_Volumen"] for a in alertas_sorted), default=0)

        # Render each alert card
        for i, alerta in enumerate(alertas_sorted):
            tipo = alerta["Tipo_Alerta"]
            prima_mayor = alerta["Prima_Volumen"]
            es_top = (prima_mayor == max_prima) and (i == 0)

            if es_top:
                css_class = "alerta-top"
                emoji = "🟢"
                etiqueta = "MAYOR PRIMA"
            elif tipo == "PRINCIPAL":
                css_class = "alerta-principal"
                emoji = "🔴"
                etiqueta = "ACTIVIDAD INSTITUCIONAL"
            else:
                css_class = "alerta-prima"
                emoji = "🟠"
                etiqueta = "PRIMA ALTA"

            sentimiento_txt, sentimiento_emoji, sentimiento_color = determinar_sentimiento(
                alerta["Tipo_Opcion"], alerta.get("Lado", "N/A")
            )

            razones = []
            if alerta["Volumen"] >= umbral_vol:
                razones.append(f"Vol {alerta['Volumen']:,} ≥ {umbral_vol:,}")
            if alerta["OI"] >= umbral_oi:
                razones.append(f"OI {alerta['OI']:,} ≥ {umbral_oi:,}")
            if alerta["Prima_Volumen"] >= umbral_prima:
                razones.append(f"Prima Total ${alerta['Prima_Volumen']:,.0f} ≥ ${umbral_prima:,.0f}")
            if es_top:
                razones.insert(0, f"💰 Mayor prima del escaneo: ${prima_mayor:,.0f}")
            razon_html = " | ".join(razones)

            prima_vol_fmt = f"${alerta['Prima_Volumen']:,.0f}"
            contract_sym_card = alerta.get("Contrato", "")

            fecha_alerta = alerta.get("Fecha_Hora", "")
            if fecha_alerta:
                fecha_alerta_solo = fecha_alerta.split()[0]
                hoy_alerta = datetime.now().strftime("%Y-%m-%d")
                badge_fecha = "🟢 HOY" if fecha_alerta_solo == hoy_alerta else f"📅 {fecha_alerta_solo}"
            else:
                badge_fecha = ""

            expander_label = (
                f"{emoji} {etiqueta} {badge_fecha} — {alerta['Tipo_Opcion']} Strike ${alerta['Strike']} | "
                f"Venc: {alerta['Vencimiento']} | Vol: {alerta['Volumen']:,} | "
                f"Prima: ${prima_mayor:,.0f}"
            )

            with st.expander(expander_label, expanded=False):
                render_alert_detail(
                    alerta, i, ticker_symbol,
                    css_class, sentimiento_txt, sentimiento_emoji, sentimiento_color,
                    emoji, etiqueta, prima_vol_fmt, contract_sym_card, razon_html,
                )

        # Two-column dashboard
        alertas_df = pd.DataFrame(alertas_sorted)

        def asignar_prioridad(row):
            if row["Prima_Volumen"] == max_prima:
                return "TOP"
            elif row["Tipo_Alerta"] == "PRINCIPAL":
                return "INSTITUCIONAL"
            return "PRIMA ALTA"

        alertas_df.insert(0, "Prioridad", alertas_df.apply(asignar_prioridad, axis=1))
        alertas_df.insert(
            1, "Sentimiento",
            alertas_df.apply(lambda row: _sentiment_badge(row["Tipo_Opcion"], row.get("Lado", "N/A")), axis=1),
        )
        if "Flow_Type" not in alertas_df.columns:
            alertas_df["Flow_Type"] = alertas_df.apply(classify_flow_type, axis=1)
        alertas_df["Flow_Type"] = alertas_df["Flow_Type"].apply(flow_badge)

        if "Hedge_Alert" not in alertas_df.columns:
            _spot = st.session_state.get("precio_subyacente") or 0.0
            if _spot > 0 and "Moneyness" not in alertas_df.columns:
                _tipo_m = alertas_df["Tipo_Opcion"].str.upper() if "Tipo_Opcion" in alertas_df.columns else pd.Series([""] * len(alertas_df))
                _strike_m = pd.to_numeric(alertas_df["Strike"], errors="coerce").fillna(0)
                _ratio_m = np.where(_tipo_m == "CALL", _strike_m / _spot, _spot / _strike_m)
                alertas_df["Moneyness"] = np.where(
                    _strike_m <= 0, "N/A",
                    np.where(_ratio_m < 0.95, "ITM", np.where(_ratio_m > 1.05, "OTM", "ATM")),
                )
                alertas_df["Distance_Pct"] = np.where(
                    _strike_m > 0, np.abs(_strike_m - _spot) / _spot * 100, 0.0
                )
            if "OI_Chg" not in alertas_df.columns:
                _bc = st.session_state.get("barchart_data")
                if _bc is not None and not _bc.empty and "Contrato" in _bc.columns and "OI_Chg" in _bc.columns:
                    _oi_map = _bc.set_index("Contrato")["OI_Chg"].to_dict()
                    alertas_df["OI_Chg"] = alertas_df["Contrato"].map(_oi_map).fillna(0)
                else:
                    alertas_df["OI_Chg"] = 0
            _ha, _hl, _hd = detect_hedge_bulk(alertas_df)
            alertas_df["Hedge_Alert"] = _ha
            alertas_df["Hedge_Level"] = _hl

        if "Tipo_Opcion" in alertas_df.columns:
            alertas_df["Tipo_Opcion"] = alertas_df["Tipo_Opcion"].apply(_type_badge)
        if "Lado" in alertas_df.columns:
            alertas_df["Lado"] = alertas_df["Lado"].apply(_fmt_lado)
        if "OI" in alertas_df.columns:
            alertas_df["OI"] = alertas_df["OI"].apply(_fmt_oi)
        if "OI_Chg" in alertas_df.columns:
            alertas_df["OI_Chg"] = alertas_df["OI_Chg"].apply(_fmt_oi_chg)
        if "Delta" in alertas_df.columns:
            alertas_df["Delta"] = alertas_df["Delta"].apply(_fmt_delta)
        alertas_df = alertas_df.rename(columns={"Prima_Volumen": "Prima Total"})
        alertas_df["Prima Total"] = alertas_df["Prima Total"].apply(_fmt_dolar)

        _col_left, _col_right = st.columns([1, 1], gap="medium")

        _ALERTAS_COLS = [
            "Prioridad", "Sentimiento", "Flow_Type", "Hedge_Alert", "Hedge_Level",
            "Tipo_Opcion", "Vencimiento", "Strike",
            "Volumen", "OI", "OI_Chg", "Delta",
            "Ask", "Bid", "Ultimo", "IV",
            "Lado", "Prima Total", "Contrato",
        ]
        _alertas_display = alertas_df[[c for c in _ALERTAS_COLS if c in alertas_df.columns]]

        with _col_left:
            st.markdown(
                render_pro_table(
                    _alertas_display,
                    title="📋 Unusual Activity — Alertas",
                    badge_count=f"{len(_alertas_display)} alertas",
                    footer_text=f"Ordenadas por prima · {len(_alertas_display)} resultados",
                    special_format={"Prioridad": _priority_badge},
                ),
                unsafe_allow_html=True,
            )
            render_net_flow_chart(alertas_sorted)

            if st.session_state.clusters_detectados:
                st.markdown("#### 🔗 Compras Continuas")
                st.markdown(
                    '<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.15);'
                    'border-radius:12px;padding:10px 14px;margin-bottom:12px;font-size:0.78rem;color:#c4b5fd;">'
                    "⚠️ <b>Actividad institucional fragmentada</b> — Múltiples contratos similares con strikes "
                    "cercanos y primas cerca del umbral.</div>",
                    unsafe_allow_html=True,
                )
                for idx_c, cluster in enumerate(st.session_state.clusters_detectados):
                    rango_str = (
                        f"${cluster['Strike_Min']} - ${cluster['Strike_Max']}"
                        if cluster["Strike_Min"] != cluster["Strike_Max"]
                        else f"${cluster['Strike_Min']}"
                    )
                    st.markdown(
                        f'<div class="alerta-cluster">'
                        f'<strong>🟣 COMPRA CONTINUA</strong> '
                        f'<span class="cluster-badge">{cluster["Contratos"]} contratos</span><br>'
                        f'<b>{cluster["Tipo_Opcion"]}</b> | Venc: <b>{cluster["Vencimiento"]}</b> | '
                        f'Rango: <b>{rango_str}</b><br>'
                        f'Prima: <b>${cluster["Prima_Total"]:,.0f}</b> | '
                        f'Vol: <b>{cluster["Vol_Total"]:,}</b></div>',
                        unsafe_allow_html=True,
                    )

                clusters_table = [
                    {
                        "Tipo": c["Tipo_Opcion"],
                        "Vencimiento": c["Vencimiento"],
                        "Contratos": c["Contratos"],
                        "Rango Strikes": f"${c['Strike_Min']} - ${c['Strike_Max']}",
                        "Prima Total": f"${c['Prima_Total']:,.0f}",
                        "Vol Total": f"{c['Vol_Total']:,}",
                    }
                    for c in st.session_state.clusters_detectados
                ]
                st.markdown(
                    render_pro_table(
                        pd.DataFrame(clusters_table),
                        title="🔗 Clusters Detectados",
                        badge_count=f"{len(clusters_table)}",
                    ),
                    unsafe_allow_html=True,
                )

        with _col_right:
            if datos_df is not None:
                render_flow_screener(datos_df, umbral_delta, key_suffix="")
            else:
                st.info("Ejecuta un escaneo para ver el flujo de opciones.")

    elif st.session_state.scan_count > 0 and not st.session_state.scan_error:
        st.success("✅ Sin alertas relevantes en este ciclo.")

    # Options Flow Screener when there are no alerts
    if not st.session_state.alertas_actuales and datos_df is not None:
        render_flow_screener(datos_df, umbral_delta, key_suffix="_noalert")

    # Scan data viewer
    if datos_df is not None:
        render_scan_data_viewer(datos_df, datos_enriquecidos_cache, umbral_delta, min_sm_flow_score)
