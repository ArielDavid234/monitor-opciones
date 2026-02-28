# -*- coding: utf-8 -*-
"""
Venta de Prima — Credit Spread Scanner.

Escanea cadenas de opciones para encontrar Bull Put Spreads y Bear Call Spreads
con alta probabilidad de ganancia y buen retorno sobre riesgo.
"""
from __future__ import annotations

import io
import logging
import pandas as pd
import streamlit as st
from datetime import datetime

from core.credit_spread_scanner import scan_credit_spreads

logger = logging.getLogger(__name__)

# ── Tickers populares por defecto ────────────────────────────────────────
_DEFAULT_TICKERS = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL"]
_ALL_TICKERS = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META",
    "GOOGL", "AMD", "NFLX", "DIS", "BA", "JPM", "GS", "V", "MA",
    "XOM", "COIN", "PLTR", "SOFI", "MARA", "IWM", "DIA", "GLD",
]


def render(**kwargs) -> None:
    """Renderiza la página de Venta de Prima — Credit Spread Scanner."""

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                    border:1px solid #0f3460;border-radius:16px;
                    padding:1.5rem 2rem;margin-bottom:1.5rem;">
            <h2 style="color:#e94560;margin:0 0 0.3rem 0;">
                💰 VENTA DE PRIMA — Credit Spread Scanner
            </h2>
            <p style="color:#94a3b8;margin:0;font-size:0.9rem;">
                Encuentra Bull Put Spreads y Bear Call Spreads con alta probabilidad
                de ganancia y retorno óptimo sobre riesgo.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Filtros ──────────────────────────────────────────────────────────
    with st.expander("⚙️ Configuración del Scanner", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            selected_tickers = st.multiselect(
                "🔍 Tickers a escanear",
                options=_ALL_TICKERS,
                default=_DEFAULT_TICKERS,
                help="Selecciona los tickers donde buscar spreads.",
                key="cs_tickers",
            )
            min_pop_pct = st.slider(
                "📊 Min POP % (Prob. de Ganancia)",
                min_value=50, max_value=95, value=70, step=5,
                help="Solo muestra spreads con probabilidad de ganancia ≥ este valor.",
                key="cs_min_pop",
            )

        with col2:
            max_dte = st.slider(
                "📅 Máx DTE (Días al Vencimiento)",
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

        col3, col4 = st.columns(2)
        with col3:
            tipo_filter = st.radio(
                "📈 Tipo de Spread",
                ["Todos", "Bull Put", "Bear Call"],
                horizontal=True,
                key="cs_tipo_filter",
            )
        with col4:
            st.markdown("")  # spacer

    # ── Botón de escaneo ─────────────────────────────────────────────────
    scan_btn = st.button(
        "🚀 Ejecutar Scanner",
        type="primary",
        use_container_width=True,
        key="cs_scan_btn",
    )

    # ── Estado del último scan ───────────────────────────────────────────
    if scan_btn:
        if not selected_tickers:
            st.warning("⚠️ Selecciona al menos un ticker.")
            return

        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def _progress_cb(ticker: str, idx: int, total: int):
            pct = (idx + 1) / total
            progress_bar.progress(pct)
            status_text.markdown(
                f'<span style="color:#94a3b8;font-size:0.85rem;">'
                f'Escaneando <b style="color:#00ff88;">{ticker}</b> '
                f'({idx + 1}/{total})...</span>',
                unsafe_allow_html=True,
            )

        with st.spinner("Analizando cadenas de opciones..."):
            df = scan_credit_spreads(
                tickers=selected_tickers,
                min_pop=min_pop_pct / 100.0,
                max_dte=max_dte,
                min_credit=min_credit,
                progress_callback=_progress_cb,
            )

        progress_bar.empty()
        status_text.empty()

        # Guardar resultados en session_state
        st.session_state["cs_results"] = df
        st.session_state["cs_scan_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Mostrar resultados ───────────────────────────────────────────────
    df: pd.DataFrame | None = st.session_state.get("cs_results")
    scan_time = st.session_state.get("cs_scan_time")

    if df is None or df.empty:
        if df is not None:
            st.info("🔍 No se encontraron spreads con los filtros actuales. Ajusta los parámetros e intenta de nuevo.")
        else:
            st.markdown(
                '<p style="color:#64748b;text-align:center;padding:2rem 0;">'
                'Pulsa <b>🚀 Ejecutar Scanner</b> para buscar oportunidades.</p>',
                unsafe_allow_html=True,
            )
        return

    # Aplicar filtro de tipo
    df_filtered = df.copy()
    if tipo_filter == "Bull Put":
        df_filtered = df_filtered[df_filtered["Tipo"] == "Bull Put"]
    elif tipo_filter == "Bear Call":
        df_filtered = df_filtered[df_filtered["Tipo"] == "Bear Call"]

    if df_filtered.empty:
        st.info(f"No hay spreads de tipo '{tipo_filter}' en los resultados.")
        return

    # ── Status bar ───────────────────────────────────────────────────────
    n_bull = len(df_filtered[df_filtered["Tipo"] == "Bull Put"])
    n_bear = len(df_filtered[df_filtered["Tipo"] == "Bear Call"])
    st.markdown(
        f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                    padding:10px 18px;display:flex;align-items:center;gap:18px;
                    font-size:0.85rem;margin-bottom:1rem;">
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

    # ── Tabla estilizada ─────────────────────────────────────────────────
    def _style_row(row):
        """Aplica estilos condicionales a cada fila."""
        styles = [""] * len(row)
        cols = list(row.index)

        # Retorno % > 25% → verde
        if "Retorno %" in cols:
            idx = cols.index("Retorno %")
            if row["Retorno %"] > 25:
                styles[idx] = "color: #00ff88; font-weight: 700;"
            elif row["Retorno %"] > 15:
                styles[idx] = "color: #fbbf24; font-weight: 600;"

        # POP > 80% → verde bold
        if "POP %" in cols:
            idx = cols.index("POP %")
            if row["POP %"] > 80:
                styles[idx] = "color: #00ff88; font-weight: 700;"

        # Tipo → color
        if "Tipo" in cols:
            idx = cols.index("Tipo")
            if row["Tipo"] == "Bull Put":
                styles[idx] = "color: #22c55e;"
            else:
                styles[idx] = "color: #ef4444;"

        return styles

    # Columnas a mostrar en la tabla
    display_cols = [
        "Ticker", "Tipo", "Spot", "Strike Vendido", "Strike Comprado",
        "DTE", "Delta Vendido", "POP %", "Crédito", "Riesgo Máx",
        "Retorno %", "Volumen", "OI", "Bid-Ask",
    ]
    display_cols = [c for c in display_cols if c in df_filtered.columns]
    df_show = df_filtered[display_cols].reset_index(drop=True)

    styled = df_show.style.apply(_style_row, axis=1)

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=min(600, 40 + len(df_show) * 35),
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
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #1e3a2f;'
                    f'border-radius:8px;padding:8px 12px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b style="color:#22c55e;">{row["Ticker"]}</b> '
                    f'<span style="color:#94a3b8;">Sell {row["Strike Vendido"]}P / Buy {row["Strike Comprado"]}P</span> '
                    f'<span style="color:#64748b;">({row["DTE"]}d)</span><br>'
                    f'<span style="color:#00ff88;">Ret: {row["Retorno %"]:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">POP: {row["POP %"]:.0f}%</span> · '
                    f'<span style="color:#fbbf24;">Cr: ${row["Crédito"]:.2f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin resultados")

    with col_top2:
        st.markdown("##### 🔴 Top 5 Bear Call Spreads")
        top_bc = df_filtered[df_filtered["Tipo"] == "Bear Call"].head(5)
        if not top_bc.empty:
            for _, row in top_bc.iterrows():
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #3a1e1e;'
                    f'border-radius:8px;padding:8px 12px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b style="color:#ef4444;">{row["Ticker"]}</b> '
                    f'<span style="color:#94a3b8;">Sell {row["Strike Vendido"]}C / Buy {row["Strike Comprado"]}C</span> '
                    f'<span style="color:#64748b;">({row["DTE"]}d)</span><br>'
                    f'<span style="color:#00ff88;">Ret: {row["Retorno %"]:.1f}%</span> · '
                    f'<span style="color:#94a3b8;">POP: {row["POP %"]:.0f}%</span> · '
                    f'<span style="color:#fbbf24;">Cr: ${row["Crédito"]:.2f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin resultados")
