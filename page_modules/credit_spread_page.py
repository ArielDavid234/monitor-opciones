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

from core.container import get_container
from core.optionkings_analytic import enrich_dataframe_with_ev, ev_label
from core.backtester import Backtester, BacktestResult
from utils.state import save_page_data, load_page_data
from ui.plotly_professional_theme import COLORS

from config.constants import ALERT_DEFAULT_ACCOUNT_SIZE

# ── Tickers populares por defecto ────────────────────────────────────────
_DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "NVDA", "AAPL", "TSLA", "AMD"]
_ALL_TICKERS = [
    "SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN", "META",
    "GOOGL", "NFLX", "DIS", "BA", "JPM", "GS", "V", "MA",
    "XOM", "COIN", "PLTR", "SOFI", "MARA", "DIA", "GLD",
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

_JS_INCOME_SCORE_STYLE = JsCode("""
function(params) {
    if (params.value >= 80) return {'backgroundColor': '#166534', 'color': '#4ade80', 'fontWeight': '700'};
    if (params.value >= 60) return {'backgroundColor': '#713f12', 'color': '#fbbf24', 'fontWeight': '600'};
    return {'backgroundColor': '#3f1219', 'color': '#f87171', 'fontWeight': '600'};
}
""")

_JS_CALIDAD_STYLE = JsCode("""
function(params) {
    if (params.value === 'Alta probabilidad') return {'color': '#4ade80', 'fontWeight': '700'};
    if (params.value === 'Buena') return {'color': '#fbbf24', 'fontWeight': '600'};
    return {'color': '#f87171', 'fontWeight': '600'};
}
""")

_JS_OPP_SCORE_STYLE = JsCode("""
function(params) {
    if (params.value >= 80) return {
        'backgroundColor': '#00ff00', 'color': '#000000',
        'fontWeight': '700', 'fontSize': '0.95rem'
    };
    if (params.value >= 60) return {
        'backgroundColor': '#ffaa00', 'color': '#000000',
        'fontWeight': '600'
    };
    return {'color': '#94a3b8'};
}
""")

_JS_OPP_LABEL_STYLE = JsCode("""
function(params) {
    if (params.value === 'Excelente') return {'color': '#00ff00', 'fontWeight': '700'};
    if (params.value === 'Buena') return {'color': '#ffaa00', 'fontWeight': '600'};
    return {'color': '#94a3b8'};
}
""")

_JS_EV_DOLLAR_STYLE = JsCode("""
function(params) {
    if (params.value >= 80)  return {'backgroundColor': '#166534', 'color': '#4ade80', 'fontWeight': '700'};
    if (params.value >  0)   return {'color': '#22d3ee', 'fontWeight': '600'};
    if (params.value === 0)  return {'color': '#94a3b8'};
    return {'backgroundColor': '#3f1219', 'color': '#f87171', 'fontWeight': '700'};
}
""")

_JS_EV_PCT_STYLE = JsCode("""
function(params) {
    if (params.value >= 20)  return {'color': '#4ade80', 'fontWeight': '700'};
    if (params.value > 0)    return {'color': '#fbbf24', 'fontWeight': '600'};
    return {'color': '#f87171'};
}
""")




# ── Cached scanner ─────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _cached_scan(
    tickers_tuple: tuple,
    min_pop: float,
    max_dte: int,
    min_credit: float,
    strict: bool,
) -> tuple:
    """Versión cacheada del scanner sin progress_callback. TTL = 5 min.

    Los resultados se reutilizan si los mismos parámetros se usan dentro de
    la ventana de caché, evitando llamadas repetidas a yfinance.
    """
    from core.credit_spread_scanner import scan_credit_spreads as _scan_fn
    return _scan_fn(
        tickers=list(tickers_tuple),
        min_pop=min_pop,
        max_dte=max_dte,
        min_credit=min_credit,
        progress_callback=None,
        strict=strict,
    )


# ── AgGrid + score breakdown fragment ──────────────────────────────────
@st.fragment
def _render_aggrid_fragment() -> None:
    """Fragment: tabla AgGrid interactiva + desglose de score.

    Re-ejecuta SÓLO cuando el usuario selecciona una fila en la tabla.
    No re-ejecuta en cambios de filtros externos ni al navegar por el sidebar.
    """
    df_show: pd.DataFrame | None = st.session_state.get("_cs_aggrid_df")
    if df_show is None or df_show.empty:
        return

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
    # ── Score Final (Fase 1+2) ──────────────────────────────────────
    gb.configure_column("Score Final", headerName="⭐ Score Final", width=130,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v >= 75) return {color:'#4ade80',fontWeight:'bold'};
                            if (v >= 55) return {color:'#facc15'};
                            return {color:'#f87171'};
                        }""",
                        sort="desc",
                        valueFormatter="x.toFixed(1)")
    gb.configure_column("Score Oportunidad", headerName="Score de Oportunidad",
                        width=155, type=["numericColumn"],
                        cellStyle=_JS_OPP_SCORE_STYLE, sort="desc",
                        valueFormatter="x.toFixed(0)")
    gb.configure_column("Nivel", headerName="Nivel", width=100,
                        cellStyle=_JS_OPP_LABEL_STYLE)
    gb.configure_column("Income Score", headerName="Income Score", width=115,
                        type=["numericColumn"], cellStyle=_JS_INCOME_SCORE_STYLE,
                        valueFormatter="x.toFixed(0)")
    gb.configure_column("Calidad", headerName="Calidad", width=130,
                        cellStyle=_JS_CALIDAD_STYLE)
    gb.configure_column("Spot", width=80, type=["numericColumn"],
                        valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("Strike Vendido", width=100, type=["numericColumn"],
                        valueFormatter="x.toFixed(1)")
    gb.configure_column("Strike Comprado", width=110, type=["numericColumn"],
                        valueFormatter="x.toFixed(1)")
    gb.configure_column("DTE", width=60, type=["numericColumn"])
    gb.configure_column("Delta Vendido", width=95, type=["numericColumn"],
                        valueFormatter="x.toFixed(3)")
    # ── Delta Neto y PoT Short (Fase 1) ──────────────────────────────
    gb.configure_column("Delta Neto", headerName="Δ Neto", width=85,
                        type=["numericColumn"],
                        valueFormatter="x.toFixed(4)")
    gb.configure_column("PoT Short", headerName="PoT Short", width=100,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v >= 40) return {color:'#f87171',fontWeight:'bold'};
                            if (v >= 25) return {color:'#facc15'};
                            return {color:'#4ade80'};
                        }""",
                        valueFormatter="x.toFixed(1) + '%'")
    # ── Fase 2: Gamma Neto, Theta Neto, Decay 7d ─────────────────
    gb.configure_column("Gamma Neto", headerName="Γ Neto", width=85,
                        type=["numericColumn"],
                        valueFormatter="x.toFixed(4)")
    gb.configure_column("Theta Neto", headerName="θ Neto", width=85,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v > 0) return {color:'#4ade80'};
                            return {color:'#f87171'};
                        }""",
                        valueFormatter="x.toFixed(3)")
    gb.configure_column("Decay 7d", headerName="Decay 7d", width=90,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v > 0.5) return {color:'#4ade80',fontWeight:'bold'};
                            if (v > 0) return {color:'#facc15'};
                            return {color:'#f87171'};
                        }""",
                        valueFormatter="'$' + x.toFixed(2)")
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
    # ── EV Ajustado (Fase 1) ─────────────────────────────────────────
    gb.configure_column("EV Ajustado", headerName="EV Aj. %", width=100,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v > 5)  return {color:'#4ade80',fontWeight:'bold'};
                            if (v > 0)  return {color:'#facc15'};
                            return {color:'#f87171'};
                        }""",
                        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'")
    # ── Fase 3: EV Real Adj + Surface Edge ─────────────────────
    gb.configure_column("EV Real Adj", headerName="EV Real %", width=100,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v > 5)  return {color:'#a78bfa',fontWeight:'bold'};
                            if (v > 0)  return {color:'#facc15'};
                            return {color:'#f87171'};
                        }""",
                        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'")
    gb.configure_column("Surface Edge", headerName="Srf Edge %", width=100,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v > 3)  return {color:'#4ade80',fontWeight:'bold'};
                            if (v > 0)  return {color:'#22d3ee'};
                            return {color:'#f87171'};
                        }""",
                        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'")
    gb.configure_column("Retorno %", width=95, type=["numericColumn"],
                        cellStyle=_JS_RETORNO_STYLE,
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("Dist Strike %", headerName="Dist Strike %", width=105,
                        type=["numericColumn"], cellStyle=_JS_DIST_STYLE,
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("IV %", width=70, type=["numericColumn"],
                        valueFormatter="x.toFixed(1) + '%'")
    # ── Debug / validación vs plataforma externa ─────────────────────
    gb.configure_column("PoT 2Δ Approx", headerName="PoT 2Δ", width=90,
                        type=["numericColumn"],
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("POP Breakeven %", headerName="POP BE %", width=100,
                        type=["numericColumn"],
                        cellStyle=_JS_POP_STYLE,
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("IV Short %", headerName="IV Short", width=85,
                        type=["numericColumn"],
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("IV Long %", headerName="IV Long", width=85,
                        type=["numericColumn"],
                        valueFormatter="x.toFixed(1) + '%'")
    gb.configure_column("Breakeven", headerName="Breakeven", width=95,
                        type=["numericColumn"],
                        valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("IV Rank", width=80, type=["numericColumn"],
                        cellStyle=_JS_IVRANK_STYLE,
                        valueFormatter="x.toFixed(0) + '%'")
    gb.configure_column("IV Pctil", headerName="IV Pctil", width=80,
                        type=["numericColumn"], cellStyle=_JS_IVRANK_STYLE,
                        valueFormatter="x.toFixed(0) + '%'")
    gb.configure_column("Tendencia", width=90)
    # ── Fase 2: Liquidez del short leg ───────────────────────────
    gb.configure_column("OI Short", headerName="OI Short", width=90,
                        type=["numericColumn"])
    gb.configure_column("Vol Short", headerName="Vol Short", width=90,
                        type=["numericColumn"])
    gb.configure_column("Liq Score", headerName="Liq Score", width=95,
                        type=["numericColumn"],
                        cellStyle="""function(params) {
                            var v = params.value;
                            if (v >= 70) return {color:'#4ade80',fontWeight:'bold'};
                            if (v >= 40) return {color:'#facc15'};
                            return {color:'#f87171'};
                        }""",
                        valueFormatter="x.toFixed(0)")
    gb.configure_column("Liquidez", width=85, type=["numericColumn"],
                        cellStyle=_JS_LIQUIDEZ_STYLE)
    gb.configure_column("Volumen", width=80, type=["numericColumn"])
    gb.configure_column("OI", headerName="Open Interest", width=100,
                        type=["numericColumn"])
    gb.configure_column("Bid-Ask", width=80, type=["numericColumn"],
                        valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("EV $", headerName="EV $ /contrato", width=120,
                        type=["numericColumn"], cellStyle=_JS_EV_DOLLAR_STYLE,
                        valueFormatter="(x >= 0 ? '+' : '') + '$' + x.toFixed(2)",
                        sort="desc")
    gb.configure_column("EV %", headerName="EV % capital", width=110,
                        type=["numericColumn"], cellStyle=_JS_EV_PCT_STYLE,
                        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'")

    gb.configure_selection(selection_mode="single", use_checkbox=False)

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
        ".ag-row-selected": {
            "background-color": "#1e3a5f !important",
            "border-left": "3px solid #00ff00 !important",
        },
        ".ag-cell": {
            "border-right": "none !important",
        },
    }

    grid_response = AgGrid(
        df_show,
        gridOptions=grid_options,
        custom_css=_AGGRID_CSS,
        height=min(620, 56 + len(df_show) * 35),
        theme="alpine",
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
    )

    # ── Desglose del Score (al hacer clic en una fila) ───────────────────
    _selected = getattr(grid_response, "selected_rows", None)
    _sel_row = None
    if _selected is not None:
        if isinstance(_selected, pd.DataFrame) and not _selected.empty:
            _sel_row = _selected.iloc[0].to_dict()
        elif isinstance(_selected, list) and len(_selected) > 0:
            _sel_row = dict(_selected[0])

    if _sel_row and "Score Oportunidad" in df_show.columns:
        _bd = get_container().credit_spread_service.score_breakdown(_sel_row)
        _total = sum(b["puntos"] for b in _bd)
        _lbl = "Excelente" if _total >= 80 else "Buena"
        _lbl_c = "#00ff00" if _total >= 80 else "#ffaa00"
        _tkr = _sel_row.get("Ticker", "")
        _tipo = _sel_row.get("Tipo", "")
        _bd_html = (
            '<div style="background:#0d1117;border:1px solid #1e293b;'
            'border-radius:12px;padding:16px 20px;margin-top:1rem;">'
            f'<h4 style="color:#e2e8f0;margin:0 0 12px 0;">'
            f'🔍 Desglose Score — <b style="color:{_lbl_c};">'
            f'{_tkr} {_tipo} → {_total}/100 ({_lbl})</b></h4>'
        )
        for _b in _bd:
            _ico = "✅" if _b["cumple"] else "❌"
            _pc = "#4ade80" if _b["cumple"] else "#f87171"
            _bd_html += (
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;padding:8px 0;'
                f'border-bottom:1px solid #1e293b;font-size:0.85rem;">'
                f'<span style="flex:2;">{_ico} '
                f'<b style="color:#e2e8f0;">{_b["criterio"]}</b></span>'
                f'<span style="flex:2;color:#94a3b8;">{_b["detalle"]}</span>'
                f'<span style="width:90px;text-align:right;color:{_pc};'
                f'font-weight:700;">+{_b["puntos"]}/{_b["maximo"]} pts</span>'
                f'</div>'
            )
        _bd_html += '</div>'
        st.markdown(_bd_html, unsafe_allow_html=True)


# ── Backtester fragment ─────────────────────────────────────────────────
@st.fragment
def _render_backtester_fragment() -> None:
    """Fragment: panel de Backtest Histórico (Fase 3).

    Re-ejecuta SÓLO al presionar '🔬 Ejecutar Backtest'.
    No re-ejecuta en cambios de filtros, selección de fila ni navegación de sidebar.
    """
    df_filtered: pd.DataFrame | None = st.session_state.get("_cs_bt_df")
    if df_filtered is None or df_filtered.empty:
        return

    # ────────────────────────────────────────────────────────────────────────
    #  FASE 3 — Panel de Backtesting Histórico
    # ────────────────────────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📊 Backtest Histórico (Fase 3)", expanded=False):
        st.markdown(
            '<p style="color:#94a3b8;font-size:0.85rem;">'
            "Simula los spreads actuales contra precios históricos del subyacente "
            "para estimar Win Rate, Profit Factor y Edge real.</p>",
            unsafe_allow_html=True,
        )
        _bt_days = st.slider(
            "Días de lookback", min_value=30, max_value=90, value=60, step=10,
            key="bt_lookback",
        )
        _bt_btn = st.button(
            "🔬 Ejecutar Backtest",
            type="secondary",
            use_container_width=True,
            key="bt_run_btn",
        )
        if _bt_btn:
            bt = Backtester(lookback_days=_bt_days)
            _bt_results_map: dict[str, BacktestResult] = {}
            spreads_by_ticker: dict[str, list[dict]] = {}
            for r in df_filtered.to_dict("records"):
                tk = r.get("Ticker", "")
                spreads_by_ticker.setdefault(tk, []).append(r)

            with st.spinner("Ejecutando backtest histórico..."):
                for tk, sp_list in spreads_by_ticker.items():
                    _bt_results_map[tk] = bt.run(tk, sp_list)

            st.session_state["bt_results"] = _bt_results_map

        _bt_results_map = st.session_state.get("bt_results")
        if _bt_results_map:
            _total_trades = sum(r.total_trades for r in _bt_results_map.values())
            _total_wins = sum(r.wins for r in _bt_results_map.values())
            _avg_wr = (_total_wins / _total_trades * 100.0) if _total_trades else 0
            _avg_pf = (
                sum(r.profit_factor for r in _bt_results_map.values() if r.total_trades > 0)
                / max(1, sum(1 for r in _bt_results_map.values() if r.total_trades > 0))
            )
            _avg_edge = (
                sum(r.edge for r in _bt_results_map.values() if r.total_trades > 0)
                / max(1, sum(1 for r in _bt_results_map.values() if r.total_trades > 0))
            )

            _wr_c = "#4ade80" if _avg_wr >= 65 else ("#facc15" if _avg_wr >= 50 else "#f87171")
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg,#0d1117,#1a1040);
                            border:2px solid #a78bfa;border-radius:12px;
                            padding:14px 20px;margin:0.5rem 0;">
                    <h4 style="color:#a78bfa;margin:0 0 8px 0;">
                        📊 Resultados del Backtest ({_total_trades} trades simulados)
                    </h4>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;color:#cbd5e1;">
                        <div>
                            <div style="color:#64748b;font-size:0.75rem;">WIN RATE</div>
                            <div style="color:{_wr_c};font-size:1.2rem;font-weight:700;">{_avg_wr:.1f}%</div>
                        </div>
                        <div>
                            <div style="color:#64748b;font-size:0.75rem;">PROFIT FACTOR</div>
                            <div style="color:#22d3ee;font-size:1.2rem;font-weight:700;">{_avg_pf:.2f}x</div>
                        </div>
                        <div>
                            <div style="color:#64748b;font-size:0.75rem;">EDGE vs POP</div>
                            <div style="color:{'#4ade80' if _avg_edge > 0 else '#f87171'};font-size:1.2rem;font-weight:700;">{_avg_edge:+.1f} pp</div>
                        </div>
                        <div>
                            <div style="color:#64748b;font-size:0.75rem;">TICKERS</div>
                            <div style="color:#94a3b8;font-size:1.2rem;font-weight:700;">{len(_bt_results_map)}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for tk, res in _bt_results_map.items():
                if res.total_trades == 0:
                    continue
                _tk_wr_c = "#4ade80" if res.win_rate >= 65 else ("#facc15" if res.win_rate >= 50 else "#f87171")
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #1e293b;border-radius:6px;'
                    f'padding:6px 12px;margin-bottom:4px;font-size:0.82rem;">'
                    f'<b style="color:#e2e8f0;">{tk}</b> — '
                    f'<span style="color:{_tk_wr_c};">WR: {res.win_rate:.1f}%</span> · '
                    f'<span style="color:#22d3ee;">PF: {res.profit_factor:.2f}x</span> · '
                    f'<span style="color:#94a3b8;">Trades: {res.total_trades}</span> · '
                    f'<span style="color:#94a3b8;">W/L: {res.wins}/{res.losses}</span> · '
                    f'<span style="color:{"#4ade80" if res.edge > 0 else "#f87171"};">Edge: {res.edge:+.1f}pp</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )



def render(**kwargs) -> None:
    """Renderiza la página de Venta de Prima — Credit Spread Scanner."""
    _cs_service = get_container().credit_spread_service

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
              <li>✅ <b style="color:#22c55e;">Crédito ≥ 15% del ancho</b> — relación riesgo/beneficio aceptable</li>
              <li>✅ <b style="color:#22c55e;">Riesgo ≤ 5% de la cuenta</b> — proteger el capital</li>
            </ul>
            <div style="margin-top:0.5rem;padding:6px 10px;background:#0d1117;border-left:3px solid #00ff88;border-radius:4px;">
              <b style="color:#00ff88;">Gestión recomendada:</b><br>
              🎯 Tomar ganancias al <b>50%</b> del crédito recibido<br>
              🛑 Salir si la pérdida llega al <b>100%</b> del crédito<br>
              ⏰ Cerrar a los <b>21 DTE</b> si la posición sigue abierta
            </div>
            <div style="margin-top:0.7rem;padding:6px 10px;background:#0d1117;border-left:3px solid #60a5fa;border-radius:4px;">
              <b style="color:#60a5fa;">Métricas Fase 1 (nuevas):</b><br>
              📌 <b>PoT Short</b> — Probability of Touch del strike vendido (≈ 2×|Δ|). PoT bajo = menor riesgo.<br>
              📌 <b>Δ Neto</b> — Delta neto del spread (|Δ short| − |Δ long|). Más bajo = spread más neutral.<br>
              📌 <b>EV Ajustado</b> — Expected Value como % del riesgo máximo. Positivo = edge estadístico.<br>
              📌 <b>⭐ Score Final</b> — Optimizado Fase 3: 18% Income + 14% Opp + 13% Anti-PoT + 11% ΔN + 12% EV Real + 10% Anti-Γ + 12% Liq + 10% θ + 6% Surface Edge
            </div>
            <div style="margin-top:0.7rem;padding:6px 10px;background:#0d1117;border-left:3px solid #a78bfa;border-radius:4px;">
              <b style="color:#a78bfa;">Métricas Fase 3 (nivel institucional):</b><br>
              📌 <b>EV Real Adj</b> — EV calculado con la IV específica del strike (no genérica). Refleja la surface real.<br>
              📌 <b>Surface Edge</b> — Diferencia entre la probabilidad implícita en la surface vs la POP genérica. Positivo = edge a favor.<br>
              📌 <b>Backtest</b> — Simulación histórica: ¿cuántos spreads similares hubieran ganado en los últimos 60 días?
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Reglas de Gestión (compacto, siempre visible) ────────────────────
    with st.expander("📋 Reglas de Gestión (mostrar al usuario)", expanded=False):
        st.markdown(
            """
            <div style="font-size:0.88rem;line-height:2;color:#cbd5e1;">
              <div style="padding:5px 0;">
                <span style="color:#22c55e;font-weight:700;">✅ Take Profit:</span>
                Cerrar al <b style="color:#00ff88;">50%</b> del crédito recibido
              </div>
              <div style="padding:5px 0;">
                <span style="color:#ef4444;font-weight:700;">❌ Stop Loss:</span>
                Cerrar al <b style="color:#ef4444;">200%</b> del crédito recibido
              </div>
              <div style="padding:5px 0;">
                <span style="color:#fbbf24;font-weight:700;">⏰ Gestión de tiempo:</span>
                Si quedan <b style="color:#fbbf24;">21 DTE</b>, cerrar si no ha llegado al profit
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Filtros en la página principal ───────────────────────────────────
    with st.expander("⚙️ Filtros — Venta de Prima", expanded=True):
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
        filter_by_ev = st.checkbox(
            "🧮 Solo spreads con EV positivo (EV > $0)",
            value=True,
            help=(
                "Expected Value: EV = (POP × Crédito) − ((1−POP) × Pérdida).\n"
                "Si EV > $0 el spread tiene edge matemático real a largo plazo. "
                "Desactiva para ver también spreads sin edge."
            ),
            key="cs_filter_by_ev",
        )
        st.markdown("---")
        st.markdown("#### 🛡️ Modo Estricto — Filtros Individuales")
        with st.expander("Personaliza las 9 reglas (todas activas por defecto)", expanded=False):
            _r1 = st.checkbox("R1: Whitelist + Precio>$20 + Vol>1M acciones", value=True, key="cs_r1")
            _r2 = st.checkbox("R2: IV Rank ≥ 30%", value=True, key="cs_r2")
            _r3 = st.checkbox("R3: DTE entre 25–45 días", value=True, key="cs_r3")
            _r4 = st.checkbox("R4: Delta vendido 0.10–0.20", value=True, key="cs_r4")
            _r5 = st.checkbox("R5: Dirección alineada con tendencia", value=True, key="cs_r5")
            _r6 = st.checkbox("R6: Ancho del spread: 2, 3 o 5 puntos", value=True, key="cs_r6")
            _r7 = st.checkbox("R7: Crédito ≥ 15% del ancho", value=True, key="cs_r7")
            _r8 = st.checkbox("R8: Distancia del strike ≥ 3%", value=True, key="cs_r8")
            _r9 = st.checkbox("R9: Liquidez (OI>500, Vol>100, Bid-Ask≤10%)", value=True, key="cs_r9")
        strict_rules = {
            "r1_whitelist": _r1, "r2_iv_rank": _r2, "r3_dte": _r3,
            "r4_delta": _r4, "r5_trend": _r5, "r6_width": _r6,
            "r7_credit_pct": _r7, "r8_distance": _r8, "r9_liquidity": _r9,
        }
        st.markdown("---")
        st.markdown("#### 💰 Cuenta")
        account_size = st.number_input(
            "Tamaño de cuenta ($)",
            min_value=1_000,
            max_value=1_000_000,
            value=int(ALERT_DEFAULT_ACCOUNT_SIZE),
            step=1_000,
            help="Se usa para la Regla 8: riesgo máx por trade ≤ 5% de tu cuenta.",
            key="cs_account_size",
        )
        st.markdown("---")

    # ── Indicador de datos pre-cargados en background ──────────────────
    from utils.background_updater import read_fast_data
    _cached_count = sum(1 for t in selected_tickers if read_fast_data(t))
    if _cached_count > 0:
        st.caption(
            f"📡 {_cached_count}/{len(selected_tickers)} tickers con datos "
            f"pre-cargados en background"
        )

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
            st.warning("⚠️ Selecciona al menos un ticker en el panel de filtros.")
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
            df, ticker_indicators = _cs_service.scan(
                tickers=selected_tickers,
                min_pop=min_pop_pct / 100.0,
                max_dte=max_dte,
                min_credit=min_credit,
                strict_rules=strict_rules,
                account_size=account_size,
                progress_callback=_progress_cb,
            )

        progress_bar.empty()
        status_text.empty()

        st.session_state["cs_results"] = df
        st.session_state["cs_ticker_indicators"] = ticker_indicators
        st.session_state["cs_scan_time"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # ── Generar alertas (10 reglas) via service ───────────────────────
        alerts_df = _cs_service.get_alerts(df, account_size=account_size)
        st.session_state["cs_alerts"] = alerts_df

        # ── Guardar snapshot de filtros para mostrar al volver a la página ─
        save_page_data("cs", {
            "filters": {
                "tickers": selected_tickers,
                "min_pop": min_pop_pct,
                "max_dte": max_dte,
                "min_credit": min_credit,
                "tipo": tipo_filter,
                "min_iv_rank": min_iv_rank,
                "trend_align": filter_by_trend,
                "filter_ev": filter_by_ev,
                "strict": strict_mode,
                "account_size": account_size,
            }
        })

    # ── Mostrar resultados ───────────────────────────────────────────────
    # Leer desde session_state (persistido entre navegaciones de página)
    _cs_state = load_page_data("cs", ["results", "scan_time", "ticker_indicators", "alerts"])
    df: pd.DataFrame | None = _cs_state["results"]
    scan_time: str | None = _cs_state["scan_time"]
    ticker_indicators: dict = _cs_state["ticker_indicators"] or {}
    alerts_df: pd.DataFrame | None = _cs_state["alerts"]

    # ────────────────────────────────────────────────────────────────────────
    #  SISTEMA DE ALERTAS — Panel de alertas (10 reglas)
    # ────────────────────────────────────────────────────────────────────────
    if df is not None and not df.empty:
        if alerts_df is not None and not alerts_df.empty:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg,#0d1f12,#132a13);
                            border:2px solid #22c55e;border-radius:14px;
                            padding:1.2rem 1.5rem;margin-bottom:1.5rem;">
                    <h3 style="color:#00ff88;margin:0 0 0.3rem 0;">
                        🚨 Sistema de Alertas — {len(alerts_df)} Estrategia{"s" if len(alerts_df) != 1 else ""} Lista{"s" if len(alerts_df) != 1 else ""}
                    </h3>
                    <p style="color:#94a3b8;margin:0;font-size:0.82rem;">
                        Cumplen las <b style="color:#22c55e;">10 reglas obligatorias</b> de seguridad.
                        Riesgo máx por trade ≤ 5% de cuenta (${account_size:,.0f}).
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for a_idx, (_, a_row) in enumerate(alerts_df.iterrows()):
                _a_tk = a_row.get("Ticker", "")
                _a_tipo = a_row.get("Tipo", "")
                _a_spot = a_row.get("Spot", 0)
                _a_sv = a_row.get("Strike Vendido", 0)
                _a_delta = abs(a_row.get("Delta Vendido", 0))
                _a_ivr = a_row.get("IV Rank", 0)
                _a_cr = a_row.get("Crédito", 0)
                _a_risk = a_row.get("Riesgo Máx", 0)
                _a_ret = a_row.get("Retorno %", 0)
                _a_pop = a_row.get("POP %", 0)
                _a_sc = a_row.get("Strike Comprado", 0)
                _a_dte = a_row.get("DTE", 0)
                _a_dist = a_row.get("Dist Strike %", 0)
                _a_opp = a_row.get("Score Oportunidad", 0)
                _opt = "Put" if "Put" in _a_tipo else "Call"
                _border_c = "#22c55e" if "Put" in _a_tipo else "#ef4444"

                st.markdown(
                    f"""
                    <div style="background:#0d1117;border:1px solid {_border_c};
                                border-left:4px solid {_border_c};
                                border-radius:10px;padding:14px 18px;
                                margin-bottom:10px;font-size:0.86rem;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <b style="color:{_border_c};font-size:1.05rem;">
                                {_a_tk} – {_opt} Credit Spread
                            </b>
                            <span style="background:rgba(0,255,136,0.1);color:#00ff88;
                                        padding:3px 10px;border-radius:12px;
                                        font-size:0.75rem;font-weight:700;">
                                Score: {_a_opp:.0f}/100
                            </span>
                        </div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;color:#cbd5e1;">
                            <span>Precio: <b style="color:white;">${_a_spot:.2f}</b></span>
                            <span>IV Rank: <b style="color:#fbbf24;">{_a_ivr:.0f}%</b></span>
                            <span>Strike vendido: <b style="color:white;">{_a_sv:.1f}</b></span>
                            <span>Strike comprado: <b style="color:white;">{_a_sc:.1f}</b></span>
                            <span>Delta: <b style="color:white;">{_a_delta:.2f}</b></span>
                            <span>DTE: <b style="color:white;">{_a_dte}d</b></span>
                            <span>Crédito: <b style="color:#00ff88;">${_a_cr:.2f}</b></span>
                            <span>Riesgo: <b style="color:#ef4444;">${_a_risk:.2f}</b></span>
                            <span>Retorno: <b style="color:#00ff88;">{_a_ret:.1f}%</b></span>
                            <span>Probabilidad: <b style="color:#22d3ee;">{_a_pop:.0f}%</b></span>
                            <span>Distancia: <b style="color:white;">{_a_dist:.1f}%</b></span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Botón "Estrategia lista para vender prima"
                if st.button(
                    f"✅ Estrategia lista para vender prima — {_a_tk} {_a_sv:.0f}/{_a_sc:.0f} {_opt}",
                    key=f"alert_save_{a_idx}",
                    use_container_width=True,
                ):
                    fav_entry = {
                        "ticker": _a_tk,
                        "tipo": _a_tipo,
                        "spot": _a_spot,
                        "strike_vendido": _a_sv,
                        "strike_comprado": _a_sc,
                        "dte": _a_dte,
                        "delta": round(_a_delta, 3),
                        "credito": _a_cr,
                        "riesgo": _a_risk,
                        "retorno_pct": _a_ret,
                        "pop_pct": _a_pop,
                        "iv_rank": _a_ivr,
                        "dist_pct": _a_dist,
                        "score": _a_opp,
                        "saved_at": datetime.now().isoformat(),
                        "source": "alert_10_rules",
                    }
                    favs = st.session_state.get("favoritos", [])
                    # Evitar duplicados
                    dup = any(
                        f.get("ticker") == _a_tk
                        and f.get("strike_vendido") == _a_sv
                        and f.get("strike_comprado") == _a_sc
                        for f in favs
                    )
                    if dup:
                        st.info(f"ℹ️ {_a_tk} {_a_sv}/{_a_sc} ya está en favoritos.")
                    else:
                        favs.append(fav_entry)
                        st.session_state["favoritos"] = favs
                        # Sync a Supabase via service layer
                        try:
                            _container = get_container()
                            _u = _container.auth.get_current_user()
                            if _u:
                                _container.auth.save_user_data(_u["id"], "favoritos", favs)
                        except Exception:
                            pass
                        st.success(
                            f"⭐ **{_a_tk} {_a_sv}/{_a_sc} {_opt}** guardado en Favoritos."
                        )

            st.markdown("---")

        elif alerts_df is not None and alerts_df.empty and df is not None and not df.empty:
            st.info(
                "🚨 **No hay alertas disponibles** — ninguna oportunidad cumple "
                "todas las 10 reglas de seguridad.\n\n"
                "Los spreads que aparecen en la tabla cumplen los filtros básicos, "
                "pero no pasan la verificación completa (tendencia, tamaño de cuenta, etc.)."
            )
    if df is None or df.empty:
        if df is not None:
            st.warning(
                "🛡️ **No se encontraron oportunidades que cumplan TODOS los "
                "criterios de seguridad.**\n\n"
                "Esto significa que el mercado actual no ofrece spreads de alta "
                "calidad según los 9 filtros estrictos. "
                "Puedes desactivar el **Modo Estricto** en el sidebar para ver "
                "todas las oportunidades sin filtrar, o ajustar los parámetros."
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

    # ── Calcular EV (Expected Value) ─────────────────────────────────────
    df_filtered = enrich_dataframe_with_ev(df_filtered)

    # Filtro EV positivo
    if filter_by_ev and "EV $" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["EV $"] > 0]

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
        _trend_colors = {"Alcista": COLORS["positive"], "Bajista": COLORS["negative"], "Neutral": COLORS["muted"]}
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

    # ── EV Hero Card — Edge matemático del conjunto de spreads ───────────
    if "EV $" in df_filtered.columns:
        _n_ev_pos = int((df_filtered["EV $"] > 0).sum())
        _n_total = len(df_filtered)
        _best_ev_d = df_filtered["EV $"].max() if _n_total else 0
        _best_ev_p = df_filtered["EV %"].max() if _n_total else 0
        _avg_ev_d = df_filtered.loc[df_filtered["EV $"] > 0, "EV $"].mean() if _n_ev_pos else 0

        _ev_color = "#00ff88" if _best_ev_d >= 80 else ("#fbbf24" if _best_ev_d > 0 else "#ef4444")
        _ev_icon = "✅" if _best_ev_d > 0 else "❌"
        _ev_badge = ev_label(_best_ev_d)

        ev_c1, ev_c2, ev_c3 = st.columns([2, 1, 1])
        with ev_c1:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg,#0d1117,#0f2430);
                            border:2px solid {_ev_color};border-radius:12px;
                            padding:12px 20px;display:flex;align-items:center;gap:16px;">
                    <span style="font-size:2.2rem;">{_ev_icon}</span>
                    <div>
                        <div style="color:#94a3b8;font-size:0.75rem;letter-spacing:.06em;">
                            MEJOR EV POR CONTRATO
                        </div>
                        <div style="color:{_ev_color};font-size:1.6rem;font-weight:800;
                                    line-height:1.2;">
                            ${_best_ev_d:+.2f}
                            <span style="font-size:0.85rem;font-weight:600;
                                        margin-left:8px;color:#94a3b8;">
                                {_ev_badge}
                            </span>
                        </div>
                        <div style="color:#64748b;font-size:0.75rem;margin-top:2px;">
                            EV% del capital en riesgo: <b style="color:{_ev_color};">{_best_ev_p:+.1f}%</b>
                            &nbsp;·&nbsp;
                            {_n_ev_pos}/{_n_total} spreads con edge positivo
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with ev_c2:
            st.metric(
                label="💚 EV Promedio (positivos)",
                value=f"${_avg_ev_d:+.2f}",
                help="Promedio del EV entre los spreads con EV > $0",
            )
        with ev_c3:
            st.metric(
                label="🎯 Spreads con Edge",
                value=f"{_n_ev_pos}/{_n_total}",
                delta=f"{(_n_ev_pos/_n_total*100):.0f}% del total" if _n_total else "—",
            )
        st.markdown("")

    # ── Hero Cards — Score Final + Score Oportunidad ──────────────────────
    _hero_col1, _hero_col2 = st.columns(2)

    # Score Final (Fase 1+2) — card principal
    with _hero_col1:
        _best_ns = (
            df_filtered["Score Final"].max()
            if "Score Final" in df_filtered.columns else 0
        )
        _ns_label = "Excelente" if _best_ns >= 75 else ("Buena" if _best_ns >= 55 else "Baja")
        _ns_color = "#4ade80" if _best_ns >= 75 else ("#facc15" if _best_ns >= 55 else "#f87171")
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#0d1117,#0f2a1e);
                        border:2px solid {_ns_color};border-radius:12px;
                        padding:12px 20px;margin-bottom:1rem;display:flex;
                        align-items:center;gap:16px;">
                <span style="font-size:2rem;">⭐</span>
                <div>
                    <div style="color:#94a3b8;font-size:0.78rem;letter-spacing:.05em;">
                        MEJOR SCORE FINAL (PONDERADO)
                    </div>
                    <div style="color:{_ns_color};font-size:1.5rem;font-weight:800;">
                        {_best_ns:.1f}/100
                        <span style="font-size:0.9rem;font-weight:600;margin-left:8px;">
                            ({_ns_label})
                        </span>
                    </div>
                    <div style="color:#64748b;font-size:0.7rem;margin-top:2px;">
                        18% Inc · 14% Opp · 13% PoT · 11% ΔN · 12% EV Real · 10% Γ · 12% Liq · 10% θ · 6% Surface
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Score de Oportunidad — card secundario
    with _hero_col2:
        _best_opp = (
            df_filtered["Score Oportunidad"].max()
            if "Score Oportunidad" in df_filtered.columns else 0
        )
        _best_opp_label = "Excelente" if _best_opp >= 80 else "Buena"
        _best_opp_color = "#00ff00" if _best_opp >= 80 else "#ffaa00"
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#0d1117,#1a2332);
                        border:2px solid {_best_opp_color};border-radius:12px;
                        padding:12px 20px;margin-bottom:1rem;display:flex;
                        align-items:center;gap:16px;">
                <span style="font-size:2rem;">🏆</span>
                <div>
                    <div style="color:#94a3b8;font-size:0.78rem;">MEJOR SCORE DE OPORTUNIDAD</div>
                    <div style="color:{_best_opp_color};font-size:1.5rem;font-weight:800;">
                        {_best_opp:.0f}/100
                        <span style="font-size:0.9rem;font-weight:600;margin-left:8px;">
                            ({_best_opp_label})
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Métricas rápidas (ampliadas Fase 1) ───────────────────────────────
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("Mejor Retorno %", f"{df_filtered['Retorno %'].max():.1f}%")
    with mc2:
        st.metric("POP Promedio", f"{df_filtered['POP %'].mean():.1f}%")
    with mc3:
        st.metric("Crédito Promedio", f"${df_filtered['Crédito'].mean():.2f}")
    with mc4:
        st.metric("DTE Promedio", f"{df_filtered['DTE'].mean():.0f}d")

    mc5, mc6, mc7, mc8 = st.columns(4)
    with mc5:
        _avg_pot = df_filtered["PoT Short"].mean() if "PoT Short" in df_filtered.columns else 0
        st.metric("Ø PoT Short", f"{_avg_pot:.1f}%",
                  help="Prob. de que el precio toque el strike vendido antes del vencimiento")
    with mc6:
        _avg_dn = df_filtered["Delta Neto"].mean() if "Delta Neto" in df_filtered.columns else 0
        st.metric("Ø Δ Neto", f"{_avg_dn:.3f}")
    with mc7:
        _avg_eva = df_filtered["EV Ajustado"].mean() if "EV Ajustado" in df_filtered.columns else 0
        st.metric("Ø EV Ajustado", f"{_avg_eva:+.1f}%")
    with mc8:
        _avg_ns = df_filtered["Score Final"].mean() if "Score Final" in df_filtered.columns else 0
        st.metric("Ø Score Final", f"{_avg_ns:.1f}")

    # ── Tabla AgGrid (interactive, sortable, filterable) ─────────────────
    display_cols = [
        "Ticker", "Tipo", "Score Final", "Score Oportunidad", "Nivel",
        "Income Score", "Calidad", "Spot",
        "Strike Vendido", "Strike Comprado",
        "DTE", "Delta Vendido", "Delta Neto", "PoT Short",
        "Gamma Neto", "Theta Neto", "Decay 7d",
        "POP %", "Prob OTM %", "Crédito",
        "Riesgo Máx", "EV Ajustado", "EV Real Adj", "Surface Edge",
        "EV $", "EV %", "Retorno %", "Dist Strike %", "IV %",
        "IV Rank", "IV Pctil", "Tendencia",
        "OI Short", "Vol Short", "Liq Score",
        "Liquidez", "Volumen", "OI", "Bid-Ask",
    ]
    display_cols = [c for c in display_cols if c in df_filtered.columns]
    df_show = df_filtered[display_cols].reset_index(drop=True)

    # ── Fragment: AgGrid + desglose de score ─────────────────────────────
    st.session_state["_cs_aggrid_df"] = df_show
    _render_aggrid_fragment()


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
                _iscore = row.get("Income Score", 0)
                _nscore = row.get("Score Final", 0)
                _pot = row.get("PoT Short", 0)
                _dn = row.get("Delta Neto", 0)
                _eva = row.get("EV Ajustado", 0)
                _ev_d = row.get("EV $", 0)
                _ev_p = row.get("EV %", 0)
                _gn = row.get("Gamma Neto", 0)
                _liq = row.get("Liq Score", 0)
                _d7 = row.get("Decay 7d", 0)
                _ivr_c = "#00ff88" if _ivr >= 40 else "#64748b"
                _ns_c = "#4ade80" if _nscore >= 75 else ("#facc15" if _nscore >= 55 else "#f87171")
                _pot_c = "#4ade80" if _pot < 25 else ("#facc15" if _pot < 40 else "#f87171")
                _ev_c = "#4ade80" if _ev_d >= 80 else ("#22d3ee" if _ev_d > 0 else "#f87171")
                _liq_c = "#4ade80" if _liq >= 70 else ("#facc15" if _liq >= 40 else "#f87171")
                _ev_badge = ev_label(_ev_d)
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #1e3a2f;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b style="color:#22c55e;">{row["Ticker"]}</b> '
                    f'<span style="color:#94a3b8;">Sell {row["Strike Vendido"]}P / '
                    f'Buy {row["Strike Comprado"]}P</span> '
                    f'<span style="color:#64748b;">({row["DTE"]}d)</span>'
                    f'<span style="float:right;color:{_ns_c};font-weight:700;">⭐ {_nscore:.1f}</span><br>'
                    f'<span style="color:#00ff88;">Ret: {row["Retorno %"]:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">POP: {row["POP %"]:.0f}%</span> · '
                    f'<span style="color:#fbbf24;">Cr: ${row["Crédito"]:.2f}</span> · '
                    f'<span style="color:#64748b;">Δ {row["Delta Vendido"]:.2f}</span><br>'
                    f'<span style="color:{_pot_c};">PoT: {_pot:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">Δ Neto: {_dn:.3f}</span> · '
                    f'<span style="color:#64748b;">Dist: {_dist:.1f}%</span> · '
                    f'<span style="color:{_ivr_c};">IVR: {_ivr:.0f}%</span> · '
                    f'<span style="color:#64748b;">{_trend}</span><br>'
                    f'<span style="color:{_ev_c};font-weight:700;">🧮 EV: ${_ev_d:+.2f}/c '
                    f'({_ev_p:+.1f}%) | EV Aj: {_eva:+.1f}% — {_ev_badge}</span><br>'
                    f'<span style="color:#94a3b8;">Γ: {_gn:.4f}</span> · '
                    f'<span style="color:#64748b;">θ 7d: ${_d7:.2f}</span> · '
                    f'<span style="color:{_liq_c};">Liq: {_liq:.0f}</span>'
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
                _iscore = row.get("Income Score", 0)
                _nscore = row.get("Score Final", 0)
                _pot = row.get("PoT Short", 0)
                _dn = row.get("Delta Neto", 0)
                _eva = row.get("EV Ajustado", 0)
                _ev_d = row.get("EV $", 0)
                _ev_p = row.get("EV %", 0)
                _gn = row.get("Gamma Neto", 0)
                _liq = row.get("Liq Score", 0)
                _d7 = row.get("Decay 7d", 0)
                _ivr_c = "#00ff88" if _ivr >= 40 else "#64748b"
                _ns_c = "#4ade80" if _nscore >= 75 else ("#facc15" if _nscore >= 55 else "#f87171")
                _pot_c = "#4ade80" if _pot < 25 else ("#facc15" if _pot < 40 else "#f87171")
                _ev_c = "#4ade80" if _ev_d >= 80 else ("#22d3ee" if _ev_d > 0 else "#f87171")
                _liq_c = "#4ade80" if _liq >= 70 else ("#facc15" if _liq >= 40 else "#f87171")
                _ev_badge = ev_label(_ev_d)
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #3a1e1e;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b style="color:#ef4444;">{row["Ticker"]}</b> '
                    f'<span style="color:#94a3b8;">Sell {row["Strike Vendido"]}C / '
                    f'Buy {row["Strike Comprado"]}C</span> '
                    f'<span style="color:#64748b;">({row["DTE"]}d)</span>'
                    f'<span style="float:right;color:{_ns_c};font-weight:700;">⭐ {_nscore:.1f}</span><br>'
                    f'<span style="color:#00ff88;">Ret: {row["Retorno %"]:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">POP: {row["POP %"]:.0f}%</span> · '
                    f'<span style="color:#fbbf24;">Cr: ${row["Crédito"]:.2f}</span> · '
                    f'<span style="color:#64748b;">Δ {row["Delta Vendido"]:.2f}</span><br>'
                    f'<span style="color:{_pot_c};">PoT: {_pot:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">Δ Neto: {_dn:.3f}</span> · '
                    f'<span style="color:#64748b;">Dist: {_dist:.1f}%</span> · '
                    f'<span style="color:{_ivr_c};">IVR: {_ivr:.0f}%</span> · '
                    f'<span style="color:#64748b;">{_trend}</span><br>'
                    f'<span style="color:{_ev_c};font-weight:700;">🧮 EV: ${_ev_d:+.2f}/c '
                    f'({_ev_p:+.1f}%) | EV Aj: {_eva:+.1f}% — {_ev_badge}</span><br>'
                    f'<span style="color:#94a3b8;">Γ: {_gn:.4f}</span> · '
                    f'<span style="color:#64748b;">θ 7d: ${_d7:.2f}</span> · '
                    f'<span style="color:{_liq_c};">Liq: {_liq:.0f}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin resultados")

    # ── Fragment: backtester histórico ──────────────────────────────────────
    st.session_state["_cs_bt_df"] = df_filtered
    _render_backtester_fragment()
