# -*- coding: utf-8 -*-
"""
Venta de Prima — Credit Spread Scanner.

Escanea cadenas de opciones para encontrar Bull Put Spreads y Bear Call Spreads
con alta probabilidad de ganancia y buen retorno sobre riesgo.
Usa AgGrid para tabla interactiva (sortable, filterable, color-coded).
"""
from __future__ import annotations

import io
import logging
import pandas as pd
import streamlit as st
from datetime import datetime

from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

from core.credit_spread_scanner import scan_credit_spreads

logger = logging.getLogger(__name__)

# ── Tickers populares por defecto ────────────────────────────────────────
_DEFAULT_TICKERS = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD"]
_ALL_TICKERS = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN", "META",
    "GOOGL", "NFLX", "DIS", "BA", "JPM", "GS", "V", "MA",
    "XOM", "COIN", "PLTR", "SOFI", "MARA", "IWM", "DIA", "GLD",
]

# ── JS cell-style functions para AgGrid ──────────────────────────────────
_JS_RETORNO_STYLE = JsCode("""
function(params) {
    if (params.value > 25) return {'color': '#00ff88', 'fontWeight': '700'};
    if (params.value > 15) return {'color': '#fbbf24', 'fontWeight': '600'};
    return {'color': '#94a3b8'};
}
""")

_JS_POP_STYLE = JsCode("""
function(params) {
    if (params.value > 80) return {'color': '#00ff88', 'fontWeight': '700'};
    if (params.value > 70) return {'color': '#22d3ee', 'fontWeight': '600'};
    return {'color': '#94a3b8'};
}
""")

_JS_TIPO_STYLE = JsCode("""
function(params) {
    if (params.value === 'Bull Put') return {'color': '#22c55e', 'fontWeight': '600'};
    return {'color': '#ef4444', 'fontWeight': '600'};
}
""")

_JS_RISK_STYLE = JsCode("""
function(params) {
    if (params.value <= 200) return {'color': '#22c55e'};
    if (params.value <= 500) return {'color': '#fbbf24'};
    return {'color': '#ef4444'};
}
""")

_JS_LIQUIDEZ_STYLE = JsCode("""
function(params) {
    if (params.value >= 5000) return {'color': '#00ff88'};
    if (params.value >= 1000) return {'color': '#94a3b8'};
    return {'color': '#64748b'};
}
""")

_JS_DIST_STYLE = JsCode("""
function(params) {
    if (params.value > 5) return {'color': '#22c55e', 'fontWeight': '600'};
    if (params.value >= 3) return {'color': '#fbbf24'};
    return {'color': '#ef4444', 'fontWeight': '700'};
}
""")

_JS_IVRANK_STYLE = JsCode("""
function(params) {
    if (params.value >= 40) return {'color': '#00ff88', 'fontWeight': '600'};
    if (params.value >= 25) return {'color': '#fbbf24'};
    return {'color': '#64748b'};
}
""")


def render(**kwargs) -> None:
    """Renderiza la página de Venta de Prima — Credit Spread Scanner."""

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                    border:1px solid #0f3460;border-radius:16px;
                    padding:1.5rem 2rem;margin-bottom:1.5rem;">
            <h2 style="color:#e94560;margin:0 0 0.3rem 0;">
                💰 VENTA DE PRIMA — Scanner de Oportunidades
            </h2>
            <p style="color:#94a3b8;margin:0;font-size:0.9rem;">
                Vista rápida de los contratos con mayor probabilidad de éxito —
                Bull Put Spreads &amp; Bear Call Spreads.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Panel educativo (colapsado por defecto) ──────────────────────────
    with st.expander("📚 Panel educativo para venta de prima", expanded=False):
        st.markdown(
            """
            <div style="font-size:0.84rem;line-height:1.7;color:#cbd5e1;">
            <b style="color:#e94560;">Antes de vender prima revisa esto:</b>
            <ul style="list-style:none;padding-left:0;margin:0.4rem 0 0 0;">
              <li>✅ <b style="color:#22c55e;">Delta ≤ 0.20</b> — alta probabilidad de expirar OTM</li>
              <li>✅ <b style="color:#22c55e;">IV alto</b> — prima inflada = más crédito recibido</li>
              <li>✅ <b style="color:#22c55e;">Liquidez alta</b> — spreads ajustados, fácil entrada/salida</li>
              <li>✅ <b style="color:#22c55e;">DTE 30–45 días</b> — zona óptima de decaimiento theta</li>
              <li>✅ <b style="color:#22c55e;">Crédito ≥ ⅓ del ancho</b> — relación riesgo/beneficio aceptable</li>
              <li>✅ <b style="color:#22c55e;">Riesgo ≤ 5% de la cuenta</b> — proteger el capital</li>
            </ul>
            <div style="margin-top:0.5rem;padding:6px 10px;background:#0d1117;border-left:3px solid #00ff88;border-radius:4px;">
              <b style="color:#00ff88;">Gestión recomendada:</b><br>
              🎯 Tomar ganancias al <b>50%</b> del crédito recibido<br>
              🛑 Salir si la pérdida llega al <b>100%</b> del crédito<br>
              ⏰ Cerrar a los <b>21 DTE</b> si la posición sigue abierta
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Filtros en el sidebar ────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Filtros — Venta de Prima")

        selected_tickers = st.multiselect(
            "🔍 Tickers a escanear",
            options=_ALL_TICKERS,
            default=_DEFAULT_TICKERS,
            help="Selecciona los tickers donde buscar spreads.",
            key="cs_tickers",
        )
        min_pop_pct = st.slider(
            "📊 Min POP %",
            min_value=50, max_value=95, value=70, step=5,
            help="Solo spreads con probabilidad de ganancia ≥ este valor.",
            key="cs_min_pop",
        )
        max_dte = st.slider(
            "📅 Máx DTE (días)",
            min_value=7, max_value=90, value=45, step=1,
            help="Máximo de días hasta vencimiento.",
            key="cs_max_dte",
        )
        min_credit = st.slider(
            "💵 Min Crédito ($)",
            min_value=0.10, max_value=5.00, value=0.30, step=0.05,
            format="$%.2f",
            help="Crédito neto mínimo del spread.",
            key="cs_min_credit",
        )
        tipo_filter = st.radio(
            "📈 Tipo de Spread",
            ["Ambos", "Bull Put", "Bear Call"],
            horizontal=True,
            key="cs_tipo_filter",
        )
        st.markdown("---")
        st.markdown("#### 🎯 Filtros Avanzados")
        min_iv_rank = st.slider(
            "📊 Min IV Rank %",
            min_value=0, max_value=80, value=0, step=5,
            help="Solo spreads de tickers con IV Rank ≥ este valor. >40 = ideal para venta de prima.",
            key="cs_min_iv_rank",
        )
        filter_by_trend = st.checkbox(
            "🧭 Solo spreads alineados con tendencia",
            value=False,
            help="Bull Put solo si tendencia Alcista, Bear Call solo si Bajista.",
            key="cs_trend_align",
        )
        st.markdown("---")

    # ── Botón de escaneo ─────────────────────────────────────────────────
    scan_btn = st.button(
        "🚀 Ejecutar Scanner",
        type="primary",
        use_container_width=True,
        key="cs_scan_btn",
    )

    # ── Ejecutar scan ────────────────────────────────────────────────────
    if scan_btn:
        if not selected_tickers:
            st.warning("⚠️ Selecciona al menos un ticker en el sidebar.")
            return

        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def _progress_cb(ticker: str, idx: int, total: int) -> None:
            pct = (idx + 1) / total
            progress_bar.progress(pct)
            status_text.markdown(
                f'<span style="color:#94a3b8;font-size:0.85rem;">'
                f'Escaneando <b style="color:#00ff88;">{ticker}</b> '
                f'({idx + 1}/{total})...</span>',
                unsafe_allow_html=True,
            )

        with st.spinner("Analizando cadenas de opciones..."):
            df, ticker_indicators = scan_credit_spreads(
                tickers=selected_tickers,
                min_pop=min_pop_pct / 100.0,
                max_dte=max_dte,
                min_credit=min_credit,
                progress_callback=_progress_cb,
            )

        progress_bar.empty()
        status_text.empty()

        st.session_state["cs_results"] = df
        st.session_state["cs_ticker_indicators"] = ticker_indicators
        st.session_state["cs_scan_time"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    # ── Mostrar resultados ───────────────────────────────────────────────
    df: pd.DataFrame | None = st.session_state.get("cs_results")
    scan_time: str | None = st.session_state.get("cs_scan_time")
    ticker_indicators: dict = st.session_state.get("cs_ticker_indicators", {})

    if df is None or df.empty:
        if df is not None:
            st.info(
                "🔍 No se encontraron spreads con los filtros actuales. "
                "Ajusta los parámetros e intenta de nuevo."
            )
        else:
            st.markdown(
                '<p style="color:#64748b;text-align:center;padding:2rem 0;">'
                "Pulsa <b>🚀 Ejecutar Scanner</b> para buscar oportunidades.</p>",
                unsafe_allow_html=True,
            )
        return

    # ── Filtro de tipo ───────────────────────────────────────────────────
    df_filtered = df.copy()
    if tipo_filter == "Bull Put":
        df_filtered = df_filtered[df_filtered["Tipo"] == "Bull Put"]
    elif tipo_filter == "Bear Call":
        df_filtered = df_filtered[df_filtered["Tipo"] == "Bear Call"]

    # Filtro IV Rank mínimo
    if min_iv_rank > 0 and "IV Rank" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["IV Rank"] >= min_iv_rank]

    # Filtro alineación con tendencia
    if filter_by_trend and "Tendencia" in df_filtered.columns:
        mask = (
            ((df_filtered["Tipo"] == "Bull Put") & (df_filtered["Tendencia"] == "Alcista")) |
            ((df_filtered["Tipo"] == "Bear Call") & (df_filtered["Tendencia"] == "Bajista"))
        )
        df_filtered = df_filtered[mask]

    if df_filtered.empty:
        st.info(f"No hay spreads de tipo '{tipo_filter}' en los resultados.")
        return

    # ── Status bar ───────────────────────────────────────────────────────
    n_bull = int((df_filtered["Tipo"] == "Bull Put").sum())
    n_bear = int((df_filtered["Tipo"] == "Bear Call").sum())
    st.markdown(
        f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                    padding:10px 18px;display:flex;align-items:center;gap:18px;
                    font-size:0.85rem;margin-bottom:1rem;flex-wrap:wrap;">
            <span style="color:#00ff88;font-weight:700;">
                {len(df_filtered)} oportunidades
            </span>
            <span style="color:#94a3b8;">
                🟢 Bull Put: <b>{n_bull}</b> &nbsp;|&nbsp; 🔴 Bear Call: <b>{n_bear}</b>
            </span>
            <span style="color:#64748b;margin-left:auto;">
                Último scan: {scan_time}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Indicadores por ticker: IV Rank / Percentile + Tendencia ─────────
    if ticker_indicators:
        _trend_colors = {"Alcista": "#22c55e", "Bajista": "#ef4444", "Neutral": "#94a3b8"}
        _trend_icons = {"Alcista": "📈", "Bajista": "📉", "Neutral": "➡️"}

        # Tarjetas horizontales por ticker
        cards_html = ""
        for tk, info in ticker_indicators.items():
            ivr = info.get("iv_rank", 0)
            ivp = info.get("iv_percentile", 0)
            trend = info.get("trend", "Neutral")
            pref = info.get("preferred_type")
            vwap = info.get("vwap", 0)
            ema9 = info.get("ema9", 0)
            ema21 = info.get("ema21", 0)

            ivr_color = "#00ff88" if ivr >= 40 else ("#fbbf24" if ivr >= 25 else "#64748b")
            t_color = _trend_colors.get(trend, "#94a3b8")
            t_icon = _trend_icons.get(trend, "➡️")
            pref_label = f' → <span style="color:#fbbf24;">{pref}</span>' if pref else ""

            cards_html += (
                f'<div style="background:#0d1117;border:1px solid #1e293b;'
                f'border-radius:8px;padding:8px 14px;min-width:220px;flex:1;">'
                f'<b style="color:#e2e8f0;font-size:0.9rem;">{tk}</b><br>'
                f'<span style="color:{ivr_color};font-size:0.82rem;">IV Rank: {ivr:.0f}%</span> · '
                f'<span style="color:{ivr_color};font-size:0.82rem;">IV Pctil: {ivp:.0f}%</span><br>'
                f'<span style="color:{t_color};font-size:0.82rem;">{t_icon} {trend}{pref_label}</span><br>'
                f'<span style="color:#64748b;font-size:0.75rem;">'
                f'VWAP ${vwap:.2f} · EMA9 ${ema9:.2f} · EMA21 ${ema21:.2f}</span>'
                f'</div>'
            )

        st.markdown(
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:1rem;">'
            f'{cards_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Métricas rápidas ─────────────────────────────────────────────────
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("Mejor Retorno %", f"{df_filtered['Retorno %'].max():.1f}%")
    with mc2:
        st.metric("POP Promedio", f"{df_filtered['POP %'].mean():.1f}%")
    with mc3:
        st.metric("Crédito Promedio", f"${df_filtered['Crédito'].mean():.2f}")
    with mc4:
        st.metric("DTE Promedio", f"{df_filtered['DTE'].mean():.0f}d")

    # ── Tabla AgGrid (interactive, sortable, filterable) ─────────────────
    display_cols = [
        "Ticker", "Tipo", "Spot", "Strike Vendido", "Strike Comprado",
        "DTE", "Delta Vendido", "POP %", "Prob OTM %", "Crédito",
        "Riesgo Máx", "Retorno %", "Dist Strike %", "IV %",
        "IV Rank", "IV Pctil", "Tendencia",
        "Liquidez", "Volumen", "OI", "Bid-Ask",
    ]
    display_cols = [c for c in display_cols if c in df_filtered.columns]
    df_show = df_filtered[display_cols].reset_index(drop=True)

    gb = GridOptionsBuilder.from_dataframe(df_show)
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        wrapHeaderText=True,
        autoHeaderHeight=True,
    )

    # Column-specific config
    gb.configure_column("Ticker", pinned="left", width=80)
    gb.configure_column("Tipo", width=95, cellStyle=_JS_TIPO_STYLE)
    gb.configure_column("Spot", width=80, type=["numericColumn"],
                        valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("Strike Vendido", width=100, type=["numericColumn"],
                        valueFormatter="x.toFixed(1)")
    gb.configure_column("Strike Comprado", width=110, type=["numericColumn"],
                        valueFormatter="x.toFixed(1)")
    gb.configure_column("DTE", width=60, type=["numericColumn"])
    gb.configure_column("Delta Vendido", width=95, type=["numericColumn"],
                        valueFormatter="x.toFixed(3)")
    gb.configure_column("POP %", width=75, type=["numericColumn"],
                        cellStyle=_JS_POP_STYLE,
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("Prob OTM %", width=95, type=["numericColumn"],
                        cellStyle=_JS_POP_STYLE,
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("Crédito", width=80, type=["numericColumn"],
                        valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("Riesgo Máx", width=95, type=["numericColumn"],
                        cellStyle=_JS_RISK_STYLE,
                        valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("Retorno %", width=95, type=["numericColumn"],
                        cellStyle=_JS_RETORNO_STYLE, sort="desc",
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("Dist Strike %", headerName="Dist Strike %", width=105,
                        type=["numericColumn"], cellStyle=_JS_DIST_STYLE,
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("IV %", width=70, type=["numericColumn"],
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("IV Rank", width=80, type=["numericColumn"],
                        cellStyle=_JS_IVRANK_STYLE,
                        valueFormatter="x.toFixed(0) + '%'")
    gb.configure_column("IV Pctil", headerName="IV Pctil", width=80,
                        type=["numericColumn"], cellStyle=_JS_IVRANK_STYLE,
                        valueFormatter="x.toFixed(0) + '%'")
    gb.configure_column("Tendencia", width=90)
    gb.configure_column("Liquidez", width=85, type=["numericColumn"],
                        cellStyle=_JS_LIQUIDEZ_STYLE)
    gb.configure_column("Volumen", width=80, type=["numericColumn"])
    gb.configure_column("OI", headerName="Open Interest", width=100,
                        type=["numericColumn"])
    gb.configure_column("Bid-Ask", width=80, type=["numericColumn"],
                        valueFormatter="'$' + x.toFixed(2)")

    grid_options = gb.build()

    # Inyectar estilos dark-theme para AgGrid
    _AGGRID_CSS = {
        ".ag-root-wrapper": {
            "background-color": "#0d1117 !important",
            "border": "1px solid #1e293b !important",
            "border-radius": "10px !important",
        },
        ".ag-header": {
            "background-color": "#161b22 !important",
            "color": "#94a3b8 !important",
            "border-bottom": "1px solid #1e293b !important",
        },
        ".ag-header-cell-text": {
            "color": "#94a3b8 !important",
            "font-weight": "600 !important",
            "font-size": "0.78rem !important",
        },
        ".ag-row": {
            "background-color": "#0d1117 !important",
            "color": "#e2e8f0 !important",
            "border-bottom": "1px solid #1e293b !important",
            "font-size": "0.82rem !important",
        },
        ".ag-row-hover": {
            "background-color": "#1e293b !important",
        },
        ".ag-cell": {
            "border-right": "none !important",
        },
    }

    AgGrid(
        df_show,
        gridOptions=grid_options,
        custom_css=_AGGRID_CSS,
        height=min(620, 56 + len(df_show) * 35),
        theme="alpine",
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
    )

    # ── Exportar CSV ─────────────────────────────────────────────────────
    st.markdown("")
    csv_buffer = io.StringIO()
    df_filtered.to_csv(csv_buffer, index=False)
    st.download_button(
        label="📥 Exportar a CSV",
        data=csv_buffer.getvalue(),
        file_name=f"credit_spreads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True,
        key="cs_export_csv",
    )

    # ── Top 5 por tipo ───────────────────────────────────────────────────
    st.markdown("---")
    col_top1, col_top2 = st.columns(2)

    with col_top1:
        st.markdown("##### 🟢 Top 5 Bull Put Spreads")
        top_bp = df_filtered[df_filtered["Tipo"] == "Bull Put"].head(5)
        if not top_bp.empty:
            for _, row in top_bp.iterrows():
                _dist = row.get("Dist Strike %", 0)
                _ivr = row.get("IV Rank", 0)
                _trend = row.get("Tendencia", "")
                _ivr_c = "#00ff88" if _ivr >= 40 else "#64748b"
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #1e3a2f;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b style="color:#22c55e;">{row["Ticker"]}</b> '
                    f'<span style="color:#94a3b8;">Sell {row["Strike Vendido"]}P / '
                    f'Buy {row["Strike Comprado"]}P</span> '
                    f'<span style="color:#64748b;">({row["DTE"]}d)</span><br>'
                    f'<span style="color:#00ff88;">Ret: {row["Retorno %"]:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">POP: {row["POP %"]:.0f}%</span> · '
                    f'<span style="color:#fbbf24;">Cr: ${row["Crédito"]:.2f}</span> · '
                    f'<span style="color:#64748b;">Δ {row["Delta Vendido"]:.2f}</span><br>'
                    f'<span style="color:#64748b;">Dist: {_dist:.1f}%</span> · '
                    f'<span style="color:{_ivr_c};">IVR: {_ivr:.0f}%</span> · '
                    f'<span style="color:#64748b;">{_trend}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin resultados")

    with col_top2:
        st.markdown("##### 🔴 Top 5 Bear Call Spreads")
        top_bc = df_filtered[df_filtered["Tipo"] == "Bear Call"].head(5)
        if not top_bc.empty:
            for _, row in top_bc.iterrows():
                _dist = row.get("Dist Strike %", 0)
                _ivr = row.get("IV Rank", 0)
                _trend = row.get("Tendencia", "")
                _ivr_c = "#00ff88" if _ivr >= 40 else "#64748b"
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #3a1e1e;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b style="color:#ef4444;">{row["Ticker"]}</b> '
                    f'<span style="color:#94a3b8;">Sell {row["Strike Vendido"]}C / '
                    f'Buy {row["Strike Comprado"]}C</span> '
                    f'<span style="color:#64748b;">({row["DTE"]}d)</span><br>'
                    f'<span style="color:#00ff88;">Ret: {row["Retorno %"]:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">POP: {row["POP %"]:.0f}%</span> · '
                    f'<span style="color:#fbbf24;">Cr: ${row["Crédito"]:.2f}</span> · '
                    f'<span style="color:#64748b;">Δ {row["Delta Vendido"]:.2f}</span><br>'
                    f'<span style="color:#64748b;">Dist: {_dist:.1f}%</span> · '
                    f'<span style="color:{_ivr_c};">IVR: {_ivr:.0f}%</span> · '
                    f'<span style="color:#64748b;">{_trend}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin resultados")
