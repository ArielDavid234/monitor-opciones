"""
Componentes reutilizables de UI para el Monitor de Opciones.
Funciones de formateo, renderizado de tarjetas y helpers de Streamlit.
"""
import time
import logging
import streamlit as st
import pandas as pd
from random import uniform

from config.constants import ANALYSIS_SLEEP_RANGE
from core.projections import analizar_proyeccion_empresa

logger = logging.getLogger(__name__)


def format_market_cap(value):
    """Formatea un valor numérico como capitalización de mercado legible."""
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    elif value >= 1e9:
        return f"${value/1e9:.1f}B"
    elif value >= 1e6:
        return f"${value/1e6:.0f}M"
    return f"${value:,.0f}"


def format_cashflow(value):
    """Formatea un valor de flujo de caja en formato legible."""
    if value >= 1e9:
        return f"${value/1e9:.1f}B"
    elif value >= 1e6:
        return f"${value/1e6:.0f}M"
    elif value > 0:
        return f"${value:,.0f}"
    return "N/A"


# ============================================================================
#                    METRIC CARDS — Pro Dashboard Style
# ============================================================================

def _generate_sparkline_svg(data, color="#00ff88"):
    """Generate an inline SVG sparkline from data points."""
    if not data or len(data) < 2:
        return ""
    width, height = 120, 32
    min_val = min(data)
    max_val = max(data)
    val_range = max_val - min_val if max_val != min_val else 1
    points = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * width
        y = height - ((val - min_val) / val_range) * (height - 4) - 2
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    fill_points = f"0,{height} " + polyline + f" {width},{height}"
    uid = abs(hash(tuple(data))) % 100000
    return (
        f'<div class="ok-metric-sparkline">'
        f'<svg width="100%" height="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<defs><linearGradient id="sg{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.3"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{fill_points}" fill="url(#sg{uid})"/>'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg></div>'
    )


def render_metric_card(title, value, delta=None, delta_suffix="%",
                       sparkline_data=None, color_override=None):
    """Render a professional metric card with optional delta indicator and sparkline.

    Args:
        title: Small gray label text.
        value: Large main value string.
        delta: Numeric change (positive → green ▲, negative → red ▼) or custom str.
        delta_suffix: Suffix after numeric delta (default "%").
        sparkline_data: List of numbers for the mini line chart.
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
    return f'<div class="ok-metric-row ok-cols-{n}">{"" .join(cards_html)}</div>'


def get_score_style(clasificacion):
    """Retorna (card_class, score_class, score_emoji) según la clasificación."""
    styles = {
        "ALTA": ("empresa-card empresa-card-bull", "score-alta", "🟢"),
        "MEDIA": ("empresa-card empresa-card-neutral", "score-media", "🟡"),
    }
    return styles.get(clasificacion, ("empresa-card empresa-card-bear", "score-baja", "🔴"))


def render_target_html(result):
    """Genera el HTML para la sección de target de analistas."""
    if result["target_mean"] <= 0:
        return ""
    upside_color = "#10b981" if result["upside_pct"] > 0 else "#ef4444"
    upside_sign = "+" if result["upside_pct"] > 0 else ""
    return f"""
        <div class="empresa-metric">
            <div class="empresa-metric-label">Target Analistas</div>
            <div class="empresa-metric-value">${result['target_mean']:,.0f}</div>
        </div>
        <div class="empresa-metric">
            <div class="empresa-metric-label">Upside</div>
            <div class="empresa-metric-value" style="color: {upside_color};">{upside_sign}{result['upside_pct']:.1f}%</div>
        </div>"""


def render_empresa_card(r, info_emp, watchlist_dict, es_emergente=False):
    """Renderiza una tarjeta HTML completa para una empresa analizada."""
    card_class, score_class, score_emoji = get_score_style(r["clasificacion"])
    if es_emergente:
        card_class = "empresa-card empresa-card-emergente"

    if info_emp:
        desc = info_emp["descripcion"]
        sector_label = info_emp["sector"]
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
                <span class="empresa-score {score_class}">{score_emoji} {r['score']}/100</span>
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
            "Score": f"{r['score']}/100",
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
        row["Recomendación"] = r["recommendation"]
        tabla_data.append(row)
    return pd.DataFrame(tabla_data)


def analizar_watchlist(watchlist_dict, session_key, label_tipo):
    """Analiza todas las empresas de un watchlist con barra de progreso."""
    resultados = []
    errores = []
    all_tickers = list(watchlist_dict.keys())
    progress_bar = st.progress(0, text=f"Iniciando análisis de {label_tipo}...")
    for idx, sym in enumerate(all_tickers):
        progress_bar.progress(
            (idx + 1) / len(all_tickers),
            text=f"Analizando {sym} ({idx+1}/{len(all_tickers)})..."
        )
        info_emp = watchlist_dict.get(sym)
        resultado, error = analizar_proyeccion_empresa(sym, info_emp)
        if resultado:
            resultados.append(resultado)
        else:
            errores.append(f"{sym}: {error}")
        if idx < len(all_tickers) - 1:
            time.sleep(uniform(*ANALYSIS_SLEEP_RANGE))
    progress_bar.empty()
    if errores:
        for err in errores:
            st.warning(f"⚠️ {err}")
    if resultados:
        resultados.sort(key=lambda x: x["score"], reverse=True)
        st.session_state[session_key] = resultados
        st.rerun()


def render_watchlist_preview(watchlist_dict, incluir_por_que=False):
    """Muestra una tabla preview del watchlist."""
    preview_data = []
    for sym, info in watchlist_dict.items():
        preview_data.append({
            "Ticker": sym,
            "Empresa": info["nombre"],
            "Sector": info["sector"],
            "Descripción": info["descripcion"],
        })
    st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True, height=670)


def render_empresa_descriptions(watchlist_dict, color_principal, color_borde, es_emergente=False):
    """Renderiza las descripciones detalladas de cada empresa del watchlist usando componentes nativos."""
    for sym, info in watchlist_dict.items():
        with st.container(border=True):
            col_t, col_s = st.columns([3, 1])
            with col_t:
                st.markdown(f"**{sym}** — {info['nombre']}")
            with col_s:
                st.caption(info['sector'])

            st.caption(info['descripcion'])

            if es_emergente and "por_que_grande" in info:
                st.info(f"🌟 **¿Por qué puede ser gigante?**\n\n{info['por_que_grande']}")
