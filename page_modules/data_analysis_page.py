# -*- coding: utf-8 -*-
"""Página: 📈 Data Analysis — Sentimiento, soportes/resistencias, distribución, IV Rank, Monte Carlo, Anomaly Detection."""
import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.formatters import (
    _fmt_dolar, _fmt_monto, _fmt_entero, _fmt_iv, _fmt_precio,
    _fmt_oi, _fmt_oi_chg, _fmt_lado, _fmt_delta,
)
from ui.components import (
    render_pro_table, render_metric_card, render_metric_row,
    _sentiment_badge, _type_badge, render_fundamentals_card,
)
from ui.charts import (
    render_pcr_gauge, render_iv_gauge, render_oi_heatmap,
    render_vol_surface, render_monte_carlo_chart, render_anomaly_scatter,
)
from core.flow_classifier import classify_flow_type, flow_badge, detect_institutional_hedge, hedge_alert_badge

logger = logging.getLogger(__name__)


def render(ticker_symbol, **kwargs):
    st.markdown("### 📈 Data Analysis")

    if not st.session_state.datos_completos:
        st.info("Ejecuta un escaneo primero para ver los análisis.")
        return

    df_analisis = pd.DataFrame(st.session_state.datos_completos)
    if "Prima_Volumen" in df_analisis.columns:
        df_analisis = df_analisis.rename(columns={"Prima_Volumen": "Prima_Vol"})

    titulo_datos = f"Datos del último escaneo — {ticker_symbol}"
    st.caption(f"*{titulo_datos}* — {len(df_analisis):,} registros")

    # ================================================================
    # DESGLOSE DE SENTIMIENTO POR PRIMAS
    # ================================================================
    st.markdown("### 💰 Desglose de Sentimiento por Primas")
    st.markdown("---")

    df_sent = df_analisis.copy()
    df_sent["_mid"] = (df_sent["Ask"] + df_sent["Bid"]) / 2

    mask_call = df_sent["Tipo"] == "CALL"
    mask_put = df_sent["Tipo"] == "PUT"
    mask_ask = df_sent["Ultimo"] >= df_sent["_mid"]
    mask_bid = df_sent["Ultimo"] < df_sent["_mid"]

    call_ask_val = df_sent.loc[mask_call & mask_ask, "Prima_Vol"].sum()
    call_bid_val = df_sent.loc[mask_call & mask_bid, "Prima_Vol"].sum()
    put_ask_val = df_sent.loc[mask_put & mask_ask, "Prima_Vol"].sum()
    put_bid_val = df_sent.loc[mask_put & mask_bid, "Prima_Vol"].sum()

    total_sent = call_ask_val + call_bid_val + put_ask_val + put_bid_val

    if total_sent > 0:
        rows_data = [
            ("📞 CALL Ask", "Compra agresiva", call_ask_val, +(call_ask_val / total_sent * 100), True),
            ("📞 CALL Bid", "Venta agresiva", call_bid_val, -(call_bid_val / total_sent * 100), False),
            ("📋 PUT Ask", "Compra agresiva", put_ask_val, -(put_ask_val / total_sent * 100), False),
            ("📋 PUT Bid", "Venta agresiva", put_bid_val, +(put_bid_val / total_sent * 100), True),
        ]

        bullish_total = call_ask_val + put_bid_val
        bearish_total = call_bid_val + put_ask_val
        net_pct = ((bullish_total - bearish_total) / total_sent) * 100

        max_abs = max(abs(r[3]) for r in rows_data)
        if max_abs == 0:
            max_abs = 1

        rows_html = ""
        for label, desc, amount, pct, is_bull in rows_data:
            cc = "g" if is_bull else "r"
            pct_str = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
            bar_w = abs(pct) / max_abs * 44

            if is_bull:
                fill_s = f"left:50%;width:{bar_w:.1f}%;background:linear-gradient(90deg,rgba(16,185,129,.6),rgba(5,150,105,.2));border-radius:0 6px 6px 0"
            else:
                fill_s = f"right:50%;width:{bar_w:.1f}%;background:linear-gradient(270deg,rgba(239,68,68,.6),rgba(185,28,28,.2));border-radius:6px 0 0 6px"

            rows_html += (
                f'<div class="sr"><div class="sl"><div class="slt">{label}</div>'
                f'<div class="sld">{desc}</div></div>'
                f'<div class="sa {cc}">{_fmt_monto(amount)}</div>'
                f'<div class="sb"><div class="sm"></div>'
                f'<div class="sf" style="{fill_s}"></div></div>'
                f'<div class="sp {cc}">{pct_str}</div></div>'
            )

        net_label = "ALCISTA" if net_pct >= 0 else "BAJISTA"
        net_emoji = "🟢" if net_pct >= 0 else "🔴"
        net_pct_str = f"+{net_pct:.1f}%" if net_pct >= 0 else f"{net_pct:.1f}%"
        bull_pct = bullish_total / total_sent * 100
        bear_pct = bearish_total / total_sent * 100
        net_bar_w = max(abs(bull_pct - bear_pct) / 100 * 44, 8)
        nc = "g" if net_pct >= 0 else "r"

        if net_pct >= 0:
            net_fill = f"left:50%;width:{net_bar_w:.1f}%;background:linear-gradient(90deg,rgba(16,185,129,.8),rgba(5,150,105,.3));border-radius:0 6px 6px 0"
        else:
            net_fill = f"right:50%;width:{net_bar_w:.1f}%;background:linear-gradient(270deg,rgba(239,68,68,.8),rgba(185,28,28,.3));border-radius:6px 0 0 6px"

        # --- Sentiment Gauge (Plotly) ---
        gauge_score = max(0, min(100, 50 + net_pct / 2))
        if net_pct >= 10:
            gauge_lbl = "ALCISTA"
        elif net_pct <= -10:
            gauge_lbl = "BAJISTA"
        else:
            gauge_lbl = "NEUTRAL"

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=gauge_score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": f"OKA Sentiment Index — {gauge_lbl}", "font": {"size": 16, "color": "white"}},
            number={"font": {"size": 42, "color": "white"}, "suffix": "/100"},
            delta={"reference": 50, "increasing": {"color": "#00ff88"}, "decreasing": {"color": "#ef4444"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#475569", "tickfont": {"color": "#94a3b8", "size": 11}},
                "bar": {"color": "#00ff88", "thickness": 0.3},
                "bgcolor": "#0f172a",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(239, 68, 68, 0.25)"},
                    {"range": [30, 50], "color": "rgba(245, 158, 11, 0.15)"},
                    {"range": [50, 70], "color": "rgba(16, 185, 129, 0.15)"},
                    {"range": [70, 100], "color": "rgba(0, 255, 136, 0.2)"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 3},
                    "thickness": 0.8,
                    "value": gauge_score,
                },
            },
        ))
        fig_gauge.update_layout(
            paper_bgcolor="#1e293b",
            plot_bgcolor="#1e293b",
            font={"color": "white", "family": "Inter, sans-serif"},
            height=400,
            margin=dict(l=30, r=30, t=60, b=10),
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

        _gauge_color = "#00ff88" if gauge_lbl == "ALCISTA" else "#ef4444" if gauge_lbl == "BAJISTA" else "#f59e0b"
        st.markdown(
            f'<h3 style="text-align:center;color:{_gauge_color};margin:-10px 0 8px;font-weight:800;">{gauge_lbl}</h3>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div style="display:flex;justify-content:space-around;padding:8px 0 12px;'
            f'background:#1e293b;border-radius:0 0 12px 12px;margin-top:-10px;">'
            f'<div style="text-align:center"><div style="color:#94a3b8;font-size:.75rem">Bullish</div>'
            f'<div style="color:#10b981;font-weight:700">{bull_pct:.1f}%</div></div>'
            f'<div style="text-align:center"><div style="color:#94a3b8;font-size:.75rem">Score</div>'
            f'<div style="color:white;font-weight:700">{gauge_score:.0f}/100</div></div>'
            f'<div style="text-align:center"><div style="color:#94a3b8;font-size:.75rem">Bearish</div>'
            f'<div style="color:#ef4444;font-weight:700">{bear_pct:.1f}%</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="sp0">'
            f'<div class="tt">💰 Desglose de Sentimiento por Primas</div>'
            f'<div class="ts">Prima ejecutada por lado del order book — Compras vs Ventas agresivas</div>'
            f'{rows_html}'
            f'<div class="sn"><div class="snr">'
            f'<div class="snl"><div class="snt">{net_emoji} NETO</div><div class="snd {nc}">{net_label}</div></div>'
            f'<div class="sa {nc}">{_fmt_monto(abs(bullish_total - bearish_total))}</div>'
            f'<div class="sb"><div class="sm"></div><div class="sf" style="{net_fill}"></div></div>'
            f'<div class="sp {nc}">{net_pct_str}</div>'
            f'</div></div>'
            f'<div class="ssum">'
            f'<div class="ssi"><div class="ssh">🟢 Alcista</div><div class="ssv g">{_fmt_monto(bullish_total)}</div><div class="ssp g">{bull_pct:.1f}%</div></div>'
            f'<div class="ssi"><div class="ssh">📊 Total</div><div class="ssv w">{_fmt_monto(total_sent)}</div><div class="ssp gy">100%</div></div>'
            f'<div class="ssi"><div class="ssh">🔴 Bajista</div><div class="ssv r">{_fmt_monto(bearish_total)}</div><div class="ssp r">{bear_pct:.1f}%</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Sin datos suficientes para calcular el sentimiento por primas.")

    st.markdown("---")

    # ================================================================
    # SOPORTES Y RESISTENCIAS POR VOLUMEN DE OPCIONES
    # ================================================================
    st.markdown("### 🛡️ Soportes y Resistencias por Opciones")

    precio_actual = st.session_state.get('precio_subyacente', None)

    df_calls_sr = df_analisis[(df_analisis["Tipo"] == "CALL") & (df_analisis["Volumen"] > 0)].copy()
    df_puts_sr = df_analisis[(df_analisis["Tipo"] == "PUT") & (df_analisis["Volumen"] > 0)].copy()

    if not df_calls_sr.empty and not df_puts_sr.empty:
        top_calls = df_calls_sr.groupby("Strike").agg(
            Vol_Total=("Volumen", "sum"),
            OI_Total=("OI", "sum"),
            Prima_Total=("Prima_Vol", "sum"),
            Contratos=("Volumen", "count"),
        ).sort_values("Vol_Total", ascending=False).head(5).reset_index()

        top_puts = df_puts_sr.groupby("Strike").agg(
            Vol_Total=("Volumen", "sum"),
            OI_Total=("OI", "sum"),
            Prima_Total=("Prima_Vol", "sum"),
            Contratos=("Volumen", "count"),
        ).sort_values("Vol_Total", ascending=False).head(5).reset_index()

        col_sr1, col_sr2 = st.columns(2)

        with col_sr1:
            st.markdown("#### 🔴 Soportes (Calls más tradeados)")
            for idx_s, row_s in top_calls.iterrows():
                pct_dist = ""
                if precio_actual and precio_actual > 0:
                    dist = ((row_s["Strike"] - precio_actual) / precio_actual) * 100
                    pct_dist = f" ({'+' if dist >= 0 else ''}{dist:.1f}%)"
                st.markdown(
                    f"""
                    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); 
                         border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 1.1rem; font-weight: 700; color: #ef4444;">
                                    S{idx_s + 1}: ${row_s['Strike']:,.1f}
                                </span>
                                <span style="font-size: 0.8rem; color: #94a3b8;">{pct_dist}</span>
                            </div>
                            <div style="text-align: right;">
                                <span style="font-size: 0.82rem; color: #f1f5f9;">
                                    Vol: <b>{row_s['Vol_Total']:,.0f}</b>
                                </span>
                            </div>
                        </div>
                        <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">
                            OI: {row_s['OI_Total']:,.0f} | Prima: {_fmt_monto(row_s['Prima_Total'])} | {int(row_s['Contratos'])} contratos
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with col_sr2:
            st.markdown("#### 🟢 Resistencias (Puts más tradeados)")
            for idx_r, row_r in top_puts.iterrows():
                pct_dist = ""
                if precio_actual and precio_actual > 0:
                    dist = ((row_r["Strike"] - precio_actual) / precio_actual) * 100
                    pct_dist = f" ({'+' if dist >= 0 else ''}{dist:.1f}%)"
                st.markdown(
                    f"""
                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); 
                         border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 1.1rem; font-weight: 700; color: #10b981;">
                                    R{idx_r + 1}: ${row_r['Strike']:,.1f}
                                </span>
                                <span style="font-size: 0.8rem; color: #94a3b8;">{pct_dist}</span>
                            </div>
                            <div style="text-align: right;">
                                <span style="font-size: 0.82rem; color: #f1f5f9;">
                                    Vol: <b>{row_r['Vol_Total']:,.0f}</b>
                                </span>
                            </div>
                        </div>
                        <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">
                            OI: {row_r['OI_Total']:,.0f} | Prima: {_fmt_monto(row_r['Prima_Total'])} | {int(row_r['Contratos'])} contratos
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Gráfica visual de niveles
        if precio_actual and precio_actual > 0:
            st.markdown("---")
            st.markdown("#### 📍 Mapa de Niveles vs Precio Actual")

            niveles_s = [(s, "S", v) for s, v in zip(top_calls["Strike"], top_calls["Vol_Total"])]
            niveles_r = [(s, "R", v) for s, v in zip(top_puts["Strike"], top_puts["Vol_Total"])]
            todos_niveles = sorted(niveles_r + niveles_s, key=lambda x: x[0])

            if todos_niveles:
                vols_plot = [n[2] for n in todos_niveles]
                max_vol = max(vols_plot) if vols_plot else 1

                fig_niveles = go.Figure()

                for i, (strike_n, tipo_n, vol_n) in enumerate(todos_niveles):
                    color = "#10b981" if tipo_n == "S" else "#ef4444"
                    fig_niveles.add_trace(go.Bar(
                        x=[vol_n],
                        y=[f"{'S' if tipo_n == 'S' else 'R'}  ${strike_n:,.1f}"],
                        orientation="h",
                        marker_color=color,
                        marker_opacity=0.55 + 0.45 * (vol_n / max_vol),
                        showlegend=False,
                        hovertemplate=(
                            f"<b>{'🟢 Soporte' if tipo_n == 'S' else '🔴 Resistencia'}</b><br>"
                            f"Strike: ${strike_n:,.2f}<br>"
                            f"Volumen: {vol_n:,.0f}<extra></extra>"
                        ),
                    ))

                fig_niveles.add_annotation(
                    x=max_vol * 0.98,
                    y=len(todos_niveles) - 0.5,
                    text=f"📍 Precio: ${precio_actual:,.2f}",
                    showarrow=False,
                    font=dict(color="#f59e0b", size=13, family="Inter"),
                    bgcolor="rgba(245,158,11,0.15)",
                    bordercolor="#f59e0b",
                    borderwidth=1,
                    borderpad=5,
                    xanchor="right",
                    yanchor="bottom",
                )

                fig_niveles.update_layout(
                    height=max(420, 40 * len(todos_niveles) + 80),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(15,23,42,0.8)",
                    font=dict(color="#94a3b8", family="Inter", size=12),
                    xaxis=dict(
                        title="Volumen Total",
                        gridcolor="rgba(51,65,85,0.4)",
                        color="#94a3b8",
                        tickformat=",",
                    ),
                    yaxis=dict(
                        title="",
                        gridcolor="rgba(51,65,85,0.2)",
                        color="#e2e8f0",
                        tickfont=dict(size=11),
                        autorange="reversed",
                    ),
                    margin=dict(l=20, r=20, t=40, b=40),
                    bargap=0.25,
                    title=dict(
                        text=f"Niveles de Soporte (🟢) y Resistencia (🔴)  —  Precio actual: <b>${precio_actual:,.2f}</b>",
                        font=dict(color="#e2e8f0", size=14),
                        x=0,
                    ),
                )

                fig_niveles.add_shape(
                    type="line",
                    x0=0, x1=1, xref="paper",
                    y0=-0.5, y1=-0.5, yref="y",
                    line=dict(color="rgba(245,158,11,0.0)", width=0),
                )

                st.plotly_chart(fig_niveles, use_container_width=True, config={"displayModeBar": False})

            soportes_abajo = sorted([n for n in niveles_s if n[0] < precio_actual], key=lambda x: x[0], reverse=True)
            resistencias_arriba = sorted([n for n in niveles_r if n[0] > precio_actual], key=lambda x: x[0])

            col_near1, col_near2 = st.columns(2)
            with col_near1:
                if soportes_abajo:
                    s_cercano = soportes_abajo[0]
                    dist_s = ((s_cercano[0] - precio_actual) / precio_actual) * 100
                    st.metric("🟢 Soporte más cercano", f"${s_cercano[0]:,.1f}",
                              delta=f"{dist_s:.2f}% abajo", delta_color="normal")
                else:
                    st.info("Sin soportes por debajo del precio actual")
            with col_near2:
                if resistencias_arriba:
                    r_cercana = resistencias_arriba[0]
                    dist_r = ((r_cercana[0] - precio_actual) / precio_actual) * 100
                    st.metric("🔴 Resistencia más cercana", f"${r_cercana[0]:,.1f}",
                              delta=f"+{dist_r:.2f}% arriba", delta_color="inverse")
                else:
                    st.info("Sin resistencias por encima del precio actual")
    else:
        st.info("No hay suficientes datos de CALLs y PUTs para calcular soportes y resistencias.")

    st.markdown("---")

    # ================================================================
    # DISTRIBUCIÓN Y GRÁFICAS
    # ================================================================
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        st.markdown("#### 📊 Distribución CALL vs PUT")
        tipo_counts = df_analisis["Tipo"].value_counts()
        st.bar_chart(tipo_counts)

        n_calls = tipo_counts.get("CALL", 0)
        n_puts = tipo_counts.get("PUT", 0)
        ratio_pc = n_puts / n_calls if n_calls > 0 else 0

        # ── Put/Call Ratio Gauge ──
        fig_pcr = render_pcr_gauge(ratio_pc)
        st.plotly_chart(fig_pcr, use_container_width=True, key="pcr_gauge")


    with col_a2:
        st.markdown("#### 📅 Volumen por Vencimiento")
        vol_by_date = (
            df_analisis.groupby("Vencimiento")["Volumen"]
            .sum()
            .sort_index()
        )
        st.bar_chart(vol_by_date)

    col_iv1, col_iv2 = st.columns(2)
    with col_iv1:
        st.markdown("#### 📉 Volatilidad Implícita por Strike (CALLs)")
        calls_iv = df_analisis[
            (df_analisis["Tipo"] == "CALL") & (df_analisis["IV"] > 0)
        ].sort_values("Strike")
        if not calls_iv.empty:
            chart_data_calls = calls_iv[["Strike", "IV"]].set_index("Strike")
            st.line_chart(chart_data_calls)
    with col_iv2:
        st.markdown("#### 📉 Volatilidad Implícita por Strike (PUTs)")
        puts_iv = df_analisis[
            (df_analisis["Tipo"] == "PUT") & (df_analisis["IV"] > 0)
        ].sort_values("Strike")
        if not puts_iv.empty:
            chart_data_puts = puts_iv[["Strike", "IV"]].set_index("Strike")
            st.line_chart(chart_data_puts)

    # Desglose por vencimiento
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
            st.markdown(
                render_pro_table(display_pc, title="📞 CALLs por Vencimiento"),
                unsafe_allow_html=True,
            )
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
            st.markdown(
                render_pro_table(display_pp, title="📋 PUTs por Vencimiento"),
                unsafe_allow_html=True,
            )
        else:
            st.info("Sin datos de PUTs.")

    # Top strikes donde se concentra el dinero
    st.markdown("#### 🎯 Top 15 Strikes con Mayor Prima Total Ejecutada")
    df_prima_strike = df_analisis.copy()
    prima_cols = ["Tipo", "Strike", "Vencimiento", "Volumen", "OI", "OI_Chg", "Prima_Vol", "IV", "Delta", "Ultimo", "Lado", "Flow_Type"]
    top_prima = df_prima_strike.nlargest(15, "Prima_Vol")[
        [c for c in prima_cols if c in df_prima_strike.columns]
    ].reset_index(drop=True)

    top_prima_display = top_prima.copy()
    top_prima_display = top_prima_display.rename(columns={"Prima_Vol": "Prima Total"})
    if "Tipo" in top_prima_display.columns and "Lado" in top_prima_display.columns:
        top_prima_display.insert(0, "Sentimiento", top_prima_display.apply(
            lambda row: _sentiment_badge(row["Tipo"], row.get("Lado", "N/A")), axis=1
        ))
    if "Tipo" in top_prima_display.columns:
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
    # Flow Type
    if "Flow_Type" not in top_prima_display.columns:
        top_prima_display["Flow_Type"] = top_prima.apply(classify_flow_type, axis=1)
    top_prima_display["Flow_Type"] = top_prima_display["Flow_Type"].apply(flow_badge)
    # Hedge Alert
    if "Hedge_Alert" not in top_prima_display.columns:
        top_prima_display["Hedge_Alert"] = top_prima.apply(
            lambda r: detect_institutional_hedge(r).get("alerta", ""), axis=1
        )

    st.markdown(
        render_pro_table(top_prima_display, title="🎯 Top 15 Mayor Prima Ejecutada", badge_count="15"),
        unsafe_allow_html=True,
    )

    # Gráfica de prima por strike
    st.markdown("#### 📊 Flujo de Prima por Strike (CALL vs PUT)")
    pivot_prima = df_analisis.pivot_table(
        index="Strike", columns="Tipo",
        values="Prima_Vol", aggfunc="sum", fill_value=0,
    )
    pivot_prima = pivot_prima[pivot_prima.sum(axis=1) > 0]
    if not pivot_prima.empty:
        pivot_prima = pivot_prima.nlargest(30, pivot_prima.columns.tolist()[0] if len(pivot_prima.columns) > 0 else pivot_prima.index).sort_index()
        st.bar_chart(pivot_prima)
    st.caption("Prima por Volumen distribuida por strike — muestra dónde se concentran las apuestas más grandes")

    # ================================================================
    # ADVANCED ANALYTICS — IV Rank, Monte Carlo, Vol Surface, Anomalies
    # ================================================================
    st.markdown("---")
    st.markdown("### 🧠 Análisis Avanzado")

    precio_mc = st.session_state.get("precio_subyacente", 0) or 0

    # ── IV Rank / Percentile ──────────────────────────────────────
    _iv_cache_key = f"_iv_rank_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    if st.session_state.get(_iv_cache_key) is None:
        try:
            from core.iv_rank import calcular_iv_rank_percentile
            # Usar IV promedio del scan como IV actual
            avg_iv = df_analisis["IV"].median() if "IV" in df_analisis.columns else None
            iv_data = calcular_iv_rank_percentile(ticker_symbol, iv_actual=avg_iv)
            st.session_state[_iv_cache_key] = iv_data
        except Exception as e:
            logger.warning(f"Error calculando IV Rank: {e}")
            st.session_state[_iv_cache_key] = None

    iv_data = st.session_state.get(_iv_cache_key)

    col_adv1, col_adv2 = st.columns(2)
    with col_adv1:
        if iv_data and iv_data["iv_rank"] > 0:
            fig_iv = render_iv_gauge(
                iv_data["iv_rank"],
                iv_data["iv_percentile"],
                iv_data["iv_actual"],
            )
            st.plotly_chart(fig_iv, use_container_width=True, key="iv_gauge")

            # Métricas resumidas debajo
            st.markdown(render_metric_row([
                render_metric_card("IV Actual", f"{iv_data['iv_actual']:.1f}%"),
                render_metric_card("IV Max 52w", f"{iv_data['iv_high_52w']:.1f}%",
                                   color_override="#ef4444"),
                render_metric_card("IV Min 52w", f"{iv_data['iv_low_52w']:.1f}%",
                                   color_override="#10b981"),
                render_metric_card("HV 20d", f"{iv_data['hv_20d']:.1f}%"),
            ]), unsafe_allow_html=True)

            # Interpretación
            if iv_data["iv_rank"] >= 60:
                st.info("📈 **IV alta** — Buen momento para VENDER opciones (prima elevada)")
            elif iv_data["iv_rank"] <= 30:
                st.info("📉 **IV baja** — Buen momento para COMPRAR opciones (prima barata)")
            else:
                st.info("↔️ **IV media** — Sin ventaja clara direccional en volatilidad")
        else:
            st.info("⏳ Calculando IV Rank... Ejecuta un escaneo para activar.")

    # ── Monte Carlo Simulation ────────────────────────────────────
    with col_adv2:
        if precio_mc > 0:
            # Obtener IV para la simulación
            iv_for_mc = 0.25  # default
            if iv_data and iv_data["iv_actual"] > 0:
                iv_for_mc = iv_data["iv_actual"] / 100
            elif "IV" in df_analisis.columns:
                med_iv = df_analisis["IV"].median()
                if med_iv > 0:
                    iv_for_mc = med_iv / 100

            mc_cache_key = f"_mc_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
            if st.session_state.get(mc_cache_key) is None:
                try:
                    from core.monte_carlo import simular_monte_carlo
                    mc_result = simular_monte_carlo(
                        spot_price=precio_mc,
                        iv=iv_for_mc,
                        days=30,
                        num_sims=1_000,
                    )
                    st.session_state[mc_cache_key] = mc_result
                except Exception as e:
                    logger.warning(f"Error Monte Carlo: {e}")
                    st.session_state[mc_cache_key] = None

            mc_result = st.session_state.get(mc_cache_key)
            if mc_result and mc_result["days"] > 0:
                fig_mc = render_monte_carlo_chart(mc_result, precio_mc, ticker_symbol)
                st.plotly_chart(fig_mc, use_container_width=True, key="mc_chart")

                pctls = mc_result["percentiles"]
                st.markdown(render_metric_row([
                    render_metric_card("P(Sube)", f"{mc_result['prob_above']:.1f}%",
                                       color_override="#10b981" if mc_result["prob_above"] > 50 else "#ef4444"),
                    render_metric_card("Precio Esperado", f"${mc_result['expected_price']:,.2f}"),
                    render_metric_card("Rango 90%",
                                       f"${pctls['p5']:,.2f} — ${pctls['p95']:,.2f}"),
                ]), unsafe_allow_html=True)
        else:
            st.info("⏳ Ejecuta un escaneo para activar Monte Carlo.")

    st.markdown("---")

    # ================================================================
    # MC OPTION PRICING — Valoración de opciones con riesgo ajustado
    # ================================================================
    st.markdown("#### 🎲 Valoración MC de Opciones (Riesgo Ajustado)")
    st.caption(
        "Simula miles de trayectorias del subyacente para estimar el precio teórico "
        "de una opción, la probabilidad de terminar ITM, y la distribución de payoffs."
    )

    # Controles del usuario
    _mc_opt_col1, _mc_opt_col2, _mc_opt_col3, _mc_opt_col4 = st.columns(4)

    # Obtener strikes disponibles del scan
    _strikes_disponibles = sorted(df_analisis["Strike"].unique()) if "Strike" in df_analisis.columns else []
    _spot = precio_mc or 0

    with _mc_opt_col1:
        mc_opt_type = st.selectbox(
            "Tipo de opción", ["CALL", "PUT"], index=0, key="mc_opt_type",
        )

    with _mc_opt_col2:
        # Default: strike ATM más cercano
        if _strikes_disponibles and _spot > 0:
            _atm_idx = int(np.argmin([abs(s - _spot) for s in _strikes_disponibles]))
            mc_strike = st.selectbox(
                "Strike", _strikes_disponibles, index=_atm_idx, key="mc_opt_strike",
                format_func=lambda x: f"${x:,.1f}",
            )
        else:
            mc_strike = st.number_input(
                "Strike ($)", value=_spot or 100.0, min_value=1.0,
                step=1.0, key="mc_opt_strike_input",
            )

    with _mc_opt_col3:
        mc_n_sims = st.select_slider(
            "Simulaciones",
            options=[1_000, 5_000, 10_000, 25_000, 50_000],
            value=10_000, key="mc_opt_nsims",
        )

    with _mc_opt_col4:
        mc_days = st.slider(
            "Días al vencimiento", min_value=5, max_value=180,
            value=30, step=5, key="mc_opt_days",
        )

    # Ejecutar simulación
    if _spot > 0 and mc_strike > 0:
        # Obtener IV para la simulación
        _mc_iv = 0.25
        if iv_data and iv_data["iv_actual"] > 0:
            _mc_iv = iv_data["iv_actual"] / 100
        elif "IV" in df_analisis.columns:
            _med = df_analisis["IV"].median()
            if _med > 0:
                _mc_iv = _med / 100

        _mc_opt_key = (
            f"_mc_opt_{ticker_symbol}_{mc_opt_type}_{mc_strike}_{mc_days}"
            f"_{mc_n_sims}_{st.session_state.get('scan_count', 0)}"
        )

        if st.session_state.get(_mc_opt_key) is None:
            try:
                from core.monte_carlo import monte_carlo_option_pricing
                from config.constants import RISK_FREE_RATE

                mc_opt_result = monte_carlo_option_pricing(
                    S0=_spot,
                    K=float(mc_strike),
                    T=mc_days / 365,
                    r=RISK_FREE_RATE,
                    sigma=_mc_iv,
                    option_type=mc_opt_type.lower(),
                    n_sims=mc_n_sims,
                    n_steps=mc_days,
                )
                st.session_state[_mc_opt_key] = mc_opt_result
            except Exception as e:
                logger.warning(f"Error MC Option Pricing: {e}")
                st.session_state[_mc_opt_key] = {"error": str(e)}

        mc_opt = st.session_state.get(_mc_opt_key, {})

        if "error" not in mc_opt:
            # Interpretación
            st.markdown(mc_opt["interpretation"])

            # Métricas principales
            st.markdown(render_metric_row([
                render_metric_card("Precio MC", f"${mc_opt['mc_price']:.2f}",
                                   color_override="#00ff88"),
                render_metric_card("P(ITM)", f"{mc_opt['itm_probability']:.1f}%",
                                   color_override="#10b981" if mc_opt["itm_probability"] >= 50 else "#ef4444"),
                render_metric_card("Payoff Esperado", f"${mc_opt['expected_payoff']:.2f}"),
                render_metric_card("Break-Even", f"${mc_opt['breakeven']:,.2f}"),
            ]), unsafe_allow_html=True)

            # Charts
            from ui.charts import render_mc_option_paths, render_mc_payoff_histogram

            col_mc1, col_mc2 = st.columns(2)
            with col_mc1:
                fig_paths = render_mc_option_paths(mc_opt, ticker_symbol)
                if fig_paths:
                    st.plotly_chart(fig_paths, use_container_width=True, key="mc_opt_paths")

            with col_mc2:
                fig_payoff = render_mc_payoff_histogram(mc_opt, ticker_symbol)
                if fig_payoff:
                    st.plotly_chart(fig_payoff, use_container_width=True, key="mc_opt_payoff")

            # Métricas de riesgo expandibles
            with st.expander("📊 Métricas de riesgo detalladas"):
                _r1, _r2, _r3 = st.columns(3)
                with _r1:
                    st.metric("Mediana Payoff", f"${mc_opt['median_payoff']:.2f}")
                    st.metric("Std Payoff", f"${mc_opt['std_payoff']:.2f}")
                with _r2:
                    st.metric("VaR 95%", f"${mc_opt['var_95']:.2f}")
                    st.metric("CVaR 95%", f"${mc_opt['cvar_95']:.2f}")
                with _r3:
                    st.metric("Max Drawdown", f"{mc_opt['max_drawdown_pct']:.1f}%")
                    st.metric("P95 Payoff", f"${mc_opt['payoff_percentiles']['p95']:.2f}")

                st.markdown(f"""
**Parámetros usados:**
- Spot: ${mc_opt['params']['S0']:,.2f} | Strike: ${mc_opt['params']['K']:,.1f}
- σ (IV): {mc_opt['params']['sigma']*100:.1f}% | r: {mc_opt['params']['r']*100:.2f}%
- T: {mc_opt['params']['T']:.4f} años ({mc_days} días) | Sims: {mc_opt['params']['n_sims']:,}
""")
                st.caption(
                    "⚠️ MC pricing es orientativo — asume distribución log-normal y "
                    "sin saltos. No incluye costos de transacción ni spread bid/ask."
                )
        else:
            st.warning(f"MC Option: {mc_opt.get('error', 'Error desconocido')}")
    else:
        st.info("⏳ Ejecuta un escaneo para activar la valoración MC de opciones.")

    st.markdown("---")

    # ── OI Heatmap ────────────────────────────────────────────────
    st.markdown("#### 🗺️ Heatmap de Open Interest")
    hm_col_selector = st.radio(
        "Métrica del heatmap", ["OI", "Volumen", "IV", "Prima_Vol"],
        horizontal=True, key="hm_metric", index=0,
    )
    hm_tipo = st.radio(
        "Tipo", ["ALL", "CALL", "PUT"],
        horizontal=True, key="hm_tipo", index=0,
    )
    fig_hm = render_oi_heatmap(
        st.session_state.datos_completos,
        tipo=hm_tipo,
        value_col=hm_col_selector,
    )
    if fig_hm:
        st.plotly_chart(fig_hm, use_container_width=True, key="oi_heatmap")
    else:
        st.info("Sin datos suficientes para el heatmap.")

    st.markdown("---")

    # ── Volatility Surface 3D ─────────────────────────────────────
    st.markdown("#### 🌋 Superficie de Volatilidad Implícita (3D)")
    fig_vs = render_vol_surface(
        st.session_state.datos_completos,
        spot_price=precio_mc,
    )
    if fig_vs:
        st.plotly_chart(fig_vs, use_container_width=True, key="vol_surface")
        st.caption("Superficie IV por Strike × Vencimiento — Identifica skew y smile de volatilidad")
    else:
        st.info("Sin datos suficientes para la superficie de volatilidad (necesita ≥2 vencimientos con IV).")

    st.markdown("---")

    # ── Anomaly Detection ─────────────────────────────────────────
    st.markdown("#### 🔍 Detector de Anomalías — ML (IsolationForest)")
    anom_cache_key = f"_anomalies_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    if st.session_state.get(anom_cache_key) is None:
        try:
            from core.anomaly_detector import detectar_anomalias
            df_anom = detectar_anomalias(st.session_state.datos_completos)
            st.session_state[anom_cache_key] = df_anom
        except Exception as e:
            logger.warning(f"Error anomaly detection: {e}")
            st.session_state[anom_cache_key] = None

    df_anomalies = st.session_state.get(anom_cache_key)
    if df_anomalies is not None and not df_anomalies.empty:
        fig_anom = render_anomaly_scatter(df_anomalies)
        if fig_anom:
            st.plotly_chart(fig_anom, use_container_width=True, key="anomaly_scatter")

        # Mostrar top anomalías como tabla
        top_anom = df_anomalies[df_anomalies["is_anomaly"]].nlargest(10, "anomaly_score")
        if not top_anom.empty:
            from core.anomaly_detector import anomaly_badge
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
                render_pro_table(anom_show, title="🔴 Top 10 Anomalías Detectadas",
                                 badge_count=len(top_anom)),
                unsafe_allow_html=True,
            )
        st.caption("IsolationForest analiza patrones de volumen, prima, IV y OI para detectar actividad fuera de lo normal.")
    else:
        st.info("Sin suficientes datos para detección de anomalías (mínimo 30 registros). Si sklearn no está instalado, se omite.")

    st.markdown("---")

    # ── Predicción de Volatilidad Implícita (IV Forecast) ─────────
    st.markdown("#### 🔮 Predicción de Volatilidad Implícita (Regresión Lineal)")
    _ivf_cache_key = f"_iv_forecast_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"

    if st.session_state.get(_ivf_cache_key) is None:
        try:
            from core.iv_rank import get_historical_iv
            from core.projections import predict_implied_volatility

            df_iv_hist = get_historical_iv(ticker_symbol, period="1y")
            if df_iv_hist.empty:
                st.session_state[_ivf_cache_key] = {"error": "Sin datos históricos suficientes"}
            else:
                forecast_result = predict_implied_volatility(df_iv_hist, forecast_days=5)
                st.session_state[_ivf_cache_key] = forecast_result
                st.session_state[f"{_ivf_cache_key}_hist"] = df_iv_hist
        except Exception as e:
            logger.warning(f"Error IV Forecast: {e}")
            st.session_state[_ivf_cache_key] = {"error": f"Error: {e}"}

    iv_forecast = st.session_state.get(_ivf_cache_key, {})
    df_iv_hist = st.session_state.get(f"{_ivf_cache_key}_hist", pd.DataFrame())

    if "error" not in iv_forecast:
        # Interpretación con formato
        st.markdown(iv_forecast["interpretation"])

        # Gráfico
        from ui.charts import render_iv_forecast_chart
        fig_ivf = render_iv_forecast_chart(df_iv_hist, iv_forecast, ticker_symbol)
        if fig_ivf:
            st.plotly_chart(fig_ivf, use_container_width=True, key="iv_forecast_chart")

        # Métricas del modelo (transparencia)
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            st.metric("IV Predicha", f"{iv_forecast['predicted_iv']:.1f}%",
                       delta=f"{iv_forecast['delta_iv']:+.1f}pp")
        with col_f2:
            st.metric("IV Actual", f"{iv_forecast['current_iv']:.1f}%")
        with col_f3:
            st.metric("R² Modelo", f"{iv_forecast['r2_score']:.3f}")
        with col_f4:
            st.metric("Rango ±1σ",
                       f"{iv_forecast['forecast_range'][0]:.1f}% — {iv_forecast['forecast_range'][1]:.1f}%")

        # Detalle del modelo (expandible)
        with st.expander("📊 Detalles del modelo (transparencia)"):
            st.markdown(f"""
**Modelo:** Regresión Lineal (scikit-learn)
**Muestras:** {iv_forecast.get('n_samples', 'N/A')} días históricos
**Forecast:** {iv_forecast['forecast_days']} días
**Features usadas:** `{', '.join(iv_forecast['model_features'])}`
**Error estándar (σ):** ±{iv_forecast.get('pred_std', 0):.2f}%

**Coeficientes del modelo:**
""")
            coefs = iv_forecast.get("coefficients", {})
            for feat, coef in coefs.items():
                arrow = "↑" if coef > 0 else "↓"
                st.markdown(f"- **{feat}**: `{coef:+.6f}` {arrow}")

            st.caption(
                "⚠️ Modelo orientativo — no es recomendación financiera. "
                "La IV real depende de eventos macro, earnings, y flujos institucionales "
                "que un modelo lineal no captura. Usar como referencia complementaria."
            )
    else:
        st.warning(f"📊 IV Forecast: {iv_forecast.get('error', 'Error desconocido')}")

    st.markdown("---")

    # ================================================================
    # DATOS FUNDAMENTALES — Alpha Vantage enrichment
    # ================================================================
    st.markdown("#### 📊 Datos Fundamentales (Alpha Vantage)")
    st.caption(
        "Valuación, rentabilidad, earnings surprise y short interest — "
        "contextualiza opciones con fundamentos reales de la empresa."
    )

    _fund_cache_key = f"_fundamentals_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    if st.session_state.get(_fund_cache_key) is None:
        try:
            from core.projections import enrich_with_fundamentals
            fund_data = enrich_with_fundamentals(ticker_symbol)
            st.session_state[_fund_cache_key] = fund_data
        except Exception as e:
            logger.warning(f"Error fundamentals: {e}")
            st.session_state[_fund_cache_key] = {"error": f"Error: {e}"}

    fund_data = st.session_state.get(_fund_cache_key, {})
    render_fundamentals_card(fund_data, ticker_symbol)
