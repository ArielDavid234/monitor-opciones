"""
Badges y helpers de alerta para tablas pro — sin dependencias internas.
"""
import streamlit as st


def _badge_html(text, variant="neutral"):
    """Return a small badge <span> in a given variant.

    Variants: bull, bear, neutral, call, put, cluster, top, inst, prima.
    """
    return f'<span class="ok-badge ok-badge-{variant}">{text}</span>'


def _sentiment_badge(tipo, lado):
    """Return badge HTML for ALCISTA / BAJISTA from tipo+lado."""
    if (tipo == "CALL" and lado == "Ask") or (tipo == "PUT" and lado == "Bid"):
        return _badge_html("▲ ALCISTA", "bull")
    elif (tipo == "PUT" and lado == "Ask") or (tipo == "CALL" and lado == "Bid"):
        return _badge_html("▼ BAJISTA", "bear")
    return _badge_html("— NEUTRAL", "neutral")


def _type_badge(tipo):
    """Return badge for CALL / PUT."""
    if tipo == "CALL":
        return _badge_html("CALL", "call")
    elif tipo == "PUT":
        return _badge_html("PUT", "put")
    return str(tipo)


def _priority_badge(prioridad):
    """Return badge for alert priority."""
    if "TOP" in str(prioridad).upper():
        return _badge_html("● TOP PRIMA", "top")
    elif "INSTITUCIONAL" in str(prioridad).upper() or "PRINCIPAL" in str(prioridad).upper():
        return _badge_html("● INSTITUCIONAL", "inst")
    elif "PRIMA" in str(prioridad).upper():
        return _badge_html("● PRIMA ALTA", "prima")
    elif "CLUSTER" in str(prioridad).upper():
        return _badge_html("● CLUSTER", "cluster")
    return str(prioridad)


def _delta_cell(value):
    """Render numeric value with up/down color."""
    try:
        v = float(str(value).replace(",", "").replace("$", "").replace("+", "").replace("%", ""))
        if v > 0:
            return f'<span class="ok-up">+{value}</span>'
        elif v < 0:
            return f'<span class="ok-down">{value}</span>'
    except (ValueError, TypeError):
        pass
    return str(value)


def _sm_flow_badge(score) -> str:
    """Return a colored HTML badge for sm_flow_score (0-100).

    Color scale mirrors smart-money conviction strength:
        ≥ 75 → green  (Smart / Whale tier)
        ≥ 55 → amber  (Mixed tier)
        <  55 → red   (Retail tier)
    """
    try:
        v = float(score)
    except (TypeError, ValueError):
        return f'<span class="ok-badge ok-badge-neutral">{score}</span>'
    if v >= 75:
        alpha = round(v / 100, 2)
        style = f"background:rgba(0,255,136,{alpha});color:#0f172a;border:none;font-weight:700;"
    elif v >= 55:
        alpha = round(v / 100, 2)
        style = f"background:rgba(255,165,0,{alpha});color:#0f172a;border:none;font-weight:700;"
    else:
        style = "background:rgba(255,60,60,0.40);color:#fff;border:none;font-weight:700;"
    return f'<span class="ok-badge" style="{style}">{v:.1f}</span>'


def _inst_flow_badge(score) -> str:
    """Return a colored HTML badge for inst_flow_score (0-100).

    Color scale:
        ≥ 85 → green (Institutional / Whale)
        ≥ 65 → amber (Mixed)
        <  65 → red  (Retail)
    """
    try:
        v = float(score)
    except (TypeError, ValueError):
        return f'<span class="ok-badge ok-badge-neutral">{score}</span>'
    if v >= 85:
        style = "background:rgba(0,255,0,0.60);color:#0f172a;border:none;font-weight:700;"
    elif v >= 65:
        style = "background:rgba(255,165,0,0.60);color:#0f172a;border:none;font-weight:700;"
    else:
        style = "background:rgba(255,60,60,0.50);color:#fff;border:none;font-weight:700;"
    return f'<span class="ok-badge" style="{style}">{v:.1f}</span>'


def institutional_flow_legend():
    """Renderiza la leyenda de Delta institucional como tabla HTML pro-dashboard."""
    st.markdown("### \U0001f3e6 Institutional Flow Legend (Delta)")
    st.markdown("""
    <table style="width:100%; border-collapse:collapse; font-size:0.82rem; margin-bottom:12px;">
      <tr style="background:#1e3a8a; color:white;">
        <th style="padding:6px 10px; text-align:left;">Delta</th>
        <th style="padding:6px 10px; text-align:left;">Significado</th>
        <th style="padding:6px 10px; text-align:left;">Importancia</th>
      </tr>
      <tr style="background:#1e293b; color:#94a3b8;">
        <td style="padding:5px 10px;">0.10 \u2013 0.25</td>
        <td style="padding:5px 10px;">Apuestas especulativas (baratas, OTM)</td>
        <td style="padding:5px 10px;">Bajo \u2013 mucho retail</td>
      </tr>
      <tr style="background:#0f172a; color:#e2e8f0;">
        <td style="padding:5px 10px;">0.30 \u2013 0.50</td>
        <td style="padding:5px 10px;">Posici\u00f3n direccional real</td>
        <td style="padding:5px 10px;">\u2b50 Importante</td>
      </tr>
      <tr style="background:#166534; color:white;">
        <td style="padding:5px 10px; font-weight:700;">0.60 \u2013 0.80</td>
        <td style="padding:5px 10px; font-weight:700;">Posici\u00f3n agresiva / institucional</td>
        <td style="padding:5px 10px; font-weight:700;">\U0001f525 Muy importante</td>
      </tr>
      <tr style="background:#1e293b; color:#fbbf24;">
        <td style="padding:5px 10px;">0.80 \u2013 1.00</td>
        <td style="padding:5px 10px;">Sustituto de acciones / cobertura</td>
        <td style="padding:5px 10px;">\U0001f3e6 Institucional / hedging</td>
      </tr>
    </table>
    <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">
      \U0001f4a1 Delta 0.40-0.50 + prima alta = alta probabilidad institucional &nbsp;|&nbsp;
      Delta &lt;0.20 = ignorar salvo prima muy grande + repetici\u00f3n
    </div>
    """, unsafe_allow_html=True)
