# -*- coding: utf-8 -*-
"""
OptionKings Analytic — Página de Análisis Profesional de Credit Spreads.

Esta página implementa los Aspectos 2 y 3 del PDF:
  • Todas las métricas obligatorias por spread (EV, Kelly, VolEdge, ProTouch, etc.)
  • Score Profesional 0-100 con gauge Plotly y desglose por componente
  • Filtros inteligentes: solo spreads que pasen EV>0, IV Pctil>50, Liq<5%, etc.
  • Tarjetas expandibles con máxima claridad visual

Arquitectura:
    core/credit_spread_scanner  → escanea spreads con yfinance
    core/optionkings_analytic   → calcula métricas y score
    ui/optionkings_components   → renderiza tarjetas con gauge Plotly
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from core.container import get_container
from core.ai_signal_engine import generate_master_signal
from core.dealer_positioning import (
    detect_gamma_squeeze_conditions,
    infer_dealer_position,
)
from core.optionkings_analytic import (
    apply_intelligent_filters,
    calculate_account_management,
    calculate_all_metrics,
    calculate_professional_score,
)
from ui.optionkings_components import (
    render_account_management_sidebar,
    render_spread_card,
)

logger = logging.getLogger(__name__)

# Tickers disponibles para el dropdown
_ALL_TICKERS = [
    "SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN", "META",
    "GOOGL", "NFLX", "DIS", "BA", "JPM", "GS", "V", "MA",
    "XOM", "COIN", "PLTR", "SOFI", "MARA", "DIA", "GLD",
]
_DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "NVDA"]

_SMART_FILTER_OPTIONS: dict[str, str] = {
    "ev_positive": "EV > $0",
    "iv_pctil": "IV Percentile > 50%",
    "liquidez": "Liquidez < 5% del crédito",
    "prob_touch": "Prob Touch < 35%",
    "max_loss_account": "Max Loss < % de cuenta",
}
_SMART_FILTER_DEFAULTS = list(_SMART_FILTER_OPTIONS.keys())


def render(**kwargs) -> None:
    """Renderiza la página OptionKings Analytic."""
    _cs_service = get_container().credit_spread_service

    # ── Sidebar: Gestión de Cuenta (Aspecto 5) ────────────────────────
    with st.sidebar:
        st.markdown("---")
        account_size, risk_pct = render_account_management_sidebar()

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#0a0a1a,#0d1f3e);
                    border:1px solid #1e3a5f;border-radius:16px;
                    padding:1.5rem 2rem;margin-bottom:1rem;">
            <h2 style="color:#00ff88;margin:0 0 0.3rem 0;">
                👑 OPTIONSKING — Análisis Profesional de Spreads
            </h2>
            <p style="color:#94a3b8;margin:0;font-size:0.88rem;">
                Score 0-100 • EV matemático • Volatility Edge • Kelly Fraction •
                Filtros inteligentes — decide en <b style="color:#00ff88;">3 segundos</b>
                si el spread tiene edge real.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Filosofía del Producto — Aspecto 7 ───────────────────────────────
    st.markdown(
        """
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;
                    margin-bottom:1.2rem;">
            <div style="background:#0d1117;border:1px solid #22c55e33;border-radius:8px;
                        padding:8px 10px;text-align:center;">
                <div style="font-size:0.7rem;color:#22c55e;font-weight:700;
                    margin-bottom:3px;">📊 DATA FIRST</div>
                <div style="font-size:0.65rem;color:#64748b;line-height:1.3;">
                    Números y gráficos objetivos siempre antes que opiniones.</div>
            </div>
            <div style="background:#0d1117;border:1px solid #ef444433;border-radius:8px;
                        padding:8px 10px;text-align:center;">
                <div style="font-size:0.7rem;color:#ef4444;font-weight:700;
                    margin-bottom:3px;">🚨 RISK TRANSPARENT</div>
                <div style="font-size:0.65rem;color:#64748b;line-height:1.3;">
                    Drawdown, touch, liquidez y EV negativo siempre visibles.</div>
            </div>
            <div style="background:#0d1117;border:1px solid #a78bfa33;border-radius:8px;
                        padding:8px 10px;text-align:center;">
                <div style="font-size:0.7rem;color:#a78bfa;font-weight:700;
                    margin-bottom:3px;">🎯 EDGE CUANTIFICADO</div>
                <div style="font-size:0.65rem;color:#64748b;line-height:1.3;">
                    EV · Score · Vol Edge como métricas primarias.</div>
            </div>
            <div style="background:#0d1117;border:1px solid #fbbf2433;border-radius:8px;
                        padding:8px 10px;text-align:center;">
                <div style="font-size:0.7rem;color:#fbbf24;font-weight:700;
                    margin-bottom:3px;">🧠 PSICOLOGÍA INTEGRADA</div>
                <div style="font-size:0.65rem;color:#64748b;line-height:1.3;">
                    Drawdown 3 pérdidas, % ganadores MC, worst case visibles.</div>
            </div>
            <div style="background:#0d1117;border:1px solid #38bdf833;border-radius:8px;
                        padding:8px 10px;text-align:center;">
                <div style="font-size:0.7rem;color:#38bdf8;font-weight:700;
                    margin-bottom:3px;">🚫 SIN ILUSIÓN</div>
                <div style="font-size:0.65rem;color:#64748b;line-height:1.3;">
                    No prometemos ganancias. Solo probabilidades y riesgos reales.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Panel educativo ───────────────────────────────────────────────────
    with st.expander("📚 ¿Cómo funciona el Score Profesional?", expanded=False):
        st.markdown(
            """
            <div style="font-size:0.85rem;line-height:1.8;color:#cbd5e1;">
            <b style="color:#00ff88;">Score = 100% matemático. Sin subjetividad.</b><br>
            <b>Fórmula:</b> Score = 30% EV + 20% Volatility Edge + 15% Risk/Reward
            + 15% Distancia Strike + 10% DTE + 10% Liquidez<br><br>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
              <div style="background:#0d1117;padding:8px 12px;border-left:3px solid #22d3ee;border-radius:4px;">
                <b style="color:#22d3ee;">EV (30%)</b><br>
                <span style="color:#94a3b8;font-size:0.8rem;">Expected Value = (POP×Crédito) − ((1−POP)×Pérdida). Si &gt;$0 = edge real.</span>
              </div>
              <div style="background:#0d1117;padding:8px 12px;border-left:3px solid #a78bfa;border-radius:4px;">
                <b style="color:#a78bfa;">Volatility Edge (20%)</b><br>
                <span style="color:#94a3b8;font-size:0.8rem;">IV actual − HV 20D. Positivo = prima inflada histórica = momento ideal para vender.</span>
              </div>
              <div style="background:#0d1117;padding:8px 12px;border-left:3px solid #fb923c;border-radius:4px;">
                <b style="color:#fb923c;">Risk/Reward (15%)</b><br>
                <span style="color:#94a3b8;font-size:0.8rem;">Crédito / MaxLoss. Objetivo ≥25% para buena relación.</span>
              </div>
              <div style="background:#0d1117;padding:8px 12px;border-left:3px solid #f472b6;border-radius:4px;">
                <b style="color:#f472b6;">Distancia Strike (15%)</b><br>
                <span style="color:#94a3b8;font-size:0.8rem;">Óptima ≈5.5% del spot. Cerca = peligroso. Lejos = poco crédito.</span>
              </div>
              <div style="background:#0d1117;padding:8px 12px;border-left:3px solid #34d399;border-radius:4px;">
                <b style="color:#34d399;">DTE Ideal (10%)</b><br>
                <span style="color:#94a3b8;font-size:0.8rem;">Pico en 37 días. Mágica zona de theta decay máximo.</span>
              </div>
              <div style="background:#0d1117;padding:8px 12px;border-left:3px solid #60a5fa;border-radius:4px;">
                <b style="color:#60a5fa;">Liquidez (10%)</b><br>
                <span style="color:#94a3b8;font-size:0.8rem;">(Bid−Ask) / Crédito. &lt;5% = excelente. &gt;10% = mal fill.</span>
              </div>
            </div>
            <div style="margin-top:10px;padding:6px 10px;background:#0d1117;border-left:3px solid #fbbf24;border-radius:4px;font-size:0.8rem;">
              <b style="color:#fbbf24;">Grados:</b>
              <span style="color:#22c55e;">A ≥80</span> Excelente · 
              <span style="color:#84cc16;">B ≥65</span> Buena · 
              <span style="color:#fbbf24;">C ≥50</span> Aceptable · 
              <span style="color:#ef4444;">D &lt;50</span> Débil
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Panel de filtros ──────────────────────────────────────────────────
    with st.expander("⚙️ Configuración del Análisis", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            selected_tickers = st.multiselect(
                "🔍 Tickers a analizar",
                options=_ALL_TICKERS,
                default=_DEFAULT_TICKERS,
                key="ok_tickers",
            )
            min_pop_pct = st.slider(
                "📊 Min POP %", 60, 95, 70, 5,
                key="ok_min_pop",
                help="Solo spreads con probabilidad de ganancia ≥ este valor.",
            )
            max_dte = st.slider(
                "📅 Máx DTE", 7, 90, 45, 1,
                key="ok_max_dte",
            )
        with col2:
            min_credit = st.slider(
                "💵 Min Crédito ($)", 0.10, 5.00, 0.25, 0.05,
                format="$%.2f",
                key="ok_min_credit",
            )
            min_score = st.slider(
                "🏆 Score mínimo para mostrar",
                0, 100, 40, 5,
                key="ok_min_score",
                help="Solo tarjetas con Score ≥ este valor.",
            )
            st.info(
                "💰 **Cuenta y riesgo** en el panel izquierdo (sidebar).",
                icon="ℹ️",
            )

        st.markdown("---")
        st.markdown("#### 🧠 Filtros Inteligentes (automáticos)")
        fi_col1, fi_col2 = st.columns(2)
        with fi_col1:
            st.markdown("**🎚️ Selecciona filtros a aplicar**")
            sf_ev = st.checkbox(
                "EV > $0",
                value=True,
                key="ok_sf_ev_positive",
            )
            sf_iv = st.checkbox(
                "IV Percentile > 50%",
                value=True,
                key="ok_sf_iv_pctil",
            )
            sf_liq = st.checkbox(
                "Liquidez < 5% del crédito",
                value=True,
                key="ok_sf_liquidez",
            )
        with fi_col2:
            sf_touch = st.checkbox(
                "Prob Touch < 35%",
                value=True,
                key="ok_sf_prob_touch",
            )
            sf_maxloss = st.checkbox(
                "Max Loss < % de cuenta",
                value=True,
                key="ok_sf_max_loss_account",
            )
            show_rejected = st.checkbox(
                "👁 Mostrar spreads rechazados (transparencia)",
                value=False,
                key="ok_show_rejected",
                help="Muestra cards grises con el motivo del rechazo.",
            )

        selected_filters = []
        if sf_ev:
            selected_filters.append("ev_positive")
        if sf_iv:
            selected_filters.append("iv_pctil")
        if sf_liq:
            selected_filters.append("liquidez")
        if sf_touch:
            selected_filters.append("prob_touch")
        if sf_maxloss:
            selected_filters.append("max_loss_account")

    # ── Botón scan ────────────────────────────────────────────────────────
    if st.button(
        "🚀 Analizar Spreads con Score Profesional",
        type="primary",
        use_container_width=True,
        key="ok_scan_btn",
    ):
        if not selected_tickers:
            st.warning("⚠️ Selecciona al menos un ticker.")
            return

        prog = st.progress(0.0)
        status = st.empty()

        def _cb(ticker: str, idx: int, total: int) -> None:
            prog.progress((idx + 1) / total)
            status.markdown(
                f'<span style="color:#94a3b8;font-size:0.82rem;">'
                f'Escaneando <b style="color:#00ff88;">{ticker}</b> '
                f'({idx + 1}/{total})…</span>',
                unsafe_allow_html=True,
            )

        with st.spinner("Analizando cadenas de opciones…"):
            df, _ = _cs_service.scan(
                tickers=selected_tickers,
                min_pop=min_pop_pct / 100.0,
                max_dte=max_dte,
                min_credit=min_credit,
                strict=False,          # OptionKings usa sus propios filtros
                account_size=account_size,
                progress_callback=_cb,
            )

        prog.empty()
        status.empty()

        st.session_state["ok_results"]   = df
        st.session_state["ok_scan_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["ok_page"]       = 0
        st.session_state["ok_settings"]  = {
            "show_rejected": show_rejected,
            "min_score": min_score,
            "selected_filters": selected_filters,
        }

    # ── Mostrar resultados ────────────────────────────────────────────────
    df: pd.DataFrame | None = st.session_state.get("ok_results")
    scan_time: str | None   = st.session_state.get("ok_scan_time")
    settings: dict          = st.session_state.get("ok_settings", {
        "show_rejected": False,
        "min_score": 40,
        "selected_filters": _SMART_FILTER_DEFAULTS,
    })
    # account_size y risk_pct ya están en session_state (escritos por el sidebar)
    acc_size: float  = float(account_size)
    risk_pct_val: float = float(risk_pct)

    if df is None:
        st.markdown(
            '<p style="color:#64748b;text-align:center;padding:3rem 0;">'
            "Pulsa <b>🚀 Analizar Spreads</b> para comenzar el análisis.</p>",
            unsafe_allow_html=True,
        )
        return

    if df.empty:
        st.warning(
            "🛡️ No se encontraron spreads con los parámetros indicados.\n\n"
            "Prueba reduciendo el Min POP o aumentando el DTE máximo."
        )
        return

    # ── Calcular métricas y score para cada spread ────────────────────────
    # Caché estática: re-computa solo si cambia el df de resultados.
    # Los filtros (cuenta, riesgo) se re-aplican en cada render sin re-escanear.
    _cache_key = id(df)
    if st.session_state.get("_ok_cache_key") != _cache_key:
        spreads_raw: list[dict] = []
        for _, row in df.iterrows():
            row_d   = row.to_dict()
            metrics = calculate_all_metrics(row_d)
            score_d = calculate_professional_score(metrics)
            spreads_raw.append({"row": row_d, "metrics": metrics, "score": score_d})
        spreads_raw.sort(key=lambda x: x["score"]["score"], reverse=True)
        st.session_state["_ok_spreads_raw"]  = spreads_raw
        st.session_state["_ok_cache_key"]    = _cache_key
    else:
        spreads_raw = st.session_state["_ok_spreads_raw"]

    # Re-aplicar filtros inteligentes con parámetros actuales (Aspecto 4 reactivo)
    show_rej = settings.get("show_rejected", False)
    min_sc   = settings.get("min_score", 40)
    selected_filters = settings.get("selected_filters", _SMART_FILTER_DEFAULTS)

    spreads_data = apply_intelligent_filters(
        spreads_raw,
        acc_size,
        risk_pct_val,
        enabled_filters=selected_filters,
    )

    # ── Consola del Analista Cuántico (AI Signal Engine) ───────────────
    _bull_flow = 0.0
    _bear_flow = 0.0
    _call_vol = 0.0
    _put_vol = 0.0
    _iv_vals: list[float] = []
    _hv_vals: list[float] = []
    _gex_total_proxy = 0.0
    _spot_vals: list[float] = []
    _zero_gamma_proxy_vals: list[float] = []
    _edge_vals: list[float] = []
    _liq_vals: list[float] = []

    for _item in spreads_data:
        _row = _item.get("row", {})
        _mtx = _item.get("metrics", {})
        _score_data = _item.get("score", {})

        _tipo = str(_row.get("Tipo", ""))
        _credit_d = float(_mtx.get("credit_dollars", 0.0) or 0.0)
        _ev_d = float(_mtx.get("ev_dollars", 0.0) or 0.0)
        _flow_unit = max(_credit_d, 0.0) + max(_ev_d, 0.0)
        if "Bull Put" in _tipo:
            _bull_flow += _flow_unit
            _put_vol += float(_row.get("Volumen Vendido", _row.get("Volumen", 1.0)) or 1.0)
        else:
            _bear_flow += _flow_unit
            _call_vol += float(_row.get("Volumen Vendido", _row.get("Volumen", 1.0)) or 1.0)

        _iv_vals.append(float(_mtx.get("iv_pct", _row.get("IV %", 0.0)) or 0.0))
        _hv_vals.append(float(_mtx.get("hv_20d", _row.get("HV 20D", 0.0)) or 0.0))
        _edge_vals.append(float(_score_data.get("score", 50.0) or 50.0))
        _liq_vals.append(float(_mtx.get("liquidez_pct", 10.0) or 10.0))

        _spot = float(_row.get("Spot", 0.0) or 0.0)
        _sv = float(_row.get("Strike Vendido", 0.0) or 0.0)
        if _spot > 0:
            _spot_vals.append(_spot)
        if _sv > 0:
            _zero_gamma_proxy_vals.append(_sv)

        _gamma_proxy = abs(float(_row.get("Gamma Neto", _row.get("Gamma", 0.0)) or 0.0))
        _oi_proxy = float(_row.get("OI Vendido", _row.get("OI", 100.0)) or 100.0)
        _spot_for_gex = _spot if _spot > 0 else 100.0
        _gex_piece = _gamma_proxy * _oi_proxy * 100.0 * (_spot_for_gex ** 2) * 0.01
        _gex_total_proxy += _gex_piece if "Bull Put" in _tipo else -_gex_piece

    _flow_total = _bull_flow + _bear_flow
    _sentiment_score = 50.0 + (((_bull_flow - _bear_flow) / _flow_total) * 50.0 if _flow_total > 0 else 0.0)
    _sentiment_score = max(0.0, min(100.0, _sentiment_score))

    _flow_hist = st.session_state.get("ok_flow_history", [])
    if not isinstance(_flow_hist, list):
        _flow_hist = []
    _net_flow = _bull_flow - _bear_flow
    _flow_hist.append(_net_flow)
    if len(_flow_hist) > 60:
        _flow_hist = _flow_hist[-60:]
    st.session_state["ok_flow_history"] = _flow_hist

    if len(_flow_hist) >= 10:
        _mean = float(pd.Series(_flow_hist).mean())
        _std = float(pd.Series(_flow_hist).std())
        _flow_z = ((_net_flow - _mean) / _std) if _std > 1e-9 else 0.0
    else:
        _flow_z = 0.0

    _spot_now = float(pd.Series(_spot_vals).median()) if _spot_vals else 0.0
    _zero_gamma_level = float(pd.Series(_zero_gamma_proxy_vals).median()) if _zero_gamma_proxy_vals else 0.0
    _prev_spot_key = "ok_ai_prev_spot"
    _spot_prev = float(st.session_state.get(_prev_spot_key, _spot_now) or _spot_now)
    st.session_state[_prev_spot_key] = _spot_now

    _current_iv = float(pd.Series(_iv_vals).mean()) if _iv_vals else 25.0
    _hv20 = float(pd.Series(_hv_vals).mean()) if _hv_vals else 20.0
    _edge_score = float(pd.Series(_edge_vals).mean()) if _edge_vals else 50.0
    _liq_mean = float(pd.Series(_liq_vals).mean()) if _liq_vals else 10.0
    _liq_score = max(0.0, min(100.0, 100.0 - (_liq_mean * 10.0)))

    _dealer_info = infer_dealer_position(
        call_volume=_call_vol if _call_vol > 0 else max(len(spreads_data), 1),
        put_volume=_put_vol if _put_vol > 0 else max(len(spreads_data), 1),
        bullish_flow=_bull_flow,
        bearish_flow=_bear_flow,
    )
    _short_proxy = float(max((_put_vol / _call_vol), 1.0) if _call_vol > 0 else 1.0)
    _squeeze_info = detect_gamma_squeeze_conditions(
        gex_total=_gex_total_proxy,
        bullish_flow_ratio=(_bull_flow / _flow_total) if _flow_total > 0 else 0.5,
        current_iv=_current_iv,
        short_interest_proxy=_short_proxy,
    )
    _dealer_info["squeeze_alert"] = bool(_squeeze_info.get("squeeze_alert", False))

    _master_signal = generate_master_signal(
        oka_sentiment={
            "score": _sentiment_score,
            "flow_zscore": _flow_z,
            "current_iv": _current_iv,
            "hv_20d": _hv20,
        },
        gex_data={
            "gex_total": _gex_total_proxy,
            "spot": _spot_now,
            "prev_spot": _spot_prev,
            "zero_gamma_level": _zero_gamma_level,
        },
        dealer_positioning=_dealer_info,
        mc_results={
            "edge_score": _edge_score,
            "liquidity_score": _liq_score,
        },
    )

    _sig_score = float(_master_signal.get("signal_score", 50.0))
    _sig_regime = str(_master_signal.get("regime", "Tactical / Mixed"))
    _alerts = _master_signal.get("alerts", {}) or {}

    st.markdown("### 🧠 Consola del Analista Cuántico (AI Signal Engine)")
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#0a1220,#0d1b2e);border:1px solid #334155;
                    border-radius:12px;padding:12px 14px;margin:0.25rem 0 0.9rem 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
                <div style="color:#94a3b8;font-size:0.82rem;">Signal Score</div>
                <div style="color:#e2e8f0;font-size:0.8rem;">Regime: <b style="color:#22d3ee;">{_sig_regime}</b></div>
            </div>
            <div style="font-size:2.35rem;font-weight:800;line-height:1.1;
                        color:{'#22c55e' if _sig_score >= 65 else ('#ef4444' if _sig_score <= 35 else '#fbbf24')};">
                {_sig_score:.1f}/100
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if bool(_alerts.get("gamma_flip_alert", False)):
        st.error("⚠️ ALERTA CRITICA: Gamma Flip detectado (Spot cruzando Zero Gamma).")
    if bool(_alerts.get("iv_spike_alert", False)):
        st.warning("⚠️ ALERTA: IV Spike activo (IV >= 130% de HV 20D).")
    if bool(_alerts.get("flow_zscore_alert", False)):
        st.warning("⚠️ ALERTA: Flow Z-score > 3 (actividad institucional altamente inusual).")
    if bool(_alerts.get("squeeze_alert", False)):
        st.error("⚠️ ALERTA DE GAMMA SQUEEZE: cobertura mecánica de dealers en curso.")

    st.markdown(
        f'<div style="background:#0d1117;border:1px solid #1f2937;border-radius:10px;padding:10px 12px;'
        f'margin-bottom:1rem;color:#cbd5e1;font-size:0.84rem;line-height:1.55;">'
        f'{_master_signal.get("recommendation", "Sin recomendación.")}'
        f"</div>",
        unsafe_allow_html=True,
    )

    aprobados  = [s for s in spreads_data if s["pasa"] and s["score"]["score"] >= min_sc]
    rechazados = [s for s in spreads_data if (not s["pasa"]) or s["score"]["score"] < min_sc]

    # ── Evaluador de Estrategias Neutrales (Iron Condor) ──────────────────
    st.markdown("### ⚖️ Análisis de Viabilidad No Direccional (Iron Condor)")
    with st.expander("Ver análisis para posiciones Neutrales", expanded=True):
        # Usa aprobados si hay datos; si no, toda la muestra escaneada
        _ic_pool = aprobados if aprobados else spreads_data

        # Agrupa IV Pctil y Vol Edge por ticker
        _ic_tickers: dict[str, dict] = {}
        for _item in _ic_pool:
            _r = _item.get("row", {})
            _m = _item.get("metrics", {})
            _tk = str(_r.get("Ticker", "??"))
            _ivp = float(_m.get("iv_pctil", _r.get("IV Pctil", 0.0)) or 0.0)
            _iv_raw = float(_m.get("iv_pct", _r.get("IV %", 0.0)) or 0.0)
            _hv = float(_m.get("hv_20d", _r.get("HV 20D", 0.0)) or 0.0)
            if _tk not in _ic_tickers:
                _ic_tickers[_tk] = {"ivp": [], "ve": []}
            _ic_tickers[_tk]["ivp"].append(_ivp)
            _ic_tickers[_tk]["ve"].append(_iv_raw - _hv)

        if not _ic_tickers:
            st.info("Sin datos suficientes. Lanza un escaneo para ver el análisis.")
        else:
            # Contexto direccional derivado del AI Signal Score (ya calculado arriba)
            _is_neutral_sig = 40.0 <= _sig_score <= 60.0
            if _is_neutral_sig:
                st.markdown(
                    f'<div style="background:#1c1f2e;border-left:4px solid #fbbf24;'
                    f'border-radius:6px;padding:8px 14px;margin-bottom:10px;font-size:0.84rem;">'
                    f'<b style="color:#fbbf24;">⚖️ Señal Ambigua detectada</b>'
                    f' <span style="color:#94a3b8;">(AI Signal Score: '
                    f'<b style="color:#fbbf24;">{_sig_score:.1f}</b>/100) — Sesgo direccional '
                    f'no claro. Evaluación de estrategias neutrales activada '
                    f'automáticamente.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                _ic_dir_word = "ALCISTA 📈" if _sig_score > 60.0 else "BAJISTA 📉"
                _ic_dir_color = "#22c55e" if _sig_score > 60.0 else "#ef4444"
                st.markdown(
                    f'<div style="background:#0d1117;border-left:4px solid {_ic_dir_color};'
                    f'border-radius:6px;padding:8px 14px;margin-bottom:10px;font-size:0.84rem;">'
                    f'<b style="color:{_ic_dir_color};">📊 Señal Direccional {_ic_dir_word}</b>'
                    f' <span style="color:#94a3b8;">(Score: <b>{_sig_score:.1f}</b>/100) '
                    f'— El Iron Condor es menos óptimo en entornos con sesgo claro, pero los '
                    f'niveles de IV siguen siendo relevantes para validar primas.</span></div>',
                    unsafe_allow_html=True,
                )

            # Tarjetas por ticker en filas de máximo 3 columnas
            _ic_sorted_tks = sorted(_ic_tickers.keys())
            for _ic_row_start in range(0, len(_ic_sorted_tks), 3):
                _ic_batch = _ic_sorted_tks[_ic_row_start : _ic_row_start + 3]
                _ic_cols = st.columns(len(_ic_batch))
                for _ci, _tk in enumerate(_ic_batch):
                    _d = _ic_tickers[_tk]
                    _avg_ivp = sum(_d["ivp"]) / len(_d["ivp"]) if _d["ivp"] else 0.0
                    _avg_ve  = sum(_d["ve"]) / len(_d["ve"]) if _d["ve"] else 0.0
                    _n_sp = len(_d["ivp"])
                    _sp_label = f"{_n_sp} spread{'s' if _n_sp != 1 else ''} analizados"
                    with _ic_cols[_ci]:
                        if _avg_ivp > 50.0:
                            st.success(
                                f"**{_tk}**\n\n"
                                f"**IV Pctil prom:** {_avg_ivp:.1f}%  \n"
                                f"**Vol Edge prom:** {_avg_ve:+.1f}%  \n"
                                f"*({_sp_label})*\n\n"
                                f"✅ **Escenario Óptimo para IRON CONDOR:** La Volatilidad "
                                f"Implícita (IV Pctil > 50%) está inflada. Este entorno "
                                f"lateral/neutral permite combinar las mejores patas de Call y "
                                f"Put cobrando primas altas a la espera de que la volatilidad "
                                f"colapse (Vol Crush) y el tiempo pase."
                            )
                        else:
                            st.warning(
                                f"**{_tk}**\n\n"
                                f"**IV Pctil prom:** {_avg_ivp:.1f}%  \n"
                                f"**Vol Edge prom:** {_avg_ve:+.1f}%  \n"
                                f"*({_sp_label})*\n\n"
                                f"⚠️ **Baja Volatilidad (IV Pctil < 50%).** VENDER un Iron "
                                f"Condor aquí NO es óptimo porque las primas cobradas son muy "
                                f"bajas para el riesgo asumido. En este entorno neutral se "
                                f"recomienda: Esperar una explosión de IV, o usar estrategias "
                                f"compradoras como el 'Double Calendar Spread'."
                            )

    # ── Métricas resumen ──────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                    padding:10px 20px;display:flex;gap:20px;flex-wrap:wrap;
                    font-size:0.85rem;margin-bottom:1.2rem;align-items:center;">
            <span style="color:#00ff88;font-weight:700;">
                {len(aprobados)} spreads con edge
            </span>
            <span style="color:#94a3b8;">
                de {len(spreads_data)} totales
                ({len(rechazados)} rechazados)
            </span>
            <span style="color:#64748b;margin-left:auto;">
                Análisis: {scan_time}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not aprobados:
        st.info(
            "🧠 **Ningún spread pasa los filtros inteligentes.**\n\n"
            "El mercado actual no ofrece spreads con edge matemático verificado. "
            "Considera: desmarcar algunos filtros, reducir min_score, "
            "o esperar mayor volatilidad (IV Percentile > 50%)."
        )
    else:
        _PAGE_SIZE = 10
        _cur_page  = int(st.session_state.get("ok_page", 0))
        _total_pages = max(1, (len(aprobados) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        _cur_page    = max(0, min(_cur_page, _total_pages - 1))
        _page_start  = _cur_page * _PAGE_SIZE
        _page_end    = _page_start + _PAGE_SIZE
        _page_items  = aprobados[_page_start:_page_end]

        st.markdown(
            f"### ✅ {len(aprobados)} Spreads con Edge Matemático Verificado"
        )

        # ── Navegación (arriba) ───────────────────────────────────────────
        _nav_c1, _nav_c2, _nav_c3 = st.columns([1, 2, 1])
        with _nav_c1:
            if st.button("◀ Anterior", key="ok_prev_top", disabled=(_cur_page == 0)):
                st.session_state["ok_page"] = _cur_page - 1
                st.rerun()
        with _nav_c2:
            st.markdown(
                f'<p style="text-align:center;color:#94a3b8;font-size:0.85rem;'
                f'margin:6px 0;">Página <b style="color:#00ff88;">{_cur_page + 1}</b>'
                f' de <b>{_total_pages}</b>'
                f' · mostrando {_page_start + 1}–{min(_page_end, len(aprobados))}'
                f' de {len(aprobados)}</p>',
                unsafe_allow_html=True,
            )
        with _nav_c3:
            if st.button("Siguiente ▶", key="ok_next_top", disabled=(_cur_page >= _total_pages - 1)):
                st.session_state["ok_page"] = _cur_page + 1
                st.rerun()

        for idx, item in enumerate(_page_items, start=_page_start):
            mgmt = calculate_account_management(
                item["metrics"], acc_size, risk_pct_val
            )
            render_spread_card(
                row=item["row"],
                metrics=item["metrics"],
                score_data=item["score"],
                idx=idx,
                management=mgmt,
            )

        # ── Navegación (abajo) ────────────────────────────────────────────
        st.markdown("---")
        _bn_c1, _bn_c2, _bn_c3 = st.columns([1, 2, 1])
        with _bn_c1:
            if st.button("◀ Anterior", key="ok_prev_bot", disabled=(_cur_page == 0)):
                st.session_state["ok_page"] = _cur_page - 1
                st.rerun()
        with _bn_c2:
            st.markdown(
                f'<p style="text-align:center;color:#94a3b8;font-size:0.85rem;'
                f'margin:6px 0;">Página <b style="color:#00ff88;">{_cur_page + 1}</b>'
                f' de <b>{_total_pages}</b></p>',
                unsafe_allow_html=True,
            )
        with _bn_c3:
            if st.button("Siguiente ▶", key="ok_next_bot", disabled=(_cur_page >= _total_pages - 1)):
                st.session_state["ok_page"] = _cur_page + 1
                st.rerun()

    # ── Spreads rechazados (transparencia) ────────────────────────────────
    if show_rej and rechazados:
        st.markdown(f"---\n### 🚫 {len(rechazados)} Spreads Rechazados (motivos)")
        for item in rechazados[:20]:   # limitar a 20 para no sobrecargar
            row_d   = item["row"]
            score_d = item["score"]
            ticker  = row_d.get("Ticker", "?")
            tipo    = row_d.get("Tipo", "?")
            sv      = row_d.get("Strike Vendido", 0)
            sc      = row_d.get("Strike Comprado", 0)
            score   = score_d.get("score", 0)
            motivos = " · ".join(item["rechazos"]) if item["rechazos"] else f"Score {score:.0f} < min"

            st.markdown(
                f'<div style="background:#0d1117;border:1px solid #2d1b1b;'
                f'border-radius:8px;padding:8px 14px;margin-bottom:6px;'
                f'font-size:0.8rem;opacity:0.7;">'
                f'<b style="color:#ef4444;">{ticker} {sv:.0f}/{sc:.0f}</b> '
                f'<span style="color:#64748b;">{tipo}</span> · '
                f'<span style="color:#94a3b8;">Score {score:.0f}</span> · '
                f'<span style="color:#f87171;">❌ {motivos}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
