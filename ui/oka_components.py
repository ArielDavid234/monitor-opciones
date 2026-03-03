# -*- coding: utf-8 -*-
"""
OKA Sentiment Index v2 — Componentes de Visualización.

Funciones de renderizado Streamlit + Plotly para la pestaña
"OKA Sentiment Index v2":

    render_okaindex_gauge(result)  → gauge gigante 0-100
    render_flow_bars(result)       → barra horizontal bullish/bearish
    render_flow_cards(result)      → tarjetas $Bullish, $Bearish, $Net
    render_trade_table(result)     → tabla top 20 trades institucionales
    render_oka_page(result)        → composición completa de la pestaña

Diseño oscuro profesional, todo en español.
"""
from __future__ import annotations

import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False


# ============================================================================
#   GAUGE PLOTLY — OKA Index 0-100
# ============================================================================

def render_okaindex_gauge(result: dict) -> None:
    """Renderiza el gauge gigante del OKA Sentiment Index.

    Colores exactos del PDF:
        0–30   rojo oscuro   → Bearish Extreme
        30–45  rojo          → Bearish
        45–55  gris          → Neutral
        55–70  verde         → Bullish
        70–100 verde oscuro  → Bullish Extreme

    Args:
        result: dict devuelto por compute_oka_index().
    """
    oka_idx       = float(result.get("oka_index",      50))
    interpretation = result.get("interpretation",      {})
    symbol        = result.get("symbol",               "?")
    timestamp     = result.get("timestamp",            "")
    gamma_on      = result.get("gamma_weighting",      False)

    label         = interpretation.get("label",        "Neutral")
    text_color    = interpretation.get("text_color",   "#94a3b8")
    emoji         = interpretation.get("emoji",        "⚪")

    if not _PLOTLY_OK:
        st.metric("OKA Index", f"{oka_idx:.1f}/100", label)
        return

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=oka_idx,
        number={
            "suffix": "",
            "font": {"size": 64, "color": text_color, "family": "monospace"},
        },
        delta={
            "reference": 50,
            "increasing": {"color": "#22c55e"},
            "decreasing": {"color": "#ef4444"},
            "valueformat": ".1f",
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickvals": [0, 30, 45, 55, 70, 100],
                "ticktext": ["0", "30", "45", "55", "70", "100"],
                "tickfont": {"size": 11, "color": "#64748b"},
                "tickcolor": "#334155",
            },
            "bar": {"color": text_color, "thickness": 0.28},
            "bgcolor": "#0d1117",
            "borderwidth": 1,
            "bordercolor": "#1e293b",
            "steps": [
                {"range": [0,  30], "color": "#3b0a0a"},   # Bearish Extreme
                {"range": [30, 45], "color": "#450a0a"},   # Bearish
                {"range": [45, 55], "color": "#1e293b"},   # Neutral
                {"range": [55, 70], "color": "#052e16"},   # Bullish
                {"range": [70, 100], "color": "#14532d"},  # Bullish Extreme
            ],
            "threshold": {
                "line": {"color": "#fbbf24", "width": 3},
                "thickness": 0.85,
                "value": 50,
            },
        },
        title={
            "text": (
                f"OKA Sentiment Index v2<br>"
                f"<span style='font-size:14px;color:#64748b;'>"
                f"{symbol} | {timestamp[:16] if timestamp else '—'}"
                f"{'  ·  Gamma ON' if gamma_on else ''}"
                f"</span>"
            ),
            "font": {"size": 20, "color": "#e2e8f0"},
        },
    ))

    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        height=380,
        margin=dict(l=30, r=30, t=60, b=20),
    )

    st.plotly_chart(fig, use_container_width=True, key="oka_gauge")

    # Interpretación en texto grande
    st.markdown(
        f"""
        <div style="text-align:center;margin:-10px 0 18px 0;">
            <span style="font-size:2.4rem;">{emoji}</span>
            <span style="font-size:1.5rem;font-weight:700;color:{text_color};
                margin-left:10px;">{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
#   FLOW CARDS — Bullish / Bearish / Net
# ============================================================================

def render_flow_cards(result: dict) -> None:
    """Renderiza las 3 tarjetas grandes de flujo (Bullish / Bearish / Net).

    Args:
        result: dict devuelto por compute_oka_index().
    """
    bullish = float(result.get("bullish_flow", 0))
    bearish = float(result.get("bearish_flow", 0))
    net     = float(result.get("net_flow",     0))
    total   = float(result.get("total_flow",   0))
    total_r = int(result.get("total_raw_trades",    0))
    total_i = int(result.get("total_institutional", 0))

    net_color = "#22c55e" if net >= 0 else "#ef4444"
    net_icon  = "▲" if net >= 0 else "▼"

    bull_pct = (bullish / total * 100) if total > 0 else 0
    bear_pct = (bearish / total * 100) if total > 0 else 0

    def _fmt(v: float) -> str:
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:,.1f}M"
        if abs(v) >= 1_000:
            return f"${v/1_000:,.0f}K"
        return f"${v:,.0f}"

    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;
                    gap:12px;margin-bottom:16px;">
            <!-- Bullish Flow -->
            <div style="background:linear-gradient(135deg,#052e16,#0d2a18);
                        border:1px solid #15803d;border-radius:12px;
                        padding:18px 16px;text-align:center;">
                <div style="font-size:0.7rem;color:#6ee7b7;letter-spacing:0.08em;
                    text-transform:uppercase;margin-bottom:6px;">
                    📈 Bullish Flow
                </div>
                <div style="font-size:1.9rem;font-weight:700;color:#4ade80;
                    font-family:monospace;">
                    {_fmt(bullish)}
                </div>
                <div style="font-size:0.75rem;color:#86efac;margin-top:4px;">
                    {bull_pct:.1f}% del flujo total · Delta-Weighted
                </div>
            </div>
            <!-- Bearish Flow -->
            <div style="background:linear-gradient(135deg,#3b0a0a,#2a0d0d);
                        border:1px solid #b91c1c;border-radius:12px;
                        padding:18px 16px;text-align:center;">
                <div style="font-size:0.7rem;color:#fca5a5;letter-spacing:0.08em;
                    text-transform:uppercase;margin-bottom:6px;">
                    📉 Bearish Flow
                </div>
                <div style="font-size:1.9rem;font-weight:700;color:#f87171;
                    font-family:monospace;">
                    {_fmt(bearish)}
                </div>
                <div style="font-size:0.75rem;color:#fca5a5;margin-top:4px;">
                    {bear_pct:.1f}% del flujo total · Delta-Weighted
                </div>
            </div>
            <!-- Net Flow -->
            <div style="background:linear-gradient(135deg,#0a0a1a,#0d1f3e);
                        border:1px solid #334155;border-radius:12px;
                        padding:18px 16px;text-align:center;">
                <div style="font-size:0.7rem;color:#94a3b8;letter-spacing:0.08em;
                    text-transform:uppercase;margin-bottom:6px;">
                    ⚡ Net Flow {net_icon}
                </div>
                <div style="font-size:1.9rem;font-weight:700;color:{net_color};
                    font-family:monospace;">
                    {_fmt(net)}
                </div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">
                    {total_i} trades inst. / {total_r} crudos analizados
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
#   FLOW BARS — Barra horizontal Bullish vs Bearish
# ============================================================================

def render_flow_bars(result: dict) -> None:
    """Renderiza la barra horizontal de distribución de flujo.

    Muestra visualmente la proporción Bullish / Neutral / Bearish del
    flujo institucional total.

    Args:
        result: dict devuelto por compute_oka_index().
    """
    bullish = float(result.get("bullish_flow", 0))
    bearish = float(result.get("bearish_flow", 0))
    total   = float(result.get("total_flow",   0))

    if not _PLOTLY_OK or total <= 0:
        return

    import plotly.graph_objects as go  # type: ignore[import]

    bull_pct = bullish / total * 100
    bear_pct = bearish / total * 100
    neut_pct = max(0.0, 100.0 - bull_pct - bear_pct)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[bull_pct], y=["Flujo"],
        orientation="h",
        marker_color="#22c55e",
        name=f"Bullish {bull_pct:.1f}%",
        text=f"Bullish<br>{bull_pct:.1f}%",
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="white", size=12, family="monospace"),
        hovertemplate=f"Bullish: {bull_pct:.1f}%<extra></extra>",
    ))
    if neut_pct > 0.5:
        fig.add_trace(go.Bar(
            x=[neut_pct], y=["Flujo"],
            orientation="h",
            marker_color="#475569",
            name=f"Neutral {neut_pct:.1f}%",
            text=f"Neutro {neut_pct:.1f}%",
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="#94a3b8", size=10),
            hovertemplate=f"Neutral: {neut_pct:.1f}%<extra></extra>",
        ))
    fig.add_trace(go.Bar(
        x=[bear_pct], y=["Flujo"],
        orientation="h",
        marker_color="#ef4444",
        name=f"Bearish {bear_pct:.1f}%",
        text=f"Bearish<br>{bear_pct:.1f}%",
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="white", size=12, family="monospace"),
        hovertemplate=f"Bearish: {bear_pct:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        xaxis=dict(visible=False, range=[0, 100]),
        yaxis=dict(visible=False),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        height=68,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        bargap=0,
    )

    st.markdown(
        '<div style="font-size:0.72rem;color:#64748b;'
        'text-transform:uppercase;letter-spacing:0.05em;'
        'margin-bottom:4px;">📊 Distribución del Flujo Institucional</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True, key="oka_flow_bar")


# ============================================================================
#   TRADE TABLE — Top 20 trades institucionales
# ============================================================================

def render_trade_table(result: dict) -> None:
    """Renderiza la tabla de los últimos 20 trades institucionales.

    Columnas: Symbol, Tipo, Agresión, Premium $, DeltaWeighted $, Dirección.

    Args:
        result: dict devuelto por compute_oka_index().
    """
    trades = result.get("institutional_trades", [])
    if not trades:
        st.info("📭 No hay trades institucionales disponibles para este símbolo.")
        return

    top_trades = trades[:20]

    def _aggr_badge(a: str) -> str:
        if a == "aggressive_buy":
            return '<span style="background:#052e16;color:#4ade80;padding:2px 8px;' \
                   'border-radius:12px;font-size:0.7rem;font-weight:600;">▲ Agr. Compra</span>'
        if a == "aggressive_sell":
            return '<span style="background:#3b0a0a;color:#f87171;padding:2px 8px;' \
                   'border-radius:12px;font-size:0.7rem;font-weight:600;">▼ Agr. Venta</span>'
        return '<span style="background:#1e293b;color:#94a3b8;padding:2px 8px;' \
               'border-radius:12px;font-size:0.7rem;">— Neutral</span>'

    def _dir_badge(d: str) -> str:
        if d == "bullish":
            return '<span style="color:#4ade80;font-weight:700;">🟢 Alcista</span>'
        if d == "bearish":
            return '<span style="color:#f87171;font-weight:700;">🔴 Bajista</span>'
        return '<span style="color:#94a3b8;">⚪ Neutral</span>'

    def _fmt_k(v: float) -> str:
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        if abs(v) >= 1_000:
            return f"${v/1_000:.0f}K"
        return f"${v:.0f}"

    rows_html = ""
    for t in top_trades:
        sym     = str(t.get("symbol",       "—"))[:22]
        ot      = str(t.get("option_type",  "—")).upper()[:4]
        aggr    = str(t.get("aggression",   "neutral"))
        prem    = float(t.get("premium",       0))
        dwp     = float(t.get("delta_weighted", 0))
        direc   = str(t.get("direction",    "neutral"))
        delta_v = float(t.get("delta",        0))
        sweep   = t.get("sweep_flag", None)
        sweep_icon = "🧹" if sweep else ""

        rows_html += f"""
        <tr style="border-bottom:1px solid #1e293b;">
            <td style="padding:6px 8px;font-size:0.76rem;color:#e2e8f0;
                font-family:monospace;white-space:nowrap;">
                {sym} {sweep_icon}
            </td>
            <td style="padding:6px 8px;text-align:center;">
                <span style="color:{'#86efac' if ot=='CALL' else '#fca5a5'};
                    font-weight:600;font-size:0.75rem;">{ot}</span>
            </td>
            <td style="padding:6px 8px;">{_aggr_badge(aggr)}</td>
            <td style="padding:6px 8px;text-align:right;font-family:monospace;
                font-size:0.76rem;color:#fbbf24;">{_fmt_k(prem)}</td>
            <td style="padding:6px 8px;text-align:right;font-family:monospace;
                font-size:0.76rem;color:#a78bfa;">{_fmt_k(dwp)}</td>
            <td style="padding:6px 8px;text-align:center;
                font-size:0.72rem;color:#64748b;">δ {delta_v:+.3f}</td>
            <td style="padding:6px 8px;">{_dir_badge(direc)}</td>
        </tr>
        """

    st.markdown(
        f"""
        <div style="margin-top:8px;">
        <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
            letter-spacing:0.05em;margin-bottom:8px;">
            🏛️ Top {len(top_trades)} Trades Institucionales
            <span style="color:#334155;font-size:0.65rem;">
                (filtros: premium ≥$50K · vol&gt;OI · size&gt;p75 · sweep)
            </span>
        </div>
        <div style="overflow-x:auto;border-radius:8px;
            border:1px solid #1e293b;background:#0d1117;">
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#0a1628;border-bottom:2px solid #1e3a5f;">
                    <th style="padding:8px 10px;text-align:left;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        Symbol
                    </th>
                    <th style="padding:8px 10px;text-align:center;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        Tipo
                    </th>
                    <th style="padding:8px 10px;text-align:left;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        Agresión
                    </th>
                    <th style="padding:8px 10px;text-align:right;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        Premium
                    </th>
                    <th style="padding:8px 10px;text-align:right;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        ΔWeighted
                    </th>
                    <th style="padding:8px 10px;text-align:center;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        Delta
                    </th>
                    <th style="padding:8px 10px;text-align:center;font-size:0.7rem;
                        color:#64748b;font-weight:600;text-transform:uppercase;">
                        Dirección
                    </th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
#   METHODOLOGY EXPANDER
# ============================================================================

def render_oka_methodology() -> None:
    """Muestra el expander educativo con la metodología del OKA Index v2."""
    with st.expander("📐 Metodología OKA Sentiment Index v2", expanded=False):
        st.markdown(
            """
            <div style="font-size:0.83rem;line-height:1.8;color:#cbd5e1;">
            <b style="color:#a78bfa;">Paso 1 — Clasificación de Agresión</b><br>
            <code style="color:#94a3b8;font-size:0.78rem;">
            price ≥ ask → Aggressive Buy &nbsp;|&nbsp;
            price ≤ bid → Aggressive Sell &nbsp;|&nbsp;
            else → Neutral
            </code>
            <br><br>
            <b style="color:#60a5fa;">Paso 2 — Filtros Institucionales (todos obligatorios)</b><br>
            <span style="color:#94a3b8;font-size:0.8rem;">
            ① Premium ≥ $50,000 &nbsp;|&nbsp;
            ② Volumen &gt; Open Interest &nbsp;|&nbsp;
            ③ Tamaño &gt; p75 diario &nbsp;|&nbsp;
            ④ Sweep flag = True
            </span>
            <br><br>
            <b style="color:#34d399;">Paso 3+4 — Premium & Delta-Weighted</b><br>
            <code style="color:#94a3b8;font-size:0.78rem;">
            Premium = price × volume × 100<br>
            DeltaWeighted = Premium × |delta|<br>
            GammaAdjusted = Premium × |delta| × gamma  (Phase 2)
            </code>
            <br><br>
            <b style="color:#fb923c;">Paso 5 — Clasificación Direccional</b><br>
            <code style="color:#94a3b8;font-size:0.78rem;">
            BullishFlow = (Call AggrBuy) + (Put AggrSell)<br>
            BearishFlow = (Put AggrBuy) + (Call AggrSell)
            </code>
            <br><br>
            <b style="color:#fbbf24;">Paso 6 — OKA Index Formula</b><br>
            <code style="color:#94a3b8;font-size:0.78rem;">
            NetFlow = BullishFlow − BearishFlow<br>
            OKA_Index = 50 + (NetFlow / TotalFlow) × 50
            </code>
            <br><br>
            <div style="background:#0d1117;border-left:3px solid #a78bfa;
                padding:8px 12px;border-radius:4px;font-size:0.78rem;">
                <b style="color:#a78bfa;">Phase 2 — Gamma Weighting:</b>
                <span style="color:#94a3b8;"> Activa el toggle arriba para ponderar también
                por gamma, capturando el impacto de convexidad en el flujo.
                Útil en entornos de alta volatilidad (earnings, eventos macro).</span>
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================================
#   RENDER COMPLETO DE LA PESTAÑA OKA
# ============================================================================

def render_oka_page(result: dict) -> None:
    """Componente principal: renderiza la pestaña OKA Sentiment Index v2.

    Composición:
        1. Gauge gigante + interpretación
        2. Tarjetas de flujo (Bullish / Bearish / Net)
        3. Barra horizontal de distribución
        4. Tabla de trades institucionales top 20
        5. Explicación metodológica (expander)
        6. Disclaimer

    Args:
        result: dict devuelto por compute_oka_index().
    """
    description = result.get("interpretation", {}).get("description", "")

    # Texto interpretativo en bloque grande
    interpretation = result.get("interpretation", {})
    text_color     = interpretation.get("text_color", "#94a3b8")
    label          = interpretation.get("label",      "Neutral")
    emoji          = interpretation.get("emoji",      "⚪")

    st.markdown(
        f"""
        <div style="background:#0a1628;border:1px solid #1e3a5f;border-radius:10px;
                    padding:10px 16px;margin-bottom:12px;font-size:0.85rem;">
            <b style="color:{text_color};font-size:1rem;">{emoji} {label}</b>
            <span style="color:#94a3b8;margin-left:12px;">{description}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Gauge
    render_okaindex_gauge(result)

    # Tarjetas de flujo
    render_flow_cards(result)

    # Barra de distribución
    render_flow_bars(result)

    st.markdown("<div style='margin:10px 0;'></div>", unsafe_allow_html=True)

    # Tabla de trades
    render_trade_table(result)

    st.markdown("<div style='margin:12px 0;'></div>", unsafe_allow_html=True)

    # Metodología
    render_oka_methodology()

    # Disclaimer obligatorio
    st.markdown(
        """
        <div style="background:#0a0a0a;border:1px solid #1e2a1e;border-radius:6px;
                    padding:8px 14px;margin-top:12px;font-size:0.72rem;color:#78716c;">
            ⚠️ <b style="color:#fbbf24;">Basado en datos de flujo agresivo institucional.</b>
            Los datos de opciones reflejan actividad pasada y no predicen dirección futura.
            Las clasificaciones de agresión son aproximaciones estadísticas basadas en
            relación precio/spread. <b>No es consejo de inversión.</b>
            Solo para análisis cuantitativo y educación financiera.
        </div>
        """,
        unsafe_allow_html=True,
    )
