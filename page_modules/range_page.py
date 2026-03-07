# -*- coding: utf-8 -*-
"""Página: 📐 Range — Expected Move (Thinkorswim Style)."""
import logging
import time

import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import datetime

from core.scanner import crear_sesion_nueva, obtener_precio_actual
from core.expected_move import calcular_expected_move, calcular_em_straddle
from ui.components import render_pro_table
from utils.retry_utils import cb_yfinance, rl_yfinance

logger = logging.getLogger(__name__)


def render(ticker_symbol, **kwargs):
    st.markdown("### 📐 Expected Move — Rango Esperado de Movimiento")
    st.caption("Calcula el rango esperado de movimiento exactamente como lo muestra Thinkorswim / Charles Schwab.")

    # ── Obtener fechas de expiración disponibles ──
    fechas_exp_disponibles = list(st.session_state.get("fechas_escaneadas", []))
    if not fechas_exp_disponibles:
        try:
            cb_yfinance.check()
            session_rango, _ = crear_sesion_nueva()
            ticker_rango = yf.Ticker(ticker_symbol, session=session_rango)
            fechas_exp_disponibles = list(ticker_rango.options)
        except Exception as e:
            logger.warning("Error obteniendo fechas de expiración: %s", e)

    if not fechas_exp_disponibles:
        st.warning("⚠️ No se encontraron fechas de expiración. Escanea primero un ticker en Live Scanning.")
        return

    # ── Obtener precio actual ──
    precio_actual_rango = st.session_state.get("precio_subyacente")
    if not precio_actual_rango:
        precio_actual_rango, _err_p = obtener_precio_actual(ticker_symbol)
        if precio_actual_rango:
            st.session_state.precio_subyacente = precio_actual_rango

    if not precio_actual_rango:
        st.error("❌ No se pudo obtener el precio actual. Escanea primero el ticker.")
        return

    # ── Header con precio actual ──
    st.markdown(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px 20px;margin-bottom:16px;">'
        f'<span style="color:#94a3b8;font-size:0.85rem;">Ticker:</span> '
        f'<span style="color:#00ff88;font-size:1.3rem;font-weight:800;">{ticker_symbol}</span>'
        f'<span style="color:#334155;margin:0 12px;">|</span>'
        f'<span style="color:#94a3b8;font-size:0.85rem;">Precio Actual:</span> '
        f'<span style="color:white;font-size:1.3rem;font-weight:700;">${precio_actual_rango:,.2f}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Obtener cadena de opciones para cada fecha y calcular EM ──
    em_results = []

    # PRIORIDAD 1: usar datos ya escaneados en session_state (sin API calls)
    datos_scan = st.session_state.get("datos_completos")
    if datos_scan:
        df_scan = pd.DataFrame(datos_scan)
        # IV en datos_completos ya viene en % (ej: 28.5), convertir a decimal
        for exp_date in sorted(df_scan["Vencimiento"].unique()):
            try:
                df_exp = df_scan[df_scan["Vencimiento"] == exp_date]
                calls_exp = df_exp[df_exp["Tipo"] == "CALL"][["Strike", "IV", "Ask", "Bid", "Ultimo"]].copy()
                puts_exp  = df_exp[df_exp["Tipo"] == "PUT"][["Strike", "IV", "Ask", "Bid", "Ultimo"]].copy()

                calls_exp = calls_exp[calls_exp["IV"] > 0]
                puts_exp  = puts_exp[puts_exp["IV"] > 0]

                if calls_exp.empty or puts_exp.empty:
                    continue

                atm_call = calls_exp.iloc[(calls_exp["Strike"] - precio_actual_rango).abs().argsort()[:1]].iloc[0]
                atm_put  = puts_exp.iloc[(puts_exp["Strike"] - precio_actual_rango).abs().argsort()[:1]].iloc[0]

                iv_call = float(atm_call["IV"]) / 100
                iv_put  = float(atm_put["IV"]) / 100
                iv_avg  = (iv_call + iv_put) / 2 if iv_call > 0 and iv_put > 0 else max(iv_call, iv_put)

                if iv_avg <= 0:
                    continue

                exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
                dte = max((exp_dt - datetime.now()).total_seconds() / 86400, 0.01)

                em = calcular_expected_move(precio_actual_rango, iv_avg, dte)

                call_price = float(atm_call.get("Ultimo") or atm_call.get("Ask") or 0)
                put_price  = float(atm_put.get("Ultimo") or atm_put.get("Ask") or 0)
                em_straddle = calcular_em_straddle(precio_actual_rango, call_price, put_price) if call_price > 0 and put_price > 0 else None

                em_results.append({
                    "expiration": exp_date,
                    "dte": round(dte, 1),
                    "iv_atm": round(iv_avg * 100, 2),
                    "em": em,
                    "em_straddle": em_straddle,
                    "call_strike": float(atm_call["Strike"]),
                    "call_price": round(call_price, 2),
                    "call_iv": round(iv_call * 100, 2),
                    "put_strike": float(atm_put["Strike"]),
                    "put_price": round(put_price, 2),
                    "put_iv": round(iv_put * 100, 2),
                })
            except Exception as e:
                logger.warning("Range (scan data): error en %s: %s", exp_date, e)
                continue

    # PRIORIDAD 2: fallback — fetch desde yfinance si no hay datos escaneados
    if not em_results:
        with st.spinner("Cargando opciones desde Yahoo Finance..."):
            try:
                cb_yfinance.check()
                session_em, _ = crear_sesion_nueva()
                ticker_em = yf.Ticker(ticker_symbol, session=session_em)

                for exp_date in fechas_exp_disponibles:
                    try:
                        if not rl_yfinance.acquire(timeout=30):
                            logger.warning("Range: timeout rate limiter para %s", exp_date)
                            continue

                        chain = ticker_em.option_chain(exp_date)
                        exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
                        dte = max((exp_dt - datetime.now()).total_seconds() / 86400, 0.01)

                        calls_df = chain.calls
                        puts_df  = chain.puts

                        if calls_df.empty or puts_df.empty:
                            continue

                        calls_df = calls_df[calls_df["impliedVolatility"].notna() & (calls_df["impliedVolatility"] > 0)]
                        puts_df  = puts_df[puts_df["impliedVolatility"].notna() & (puts_df["impliedVolatility"] > 0)]

                        if calls_df.empty or puts_df.empty:
                            continue

                        atm_call = calls_df.loc[(calls_df["strike"] - precio_actual_rango).abs().idxmin()]
                        atm_put  = puts_df.loc[(puts_df["strike"] - precio_actual_rango).abs().idxmin()]

                        iv_call = float(atm_call.get("impliedVolatility", 0) or 0)
                        iv_put  = float(atm_put.get("impliedVolatility", 0) or 0)
                        iv_avg  = (iv_call + iv_put) / 2 if iv_call > 0 and iv_put > 0 else max(iv_call, iv_put)
                        if iv_avg <= 0:
                            continue

                        em = calcular_expected_move(precio_actual_rango, iv_avg, dte)
                        call_price = float(atm_call.get("lastPrice", 0) or atm_call.get("ask", 0) or 0)
                        put_price  = float(atm_put.get("lastPrice", 0) or atm_put.get("ask", 0) or 0)
                        em_straddle = calcular_em_straddle(precio_actual_rango, call_price, put_price) if call_price > 0 and put_price > 0 else None

                        em_results.append({
                            "expiration": exp_date,
                            "dte": round(dte, 1),
                            "iv_atm": round(iv_avg * 100, 2),
                            "em": em,
                            "em_straddle": em_straddle,
                            "call_strike": float(atm_call["strike"]),
                            "call_price": round(call_price, 2),
                            "call_iv": round(iv_call * 100, 2),
                            "put_strike": float(atm_put["strike"]),
                            "put_price": round(put_price, 2),
                            "put_iv": round(iv_put * 100, 2),
                        })

                    except Exception as e:
                        logger.warning("Range (yfinance): error en %s: %s", exp_date, e)
                        continue

            except Exception as e:
                st.error(f"Error obteniendo cadena de opciones: {e}")

    # ── Tabla principal de Expected Move por fecha ──
    if not em_results:
        if not st.session_state.get("datos_completos"):
            st.info("⏳ Ejecuta un escaneo en **Live Scanning** primero — Range usará los datos ya cargados sin llamadas adicionales a la API.")
        else:
            st.warning("⚠️ No se pudo calcular el Expected Move. Los datos escaneados no tienen IV disponible para este ticker.")
        return

    st.markdown("#### 📊 Expected Move por Fecha de Expiración")

    tabla_em = []
    for r in em_results:
        em = r["em"]
        em_s = r["em_straddle"]
        tabla_em.append({
            "Expiración": r["expiration"],
            "DTE": f"{r['dte']:.0f}d" if r["dte"] >= 1 else f"{r['dte']*24:.0f}h",
            "IV ATM": f"{r['iv_atm']:.1f}%",
            "EM ±$": f"±${em['em_dolares']:,.2f}",
            "EM %": f"±{em['porcentaje']:.2f}%",
            "Rango": f"${em['lower']:,.2f} — ${em['upper']:,.2f}",
            "Straddle ±$": f"±${em_s['em_dolares']:,.2f}" if em_s else "N/D",
            "Call ATM": f"${r['call_strike']:,.1f} (${r['call_price']:.2f})",
            "Put ATM": f"${r['put_strike']:,.1f} (${r['put_price']:.2f})",
        })

    em_df = pd.DataFrame(tabla_em)
    st.markdown(
        render_pro_table(em_df, title=f"📐 Expected Move — {ticker_symbol}", badge_count=f"{len(tabla_em)} fechas"),
        unsafe_allow_html=True,
    )

    # ── Detalle visual: seleccionar fecha para ver breakdown ──
    st.markdown("---")
    st.markdown("#### 🔍 Detalle por Expiración")

    selected_exp = st.selectbox(
        "Selecciona una fecha de expiración:",
        [r["expiration"] for r in em_results],
        format_func=lambda x: f"{x}  ({next((r['dte'] for r in em_results if r['expiration'] == x), 0):.0f} días)",
        key="em_detail_select",
    )

    sel = next((r for r in em_results if r["expiration"] == selected_exp), None)
    if sel:
        em = sel["em"]
        em_s = sel["em_straddle"]

        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        with col_e1:
            st.metric("📅 DTE", f"{sel['dte']:.1f} días")
        with col_e2:
            st.metric("📊 IV ATM", f"{sel['iv_atm']:.1f}%")
        with col_e3:
            st.metric("±$ Expected Move", f"±${em['em_dolares']:,.2f}", f"±{em['porcentaje']:.2f}%")
        with col_e4:
            if em_s:
                st.metric("±$ Straddle EM", f"±${em_s['em_dolares']:,.2f}", f"±{em_s['porcentaje']:.2f}%")
            else:
                st.metric("±$ Straddle EM", "N/D")

        # Barra visual de rango
        st.markdown("")
        full_range = em["upper"] - em["lower"]
        if full_range > 0:
            precio_pos = (precio_actual_rango - em["lower"]) / full_range
        else:
            precio_pos = 0.5

        bar_c1, bar_c2, bar_c3 = st.columns([1, 6, 1])
        with bar_c1:
            st.markdown(f"**▼ ${em['lower']:,.2f}**")
        with bar_c2:
            progress_val = max(0.0, min(1.0, precio_pos))
            st.progress(progress_val, text=f"● ${precio_actual_rango:,.2f}  —  Rango: ${em['lower']:,.2f} a ${em['upper']:,.2f}")
        with bar_c3:
            st.markdown(f"**▲ ${em['upper']:,.2f}**")

        # Contratos ATM usados
        st.markdown("")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.success(f"""
**📈 CALL ATM**
- Strike: **${sel['call_strike']:,.1f}**
- Prima: **${sel['call_price']:.2f}**
- IV: **{sel['call_iv']:.1f}%**
""")
        with col_c2:
            st.error(f"""
**📉 PUT ATM**
- Strike: **${sel['put_strike']:,.1f}**
- Prima: **${sel['put_price']:.2f}**
- IV: **{sel['put_iv']:.1f}%**
""")
