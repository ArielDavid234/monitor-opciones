"""Initial data preparation helpers for the Data Analysis page."""
import logging

import pandas as pd
import streamlit as st

from core.dealer_positioning import (
    infer_dealer_position,
    detect_gamma_squeeze_conditions,
    detect_liquidity_magnet,
)
from core.gex_engine import build_gex_profile, calculate_volatility_skew

logger = logging.getLogger(__name__)


def prepare_analysis_data(df_analisis):
    """Compute dealer state, flow ratios, GEX profile and skew.

    Returns:
        dict with keys: dealer_state, squeeze, magnet, gex_res, gex_profile,
                        skew_res, spot_gex, gex_total, bullish_flow, bearish_flow.
    """
    _call_vol = (
        float(df_analisis.loc[df_analisis["Tipo"] == "CALL", "Volumen"].sum())
        if "Volumen" in df_analisis.columns else 0.0
    )
    _put_vol = (
        float(df_analisis.loc[df_analisis["Tipo"] == "PUT", "Volumen"].sum())
        if "Volumen" in df_analisis.columns else 0.0
    )

    _bullish_flow = 0.0
    _bearish_flow = 0.0
    if all(c in df_analisis.columns for c in ["Ask", "Bid", "Ultimo", "Tipo"]) and "Prima_Vol" in df_analisis.columns:
        _df_flow = df_analisis.copy()
        _df_flow["_mid"] = (_df_flow["Ask"] + _df_flow["Bid"]) / 2.0
        _mask_call = _df_flow["Tipo"] == "CALL"
        _mask_put = _df_flow["Tipo"] == "PUT"
        _mask_ask = _df_flow["Ultimo"] >= _df_flow["_mid"]
        _mask_bid = _df_flow["Ultimo"] < _df_flow["_mid"]
        _bullish_flow = float(
            _df_flow.loc[_mask_call & _mask_ask, "Prima_Vol"].sum()
            + _df_flow.loc[_mask_put & _mask_bid, "Prima_Vol"].sum()
        )
        _bearish_flow = float(
            _df_flow.loc[_mask_call & _mask_bid, "Prima_Vol"].sum()
            + _df_flow.loc[_mask_put & _mask_ask, "Prima_Vol"].sum()
        )
    elif all(c in df_analisis.columns for c in ["Ultimo", "Volumen", "Tipo"]):
        _df_flow = df_analisis.copy()
        _df_flow["_prem"] = _df_flow["Ultimo"].fillna(0) * _df_flow["Volumen"].fillna(0) * 100.0
        _bullish_flow = float(_df_flow.loc[_df_flow["Tipo"] == "CALL", "_prem"].sum())
        _bearish_flow = float(_df_flow.loc[_df_flow["Tipo"] == "PUT", "_prem"].sum())

    dealer_state = infer_dealer_position(
        call_volume=_call_vol,
        put_volume=_put_vol,
        bullish_flow=_bullish_flow,
        bearish_flow=_bearish_flow,
    )

    spot_gex = st.session_state.get("precio_subyacente", 0.0)
    try:
        spot_gex = float(spot_gex) if spot_gex is not None else 0.0
    except Exception:
        spot_gex = 0.0
    if spot_gex <= 0:
        if "Spot" in df_analisis.columns and not df_analisis["Spot"].dropna().empty:
            spot_gex = float(df_analisis["Spot"].dropna().iloc[0])
        elif "Strike" in df_analisis.columns:
            spot_gex = float(df_analisis["Strike"].median())

    try:
        gex_res = build_gex_profile(df_analisis, spot_price=spot_gex)
        gex_profile = gex_res.get("profile", pd.DataFrame())
        skew_res = calculate_volatility_skew(df_analisis)
    except Exception as exc:
        logger.error("Error calculando GEX/Skew: %s", exc, exc_info=True)
        gex_profile = pd.DataFrame()
        skew_res = {
            "put_iv_10otm": 0.0,
            "call_iv_10otm": 0.0,
            "skew": 0.0,
            "regime": "Sin datos",
        }
        gex_res = {}

    _gex_total = (
        float(gex_profile["Net GEX"].sum())
        if not gex_profile.empty and "Net GEX" in gex_profile.columns else 0.0
    )
    _flow_total = _bullish_flow + _bearish_flow
    _bull_ratio = (_bullish_flow / _flow_total) if _flow_total > 0 else 0.5
    _iv_now = (
        float(df_analisis["IV"].dropna().mean())
        if "IV" in df_analisis.columns and not df_analisis["IV"].dropna().empty else 30.0
    )
    _oi_calls = (
        float(df_analisis.loc[df_analisis["Tipo"] == "CALL", "OI"].sum())
        if "OI" in df_analisis.columns else 0.0
    )
    _oi_puts = (
        float(df_analisis.loc[df_analisis["Tipo"] == "PUT", "OI"].sum())
        if "OI" in df_analisis.columns else 0.0
    )
    _short_proxy = (_oi_puts / _oi_calls) if _oi_calls > 0 else 1.0

    squeeze = detect_gamma_squeeze_conditions(
        gex_total=_gex_total,
        bullish_flow_ratio=float(_bull_ratio),
        current_iv=float(_iv_now),
        short_interest_proxy=float(_short_proxy),
    )
    magnet = detect_liquidity_magnet(df_analisis, spot_price=spot_gex, move_pct=0.01)

    return {
        "dealer_state": dealer_state,
        "squeeze": squeeze,
        "magnet": magnet,
        "gex_res": gex_res,
        "gex_profile": gex_profile,
        "skew_res": skew_res,
        "spot_gex": spot_gex,
        "gex_total": _gex_total,
        "bullish_flow": _bullish_flow,
        "bearish_flow": _bearish_flow,
    }
