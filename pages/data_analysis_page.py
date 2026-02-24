# -*- coding: utf-8 -*-
"""Página: 📈 Data Analysis — Sentimiento, soportes/resistencias, distribución."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.formatters import (
    _fmt_dolar, _fmt_monto, _fmt_entero, _fmt_iv, _fmt_precio,
    _fmt_oi, _fmt_oi_chg, _fmt_lado,
)
from ui.components import (
    render_pro_table, _sentiment_badge, _type_badge,
)
from core.flow_classifier import classify_flow_type, flow_badge


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
        st.metric("Put/Call Ratio", f"{ratio_pc:.3f}")
        if ratio_pc < 0.7:
            st.success("📈 Ratio < 0.7: Mayor actividad en CALLs (sentimiento alcista)")
        else:
            st.info("↔️ Ratio neutral")

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
    prima_cols = ["Tipo", "Strike", "Vencimiento", "Volumen", "OI", "OI_Chg", "Prima_Vol", "IV", "Ultimo", "Lado", "Flow_Type"]
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
    top_prima_display["Ultimo"] = top_prima_display["Ultimo"].apply(_fmt_precio)
    top_prima_display["Strike"] = top_prima_display["Strike"].apply(lambda x: f"${x:,.1f}")
    if "Lado" in top_prima_display.columns:
        top_prima_display["Lado"] = top_prima_display["Lado"].apply(_fmt_lado)
    # Flow Type
    if "Flow_Type" not in top_prima_display.columns:
        top_prima_display["Flow_Type"] = top_prima.apply(classify_flow_type, axis=1)
    top_prima_display["Flow_Type"] = top_prima_display["Flow_Type"].apply(flow_badge)

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
