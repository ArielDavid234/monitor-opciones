"""Live Scanning — main render orchestrator."""
import logging
import time

import streamlit as st

from config.constants import AUTO_REFRESH_INTERVAL
from infrastructure.platform.business_value import get_plan_policy, get_plan_sla, get_user_plan
from utils.helpers import _enriquecer_datos_opcion

from page_modules.live_scanning._sidebar_filters import (
    render_sidebar_filters,
    render_scan_controls,
    render_status_bar,
)
from page_modules.live_scanning._scanner_engine import render_plan_usage, run_scan
from page_modules.live_scanning._metrics_panel import render_metrics_panel
from page_modules.live_scanning._results_display import render_alerts_section

logger = logging.getLogger(__name__)


def render(ticker_symbol, **kwargs):
    import pandas as pd
    from core.container import get_container

    _container = get_container()
    _auth = _container.auth
    _current_user = _auth.get_current_user() or {}
    _user_id = str(_current_user.get("id") or "")
    _user_plan = get_user_plan(_current_user)
    _plan_policy = get_plan_policy(_user_plan)
    _plan_sla = get_plan_sla(_user_plan)

    (
        umbral_vol, umbral_oi, umbral_prima, umbral_delta,
        min_sm_flow_score, min_inst_flow,
        inst_only_inst_whale, inst_only_delta_60_80, inst_only_stock_sub,
    ) = render_sidebar_filters(ticker_symbol, **kwargs)

    scan_btn, auto_scan = render_scan_controls(ticker_symbol)

    render_status_bar()

    render_plan_usage(_auth, _user_id, _user_plan, _plan_policy, _plan_sla)

    auto_trigger = st.session_state.trigger_scan
    if auto_trigger:
        st.session_state.trigger_scan = False

    if scan_btn or auto_trigger:
        run_scan(
            ticker_symbol=ticker_symbol,
            umbral_vol=umbral_vol,
            umbral_oi=umbral_oi,
            umbral_prima=umbral_prima,
            umbral_delta=umbral_delta,
            user_id=_user_id,
            user_plan=_user_plan,
            plan_policy=_plan_policy,
            auth=_auth,
            container=_container,
            auto_trigger=auto_trigger,
        )

    st.session_state.auto_scan = auto_scan

    if st.session_state.get("scan_error"):
        _scan_err = st.session_state.scan_error
        st.warning(f"{_scan_err}")
        if st.button("✖ Descartar error", key="dismiss_scan_error"):
            st.session_state.scan_error = None
            st.rerun()

    # Build datos_df once + cache enrichment — all downstream sections reuse these
    _datos_df: pd.DataFrame | None = None
    _datos_enriquecidos_cache = None
    _enrich_key = None

    if st.session_state.datos_completos:
        _datos_df = pd.DataFrame(st.session_state.datos_completos)
        _enrich_key = (
            st.session_state.get("scan_count", 0),
            st.session_state.get("last_scan_time", ""),
            st.session_state.get("precio_subyacente", 0),
        )
        if st.session_state.get("_enrich_cache_key") != _enrich_key:
            _datos_enriquecidos_cache = _enriquecer_datos_opcion(
                st.session_state.datos_completos,
                precio_subyacente=st.session_state.get("precio_subyacente"),
            )
            st.session_state["_enrich_cache"] = _datos_enriquecidos_cache
            st.session_state["_enrich_cache_key"] = _enrich_key
        else:
            _datos_enriquecidos_cache = st.session_state["_enrich_cache"]

    if _datos_df is not None:
        render_metrics_panel(_datos_df, ticker_symbol, _enrich_key)

    render_alerts_section(
        ticker_symbol=ticker_symbol,
        datos_df=_datos_df,
        datos_enriquecidos_cache=_datos_enriquecidos_cache,
        umbral_vol=umbral_vol,
        umbral_oi=umbral_oi,
        umbral_prima=umbral_prima,
        umbral_delta=umbral_delta,
        min_sm_flow_score=min_sm_flow_score,
    )

    # Auto-refresh countdown
    if auto_scan and st.session_state.scan_count > 0:
        countdown = AUTO_REFRESH_INTERVAL
        placeholder = st.empty()
        progress_bar = st.progress(1.0)
        for remaining in range(countdown, 0, -1):
            mins, secs = divmod(remaining, 60)
            pct = remaining / countdown
            placeholder.markdown(
                f'<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;'
                f'padding:10px 18px;display:flex;align-items:center;gap:12px;font-size:0.85rem;">'
                f'<span style="color:#00ff88;font-size:1.1rem;">🔄</span>'
                f'<span style="color:#94a3b8;">Próximo escaneo en</span>'
                f'<span style="color:#ffffff;font-weight:700;font-family:JetBrains Mono,monospace;">'
                f"{mins}:{secs:02d}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            progress_bar.progress(pct)
            time.sleep(1)
        placeholder.empty()
        progress_bar.empty()
        st.session_state.trigger_scan = True
        st.rerun()
