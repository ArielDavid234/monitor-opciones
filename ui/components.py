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
        # Columna "Recomendación" eliminada según solicitud del usuario
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
    """Renderiza las descripciones detalladas de cada empresa del watchlist con expanders colapsables individuales."""
    for sym, info in watchlist_dict.items():
        # Crear un expander colapsado para cada empresa
        with st.expander(f"**{sym}** — {info['nombre']} · {info['sector']}", expanded=False):
            st.caption(f"**Sector:** {info['sector']}")
            st.markdown(f"📝 {info['descripcion']}")
            
            if es_emergente and "por_que_grande" in info:
                st.info(f"🌟 **¿Por qué puede ser gigante?**\n\n{info['por_que_grande']}")


def _rsi_color(rsi):
    """Color para RSI."""
    if rsi >= 70: return "#ef4444"   # rojo — sobrecompra
    if rsi <= 30: return "#22c55e"   # verde — sobreventa
    return "#f59e0b"                 # amarillo — neutral


def _rsi_label(rsi):
    if rsi >= 70: return "SOBRECOMPRA"
    if rsi <= 30: return "SOBREVENTA"
    return "NEUTRAL"


def _tendencia_emoji(t):
    if t == "ALCISTA": return "🟢"
    if t == "BAJISTA": return "🔴"
    return "🟡"


def _veredicto_color(v):
    if "COMPRA" in v: return "#22c55e"
    if "CONSIDERAR" in v: return "#f59e0b"
    if "MANTENER" in v: return "#3b82f6"
    return "#ef4444"


def _format_large_number(val):
    """Formatea números grandes a B/M/K."""
    if not val or val == 0: return "N/D"
    if abs(val) >= 1e12: return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9: return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6: return f"${val/1e6:.0f}M"
    if abs(val) >= 1e3: return f"${val/1e3:.0f}K"
    return f"${val:,.0f}"


def _score_bar_html(score, max_score, label, color):
    """Genera HTML de una barra de score visual."""
    pct = min(score / max_score * 100, 100) if max_score > 0 else 0
    return f"""
    <div style="margin: 4px 0;">
        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94a3b8;">
            <span>{label}</span><span style="color:{color}; font-weight:700;">{score}/{max_score}</span>
        </div>
        <div style="background:#1e293b; border-radius:4px; height:8px; overflow:hidden;">
            <div style="width:{pct:.0f}%; height:100%; background:{color}; border-radius:4px;"></div>
        </div>
    </div>"""


def render_analisis_completo(resultados, watchlist_dict, es_emergente=False):
    """
    Renderiza análisis completo combinando Fundamental + Técnico + Sentimiento
    para cada empresa analizada. Usa tabs dentro de expanders colapsables.
    """
    if not resultados:
        st.info("⚠️ Presiona **Analizar** primero para obtener el análisis completo con datos en vivo.")
        return

    for r in resultados:
        sym = r["symbol"]
        info_wl = watchlist_dict.get(sym, {})
        tecnico = r.get("tecnico", {})
        tendencia = tecnico.get("tendencia", "N/D") if tecnico else "N/D"
        tend_emoji = _tendencia_emoji(tendencia)

        # — Cabecera del expander con score y tendencia —
        score_fund = r.get("score", 0)
        score_tec = r.get("score_tecnico", 0)
        score_comb = r.get("score_combinado", score_fund)
        veredicto = r.get("veredicto", r.get("clasificacion", "N/D"))

        header = f"{tend_emoji} **{sym}** — {r['nombre']} · Score: {score_comb}/100 · {veredicto}"
        with st.expander(header, expanded=False):

            # ── Scores resumen visual ──
            v_color = _veredicto_color(veredicto)
            st.markdown(f"""
            <div style="display:flex; gap:8px; align-items:center; margin-bottom:12px; flex-wrap:wrap;">
                <span style="background:{v_color}22; color:{v_color}; padding:4px 12px; border-radius:6px; font-weight:700; font-size:0.85rem; border:1px solid {v_color}44;">
                    ⚖️ {veredicto}
                </span>
                <span style="background:#1e293b; color:#e2e8f0; padding:4px 10px; border-radius:6px; font-size:0.8rem;">
                    Fund: <b>{score_fund}/100</b>
                </span>
                <span style="background:#1e293b; color:#e2e8f0; padding:4px 10px; border-radius:6px; font-size:0.8rem;">
                    Téc: <b>{score_tec}/100</b>
                </span>
                <span style="background:#1e293b; color:#e2e8f0; padding:4px 10px; border-radius:6px; font-size:0.8rem;">
                    Combinado: <b style="color:#00ff88;">{score_comb}/100</b>
                </span>
            </div>
            """, unsafe_allow_html=True)

            # ── TABS: Fundamental | Técnico | Sentimiento | Veredicto ──
            tab_fund, tab_tec, tab_sent, tab_vered = st.tabs([
                "📊 Fundamental", "📈 Técnico", "🎯 Sentimiento", "⚖️ Veredicto"
            ])

            # ═══════════ TAB FUNDAMENTAL ═══════════
            with tab_fund:
                st.markdown("##### 📊 Análisis Fundamental — Salud y Valor")
                if info_wl:
                    st.caption(f"_{info_wl.get('descripcion', '')}_")

                # Fila 1: Ingresos y Rentabilidad
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Ingresos Totales", _format_large_number(r.get("revenue", 0)))
                c2.metric("Crec. Ingresos", f"{r['revenue_growth']*100:.1f}%",
                          delta=f"{r['revenue_growth']*100:.1f}%")
                c3.metric("Margen Bruto", f"{r['gross_margins']*100:.1f}%")
                c4.metric("Margen Operativo", f"{r['operating_margins']*100:.1f}%")

                # Fila 2: Valuación
                c5, c6, c7, c8 = st.columns(4)
                c5.metric("P/E Forward", f"{r['forward_pe']:.1f}x" if r['forward_pe'] > 0 else "N/D")
                c6.metric("P/E Trailing", f"{r['trailing_pe']:.1f}x" if r['trailing_pe'] > 0 else "N/D")
                c7.metric("PEG Ratio", f"{r['peg_ratio']:.2f}" if r['peg_ratio'] > 0 else "N/D")
                c8.metric("P/S Ratio", f"{r['price_to_sales']:.1f}x" if r.get('price_to_sales', 0) > 0 else "N/D")

                # Fila 3: Flujo de caja y Beneficios
                c9, c10, c11, c12 = st.columns(4)
                c9.metric("FCF", _format_large_number(r.get("free_cashflow", 0)))
                c10.metric("Cash Flow Op.", _format_large_number(r.get("operating_cashflow", 0)))
                c11.metric("Crec. Beneficios", f"{r['earnings_growth']*100:.1f}%")
                c12.metric("Margen Neto", f"{r['profit_margins']*100:.1f}%")

                # Valoración cualitativa
                pe = r['forward_pe'] if r['forward_pe'] > 0 else r['trailing_pe']
                peg = r['peg_ratio']
                if pe > 0 and peg > 0:
                    if peg < 1:
                        st.success(f"📗 **Infravalorada** respecto a su crecimiento (PEG {peg:.2f} < 1). "
                                   f"La empresa crece más rápido que lo que paga el mercado.")
                    elif peg < 1.5:
                        st.info(f"📘 **Valoración razonable** (PEG {peg:.2f}). "
                                f"El precio refleja el crecimiento proyectado.")
                    elif peg < 2.5:
                        st.warning(f"📙 **Ligeramente cara** para su crecimiento (PEG {peg:.2f}). "
                                   f"Considerar esperar corrección.")
                    else:
                        st.error(f"📕 **Sobrevalorada** (PEG {peg:.2f} > 2.5). "
                                 f"El precio excede significativamente su tasa de crecimiento.")
                elif pe > 0:
                    if pe < 15:
                        st.success(f"📗 P/E bajo ({pe:.1f}x) — potencialmente infravalorada.")
                    elif pe < 25:
                        st.info(f"📘 P/E razonable ({pe:.1f}x) — mercado precio un crecimiento moderado.")
                    elif pe < 40:
                        st.warning(f"📙 P/E elevado ({pe:.1f}x) — mercado espera alto crecimiento.")
                    else:
                        st.error(f"📕 P/E muy alto ({pe:.1f}x) — valuación agresiva.")

                # Razones del score fundamental
                if r.get("razones"):
                    with st.container():
                        st.markdown("**Factores del Score Fundamental:**")
                        for razon in r["razones"]:
                            st.markdown(f"- {razon}")

            # ═══════════ TAB TÉCNICO ═══════════
            with tab_tec:
                st.markdown("##### 📈 Análisis Técnico — Precio y Timing")

                if not tecnico:
                    st.warning("⚠️ Datos técnicos no disponibles para esta empresa.")
                else:
                    # Gráfico de precio + SMAs + Volumen
                    if tecnico.get("chart_dates"):
                        fig = go.Figure()

                        # Precio
                        fig.add_trace(go.Scatter(
                            x=tecnico["chart_dates"],
                            y=tecnico["chart_close"],
                            mode='lines',
                            name='Precio',
                            line=dict(color='#00ff88', width=2),
                        ))
                        # SMA 20
                        sma20_clean = [v for v in tecnico["chart_sma20"] if v is not None]
                        dates_sma20 = tecnico["chart_dates"][-len(sma20_clean):]
                        if sma20_clean:
                            fig.add_trace(go.Scatter(
                                x=dates_sma20,
                                y=sma20_clean,
                                mode='lines',
                                name='SMA 20',
                                line=dict(color='#3b82f6', width=1, dash='dash'),
                            ))
                        # SMA 50
                        sma50_clean = [v for v in tecnico["chart_sma50"] if v is not None]
                        dates_sma50 = tecnico["chart_dates"][-len(sma50_clean):]
                        if sma50_clean:
                            fig.add_trace(go.Scatter(
                                x=dates_sma50,
                                y=sma50_clean,
                                mode='lines',
                                name='SMA 50',
                                line=dict(color='#f59e0b', width=1, dash='dash'),
                            ))

                        # Volumen como barras en eje secundario
                        vol_colors = []
                        closes = tecnico["chart_close"]
                        for i, v in enumerate(closes):
                            if i == 0:
                                vol_colors.append('#3b82f6')
                            elif v >= closes[i - 1]:
                                vol_colors.append('#22c55e88')
                            else:
                                vol_colors.append('#ef444488')
                        fig.add_trace(go.Bar(
                            x=tecnico["chart_dates"],
                            y=tecnico["chart_volume"],
                            name='Volumen',
                            marker_color=vol_colors,
                            yaxis='y2',
                            opacity=0.4,
                        ))

                        fig.update_layout(
                            template='plotly_dark',
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            height=380,
                            margin=dict(l=0, r=0, t=30, b=0),
                            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                                        font=dict(size=10)),
                            xaxis=dict(showgrid=False, color='#64748b'),
                            yaxis=dict(title='Precio ($)', showgrid=True, gridcolor='#1e293b', color='#94a3b8'),
                            yaxis2=dict(overlaying='y', side='right', showgrid=False, showticklabels=False,
                                        range=[0, max(tecnico["chart_volume"]) * 4] if tecnico["chart_volume"] else [0, 1]),
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"chart_{sym}")

                    # Indicadores Técnicos
                    ct1, ct2, ct3, ct4 = st.columns(4)
                    ct1.metric("Tendencia", f"{_tendencia_emoji(tecnico['tendencia'])} {tecnico['tendencia']}")
                    rsi_v = tecnico['rsi']
                    ct2.metric("RSI (14)", f"{rsi_v:.0f}", delta=_rsi_label(rsi_v))
                    ct3.metric("ADX (14)", f"{tecnico['adx']:.0f}",
                               delta="Fuerte" if tecnico['adx'] > 25 else "Débil")
                    ct4.metric("Vol. Ratio", f"{tecnico['vol_ratio']:.2f}x",
                               delta=f"{'↑ Alto' if tecnico['vol_ratio'] > 1.2 else '→ Normal' if tecnico['vol_ratio'] > 0.8 else '↓ Bajo'}")

                    # SMAs y Soportes
                    cs1, cs2, cs3 = st.columns(3)
                    cs1.metric("SMA 20", f"${tecnico['sma_20']:,.2f}")
                    cs2.metric("SMA 50", f"${tecnico['sma_50']:,.2f}")
                    cs3.metric("SMA 200", f"${tecnico['sma_200']:,.2f}" if tecnico['sma_200'] > 0 else "N/D")

                    cs4, cs5, cs6 = st.columns(3)
                    cs4.metric("Soporte (20d)", f"${tecnico['soporte_20d']:,.2f}")
                    cs5.metric("Resistencia (20d)", f"${tecnico['resistencia_20d']:,.2f}")
                    cs6.metric("Rango 52 sem.", f"{tecnico['rango_52w_pct']:.0f}%")

                    # Señales técnicas
                    señales = r.get("señales_tecnicas", [])
                    if señales:
                        st.markdown("**Señales Técnicas:**")
                        for s in señales:
                            st.markdown(f"- {s}")

            # ═══════════ TAB SENTIMIENTO ═══════════
            with tab_sent:
                st.markdown("##### 🎯 Sentimiento y Catalizadores")

                # Consenso de analistas
                rec = r.get("recommendation", "N/A")
                rec_map = {
                    "strong_buy": ("COMPRA FUERTE", "#22c55e"),
                    "strongbuy": ("COMPRA FUERTE", "#22c55e"),
                    "buy": ("COMPRA", "#22c55e"),
                    "overweight": ("SOBREPONDERAR", "#3b82f6"),
                    "hold": ("MANTENER", "#f59e0b"),
                    "underweight": ("INFRAPONDERAR", "#f97316"),
                    "sell": ("VENDER", "#ef4444"),
                    "strong_sell": ("VENTA FUERTE", "#ef4444"),
                }
                rec_lower = rec.lower() if rec else ""
                rec_label, rec_color = rec_map.get(rec_lower, (rec.upper(), "#94a3b8"))

                st.markdown(f"""
                <div style="display:flex; gap:12px; align-items:center; margin-bottom:16px;">
                    <span style="background:{rec_color}22; color:{rec_color}; padding:6px 16px;
                           border-radius:8px; font-weight:700; font-size:0.95rem; border:1px solid {rec_color}44;">
                        {rec_label}
                    </span>
                    <span style="color:#94a3b8; font-size:0.85rem;">
                        Consenso de <b style="color:#e2e8f0;">{r.get('num_analysts', 0)}</b> analistas
                    </span>
                </div>
                """, unsafe_allow_html=True)

                # Precios objetivo
                ca1, ca2, ca3, ca4 = st.columns(4)
                ca1.metric("Precio Actual", f"${r['precio']:,.2f}")
                ca2.metric("Objetivo Medio", f"${r.get('target_mean', 0):,.2f}" if r.get('target_mean', 0) > 0 else "N/D")
                ca3.metric("Objetivo Alto", f"${r.get('target_high', 0):,.2f}" if r.get('target_high', 0) > 0 else "N/D")
                ca4.metric("Objetivo Bajo", f"${r.get('target_low', 0):,.2f}" if r.get('target_low', 0) > 0 else "N/D")

                # Upside y Beta
                cb1, cb2, cb3 = st.columns(3)
                upside = r.get("upside_pct", 0)
                upside_color = "#22c55e" if upside > 0 else "#ef4444"
                cb1.metric("Upside Potencial", f"{'+' if upside > 0 else ''}{upside:.1f}%",
                           delta=f"{'+' if upside > 0 else ''}{upside:.1f}%")
                beta_val = r.get("beta", 0)
                cb2.metric("Beta", f"{beta_val:.2f}" if beta_val > 0 else "N/D",
                           delta="Más volátil" if beta_val > 1 else "Menos volátil" if beta_val > 0 else None)
                cap_str = format_market_cap(r.get("market_cap", 0))
                cb3.metric("Cap. Mercado", cap_str)

                # 52 semanas
                cc1, cc2 = st.columns(2)
                cc1.metric("Mínimo 52 sem.", f"${r.get('fifty_two_low', 0):,.2f}")
                cc2.metric("Máximo 52 sem.", f"${r.get('fifty_two_high', 0):,.2f}")

                if es_emergente and info_wl.get("por_que_grande"):
                    st.info(f"🌟 **¿Por qué puede ser gigante?**\n\n{info_wl['por_que_grande']}")

            # ═══════════ TAB VEREDICTO ═══════════
            with tab_vered:
                st.markdown("##### ⚖️ Veredicto Combinado — Fundamental × Técnico")
                st.markdown(
                    "_El objetivo es cruzar la información fundamental (por qué invertir) "
                    "con el análisis técnico (cuándo hacerlo)._"
                )

                # Barras de score visuales
                st.markdown(
                    _score_bar_html(score_fund, 100, "Score Fundamental", "#3b82f6")
                    + _score_bar_html(score_tec, 100, "Score Técnico", "#f59e0b")
                    + _score_bar_html(score_comb, 100, "Score Combinado", "#00ff88"),
                    unsafe_allow_html=True
                )

                st.markdown("")

                # Veredicto grande
                v_color = _veredicto_color(veredicto)
                st.markdown(f"""
                <div style="text-align:center; padding:16px; background:{v_color}11;
                     border:2px solid {v_color}33; border-radius:12px; margin:12px 0;">
                    <div style="font-size:1.6rem; font-weight:800; color:{v_color};">
                        {veredicto}
                    </div>
                    <div style="font-size:0.85rem; color:#94a3b8; margin-top:6px;">
                        {r['nombre']} · {r.get('sector', '')} · ${r['precio']:,.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Resumen puntos clave
                col_f, col_t = st.columns(2)
                with col_f:
                    st.markdown("**📊 Fundamental:**")
                    for razon in r.get("razones", [])[:5]:
                        st.markdown(f"- {razon}")
                    if not r.get("razones"):
                        st.caption("Sin datos fundamentales relevantes.")

                with col_t:
                    st.markdown("**📈 Técnico:**")
                    for s in r.get("señales_tecnicas", [])[:5]:
                        st.markdown(f"- {s}")
                    if not r.get("señales_tecnicas"):
                        st.caption("Sin datos técnicos disponibles.")

                # Aviso educativo
                st.caption(
                    "⚠️ Este análisis es informativo y no constituye asesoramiento financiero. "
                    "Siempre realiza tu propia investigación antes de invertir."
                )


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
