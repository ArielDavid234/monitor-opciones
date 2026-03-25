"""Volume analysis, distribution charts, and anomaly detection for Data Analysis."""
import logging

import streamlit as st

from ui.components import render_pro_table, render_metric_card, render_metric_row
from ui.charts import render_anomaly_scatter
from core.flow_classifier import classify_flow_type, flow_badge, detect_institutional_hedge
from utils.formatters import (
    _fmt_dolar, _fmt_entero, _fmt_iv, _fmt_oi, _fmt_oi_chg, _fmt_lado,
    _fmt_delta, _fmt_precio,
)
from ui.charts import render_pcr_gauge

logger = logging.getLogger(__name__)


def render_distribution_charts(df_analisis):
    """Render CALL/PUT distribution, IV curves, prima-by-expiry, and top-strikes."""
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        st.markdown("#### 📊 Distribución CALL vs PUT")
        tipo_counts = df_analisis["Tipo"].value_counts()
        st.bar_chart(tipo_counts)

        n_calls = tipo_counts.get("CALL", 0)
        n_puts = tipo_counts.get("PUT", 0)
        ratio_pc = n_puts / n_calls if n_calls > 0 else 0
        fig_pcr = render_pcr_gauge(ratio_pc)
        st.plotly_chart(fig_pcr, use_container_width=True, key="pcr_gauge")

    with col_a2:
        st.markdown("#### 📅 Volumen por Vencimiento")
        vol_by_date = df_analisis.groupby("Vencimiento")["Volumen"].sum().sort_index()
        st.bar_chart(vol_by_date)

    col_iv1, col_iv2 = st.columns(2)
    with col_iv1:
        st.markdown("#### 📉 Volatilidad Implícita por Strike (CALLs)")
        calls_iv = df_analisis[(df_analisis["Tipo"] == "CALL") & (df_analisis["IV"] > 0)].sort_values("Strike")
        if not calls_iv.empty:
            st.line_chart(calls_iv[["Strike", "IV"]].set_index("Strike"))
    with col_iv2:
        st.markdown("#### 📉 Volatilidad Implícita por Strike (PUTs)")
        puts_iv = df_analisis[(df_analisis["Tipo"] == "PUT") & (df_analisis["IV"] > 0)].sort_values("Strike")
        if not puts_iv.empty:
            st.line_chart(puts_iv[["Strike", "IV"]].set_index("Strike"))

    df_calls_s = df_analisis[df_analisis["Tipo"] == "CALL"]
    df_puts_s = df_analisis[df_analisis["Tipo"] == "PUT"]
    col_pv1, col_pv2 = st.columns(2)

    with col_pv1:
        st.markdown("#### 📞 Prima Total en CALLs por Vencimiento")
        if not df_calls_s.empty:
            prima_calls_venc = df_calls_s.groupby("Vencimiento").agg(
                Prima_Total=("Prima_Vol", "sum"),
                Contratos=("Volumen", "count"),
                Volumen_Total=("Volumen", "sum"),
            ).sort_values("Prima_Total", ascending=False).reset_index()
            display_pc = prima_calls_venc.copy()
            display_pc["Prima_Total"] = display_pc["Prima_Total"].apply(_fmt_dolar)
            display_pc["Volumen_Total"] = display_pc["Volumen_Total"].apply(_fmt_entero)
            st.markdown(render_pro_table(display_pc, title="📞 CALLs por Vencimiento"), unsafe_allow_html=True)
        else:
            st.info("Sin datos de CALLs.")

    with col_pv2:
        st.markdown("#### 📋 Prima Total en PUTs por Vencimiento")
        if not df_puts_s.empty:
            prima_puts_venc = df_puts_s.groupby("Vencimiento").agg(
                Prima_Total=("Prima_Vol", "sum"),
                Contratos=("Volumen", "count"),
                Volumen_Total=("Volumen", "sum"),
            ).sort_values("Prima_Total", ascending=False).reset_index()
            display_pp = prima_puts_venc.copy()
            display_pp["Prima_Total"] = display_pp["Prima_Total"].apply(_fmt_dolar)
            display_pp["Volumen_Total"] = display_pp["Volumen_Total"].apply(_fmt_entero)
            st.markdown(render_pro_table(display_pp, title="📋 PUTs por Vencimiento"), unsafe_allow_html=True)
        else:
            st.info("Sin datos de PUTs.")

    st.markdown("#### 🎯 Top 15 Strikes con Mayor Prima Total Ejecutada")
    prima_cols = ["Tipo", "Strike", "Vencimiento", "Volumen", "OI", "OI_Chg", "Prima_Vol", "IV", "Delta", "Ultimo", "Lado", "Flow_Type"]
    top_prima = df_analisis.nlargest(15, "Prima_Vol")[
        [c for c in prima_cols if c in df_analisis.columns]
    ].reset_index(drop=True)

    top_prima_display = top_prima.copy()
    top_prima_display = top_prima_display.rename(columns={"Prima_Vol": "Prima Total"})
    if "Tipo" in top_prima_display.columns and "Lado" in top_prima_display.columns:
        from ui.components import _sentiment_badge, _type_badge
        top_prima_display.insert(0, "Sentimiento", top_prima_display.apply(
            lambda row: _sentiment_badge(row["Tipo"], row.get("Lado", "N/A")), axis=1,
        ))
        top_prima_display["Tipo"] = top_prima_display["Tipo"].apply(_type_badge)
    top_prima_display["Prima Total"] = top_prima_display["Prima Total"].apply(_fmt_dolar)
    top_prima_display["Volumen"] = top_prima_display["Volumen"].apply(_fmt_entero)
    if "OI" in top_prima_display.columns:
        top_prima_display["OI"] = top_prima_display["OI"].apply(_fmt_oi)
    if "OI_Chg" in top_prima_display.columns:
        top_prima_display["OI_Chg"] = top_prima_display["OI_Chg"].apply(_fmt_oi_chg)
    top_prima_display["IV"] = top_prima_display["IV"].apply(_fmt_iv)
    if "Delta" in top_prima_display.columns:
        top_prima_display["Delta"] = top_prima_display["Delta"].apply(_fmt_delta)
    top_prima_display["Ultimo"] = top_prima_display["Ultimo"].apply(_fmt_precio)
    top_prima_display["Strike"] = top_prima_display["Strike"].apply(lambda x: f"${x:,.1f}")
    if "Lado" in top_prima_display.columns:
        top_prima_display["Lado"] = top_prima_display["Lado"].apply(_fmt_lado)
    if "Flow_Type" not in top_prima_display.columns:
        top_prima_display["Flow_Type"] = top_prima.apply(classify_flow_type, axis=1)
    top_prima_display["Flow_Type"] = top_prima_display["Flow_Type"].apply(flow_badge)
    if "Hedge_Alert" not in top_prima_display.columns:
        top_prima_display["Hedge_Alert"] = top_prima.apply(
            lambda r: detect_institutional_hedge(r).get("alerta", ""), axis=1
        )

    st.markdown(
        render_pro_table(top_prima_display, title="🎯 Top 15 Mayor Prima Ejecutada", badge_count="15"),
        unsafe_allow_html=True,
    )

    st.markdown("#### 📊 Flujo de Prima por Strike (CALL vs PUT)")
    pivot_prima = df_analisis.pivot_table(
        index="Strike", columns="Tipo",
        values="Prima_Vol", aggfunc="sum", fill_value=0,
    )
    pivot_prima = pivot_prima[pivot_prima.sum(axis=1) > 0]
    if not pivot_prima.empty:
        col0 = pivot_prima.columns.tolist()[0] if len(pivot_prima.columns) > 0 else pivot_prima.index
        pivot_prima = pivot_prima.nlargest(30, col0).sort_index()
        st.bar_chart(pivot_prima)
    st.caption("Prima por Volumen distribuida por strike — muestra dónde se concentran las apuestas más grandes")


def render_anomaly_section(ticker_symbol, datos_completos):
    """Render IsolationForest anomaly detection section."""
    st.markdown("#### 🔍 Detector de Anomalías — ML (IsolationForest)")
    anom_cache_key = f"_anomalies_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    if st.session_state.get(anom_cache_key) is None:
        try:
            from core.anomaly_detector import detectar_anomalias
            df_anom = detectar_anomalias(datos_completos)
            st.session_state[anom_cache_key] = df_anom
        except Exception as e:
            logger.warning("Error anomaly detection: %s", e)
            st.session_state[anom_cache_key] = None

    df_anomalies = st.session_state.get(anom_cache_key)
    if df_anomalies is not None and not df_anomalies.empty:
        fig_anom = render_anomaly_scatter(df_anomalies)
        if fig_anom:
            st.plotly_chart(fig_anom, use_container_width=True, key="anomaly_scatter")

        top_anom = df_anomalies[df_anomalies["is_anomaly"]].nlargest(10, "anomaly_score")
        if not top_anom.empty:
            anom_display_cols = ["Tipo", "Strike", "Vencimiento", "Volumen", "OI", "IV", "anomaly_score"]
            anom_display_cols = [c for c in anom_display_cols if c in top_anom.columns]
            anom_show = top_anom[anom_display_cols].copy()
            if "Strike" in anom_show.columns:
                anom_show["Strike"] = anom_show["Strike"].apply(lambda x: f"${x:,.1f}")
            if "Volumen" in anom_show.columns:
                anom_show["Volumen"] = anom_show["Volumen"].apply(_fmt_entero)
            if "OI" in anom_show.columns:
                anom_show["OI"] = anom_show["OI"].apply(_fmt_oi)
            if "IV" in anom_show.columns:
                anom_show["IV"] = anom_show["IV"].apply(_fmt_iv)
            anom_show = anom_show.rename(columns={"anomaly_score": "Anomaly Score"})
            st.markdown(
                render_pro_table(anom_show, title="🔴 Top 10 Anomalías Detectadas", badge_count=len(top_anom)),
                unsafe_allow_html=True,
            )
        st.caption("IsolationForest analiza patrones de volumen, prima, IV y OI para detectar actividad fuera de lo normal.")
    else:
        st.info("Sin suficientes datos para detección de anomalías (mínimo 30 registros). Si sklearn no está instalado, se omite.")
