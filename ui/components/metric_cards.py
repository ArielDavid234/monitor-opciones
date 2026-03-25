"""
Tarjetas de métricas y tablas comparativas de empresas.
"""
import pandas as pd
import streamlit as st

from ui.components.common import format_market_cap, format_cashflow, _generate_sparkline_svg
from ui.components.score_display import get_score_style, render_target_html


def render_metric_card(title, value, delta=None, delta_suffix="%",
                       sparkline_data=None, color_override=None):
    """Render a professional metric card with optional delta indicator and sparkline.

    Args:
        title: Small gray label text.
        value: Large main value string.
        delta: Numeric change (positive → green ▲, negative → red ▼) or custom str.
        delta_suffix: Suffix after numeric delta (default "%").
        sparkline_data: List of numbers for the mini line chart (Plotly or SVG fallback).
        color_override: Force a specific color for delta & sparkline.
    """
    delta_html = ""
    if delta is not None:
        if isinstance(delta, str):
            delta_html = f'<div class="ok-metric-delta" style="color:#64748b">{delta}</div>'
        else:
            is_positive = delta >= 0
            arrow = "▲" if is_positive else "▼"
            delta_class = "ok-delta-up" if is_positive else "ok-delta-down"
            style_attr = ""
            if color_override:
                delta_class = ""
                style_attr = f' style="color:{color_override}"'
            sign = "+" if is_positive else ""
            delta_html = (
                f'<div class="ok-metric-delta {delta_class}"{style_attr}>'
                f'<span>{arrow}</span> {sign}{delta:.1f}{delta_suffix}</div>'
            )
    sparkline_html = ""
    if sparkline_data and len(sparkline_data) > 1:
        spark_color = color_override or "#00ff88"
        sparkline_html = _generate_sparkline_svg(sparkline_data, spark_color)
    return (
        f'<div class="ok-metric-card">'
        f'<div class="ok-metric-title">{title}</div>'
        f'<div class="ok-metric-value">{value}</div>'
        f'{delta_html}'
        f'{sparkline_html}'
        f'</div>'
    )


def render_metric_row(cards_html):
    """Wrap a list of card HTML strings in a CSS-grid row."""
    n = len(cards_html)
    return f'<div class="ok-metric-row ok-cols-{n}">{"".join(cards_html)}</div>'


def render_empresa_card(r, info_emp, watchlist_dict, es_emergente=False):
    """Renderiza una tarjeta HTML completa para una empresa analizada."""
    card_class, score_class, score_emoji = get_score_style(r["clasificacion"])
    if es_emergente:
        card_class = "empresa-card empresa-card-emergente"

    if info_emp:
        desc = info_emp.get("descripcion") or f"Sector: {r['sector']} | Industria: {r['industria']}"
        sector_label = info_emp.get("sector") or r["sector"]
    else:
        desc = f"Sector: {r['sector']} | Industria: {r['industria']}"
        sector_label = r["sector"]

    mc_str = format_market_cap(r["market_cap"])
    fcf_str = format_cashflow(r["free_cashflow"])
    razones_html = " · ".join(r["razones"]) if r["razones"] else "Sin datos suficientes"
    target_html = render_target_html(r)

    por_que_html = ""
    if es_emergente and info_emp:
        por_que = info_emp.get("por_que_grande", "")
        if por_que:
            por_que_html = f"""
                <div class="por-que-grande">
                    🌟 <b>¿Por qué puede ser gigante?</b><br>
                    {por_que}
                </div>"""

    emergente_badge = '<span class="emergente-badge">EMERGENTE</span>' if es_emergente else ""
    growth_color = '#10b981' if r['revenue_growth'] > 0 else '#ef4444'
    growth_sign = '+' if r['revenue_growth'] > 0 else ''

    return f"""
    <div class="{card_class}">
        <div class="empresa-header">
            <div>
                <span class="empresa-ticker">{r['symbol']}</span>
                {emergente_badge}
                <span style="color: #64748b; font-size: 0.75rem; margin-left: 8px;">{sector_label}</span>
                <div class="empresa-nombre">{r['nombre']} · ${r['precio']:,.2f}</div>
            </div>
            <div>
                <span class="empresa-score {score_class}">{score_emoji} {r.get('score_combinado', r['score'])}/100</span>
            </div>
        </div>
        <div class="empresa-desc">{desc}</div>
        {por_que_html}
        <div class="empresa-metrics">
            <div class="empresa-metric">
                <div class="empresa-metric-label">Market Cap</div>
                <div class="empresa-metric-value">{mc_str}</div>
            </div>
            <div class="empresa-metric">
                <div class="empresa-metric-label">Crec. Ingresos</div>
                <div class="empresa-metric-value" style="color: {growth_color};">
                    {growth_sign}{r['revenue_growth']*100:.1f}%
                </div>
            </div>
            <div class="empresa-metric">
                <div class="empresa-metric-label">Margen Operativo</div>
                <div class="empresa-metric-value">{r['operating_margins']*100:.1f}%</div>
            </div>
            <div class="empresa-metric">
                <div class="empresa-metric-label">P/E Forward</div>
                <div class="empresa-metric-value">{r['forward_pe']:.1f}x</div>
            </div>
            <div class="empresa-metric">
                <div class="empresa-metric-label">PEG Ratio</div>
                <div class="empresa-metric-value">{r['peg_ratio']:.2f}</div>
            </div>
            <div class="empresa-metric">
                <div class="empresa-metric-label">FCF</div>
                <div class="empresa-metric-value">{fcf_str}</div>
            </div>
            {target_html}
            <div class="empresa-metric">
                <div class="empresa-metric-label">Beta</div>
                <div class="empresa-metric-value">{r['beta']:.2f}</div>
            </div>
            <div class="empresa-metric">
                <div class="empresa-metric-label">Analistas</div>
                <div class="empresa-metric-value">{r['num_analysts']}</div>
            </div>
        </div>
        <div style="margin-top: 12px; font-size: 0.72rem; color: #94a3b8;">
            📌 {razones_html}
        </div>
    </div>
    """


def render_tabla_comparativa(resultados, es_emergente=False):
    """Genera un DataFrame para la tabla comparativa de proyecciones."""
    tabla_data = []
    for r in resultados:
        row = {
            "Ticker": r["symbol"],
            "Nombre": r["nombre"],
            "Precio": f"${r['precio']:,.2f}",
            "Score": f"{r.get('score_combinado', r['score'])}/100",
            "Proyección": r["clasificacion"],
            "Crec. Ingresos": f"{r['revenue_growth']*100:.1f}%",
            "Margen Op.": f"{r['operating_margins']*100:.1f}%",
            "P/E Fwd": f"{r['forward_pe']:.1f}x",
        }
        if es_emergente:
            row["Upside"] = f"{'+' if r['upside_pct']>0 else ''}{r['upside_pct']:.1f}%"
        else:
            row["PEG"] = f"{r['peg_ratio']:.2f}"
            row["Upside Analistas"] = f"{'+' if r['upside_pct']>0 else ''}{r['upside_pct']:.1f}%"
        # Columna "Recomendación" eliminada según solicitud del usuario
        tabla_data.append(row)
    return pd.DataFrame(tabla_data)
