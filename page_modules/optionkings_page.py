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

from config.constants import ALERT_DEFAULT_ACCOUNT_SIZE
from core.container import get_container
from core.optionkings_analytic import (
    calculate_all_metrics,
    calculate_professional_score,
    passes_smart_filters,
)
from ui.optionkings_components import render_spread_card

logger = logging.getLogger(__name__)

# Tickers disponibles para el dropdown
_ALL_TICKERS = [
    "SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN", "META",
    "GOOGL", "NFLX", "DIS", "BA", "JPM", "GS", "V", "MA",
    "XOM", "COIN", "PLTR", "SOFI", "MARA", "DIA", "GLD",
]
_DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "NVDA"]


def render(**kwargs) -> None:
    """Renderiza la página OptionKings Analytic."""
    _cs_service = get_container().credit_spread_service

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#0a0a1a,#0d1f3e);
                    border:1px solid #1e3a5f;border-radius:16px;
                    padding:1.5rem 2rem;margin-bottom:1.5rem;">
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
            account_size = st.number_input(
                "💼 Tamaño de cuenta ($)",
                min_value=1_000,
                max_value=1_000_000,
                value=int(ALERT_DEFAULT_ACCOUNT_SIZE),
                step=1_000,
                key="ok_account_size",
                help="Para calcular Max Loss < 5% de cuenta.",
            )
            min_score = st.slider(
                "🏆 Score mínimo para mostrar",
                0, 100, 40, 5,
                key="ok_min_score",
                help="Solo tarjetas con Score ≥ este valor.",
            )

        st.markdown("---")
        st.markdown("#### 🧠 Filtros Inteligentes (automáticos)")
        fi_col1, fi_col2 = st.columns(2)
        with fi_col1:
            apply_smart = st.checkbox(
                "🔬 Aplicar filtros inteligentes del PDF",
                value=True,
                key="ok_smart_filters",
                help=(
                    "EV > $0 · IV Percentile > 50% · "
                    "Liquidez < 5% · Prob Touch < 35% · "
                    "Max Loss < 5% cuenta"
                ),
            )
        with fi_col2:
            show_rejected = st.checkbox(
                "👁 Mostrar spreads rechazados (transparencia)",
                value=False,
                key="ok_show_rejected",
                help="Muestra cards grises con el motivo del rechazo.",
            )

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
        st.session_state["ok_account"]   = account_size
        st.session_state["ok_settings"]  = {
            "apply_smart": apply_smart,
            "show_rejected": show_rejected,
            "min_score": min_score,
        }

    # ── Mostrar resultados ────────────────────────────────────────────────
    df: pd.DataFrame | None = st.session_state.get("ok_results")
    scan_time: str | None   = st.session_state.get("ok_scan_time")
    settings: dict          = st.session_state.get("ok_settings", {
        "apply_smart": True, "show_rejected": False, "min_score": 40,
    })
    acc_size: float = float(st.session_state.get("ok_account", ALERT_DEFAULT_ACCOUNT_SIZE))

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
    spreads_data: list[dict] = []
    for _, row in df.iterrows():
        row_d    = row.to_dict()
        metrics  = calculate_all_metrics(row_d)
        score_d  = calculate_professional_score(metrics)
        pasa, rechazos = passes_smart_filters(row_d, metrics, acc_size)
        spreads_data.append({
            "row":      row_d,
            "metrics":  metrics,
            "score":    score_d,
            "pasa":     pasa,
            "rechazos": rechazos,
        })

    # Ordenar por score descendente
    spreads_data.sort(key=lambda x: x["score"]["score"], reverse=True)

    # Aplicar filtros
    apply_sf   = settings.get("apply_smart", True)
    show_rej   = settings.get("show_rejected", False)
    min_sc     = settings.get("min_score", 40)

    aprobados  = [s for s in spreads_data if (not apply_sf or s["pasa"]) and s["score"]["score"] >= min_sc]
    rechazados = [s for s in spreads_data if (apply_sf and not s["pasa"]) or s["score"]["score"] < min_sc]

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
            "Considera: desactivar filtros inteligentes, reducir min_score, "
            "o esperar mayor volatilidad (IV Percentile > 50%)."
        )
    else:
        st.markdown(
            f"### ✅ {len(aprobados)} Spreads con Edge Matemático Verificado"
        )
        for idx, item in enumerate(aprobados):
            render_spread_card(
                row=item["row"],
                metrics=item["metrics"],
                score_data=item["score"],
                idx=idx,
            )

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
