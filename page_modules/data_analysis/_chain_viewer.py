"""Sentiment breakdown and supports/resistances for Data Analysis."""
import plotly.graph_objects as go
import streamlit as st

from ui.plotly_professional_theme import apply_theme, COLORS, pro_gauge_layout
from utils.formatters import _fmt_monto


def render_sentiment_breakdown(df_analisis):
    """Render the 💰 Desglose de Sentimiento section with gauge and bar chart."""
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

    if total_sent <= 0:
        st.info("Sin datos suficientes para calcular el sentimiento por primas.")
        return

    rows_data = [
        ("📞 CALL Ask", "Compra agresiva", call_ask_val, +(call_ask_val / total_sent * 100), True),
        ("📞 CALL Bid", "Venta agresiva", call_bid_val, -(call_bid_val / total_sent * 100), False),
        ("📋 PUT Ask", "Compra agresiva", put_ask_val, -(put_ask_val / total_sent * 100), False),
        ("📋 PUT Bid", "Venta agresiva", put_bid_val, +(put_bid_val / total_sent * 100), True),
    ]

    bullish_total = call_ask_val + put_bid_val
    bearish_total = call_bid_val + put_ask_val
    net_pct = ((bullish_total - bearish_total) / total_sent) * 100

    max_abs = max(abs(r[3]) for r in rows_data) or 1

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
    fig_gauge.update_layout(**{**pro_gauge_layout(400), "margin": dict(l=30, r=30, t=60, b=10)})
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
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="sp0">'
        f'<div class="tt">💰 Desglose de Sentimiento por Primas</div>'
        f'<div class="ts">Prima ejecutada por lado del order book — Compras vs Ventas agresivas</div>'
        f"{rows_html}"
        f'<div class="sn"><div class="snr">'
        f'<div class="snl"><div class="snt">{net_emoji} NETO</div><div class="snd {nc}">{net_label}</div></div>'
        f'<div class="sa {nc}">{_fmt_monto(abs(bullish_total - bearish_total))}</div>'
        f'<div class="sb"><div class="sm"></div><div class="sf" style="{net_fill}"></div></div>'
        f'<div class="sp {nc}">{net_pct_str}</div>'
        f"</div></div>"
        f'<div class="ssum">'
        f'<div class="ssi"><div class="ssh">🟢 Alcista</div><div class="ssv g">{_fmt_monto(bullish_total)}</div><div class="ssp g">{bull_pct:.1f}%</div></div>'
        f'<div class="ssi"><div class="ssh">📊 Total</div><div class="ssv w">{_fmt_monto(total_sent)}</div><div class="ssp gy">100%</div></div>'
        f'<div class="ssi"><div class="ssh">🔴 Bajista</div><div class="ssv r">{_fmt_monto(bearish_total)}</div><div class="ssp r">{bear_pct:.1f}%</div></div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_supports_resistances(df_analisis, precio_actual):
    """Render the 🛡️ Soportes y Resistencias section."""
    st.markdown("### 🛡️ Soportes y Resistencias por Opciones")

    df_calls_sr = df_analisis[(df_analisis["Tipo"] == "CALL") & (df_analisis["Volumen"] > 0)].copy()
    df_puts_sr = df_analisis[(df_analisis["Tipo"] == "PUT") & (df_analisis["Volumen"] > 0)].copy()

    if df_calls_sr.empty or df_puts_sr.empty:
        st.info("No hay suficientes datos de CALLs y PUTs para calcular soportes y resistencias.")
        return

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

            apply_theme(
                fig_niveles,
                title=f"Niveles de Soporte (🟢) y Resistencia (🔴)  —  Precio actual: <b>${precio_actual:,.2f}</b>",
                height=max(420, 40 * len(todos_niveles) + 80),
                margin=dict(l=20, r=20, t=40, b=40),
                xaxis_title="Volumen Total",
                xaxis_tickformat=",",
            )
            fig_niveles.update_layout(
                bargap=0.25,
                yaxis=dict(
                    title="",
                    color=COLORS["text"],
                    tickfont=dict(size=11, color=COLORS["text"]),
                    gridcolor=COLORS["faint"],
                    autorange="reversed",
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
