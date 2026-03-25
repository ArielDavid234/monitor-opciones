"""Net flow bar chart and options flow screener for the Live Scanning page."""
import streamlit as st
import plotly.graph_objects as go

from ui.plotly_professional_theme import apply_theme, COLORS
from ui.components import render_pro_table
from utils.formatters import (
    _fmt_dolar, _fmt_iv, _fmt_delta, _fmt_gamma, _fmt_theta, _fmt_rho,
)
from core.flow_classifier import classify_flow_type


def render_net_flow_chart(alertas_sorted):
    """Render the CALLS vs PUTS net premium flow bar chart."""
    _calls_prima = sum(
        d.get("Prima_Volumen", 0) for d in alertas_sorted if d.get("Tipo_Opcion") == "CALL"
    )
    _puts_prima = sum(
        d.get("Prima_Volumen", 0) for d in alertas_sorted if d.get("Tipo_Opcion") == "PUT"
    )
    if not (_calls_prima > 0 or _puts_prima > 0):
        return

    _net_fig = go.Figure()
    _net_fig.add_trace(go.Bar(
        x=["CALLS"], y=[_calls_prima],
        marker_color=COLORS["positive"], name="Calls",
        text=[f"${_calls_prima:,.0f}"], textposition="auto",
        textfont=dict(color="#ffffff", size=12),
    ))
    _net_fig.add_trace(go.Bar(
        x=["PUTS"], y=[_puts_prima],
        marker_color=COLORS["negative"], name="Puts",
        text=[f"${_puts_prima:,.0f}"], textposition="auto",
        textfont=dict(color="#ffffff", size=12),
    ))
    apply_theme(
        _net_fig,
        title="Net Premium Flow",
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_tickformat="$,.0f",
        xaxis_showgrid=False,
    )
    _net_fig.update_layout(bargap=0.35)
    st.plotly_chart(_net_fig, use_container_width=True, config={"displayModeBar": False})


def render_flow_screener(datos_df, umbral_delta, key_suffix=""):
    """Render the Options Flow Screener widget.

    Args:
        datos_df: DataFrame with full scan data.
        umbral_delta: minimum |delta| filter.
        key_suffix: unique suffix for widget keys (to avoid duplicate-key errors).
    """
    st.markdown(
        '<div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;">'
        "🔍 Options Flow Screener</div>",
        unsafe_allow_html=True,
    )

    if key_suffix:
        _rf1, _rf2, _rf3 = st.columns(3)
        with _rf1:
            filtro_tipo = st.selectbox("Tipo", ["Todos", "CALL", "PUT"], key=f"filtro_tipo_scanner{key_suffix}")
        with _rf2:
            filtro_fecha = st.selectbox(
                "Vencimiento",
                ["Todos"] + sorted(datos_df["Vencimiento"].unique().tolist()),
                key=f"filtro_fecha_scanner{key_suffix}",
            )
        with _rf3:
            min_vol_filtro = st.number_input("Volumen mínimo", value=0, step=100, key=f"min_vol_scanner{key_suffix}")
    else:
        _rf1, _rf2 = st.columns(2)
        with _rf1:
            filtro_tipo = st.selectbox("Tipo", ["Todos", "CALL", "PUT"], key="filtro_tipo_scanner")
        with _rf2:
            filtro_fecha = st.selectbox(
                "Vencimiento",
                ["Todos"] + sorted(datos_df["Vencimiento"].unique().tolist()),
                key="filtro_fecha_scanner",
            )
        min_vol_filtro = st.number_input("Volumen mínimo", value=0, step=100, key="min_vol_scanner")

    df_filtered = datos_df.copy()
    if filtro_tipo != "Todos":
        df_filtered = df_filtered[df_filtered["Tipo"] == filtro_tipo]
    if filtro_fecha != "Todos":
        df_filtered = df_filtered[df_filtered["Vencimiento"] == filtro_fecha]
    if min_vol_filtro > 0:
        df_filtered = df_filtered[df_filtered["Volumen"] >= min_vol_filtro]

    display_df = df_filtered.copy()
    if "Prima_Vol" in display_df.columns:
        display_df = display_df.rename(columns={"Prima_Vol": "Prima Total"})
        display_df["Prima Total"] = display_df["Prima Total"].apply(_fmt_dolar)
    display_df["IV"] = display_df["IV"].apply(_fmt_iv)
    if "Delta" in display_df.columns:
        if umbral_delta > 0:
            display_df = display_df[
                display_df["Delta"].apply(lambda d: d is not None and abs(d) >= umbral_delta)
            ]
        display_df["Delta"] = display_df["Delta"].apply(_fmt_delta)
    if "Gamma" in display_df.columns:
        display_df["Gamma"] = display_df["Gamma"].apply(_fmt_gamma)
    if "Theta" in display_df.columns:
        display_df["Theta"] = display_df["Theta"].apply(_fmt_theta)
    if "Rho" in display_df.columns:
        display_df["Rho"] = display_df["Rho"].apply(_fmt_rho)
    if "Flow_Type" not in display_df.columns:
        display_df["Flow_Type"] = display_df.apply(classify_flow_type, axis=1)

    cols_ocultar_df = [c for c in ["OI", "OI_Chg"] if c in display_df.columns]
    cols_order = ["Flow_Type"] + [c for c in display_df.columns if c != "Flow_Type" and c not in cols_ocultar_df]
    cols_order = [c for c in cols_order if c in display_df.columns]

    max_h = 600 if not key_suffix else 500
    st.markdown(
        render_pro_table(
            display_df[cols_order].sort_values("Volumen", ascending=False),
            title="🔍 Options Flow",
            badge_count=f"{len(df_filtered):,} opciones",
            max_height=max_h,
        ),
        unsafe_allow_html=True,
    )
    st.caption(f"Mostrando {len(df_filtered):,} de {len(datos_df):,} opciones")
