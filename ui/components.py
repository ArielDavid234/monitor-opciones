"""
Componentes reutilizables de UI para el Monitor de Opciones.
Funciones de formateo, renderizado de tarjetas y helpers de Streamlit.
"""
import time
import logging
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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


def render_plotly_sparkline(data, color="#00ff88", height=60):
    """Render a tiny Plotly area sparkline chart for embedding in metric sections.

    Call this via st.plotly_chart() separately after rendering the card HTML.
    Returns a Plotly figure object.
    """
    if not data or len(data) < 2:
        return None
    # Convert hex color to rgba with 0.15 opacity for fill
    if color.startswith("#") and len(color) == 7:
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fill_color = f"rgba({r},{g},{b},0.15)"
    elif color.startswith("rgb("):
        fill_color = color.replace("rgb(", "rgba(").replace(")", ",0.15)")
    else:
        fill_color = "rgba(0,255,136,0.15)"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=list(data),
        mode="lines",
        fill="tozeroy",
        line=dict(color=color, width=2, shape="spline"),
        fillcolor=fill_color,
        hovertemplate="%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


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


# ============================================================================
#                   PRO HTML TABLE — Dark Dashboard Style
# ============================================================================

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


_SPECIAL_COLS = {
    "Sentimiento": "sentiment",
    "Tipo": "type",
    "Tipo_Opcion": "type",
    "Prioridad": "priority",
}

_NUMERIC_COLS = {
    "Volumen", "OI", "OI_Chg", "Vol Total", "OI Total",
    "Prima Total", "Prima Prom.", "Prima_Total", "Prima_Volumen",
    "Strike", "Ultimo", "Último", "Ask", "Bid", "IV", "Delta",
    "Spread_%", "Liquidez", "Contratos", "Volumen_Total",
}


def render_pro_table(df, title=None, badge_count=None, max_height=520,
                     footer_text=None, special_format=None):
    """Render a professional dark HTML table from a DataFrame.

    Args:
        df: pandas DataFrame to render.
        title: optional header text.
        badge_count: optional count to show in a green badge next to the title.
        max_height: max pixel height before scroll (0 = no limit).
        footer_text: optional text for the footer.
        special_format: dict mapping column names to formatter callables.
    Returns:
        An HTML string ready for st.markdown(..., unsafe_allow_html=True).
    """
    if df is None or df.empty:
        return ""

    special_format = special_format or {}

    # Header
    header_html = ""
    if title:
        badge_part = f' <span class="ok-table-badge">{badge_count}</span>' if badge_count is not None else ""
        header_html = (
            f'<div class="ok-table-header">'
            f'<div class="ok-table-title">{title}{badge_part}</div>'
            f'</div>'
        )

    # Build <thead>
    ths = "".join(f'<th>{col}</th>' for col in df.columns)
    thead = f'<thead><tr>{ths}</tr></thead>'

    # Build <tbody>
    rows = []
    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = row[col]
            if val is None or (isinstance(val, float) and pd.isna(val)):
                val = "-"

            # Decide class
            td_cls = ""
            if col in ("Ticker", "Contrato"):
                td_cls = ' class="td-ticker"'
            elif col in _NUMERIC_COLS or col in ("OI Chg",):
                td_cls = ' class="td-num"'

            # Format value
            if col in special_format:
                val = special_format[col](val)
            elif col in _SPECIAL_COLS:
                fmt_kind = _SPECIAL_COLS[col]
                if fmt_kind == "sentiment":
                    val = str(val)  # already formatted before passing
                elif fmt_kind == "type":
                    val = _type_badge(str(val))
                elif fmt_kind == "priority":
                    val = _priority_badge(str(val))
            elif col == "OI_Chg" or col == "OI Chg":
                val = _delta_cell(val)

            cells.append(f'<td{td_cls}>{val}</td>')
        rows.append(f'<tr>{"".join(cells)}</tr>')
    tbody = f'<tbody>{"".join(rows)}</tbody>'

    # Scroll container
    style_attr = f' style="max-height:{max_height}px"' if max_height else ""

    # Footer
    footer_html = ""
    if footer_text:
        footer_html = f'<div class="ok-table-footer">{footer_text}</div>'

    return (
        f'<div class="ok-table-wrap">'
        f'{header_html}'
        f'<div class="ok-table-scroll"{style_attr}>'
        f'<table class="ok-tbl table-zebra">{thead}{tbody}</table>'
        f'</div>'
        f'{footer_html}'
        f'</div>'
    )
