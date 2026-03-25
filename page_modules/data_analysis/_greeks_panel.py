"""Greeks panel: IV Rank, Monte Carlo simulation & option pricing, IV forecast, fundamentals."""
import logging

import numpy as np
import streamlit as st

from ui.components import render_metric_card, render_metric_row, render_fundamentals_card
from ui.charts import render_iv_gauge, render_monte_carlo_chart

logger = logging.getLogger(__name__)


def render_iv_rank_mc(df_analisis, ticker_symbol, precio_mc):
    """Render IV Rank gauge + Monte Carlo simulation in a two-column layout.

    Returns:
        iv_data (dict | None) — cached IV rank data for downstream reuse.
    """
    st.markdown("---")
    st.markdown("### 🧠 Análisis Avanzado")

    _iv_cache_key = f"_iv_rank_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    if st.session_state.get(_iv_cache_key) is None:
        try:
            from core.iv_rank import calcular_iv_rank_percentile
            avg_iv = df_analisis["IV"].median() if "IV" in df_analisis.columns else None
            iv_data = calcular_iv_rank_percentile(ticker_symbol, iv_actual=avg_iv)
            st.session_state[_iv_cache_key] = iv_data
        except Exception as e:
            logger.warning("Error calculando IV Rank: %s", e)
            st.session_state[_iv_cache_key] = None

    iv_data = st.session_state.get(_iv_cache_key)

    col_adv1, col_adv2 = st.columns(2)

    with col_adv1:
        if iv_data and iv_data["iv_rank"] > 0:
            fig_iv = render_iv_gauge(
                iv_data["iv_rank"],
                iv_data["iv_percentile"],
                iv_data["iv_actual"],
            )
            st.plotly_chart(fig_iv, use_container_width=True, key="iv_gauge")
            st.markdown(render_metric_row([
                render_metric_card("IV Actual", f"{iv_data['iv_actual']:.1f}%"),
                render_metric_card("IV Max 52w", f"{iv_data['iv_high_52w']:.1f}%", color_override="#ef4444"),
                render_metric_card("IV Min 52w", f"{iv_data['iv_low_52w']:.1f}%", color_override="#10b981"),
                render_metric_card("HV 20d", f"{iv_data['hv_20d']:.1f}%"),
            ]), unsafe_allow_html=True)

            if iv_data["iv_rank"] >= 60:
                st.info("📈 **IV alta** — Buen momento para VENDER opciones (prima elevada)")
            elif iv_data["iv_rank"] <= 30:
                st.info("📉 **IV baja** — Buen momento para COMPRAR opciones (prima barata)")
            else:
                st.info("↔️ **IV media** — Sin ventaja clara direccional en volatilidad")
        else:
            st.info("⏳ Calculando IV Rank... Ejecuta un escaneo para activar.")

    with col_adv2:
        if precio_mc > 0:
            iv_for_mc = 0.25
            if iv_data and iv_data["iv_actual"] > 0:
                iv_for_mc = iv_data["iv_actual"] / 100
            elif "IV" in df_analisis.columns:
                med_iv = df_analisis["IV"].median()
                if med_iv > 0:
                    iv_for_mc = med_iv / 100

            mc_cache_key = f"_mc_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
            if st.session_state.get(mc_cache_key) is None:
                try:
                    from core.monte_carlo import simular_monte_carlo
                    mc_result = simular_monte_carlo(spot_price=precio_mc, iv=iv_for_mc, days=30, num_sims=1_000)
                    st.session_state[mc_cache_key] = mc_result
                except Exception as e:
                    logger.warning("Error Monte Carlo: %s", e)
                    st.session_state[mc_cache_key] = None

            mc_result = st.session_state.get(mc_cache_key)
            if mc_result and mc_result["days"] > 0:
                fig_mc = render_monte_carlo_chart(mc_result, precio_mc, ticker_symbol)
                st.plotly_chart(fig_mc, use_container_width=True, key="mc_chart")
                pctls = mc_result["percentiles"]
                st.markdown(render_metric_row([
                    render_metric_card(
                        "P(Sube)", f"{mc_result['prob_above']:.1f}%",
                        color_override="#10b981" if mc_result["prob_above"] > 50 else "#ef4444",
                    ),
                    render_metric_card("Precio Esperado", f"${mc_result['expected_price']:,.2f}"),
                    render_metric_card("Rango 90%", f"${pctls['p5']:,.2f} — ${pctls['p95']:,.2f}"),
                ]), unsafe_allow_html=True)
        else:
            st.info("⏳ Ejecuta un escaneo para activar Monte Carlo.")

    return iv_data


def render_mc_option_pricing(df_analisis, ticker_symbol, precio_mc, iv_data):
    """Render the MC option pricing section."""
    st.markdown("#### 🎲 Valoración MC de Opciones (Riesgo Ajustado)")
    st.caption(
        "Simula miles de trayectorias del subyacente para estimar el precio teórico "
        "de una opción, la probabilidad de terminar ITM, y la distribución de payoffs."
    )

    _mc_opt_col1, _mc_opt_col2, _mc_opt_col3, _mc_opt_col4 = st.columns(4)
    _strikes_disponibles = sorted(df_analisis["Strike"].unique()) if "Strike" in df_analisis.columns else []
    _spot = precio_mc or 0

    with _mc_opt_col1:
        mc_opt_type = st.selectbox("Tipo de opción", ["CALL", "PUT"], index=0, key="mc_opt_type")

    with _mc_opt_col2:
        if _strikes_disponibles and _spot > 0:
            _atm_idx = int(np.argmin([abs(s - _spot) for s in _strikes_disponibles]))
            mc_strike = st.selectbox(
                "Strike", _strikes_disponibles, index=_atm_idx, key="mc_opt_strike",
                format_func=lambda x: f"${x:,.1f}",
            )
        else:
            mc_strike = st.number_input("Strike ($)", value=_spot or 100.0, min_value=1.0, step=1.0, key="mc_opt_strike_input")

    with _mc_opt_col3:
        mc_n_sims = st.select_slider(
            "Simulaciones", options=[1_000, 5_000, 10_000, 25_000, 50_000],
            value=10_000, key="mc_opt_nsims",
        )

    with _mc_opt_col4:
        mc_days = st.slider("Días al vencimiento", min_value=5, max_value=180, value=30, step=5, key="mc_opt_days")

    if not (_spot > 0 and mc_strike > 0):
        st.info("⏳ Ejecuta un escaneo para activar la valoración MC de opciones.")
        return

    _mc_iv = 0.25
    if iv_data and iv_data["iv_actual"] > 0:
        _mc_iv = iv_data["iv_actual"] / 100
    elif "IV" in df_analisis.columns:
        _med = df_analisis["IV"].median()
        if _med > 0:
            _mc_iv = _med / 100

    _mc_opt_key = (
        f"_mc_opt_{ticker_symbol}_{mc_opt_type}_{mc_strike}_{mc_days}"
        f"_{mc_n_sims}_{st.session_state.get('scan_count', 0)}"
    )

    if st.session_state.get(_mc_opt_key) is None:
        try:
            from core.monte_carlo import monte_carlo_option_pricing
            from config.constants import RISK_FREE_RATE
            mc_opt_result = monte_carlo_option_pricing(
                S0=_spot, K=float(mc_strike), T=mc_days / 365,
                r=RISK_FREE_RATE, sigma=_mc_iv,
                option_type=mc_opt_type.lower(),
                n_sims=mc_n_sims, n_steps=mc_days,
            )
            st.session_state[_mc_opt_key] = mc_opt_result
        except Exception as e:
            logger.warning("Error MC Option Pricing: %s", e)
            st.session_state[_mc_opt_key] = {"error": str(e)}

    mc_opt = st.session_state.get(_mc_opt_key, {})

    if "error" in mc_opt:
        st.warning(f"MC Option: {mc_opt.get('error', 'Error desconocido')}")
        return

    st.markdown(mc_opt["interpretation"])
    st.markdown(render_metric_row([
        render_metric_card("Precio MC", f"${mc_opt['mc_price']:.2f}", color_override="#00ff88"),
        render_metric_card(
            "P(ITM)", f"{mc_opt['itm_probability']:.1f}%",
            color_override="#10b981" if mc_opt["itm_probability"] >= 50 else "#ef4444",
        ),
        render_metric_card("Payoff Esperado", f"${mc_opt['expected_payoff']:.2f}"),
        render_metric_card("Break-Even", f"${mc_opt['breakeven']:,.2f}"),
    ]), unsafe_allow_html=True)

    from ui.charts import render_mc_option_paths, render_mc_payoff_histogram
    col_mc1, col_mc2 = st.columns(2)
    with col_mc1:
        fig_paths = render_mc_option_paths(mc_opt, ticker_symbol)
        if fig_paths:
            st.plotly_chart(fig_paths, use_container_width=True, key="mc_opt_paths")
    with col_mc2:
        fig_payoff = render_mc_payoff_histogram(mc_opt, ticker_symbol)
        if fig_payoff:
            st.plotly_chart(fig_payoff, use_container_width=True, key="mc_opt_payoff")

    with st.expander("📊 Métricas de riesgo detalladas"):
        _r1, _r2, _r3 = st.columns(3)
        with _r1:
            st.metric("Mediana Payoff", f"${mc_opt['median_payoff']:.2f}")
            st.metric("Std Payoff", f"${mc_opt['std_payoff']:.2f}")
        with _r2:
            st.metric("VaR 95%", f"${mc_opt['var_95']:.2f}")
            st.metric("CVaR 95%", f"${mc_opt['cvar_95']:.2f}")
        with _r3:
            st.metric("Max Drawdown", f"{mc_opt['max_drawdown_pct']:.1f}%")
            st.metric("P95 Payoff", f"${mc_opt['payoff_percentiles']['p95']:.2f}")

        st.markdown(f"""
**Parámetros usados:**
- Spot: ${mc_opt['params']['S0']:,.2f} | Strike: ${mc_opt['params']['K']:,.1f}
- σ (IV): {mc_opt['params']['sigma']*100:.1f}% | r: {mc_opt['params']['r']*100:.2f}%
- T: {mc_opt['params']['T']:.4f} años ({mc_days} días) | Sims: {mc_opt['params']['n_sims']:,}
""")
        st.caption(
            "⚠️ MC pricing es orientativo — asume distribución log-normal y "
            "sin saltos. No incluye costos de transacción ni spread bid/ask."
        )


def render_iv_forecast_section(ticker_symbol, df_analisis):
    """Render IV forecast (linear regression) section."""
    import pandas as pd

    st.markdown("#### 🔮 Predicción de Volatilidad Implícita (Regresión Lineal)")
    _ivf_cache_key = f"_iv_forecast_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"

    if st.session_state.get(_ivf_cache_key) is None:
        try:
            from core.iv_rank import get_historical_iv
            from core.projections import predict_implied_volatility
            df_iv_hist = get_historical_iv(ticker_symbol, period="1y")
            if df_iv_hist.empty:
                st.session_state[_ivf_cache_key] = {"error": "Sin datos históricos suficientes"}
            else:
                forecast_result = predict_implied_volatility(df_iv_hist, forecast_days=5)
                st.session_state[_ivf_cache_key] = forecast_result
                st.session_state[f"{_ivf_cache_key}_hist"] = df_iv_hist
        except Exception as e:
            logger.warning("Error IV Forecast: %s", e)
            st.session_state[_ivf_cache_key] = {"error": f"Error: {e}"}

    iv_forecast = st.session_state.get(_ivf_cache_key, {})
    df_iv_hist = st.session_state.get(f"{_ivf_cache_key}_hist", pd.DataFrame())

    if "error" in iv_forecast:
        st.warning(f"📊 IV Forecast: {iv_forecast.get('error', 'Error desconocido')}")
        return

    st.markdown(iv_forecast["interpretation"])

    from ui.charts import render_iv_forecast_chart
    fig_ivf = render_iv_forecast_chart(df_iv_hist, iv_forecast, ticker_symbol)
    if fig_ivf:
        st.plotly_chart(fig_ivf, use_container_width=True, key="iv_forecast_chart")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        st.metric("IV Predicha", f"{iv_forecast['predicted_iv']:.1f}%", delta=f"{iv_forecast['delta_iv']:+.1f}pp")
    with col_f2:
        st.metric("IV Actual", f"{iv_forecast['current_iv']:.1f}%")
    with col_f3:
        st.metric("R² Modelo", f"{iv_forecast['r2_score']:.3f}")
    with col_f4:
        st.metric("Rango ±1σ", f"{iv_forecast['forecast_range'][0]:.1f}% — {iv_forecast['forecast_range'][1]:.1f}%")

    with st.expander("📊 Detalles del modelo (transparencia)"):
        st.markdown(f"""
**Modelo:** Regresión Lineal (scikit-learn)
**Muestras:** {iv_forecast.get('n_samples', 'N/A')} días históricos
**Forecast:** {iv_forecast['forecast_days']} días
**Features usadas:** `{', '.join(iv_forecast['model_features'])}`
**Error estándar (σ):** ±{iv_forecast.get('pred_std', 0):.2f}%

**Coeficientes del modelo:**
""")
        coefs = iv_forecast.get("coefficients", {})
        for feat, coef in coefs.items():
            arrow = "↑" if coef > 0 else "↓"
            st.markdown(f"- **{feat}**: `{coef:+.6f}` {arrow}")
        st.caption(
            "⚠️ Modelo orientativo — no es recomendación financiera. "
            "La IV real depende de eventos macro, earnings, y flujos institucionales "
            "que un modelo lineal no captura. Usar como referencia complementaria."
        )


def render_fundamentals_section(ticker_symbol):
    """Render Alpha Vantage fundamentals card."""
    st.markdown("#### 📊 Datos Fundamentales (Alpha Vantage)")
    st.caption(
        "Valuación, rentabilidad, earnings surprise y short interest — "
        "contextualiza opciones con fundamentos reales de la empresa."
    )

    _fund_cache_key = f"_fundamentals_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    _cached_fund = st.session_state.get(_fund_cache_key)
    if _cached_fund is None or "error" in _cached_fund:
        try:
            from core.projections import enrich_with_fundamentals
            fund_data = enrich_with_fundamentals(ticker_symbol)
            if "error" not in fund_data:
                st.session_state[_fund_cache_key] = fund_data
        except Exception as e:
            logger.warning("Error fundamentals: %s", e)
            fund_data = {"error": f"Error: {e}"}
    else:
        fund_data = _cached_fund

    render_fundamentals_card(fund_data, ticker_symbol)
