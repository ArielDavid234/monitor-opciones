"""Metrics panel for the Live Scanning page."""
import streamlit as st

from ui.components import render_metric_card, render_metric_row


def render_metrics_panel(datos_df, ticker_symbol, enrich_key):
    """Render the scan metrics row (flow sentiment, GEX, IV rank, etc.)."""
    from core.gamma_exposure import calcular_gex_desde_scanner

    st.markdown("### 📊 Métricas del Escaneo")

    _n_calls = len(datos_df[datos_df["Tipo"] == "CALL"])
    _n_puts = len(datos_df[datos_df["Tipo"] == "PUT"])
    _n_alertas = len(st.session_state.alertas_actuales)
    _n_clusters = len(st.session_state.clusters_detectados)
    _total = len(datos_df)
    _call_pct = (_n_calls / _total * 100) if _total else 0
    _put_pct = (_n_puts / _total * 100) if _total else 0
    _pc_ratio = _n_puts / _n_calls if _n_calls > 0 else 0
    _total_vol = int(datos_df["Volumen"].sum()) if "Volumen" in datos_df.columns else 0
    _flow_pct = _call_pct - _put_pct
    _spk = sorted(datos_df["Volumen"].dropna().tail(12).tolist()) if "Volumen" in datos_df.columns else None
    _spk_oi = sorted(datos_df["OI"].dropna().tail(12).tolist()) if "OI" in datos_df.columns else None

    _precio_sub_gex = st.session_state.get("precio_subyacente") or 0
    if _precio_sub_gex and _precio_sub_gex > 0:
        if st.session_state.get("_gex_cache_key") != enrich_key:
            _gex_result = calcular_gex_desde_scanner(
                st.session_state.datos_completos, spot_price=_precio_sub_gex, mode="standard"
            )
            st.session_state["_gex_cache"] = _gex_result
            st.session_state["_gex_cache_key"] = enrich_key
        else:
            _gex_result = st.session_state["_gex_cache"]
        _gex_total = _gex_result["total_gex"]
        _gex_zero = _gex_result["zero_gamma_level"]
        _gex_cw = _gex_result["call_wall"]
        _gex_pw = _gex_result["put_wall"]
    else:
        _gex_total = 0.0
        _gex_zero = 0.0
        _gex_cw = 0.0
        _gex_pw = 0.0
    _gex_fmt = f"${_gex_total:+.2f}M" if _gex_total != 0 else "N/D"

    st.markdown(render_metric_row([
        render_metric_card("Flow Sentiment", f"{_flow_pct:+.1f}%", delta=_flow_pct, sparkline_data=_spk),
        render_metric_card("Total Volume", f"{_total_vol:,}", delta=_call_pct, delta_suffix="% calls"),
        render_metric_card(
            "Gamma Exposure", _gex_fmt, sparkline_data=_spk_oi,
            color_override="#00ff88" if _gex_total >= 0 else "#ef4444",
        ),
        render_metric_card(
            "Put/Call Ratio", f"{_pc_ratio:.2f}",
            delta=-(_pc_ratio - 1) * 100 if _pc_ratio != 0 else 0,
            color_override="#ef4444" if _pc_ratio > 1 else "#00ff88",
        ),
        render_metric_card("Unusual Alerts", f"{_n_alertas}", delta=float(_n_clusters), delta_suffix=" clusters"),
    ]), unsafe_allow_html=True)

    if _precio_sub_gex and _gex_total != 0:
        st.markdown(render_metric_row([
            render_metric_card("Zero Gamma", f"${_gex_zero:,.2f}"),
            render_metric_card("Call Wall", f"${_gex_cw:,.2f}", color_override="#00ff88"),
            render_metric_card("Put Wall", f"${_gex_pw:,.2f}", color_override="#ef4444"),
            render_metric_card("Spot Price", f"${_precio_sub_gex:,.2f}"),
        ]), unsafe_allow_html=True)

    # IV Rank quick indicator (cached)
    _iv_r_cache_key = f"_iv_rank_live_{ticker_symbol}_{st.session_state.get('scan_count', 0)}"
    if st.session_state.get(_iv_r_cache_key) is None:
        try:
            from core.iv_rank import calcular_iv_rank_percentile
            avg_iv_live = datos_df["IV"].median() if "IV" in datos_df.columns else None
            st.session_state[_iv_r_cache_key] = calcular_iv_rank_percentile(
                ticker_symbol, iv_actual=avg_iv_live,
            )
        except Exception:
            st.session_state[_iv_r_cache_key] = {}

    _iv_live = st.session_state.get(_iv_r_cache_key, {})
    if _iv_live and _iv_live.get("iv_rank", 0) > 0:
        _ivr = _iv_live["iv_rank"]
        _ivp = _iv_live["iv_percentile"]
        _iv_col = "#ef4444" if _ivr >= 60 else "#f59e0b" if _ivr >= 30 else "#10b981"
        st.markdown(render_metric_row([
            render_metric_card("IV Rank", f"{_ivr:.0f}%", color_override=_iv_col),
            render_metric_card("IV Percentile", f"{_ivp:.0f}%", color_override=_iv_col),
            render_metric_card("IV Actual", f"{_iv_live['iv_actual']:.1f}%"),
            render_metric_card("HV 20d", f"{_iv_live['hv_20d']:.1f}%"),
        ]), unsafe_allow_html=True)
