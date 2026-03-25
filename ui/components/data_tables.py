"""
Tablas pro HTML, análisis completo y helpers de watchlist.
"""
import time
import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from random import uniform

from config.constants import ANALYSIS_SLEEP_RANGE
from core.projections import analizar_proyeccion_empresa
from ui.plotly_professional_theme import COLORS

from ui.components.score_display import (
    _rsi_label, _tendencia_emoji, _veredicto_color, _score_bar_html,
)
from ui.components.alert_badges import (
    _sm_flow_badge, _inst_flow_badge, institutional_flow_legend,
    _badge_html, _sentiment_badge, _type_badge, _priority_badge, _delta_cell,
)
from ui.components.common import format_market_cap, _format_large_number

logger = logging.getLogger(__name__)


# ── Column metadata for render_pro_table ─────────────────────────────────────

_SPECIAL_COLS = {
    "Sentimiento": "sentiment",
    "Tipo": "type",
    "Tipo_Opcion": "type",
    "Prioridad": "priority",
    "Flow_Type": "flow",
    "Hedge_Alert": "hedge_alert",
    "Hedge_Level": "_hidden",
    "sm_flow_score": "sm_flow",
    "SM Flow": "sm_flow",
    "inst_flow_score": "inst_flow",
    "Inst Flow": "inst_flow",
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

    # Build <thead> — skip _hidden columns
    ths = "".join(f'<th>{col}</th>' for col in df.columns if _SPECIAL_COLS.get(col) != "_hidden")
    thead = f'<thead><tr>{ths}</tr></thead>'

    # Build <tbody> — pre-format per column then join (faster than iterrows)
    visible_cols = [c for c in df.columns if _SPECIAL_COLS.get(c) != "_hidden"]
    # Pre-compute td class per column (constant per column)
    _col_cls = {}
    for col in visible_cols:
        if col in ("Ticker", "Contrato"):
            _col_cls[col] = ' class="td-ticker"'
        elif col in _NUMERIC_COLS or col in ("OI Chg",):
            _col_cls[col] = ' class="td-num"'
        else:
            _col_cls[col] = ""

    # Pre-import flow badges once (avoid per-cell import)
    _flow_badge_fn = None
    _ha_badge_fn = None
    if any(_SPECIAL_COLS.get(c) == "flow" for c in visible_cols):
        from core.flow_classifier import flow_badge as _flow_badge_fn
    if any(_SPECIAL_COLS.get(c) == "hedge_alert" for c in visible_cols):
        from core.flow_classifier import hedge_alert_badge as _ha_badge_fn

    # Pre-format each column as a list of HTML cell strings
    col_cells = {}
    for col in visible_cols:
        series = df[col]
        cls = _col_cls[col]

        if col in special_format:
            fmt_fn = special_format[col]
            vals = [fmt_fn(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
        elif col in _SPECIAL_COLS:
            fmt_kind = _SPECIAL_COLS[col]
            if fmt_kind == "sentiment":
                vals = [str(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
            elif fmt_kind == "type":
                vals = [_type_badge(str(v)) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
            elif fmt_kind == "priority":
                vals = [_priority_badge(str(v)) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
            elif fmt_kind == "flow" and _flow_badge_fn:
                vals = [_flow_badge_fn(str(v)) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
            elif fmt_kind == "hedge_alert" and _ha_badge_fn:
                _levels = df["Hedge_Level"] if "Hedge_Level" in df.columns else pd.Series(["warning"] * len(df))
                vals = [
                    _ha_badge_fn(str(v), str(lv)) if v is not None and str(v).strip() else ""
                    for v, lv in zip(series, _levels)
                ]
            elif fmt_kind == "sm_flow":
                vals = [_sm_flow_badge(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
            elif fmt_kind == "inst_flow":
                vals = [_inst_flow_badge(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
            else:
                vals = [str(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
        elif col in ("OI_Chg", "OI Chg"):
            vals = [_delta_cell(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]
        else:
            vals = [str(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else "-" for v in series]

        col_cells[col] = [f'<td{cls}>{v}</td>' for v in vals]

    # Assemble rows
    n_rows = len(df)
    rows = []
    for i in range(n_rows):
        row_html = "".join(col_cells[col][i] for col in visible_cols)
        rows.append(f'<tr>{row_html}</tr>')
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
        if not isinstance(info, dict):
            info = {}

        nombre = info.get("nombre") or "N/D"
        sector = info.get("sector") or "N/D"

        preview_data.append({
            "Ticker": sym,
            "Empresa": nombre,
            "Sector": sector,
        })
    st.markdown(
        render_pro_table(pd.DataFrame(preview_data), title="📋 Watchlist", max_height=670),
        unsafe_allow_html=True,
    )


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
                            line=dict(color=COLORS['positive'], width=2),
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
                                line=dict(color=COLORS['accent'], width=1, dash='dash'),
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
                                line=dict(color=COLORS['warning'], width=1, dash='dash'),
                            ))

                        # Volumen como barras en eje secundario
                        vol_colors = []
                        closes = tecnico["chart_close"]
                        for i, v in enumerate(closes):
                            if i == 0:
                                vol_colors.append(f'{COLORS["accent"]}80')
                            elif v >= closes[i - 1]:
                                vol_colors.append(f'{COLORS["positive"]}80')
                            else:
                                vol_colors.append(f'{COLORS["negative"]}80')
                        fig.add_trace(go.Bar(
                            x=tecnico["chart_dates"],
                            y=tecnico["chart_volume"],
                            name='Volumen',
                            marker_color=vol_colors,
                            yaxis='y2',
                            opacity=0.4,
                        ))

                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor=COLORS["bg"],
                            height=380,
                            margin=dict(l=0, r=0, t=30, b=0),
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                        xanchor="right", x=1, font=dict(size=10,
                                        color=COLORS["muted"])),
                            font=dict(family="Inter, system-ui, sans-serif",
                                      color=COLORS["text"], size=12),
                            hoverlabel=dict(bgcolor=COLORS["surface"],
                                            bordercolor=COLORS["faint"],
                                            font=dict(family="Inter, system-ui, sans-serif",
                                                      size=12, color=COLORS["text"])),
                            xaxis=dict(showgrid=False, color=COLORS["muted"],
                                       tickfont=dict(size=10, color=COLORS["muted"])),
                            yaxis=dict(title=dict(text="Precio ($)",
                                                   font=dict(size=11, color=COLORS["muted"])),
                                       showgrid=True, gridcolor=COLORS["faint"],
                                       color=COLORS["muted"]),
                            yaxis2=dict(overlaying="y", side="right", showgrid=False,
                                        showticklabels=False,
                                        range=[0, max(tecnico["chart_volume"]) * 4]
                                        if tecnico["chart_volume"] else [0, 1]),
                            hovermode="x unified",
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
