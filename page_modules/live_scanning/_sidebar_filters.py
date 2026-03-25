"""Sidebar / inline filter controls for the Live Scanning page."""
import time as _t
import streamlit as st
from ui.components import institutional_flow_legend


def render_sidebar_filters(ticker_symbol, **kwargs):
    """Render ⚙️ Umbrales and 🏦 Institutional Flow filter expanders.

    Returns:
        tuple: (umbral_vol, umbral_oi, umbral_prima, umbral_delta,
                min_sm_flow_score, min_inst_flow,
                inst_only_inst_whale, inst_only_delta_60_80, inst_only_stock_sub)
    """
    umbral_vol = kwargs.get("umbral_vol", st.session_state.umbral_vol)
    umbral_oi = kwargs.get("umbral_oi", st.session_state.umbral_oi)
    umbral_prima = kwargs.get("umbral_prima", st.session_state.umbral_prima)
    umbral_delta = kwargs.get("umbral_delta", st.session_state.umbral_delta)

    _fcol_left, _fcol_right = st.columns(2)

    with _fcol_left:
        with st.expander("⚙️ Umbrales de Filtrado", expanded=False):
            _umb_c1, _umb_c2 = st.columns(2)
            with _umb_c1:
                umbral_vol = st.number_input(
                    "Volumen mínimo", value=st.session_state.umbral_vol, step=500, format="%d",
                    help="Solo muestra opciones con Volumen ≥ este valor", key="inp_umbral_vol",
                )
                umbral_oi = st.number_input(
                    "Open Interest mínimo", value=st.session_state.umbral_oi, step=1_000, format="%d",
                    help="Solo muestra contratos con OI ≥ este valor", key="inp_umbral_oi",
                )
            with _umb_c2:
                umbral_prima = st.number_input(
                    "Prima Total mínima ($)", value=st.session_state.umbral_prima, step=500_000, format="%d",
                    help="Prima Total = Volumen × Precio × 100", key="inp_umbral_prima",
                )
                umbral_delta = st.slider(
                    "Delta mínimo (|Δ|)",
                    min_value=0.00, max_value=1.00, value=float(st.session_state.umbral_delta),
                    step=0.01, format="%.2f",
                    help=(
                        "Filtra contratos por valor absoluto de Delta.\n\n"
                        "• Delta mide la sensibilidad del precio de la opción ante movimientos del subyacente.\n"
                        "• Calls: 0 → 1 | Puts: -1 → 0\n"
                        "• 0.50 ≈ ATM (mayor probabilidad ITM ~50%)\n"
                        "• 0.16 ≈ límite 1σ (probabilidad ITM ~16%)\n"
                        "• 0.00 = sin filtro (mostrar todos)"
                    ),
                    key="inp_umbral_delta",
                )
            min_sm_flow_score = st.slider(
                "Min SM Flow Score",
                min_value=0, max_value=100,
                value=int(st.session_state.get("min_sm_flow_score", 60)),
                step=5,
                help=(
                    "Filtra el visor de datos enriquecidos por Smart Money Flow Score.\n\n"
                    "• Score 0-100: cuantifica la probabilidad de flujo institucional.\n"
                    "• ≥ 90 = Whale | ≥ 75 = Smart | ≥ 50 = Mixed | < 50 = Retail\n"
                    "• 0 = sin filtro (mostrar todos)"
                ),
                key="inp_min_sm_flow",
            )
            st.session_state.umbral_vol = umbral_vol
            st.session_state.umbral_oi = umbral_oi
            st.session_state.umbral_prima = umbral_prima
            st.session_state.umbral_delta = umbral_delta
            st.session_state.min_sm_flow_score = min_sm_flow_score

    with _fcol_right:
        with st.expander("🏦 Institutional Flow Filter", expanded=False):
            min_inst_flow = st.slider(
                "Min Inst Flow Score",
                min_value=0, max_value=100,
                value=int(st.session_state.get("min_inst_flow_score", 65)),
                step=5,
                help=(
                    "Filtra por Institutional Flow Score (0-100).\n\n"
                    "• ≥ 88 = Whale | ≥ 75 = Institutional | ≥ 55 = Mixed | < 55 = Retail\n"
                    "• 0 = sin filtro"
                ),
                key="inp_min_inst_flow",
            )
            st.session_state.min_inst_flow_score = min_inst_flow
            inst_only_inst_whale = st.checkbox("Solo Institutional & Whale", key="ck_inst_whale")
            inst_only_delta_60_80 = st.checkbox("Solo Delta 0.60-0.80 (agresivo)", key="ck_delta_60_80")
            inst_only_stock_sub = st.checkbox("Solo Stock Substitute (≥0.80)", key="ck_stock_sub")
            institutional_flow_legend()

    return (
        umbral_vol, umbral_oi, umbral_prima, umbral_delta,
        min_sm_flow_score, min_inst_flow,
        inst_only_inst_whale, inst_only_delta_60_80, inst_only_stock_sub,
    )


def render_scan_controls(ticker_symbol):
    """Render scan button, auto-scan checkbox, and background data indicator.

    Returns:
        tuple: (scan_btn, auto_scan)
    """
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        scan_btn = st.button("🚀 Escanear Ahora", type="primary", use_container_width=True)
    with col_btn2:
        auto_scan = st.checkbox("🔄 Auto-escaneo (5 min)")

    from utils.background_updater import read_fast_data
    _fast = read_fast_data(ticker_symbol)
    if _fast:
        _age = (_t.time() - _fast.get("updated_at", 0)) / 60
        st.caption(
            f"📡 Datos background: spot **${_fast['spot']}** · "
            f"IV Rank **{_fast.get('iv_rank', 0):.0f}%** · "
            f"hace {_age:.0f} min"
        )

    return scan_btn, auto_scan


def render_status_bar():
    """Render last-scan status bar."""
    if st.session_state.last_scan_time:
        from datetime import datetime
        scan_date = st.session_state.last_scan_time.split()[0] if " " in st.session_state.last_scan_time else ""
        hoy = datetime.now().strftime("%Y-%m-%d")
        es_hoy = scan_date == hoy
        st.markdown(
            f"""
            <div class="status-bar">
                <div class="status-dot"></div>
                <span>Último escaneo: <b>{st.session_state.last_scan_time}</b> {'<span style="color: #00ff88;">✓ HOY</span>' if es_hoy else '<span style="color: #fbbf24;">⚠️ Histórico</span>'}</span>
                <span>Perfil TLS: <b>{st.session_state.last_perfil}</b></span>
                <span>Ciclos: <b>{st.session_state.scan_count}</b></span>
                <span>Fechas: <b>{len(st.session_state.fechas_escaneadas)}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
