# -*- coding: utf-8 -*-
"""Data Analysis — main render orchestrator.

Sentimiento, soportes/resistencias, distribución, IV Rank, Monte Carlo, Anomaly Detection.
"""
import logging

import pandas as pd
import streamlit as st

from page_modules.data_analysis._sidebar_controls import prepare_analysis_data
from page_modules.data_analysis._charts import (
    render_gex_section,
    render_oi_heatmap_section,
    render_vol_surface_section,
)
from page_modules.data_analysis._chain_viewer import (
    render_sentiment_breakdown,
    render_supports_resistances,
)
from page_modules.data_analysis._volume_analysis import (
    render_distribution_charts,
    render_anomaly_section,
)
from page_modules.data_analysis._greeks_panel import (
    render_iv_rank_mc,
    render_mc_option_pricing,
    render_iv_forecast_section,
    render_fundamentals_section,
)

logger = logging.getLogger(__name__)


def render(ticker_symbol, **kwargs):
    st.markdown("### 📈 Data Analysis")

    if not st.session_state.datos_completos:
        st.info("Ejecuta un escaneo primero para ver los análisis.")
        return

    df_analisis = pd.DataFrame(st.session_state.datos_completos)
    if "Prima_Volumen" in df_analisis.columns:
        df_analisis = df_analisis.rename(columns={"Prima_Volumen": "Prima_Vol"})

    # Prepare dealer state, GEX profile, flow ratios, etc.
    page_data = prepare_analysis_data(df_analisis)

    # GEX + Volatility Engine
    render_gex_section(
        df_analisis=df_analisis,
        spot_gex=page_data["spot_gex"],
        gex_res=page_data["gex_res"],
        gex_profile=page_data["gex_profile"],
        skew_res=page_data["skew_res"],
        dealer_state=page_data["dealer_state"],
        squeeze=page_data["squeeze"],
        magnet=page_data["magnet"],
    )

    st.markdown("---")
    st.caption(f"*Datos del último escaneo — {ticker_symbol}* — {len(df_analisis):,} registros")

    # Sentiment breakdown
    render_sentiment_breakdown(df_analisis)

    st.markdown("---")

    # Supports & Resistances
    precio_actual = st.session_state.get("precio_subyacente", None)
    render_supports_resistances(df_analisis, precio_actual)

    st.markdown("---")

    # Distribution charts, top strikes, prima by expiry
    render_distribution_charts(df_analisis)

    # Advanced analytics: IV Rank + Monte Carlo
    precio_mc = st.session_state.get("precio_subyacente", 0) or 0
    iv_data = render_iv_rank_mc(df_analisis, ticker_symbol, precio_mc)

    st.markdown("---")

    # MC Option Pricing
    render_mc_option_pricing(df_analisis, ticker_symbol, precio_mc, iv_data)

    st.markdown("---")

    # OI Heatmap
    render_oi_heatmap_section(st.session_state.datos_completos)

    st.markdown("---")

    # Volatility Surface 3D
    render_vol_surface_section(st.session_state.datos_completos, precio_mc)

    st.markdown("---")

    # Anomaly Detection
    render_anomaly_section(ticker_symbol, st.session_state.datos_completos)

    st.markdown("---")

    # IV Forecast
    render_iv_forecast_section(ticker_symbol, df_analisis)

    st.markdown("---")

    # Fundamentals
    render_fundamentals_section(ticker_symbol)
