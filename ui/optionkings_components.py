# -*- coding: utf-8 -*-
"""
OptionKings Analytic — Componentes de Visualización.

Tarjeta profesional por spread con:
  • Gauge Plotly de Score 0-100 (rojo / amarillo / verde)
  • Métricas completas en columnas (crédito, EV, vol edge, kelly, etc.)
  • Badge de liquidez codificado por color
  • Desglose del score con barra de progreso por componente

Uso:
    from ui.optionkings_components import render_spread_card

    render_spread_card(row, metrics, score_data, idx=0)
"""
from __future__ import annotations

import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False


# ============================================================================
#   GAUGE PLOTLY — Score Profesional 0-100
# ============================================================================

def _score_gauge(score: float, grade_color: str) -> "go.Figure":  # type: ignore[name-defined]
    """Genera un gauge Plotly semicircular para el score 0-100.

    Colores:
        rojo    <50  (sin edge)
        amarillo 50-75 (edge débil)
        verde   >75  (edge fuerte)

    Args:
        score:       valor numérico 0-100
        grade_color: hex color del grado (ej '#22c55e')
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={
            "suffix": "/100",
            "font": {"size": 40, "color": grade_color, "family": "monospace"},
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#475569",
                "tickfont": {"color": "#64748b", "size": 10},
                "dtick": 25,
            },
            "bar": {"color": grade_color, "thickness": 0.28},
            "bgcolor": "#0d1117",
            "borderwidth": 1,
            "bordercolor": "#1e293b",
            "steps": [
                {"range": [0,  50], "color": "#1a0a0a"},     # zona roja
                {"range": [50, 75], "color": "#1a1400"},     # zona amarilla
                {"range": [75, 100], "color": "#081a0e"},    # zona verde
            ],
            "threshold": {
                "line": {"color": grade_color, "width": 3},
                "thickness": 0.85,
                "value": score,
            },
        },
    ))
    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font={"family": "Inter, sans-serif"},
        margin=dict(l=15, r=15, t=20, b=10),
        height=200,
    )
    return fig


# ============================================================================
#   BADGE DE LIQUIDEZ
# ============================================================================

def _liquidez_badge_html(liquidez_pct: float) -> str:
    """Genera HTML del badge de liquidez codificado por color.

    < 5%  → verde   (Excelente — spread tight)
    5-10% → amarillo  (Media — aceptable)
    >10%  → rojo    (Ancha — cuidado)
    """
    if liquidez_pct < 5:
        bg, color, label = "#166534", "#4ade80", f"💧 Liq Excelente ({liquidez_pct:.1f}%)"
    elif liquidez_pct < 10:
        bg, color, label = "#713f12", "#fbbf24", f"💧 Liq Media ({liquidez_pct:.1f}%)"
    else:
        bg, color, label = "#3f1219", "#f87171", f"⚠️ Liq Ancha ({liquidez_pct:.1f}%)"

    return (
        f'<span style="background:{bg};color:{color};padding:3px 10px;'
        f'border-radius:12px;font-size:0.75rem;font-weight:700;">{label}</span>'
    )


# ============================================================================
#   BARRA DE PROGRESO PARA COMPONENTES DEL SCORE
# ============================================================================

def _score_bar_html(label: str, value: float, weight_pct: int, color: str) -> str:
    """Barra horizontal de progreso para un componente del score."""
    bar_width = max(0, min(100, value))
    contribution = round(value * weight_pct / 100, 1)
    return (
        f'<div style="margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:0.75rem;color:#94a3b8;margin-bottom:2px;">'
        f'<span>{label} <span style="color:#475569;">({weight_pct}%)</span></span>'
        f'<span style="color:{color};">{value:.0f}/100 → <b>{contribution:.1f}pts</b></span>'
        f'</div>'
        f'<div style="background:#1e293b;border-radius:4px;height:8px;">'
        f'<div style="background:{color};width:{bar_width}%;height:8px;'
        f'border-radius:4px;transition:width 0.3s;"></div>'
        f'</div>'
        f'</div>'
    )


# ============================================================================
#   TARJETA PRINCIPAL — render_spread_card
# ============================================================================

def render_spread_card(
    row: dict,
    metrics: dict,
    score_data: dict,
    idx: int = 0,
) -> None:
    """Renderiza una tarjeta expandible completa para un credit spread.

    Contiene:
        • Header con ticker, tipo, grade badge y liquidez badge
        • Gauge Plotly del score profesional (izquierda)
        • Columnas de métricas (derecha): crédito, maxLoss, breakeven, POP,
          EV, vol edge, kelly, risk 3 losses, prob touch
        • Desglose del score por componente con barras de progreso

    Args:
        row:        fila dict del DataFrame de spreads (campos del escáner).
        metrics:    dict de calculate_all_metrics(row).
        score_data: dict de calculate_professional_score(metrics).
        idx:        índice para keys únicos en Streamlit.
    """
    ticker     = row.get("Ticker", "?")
    tipo       = row.get("Tipo", "?")
    dte        = int(row.get("DTE", 0))
    sv         = row.get("Strike Vendido", 0)
    sc         = row.get("Strike Comprado", 0)
    exp        = row.get("Expiración", "")
    spot       = float(row.get("Spot", 0))

    score      = score_data.get("score", 0)
    grade      = score_data.get("grade", "D")
    grade_lbl  = score_data.get("grade_label", "")
    grade_col  = score_data.get("grade_color", "#ef4444")

    tipo_icon  = "🟢" if "Bull Put" in tipo else "🔴"
    opt_letter = "P" if "Bull Put" in tipo else "C"
    liq_html   = _liquidez_badge_html(metrics.get("liquidez_pct", 999))
    ev_icon    = "✅" if metrics.get("ev_is_positive") else "❌"

    # ── Título del expander ───────────────────────────────────────────────
    expander_title = (
        f"{tipo_icon} {ticker}  {sv:.0f}/{sc:.0f}{opt_letter}  "
        f"DTE {dte}  |  Score {score:.0f}/100 [{grade}]  ·  "
        f"EV {ev_icon} ${metrics.get('ev_dollars', 0):+.2f}  ·  "
        f"POP {metrics.get('pop_pct', 0):.0f}%"
    )

    with st.expander(expander_title, expanded=(idx == 0)):

        # ── Sub-header ────────────────────────────────────────────────────
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;'
            f'margin-bottom:1rem;">'
            f'<span style="background:#1e293b;color:{grade_col};padding:4px 12px;'
            f'border-radius:20px;font-weight:700;font-size:0.8rem;">'
            f'Grado {grade} — {grade_lbl}</span>'
            f'{liq_html}'
            f'<span style="color:#64748b;font-size:0.78rem;">'
            f'Spot ${spot:.2f} · Exp {exp} · {tipo}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Columna gauge + columnas de métricas ──────────────────────────
        col_gauge, col_m1, col_m2, col_m3 = st.columns([1.4, 1, 1, 1])

        # ── Gauge ─────────────────────────────────────────────────────────
        with col_gauge:
            if _PLOTLY_OK:
                st.plotly_chart(
                    _score_gauge(score, grade_col),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
            else:
                st.metric("Score Profesional", f"{score:.0f}/100")
            st.markdown(
                f'<p style="text-align:center;color:{grade_col};'
                f'font-size:0.78rem;margin-top:-12px;">'
                f'Score Profesional OptionKings</p>',
                unsafe_allow_html=True,
            )

        # ── Columna 1: Crédito, Max Loss, Breakeven, POP ─────────────────
        with col_m1:
            st.metric(
                label="💵 Crédito recibido",
                value=f"${metrics['credit_dollars']:.2f}",
                help="Prima neta cobrada por contrato (× 100 acciones).",
            )
            st.metric(
                label="🛑 Max Loss",
                value=f"${metrics['max_loss_dollars']:.2f}",
                help="Pérdida máxima = (Ancho − Crédito) × 100. Capital en riesgo por contrato.",
            )
            st.metric(
                label="⚖️ Breakeven",
                value=f"${metrics['breakeven']:.2f}",
                help=(
                    "Bull Put: Strike Vendido − Crédito. "
                    "Bear Call: Strike Vendido + Crédito."
                ),
            )
            st.metric(
                label="🎯 POP",
                value=f"{metrics['pop_pct']:.1f}%",
                help="Probabilidad de Ganancia ≈ 1 − |Δ|. % de veces que expira sin tocar el strike.",
            )

        # ── Columna 2: Prob Touch, EV, EV%, Vol Edge ─────────────────────
        with col_m2:
            st.metric(
                label="🖐 Prob de Touch",
                value=f"{metrics['prob_touch_pct']:.1f}%",
                help="≈ 2 × |Delta|. Probabilidad de que el precio TOQUE el strike (no solo expire ATM).",
            )
            ev_d = metrics["ev_dollars"]
            ev_delta_str = f"{metrics['ev_percent']:+.1f}% del capital"
            st.metric(
                label="🧮 Expected Value",
                value=f"${ev_d:+.2f}",
                delta=ev_delta_str,
                delta_color="normal" if ev_d >= 0 else "inverse",
                help=(
                    f"EV = (POP × Crédito) − ((1−POP) × Pérdida)\n"
                    f"= (${metrics['expected_profit']:.2f}) − (${metrics['expected_loss_amt']:.2f})\n"
                    f"Positivo = edge matemático real a largo plazo."
                ),
            )
            ve = metrics["vol_edge"]
            ve_color = "normal" if ve > 0 else "inverse"
            st.metric(
                label="📐 Volatility Edge",
                value=f"{ve:+.1f}pp",
                delta=f"IV {metrics['iv_pct']:.1f}% vs HV {metrics['hv_20d']:.1f}%",
                delta_color=ve_color,
                help=(
                    "Volatility Edge = IV actual − HV 20D.\n"
                    "> 0 → prima INFLADA respecto a volatilidad histórica → favorable para el vendedor.\n"
                    "< 0 → prima BARATA → riesgo de vender crédito insuficiente."
                ),
            )
            st.metric(
                label="📊 IV Percentile",
                value=f"{metrics['iv_pctil']:.0f}%",
                help="% de días del último año con IV < actual. >50% = IV cara = ideal para vender.",
            )

        # ── Columna 3: Kelly, Risk 3 Losses, Retorno, Liq % ─────────────
        with col_m3:
            hk = metrics["half_kelly"]
            st.metric(
                label="📐 Half Kelly",
                value=f"{hk*100:.1f}%",
                help=(
                    "Fracción óptima del capital a arriesgar (Half Kelly = Kelly/2).\n"
                    "Kelly = EV / MaxLoss. Half Kelly reduce el riesgo de ruina."
                ),
            )
            r3 = metrics["risk_3_losses"]
            st.metric(
                label="⚠️ Risk 3 Pérdidas",
                value=f"${r3:.2f}",
                help=(
                    "Drawdown estimado si ocurren 3 pérdidas consecutivas.\n"
                    f"= P(loss)³ × MaxLoss = ({1 - metrics['pop_pct']/100:.2f})³ × ${metrics['max_loss_dollars']:.2f}"
                ),
            )
            st.metric(
                label="📈 Retorno / Riesgo",
                value=f"{metrics['retorno_pct']:.1f}%",
                help="Crédito / MaxLoss × 100. Objetivo: ≥ 25% para buena relación.",
            )
            liq = metrics["liquidez_pct"]
            liq_label = "✅ Excelente" if liq < 5 else ("⚠️ Media" if liq < 10 else "❌ Ancha")
            st.metric(
                label="💧 Liquidez Spread",
                value=f"{liq:.1f}%",
                delta=liq_label,
                delta_color="normal" if liq < 5 else ("off" if liq < 10 else "inverse"),
                help="(Bid−Ask del short) / Crédito. <5% = excelente, >10% = cuidado.",
            )

        # ── Desglose del score ────────────────────────────────────────────
        st.markdown(
            '<div style="background:#0d1117;border:1px solid #1e293b;'
            'border-radius:10px;padding:14px 18px;margin-top:10px;">'
            '<div style="color:#94a3b8;font-size:0.8rem;font-weight:600;'
            'margin-bottom:10px;">🔍 DESGLOSE DEL SCORE</div>',
            unsafe_allow_html=True,
        )

        # Barras de cada componente
        components = [
            ("EV Expected Value",    score_data.get("ev_c", 0),       30, "#22d3ee"),
            ("Volatility Edge",      score_data.get("vol_edge_c", 0), 20, "#a78bfa"),
            ("Risk/Reward Balance",  score_data.get("rr_c", 0),       15, "#fb923c"),
            ("Distancia Strike Ópt", score_data.get("dist_c", 0),     15, "#f472b6"),
            ("DTE Ideal (30-45d)",   score_data.get("dte_c", 0),      10, "#34d399"),
            ("Liquidez Bid-Ask",     score_data.get("liq_c", 0),      10, "#60a5fa"),
        ]
        bars_html = ""
        for lbl, val, wt, clr in components:
            bars_html += _score_bar_html(lbl, val, wt, clr)

        st.markdown(bars_html + '</div>', unsafe_allow_html=True)
