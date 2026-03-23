# -*- coding: utf-8 -*-
"""
AgGrid configuration module for the Credit Spread Scanner table.

Centralises all JsCode cell-style callbacks, the dark-theme CSS dict and the
GridOptionsBuilder setup.  Extracted from page_modules/credit_spread_page.py
to keep the page module focused on Streamlit layout logic only.

Usage:
    from ui.components.aggrid_credit_spreads import build_aggrid_options

    grid_options, css = build_aggrid_options(df_show)
    grid_response = AgGrid(df_show, gridOptions=grid_options, custom_css=css, ...)
"""
from __future__ import annotations

import pandas as pd
from st_aggrid import GridOptionsBuilder, JsCode


# ── JS cell-style callbacks ───────────────────────────────────────────────────

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

_JS_UNIFIED_SCORE_STYLE = JsCode("""
function(params) {
    if (params.value >= 80) return {'backgroundColor': '#14532d', 'color': '#86efac', 'fontWeight': '700'};
    if (params.value >= 65) return {'backgroundColor': '#78350f', 'color': '#fde68a', 'fontWeight': '600'};
    return {'backgroundColor': '#3f1219', 'color': '#fca5a5', 'fontWeight': '600'};
}
""")

_JS_RISK_PROFILE_STYLE = JsCode("""
function(params) {
    if (params.value === 'Conservadora') return {'color': '#4ade80', 'fontWeight': '700'};
    if (params.value === 'Balanceada') return {'color': '#fbbf24', 'fontWeight': '600'};
    return {'color': '#f87171', 'fontWeight': '700'};
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


# ── Dark-theme CSS for AgGrid ─────────────────────────────────────────────────

AGGRID_DARK_CSS: dict[str, dict[str, str]] = {
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


# ── GridOptionsBuilder factory ────────────────────────────────────────────────

def build_aggrid_options(df: pd.DataFrame) -> tuple[dict, dict]:
    """Build AgGrid grid options and dark-theme CSS for the credit spread table.

    Configures all columns with appropriate formatters, cell styles and widths.
    Returns the built options dict and the CSS dict ready to pass to
    :func:`st_aggrid.AgGrid`.

    Args:
        df: The credit spreads DataFrame (as returned by the scanner).

    Returns:
        ``(grid_options, AGGRID_DARK_CSS)``
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        wrapHeaderText=True,
        autoHeaderHeight=True,
    )

    # ── Identification ──────────────────────────────────────────────────────
    gb.configure_column("Ticker", pinned="left", width=80)
    gb.configure_column("Tipo", width=95, cellStyle=_JS_TIPO_STYLE)

    # ── Score Final (Fase 1+2) ──────────────────────────────────────────────
    gb.configure_column(
        "Score Final",
        headerName="⭐ Score Final",
        width=130,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v >= 75) return {color:'#4ade80',fontWeight:'bold'};
            if (v >= 55) return {color:'#facc15'};
            return {color:'#f87171'};
        }"""),
        sort="desc",
        valueFormatter="x.toFixed(1)",
    )
    gb.configure_column(
        "Score Oportunidad",
        headerName="Score de Oportunidad",
        width=155,
        type=["numericColumn"],
        cellStyle=_JS_OPP_SCORE_STYLE,
        sort="desc",
        valueFormatter="x.toFixed(0)",
    )
    gb.configure_column(
        "Score Unificado",
        headerName="🧠 Score Unificado",
        width=150,
        type=["numericColumn"],
        cellStyle=_JS_UNIFIED_SCORE_STYLE,
        sort="desc",
        valueFormatter="x.toFixed(1)",
    )
    gb.configure_column("Perfil Riesgo", headerName="Perfil Riesgo", width=120, cellStyle=_JS_RISK_PROFILE_STYLE)
    gb.configure_column("Nivel", headerName="Nivel", width=100, cellStyle=_JS_OPP_LABEL_STYLE)
    gb.configure_column(
        "Income Score",
        headerName="Income Score",
        width=115,
        type=["numericColumn"],
        cellStyle=_JS_INCOME_SCORE_STYLE,
        valueFormatter="x.toFixed(0)",
    )
    gb.configure_column("Calidad", headerName="Calidad", width=130, cellStyle=_JS_CALIDAD_STYLE)

    # ── Strikes / DTE ───────────────────────────────────────────────────────
    gb.configure_column("Spot", width=80, type=["numericColumn"], valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column("Strike Vendido", width=100, type=["numericColumn"], valueFormatter="x.toFixed(1)")
    gb.configure_column("Strike Comprado", width=110, type=["numericColumn"], valueFormatter="x.toFixed(1)")
    gb.configure_column("DTE", width=60, type=["numericColumn"])
    gb.configure_column(
        "Delta Vendido",
        width=95,
        type=["numericColumn"],
        valueFormatter="x.toFixed(3)",
    )

    # ── Delta Neto + PoT Short (Fase 1) ────────────────────────────────────
    gb.configure_column(
        "Delta Neto",
        headerName="Δ Neto",
        width=85,
        type=["numericColumn"],
        valueFormatter="x.toFixed(4)",
    )
    gb.configure_column(
        "PoT Short",
        headerName="PoT Short",
        width=100,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v >= 40) return {color:'#f87171',fontWeight:'bold'};
            if (v >= 25) return {color:'#facc15'};
            return {color:'#4ade80'};
        }"""),
        valueFormatter="x.toFixed(1) + '%'",
    )

    # ── Fase 2: Gamma / Theta / Decay ──────────────────────────────────────
    gb.configure_column(
        "Gamma Neto",
        headerName="Γ Neto",
        width=85,
        type=["numericColumn"],
        valueFormatter="x.toFixed(4)",
    )
    gb.configure_column(
        "Theta Neto",
        headerName="θ Neto",
        width=85,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v > 0) return {color:'#4ade80'};
            return {color:'#f87171'};
        }"""),
        valueFormatter="x.toFixed(3)",
    )
    gb.configure_column(
        "Decay 7d",
        headerName="Decay 7d",
        width=90,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v > 0.5) return {color:'#4ade80',fontWeight:'bold'};
            if (v > 0) return {color:'#facc15'};
            return {color:'#f87171'};
        }"""),
        valueFormatter="'$' + x.toFixed(2)",
    )

    # ── POP / Prob ──────────────────────────────────────────────────────────
    gb.configure_column(
        "POP %",
        width=75,
        type=["numericColumn"],
        cellStyle=_JS_POP_STYLE,
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column("Explicacion Ejecutiva", width=320)
    gb.configure_column("Senales Positivas", width=320)
    gb.configure_column("Senales Negativas", width=320)
    gb.configure_column("Riesgos Clave", width=300)
    gb.configure_column(
        "Prob OTM %",
        width=95,
        type=["numericColumn"],
        cellStyle=_JS_POP_STYLE,
        valueFormatter="x.toFixed(1) + '%'",
    )

    # ── Credit / Risk ───────────────────────────────────────────────────────
    gb.configure_column("Crédito", width=80, type=["numericColumn"], valueFormatter="'$' + x.toFixed(2)")
    gb.configure_column(
        "Riesgo Máx",
        width=95,
        type=["numericColumn"],
        cellStyle=_JS_RISK_STYLE,
        valueFormatter="'$' + x.toFixed(2)",
    )

    # ── EV Ajustado (Fase 1) ────────────────────────────────────────────────
    gb.configure_column(
        "EV Ajustado",
        headerName="EV Aj. %",
        width=100,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v > 5)  return {color:'#4ade80',fontWeight:'bold'};
            if (v > 0)  return {color:'#facc15'};
            return {color:'#f87171'};
        }"""),
        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'",
    )

    # ── Fase 3: EV Real Adj + Surface Edge ─────────────────────────────────
    gb.configure_column(
        "EV Real Adj",
        headerName="EV Real %",
        width=100,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v > 5)  return {color:'#a78bfa',fontWeight:'bold'};
            if (v > 0)  return {color:'#facc15'};
            return {color:'#f87171'};
        }"""),
        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'",
    )
    gb.configure_column(
        "Surface Edge",
        headerName="Srf Edge %",
        width=100,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v > 3)  return {color:'#4ade80',fontWeight:'bold'};
            if (v > 0)  return {color:'#22d3ee'};
            return {color:'#f87171'};
        }"""),
        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'",
    )

    # ── Retorno / Distance ──────────────────────────────────────────────────
    gb.configure_column(
        "Retorno %",
        width=95,
        type=["numericColumn"],
        cellStyle=_JS_RETORNO_STYLE,
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column(
        "Dist Strike %",
        headerName="Dist Strike %",
        width=105,
        type=["numericColumn"],
        cellStyle=_JS_DIST_STYLE,
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column("IV %", width=70, type=["numericColumn"], valueFormatter="x.toFixed(1) + '%'")

    # ── Debug / validation columns ──────────────────────────────────────────
    gb.configure_column(
        "PoT 2Δ Approx",
        headerName="PoT 2Δ",
        width=90,
        type=["numericColumn"],
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column(
        "PoT Skew Adj",
        headerName="PoT Skew+",
        width=90,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v > 2) return {color:'#fb923c',fontWeight:'bold'};
            if (v > 0) return {color:'#facc15'};
            return {color:'#94a3b8'};
        }"""),
        valueFormatter="v => v > 0 ? '+' + v.toFixed(2) + 'pp' : '0'",
    )
    gb.configure_column(
        "POP Breakeven %",
        headerName="POP BE %",
        width=100,
        type=["numericColumn"],
        cellStyle=_JS_POP_STYLE,
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column(
        "IV Short %",
        headerName="IV Short",
        width=85,
        type=["numericColumn"],
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column(
        "IV Long %",
        headerName="IV Long",
        width=85,
        type=["numericColumn"],
        valueFormatter="x.toFixed(1) + '%'",
    )
    gb.configure_column(
        "Breakeven",
        headerName="Breakeven",
        width=95,
        type=["numericColumn"],
        valueFormatter="'$' + x.toFixed(2)",
    )

    # ── IV Rank / Percentile ────────────────────────────────────────────────
    gb.configure_column(
        "IV Rank",
        width=80,
        type=["numericColumn"],
        cellStyle=_JS_IVRANK_STYLE,
        valueFormatter="x.toFixed(0) + '%'",
    )
    gb.configure_column(
        "IV Pctil",
        headerName="IV Pctil",
        width=80,
        type=["numericColumn"],
        cellStyle=_JS_IVRANK_STYLE,
        valueFormatter="x.toFixed(0) + '%'",
    )
    gb.configure_column("Tendencia", width=90)

    # ── Fase 2: Short-leg liquidity ─────────────────────────────────────────
    gb.configure_column("OI Short", headerName="OI Short", width=90, type=["numericColumn"])
    gb.configure_column("Vol Short", headerName="Vol Short", width=90, type=["numericColumn"])
    gb.configure_column(
        "Liq Score",
        headerName="Liq Score",
        width=95,
        type=["numericColumn"],
        cellStyle=JsCode("""
        function(params) {
            var v = params.value;
            if (v >= 70) return {color:'#4ade80',fontWeight:'bold'};
            if (v >= 40) return {color:'#facc15'};
            return {color:'#f87171'};
        }"""),
        valueFormatter="x.toFixed(0)",
    )
    gb.configure_column("Liquidez", width=85, type=["numericColumn"], cellStyle=_JS_LIQUIDEZ_STYLE)
    gb.configure_column("Volumen", width=80, type=["numericColumn"])
    gb.configure_column("OI", headerName="Open Interest", width=100, type=["numericColumn"])
    gb.configure_column("Bid-Ask", width=80, type=["numericColumn"], valueFormatter="'$' + x.toFixed(2)")

    # ── EV $ / EV % ─────────────────────────────────────────────────────────
    gb.configure_column(
        "EV $",
        headerName="EV $ /contrato",
        width=120,
        type=["numericColumn"],
        cellStyle=_JS_EV_DOLLAR_STYLE,
        valueFormatter="(x >= 0 ? '+' : '') + '$' + x.toFixed(2)",
        sort="desc",
    )
    gb.configure_column(
        "EV %",
        headerName="EV % capital",
        width=110,
        type=["numericColumn"],
        cellStyle=_JS_EV_PCT_STYLE,
        valueFormatter="(x >= 0 ? '+' : '') + x.toFixed(1) + '%'",
    )

    gb.configure_selection(selection_mode="single", use_checkbox=False)

    return gb.build(), AGGRID_DARK_CSS
