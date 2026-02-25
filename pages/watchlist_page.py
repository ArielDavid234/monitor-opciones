# -*- coding: utf-8 -*-
"""Página: 📌 Watchlist — Compañías guardadas para análisis rápido."""
import streamlit as st

from utils.favorites import _agregar_a_watchlist, _eliminar_de_watchlist


# ─── Estilos para las tarjetas de Watchlist ─────────────────────────────────
_WL_CARD_CSS = """
<style>
.wl-card{
    border:1px solid #2a2a3a;
    border-radius:10px;
    padding:16px 18px;
    background:#0d1117;
    margin-bottom:8px;
    transition: border-color 0.2s;
}
.wl-card:hover{ border-color:#00ff88; }
.wl-ticker{
    font-size:1.5rem;
    font-weight:800;
    color:#00ff88;
    letter-spacing:1px;
}
.wl-nombre{
    color:#ccc;
    font-size:0.9rem;
    margin-top:2px;
}
.wl-fecha{
    color:#555;
    font-size:0.72rem;
    margin-top:6px;
}
</style>
"""


def render(ticker_symbol, **kwargs):
    st.markdown(_WL_CARD_CSS, unsafe_allow_html=True)

    st.markdown("### 📌 Watchlist")
    st.caption(
        "Guarda las compañías que más te interesan. "
        "Haz clic en **🔍 Analizar** para ir directo a Live Scanning y ejecutar el escaneo automáticamente."
    )

    # ── Formulario para agregar ──────────────────────────────────────────────
    with st.form("form_add_watchlist", clear_on_submit=True):
        col_t, col_n, col_btn = st.columns([1, 2, 1])
        with col_t:
            wl_new_ticker = st.text_input(
                "Ticker", placeholder="AAPL", max_chars=10,
                label_visibility="visible",
            )
        with col_n:
            wl_new_nombre = st.text_input(
                "Nombre (opcional)", placeholder="Apple Inc.",
                label_visibility="visible",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            wl_submitted = st.form_submit_button("➕ Agregar", use_container_width=True)

        if wl_submitted:
            ok, msg = _agregar_a_watchlist(wl_new_ticker, wl_new_nombre)
            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.warning(f"⚠️ {msg}")

    # ── Grid de tarjetas ─────────────────────────────────────────────────────
    watchlist = st.session_state.get("watchlist", [])

    if not watchlist:
        st.info("Sin compañías en la Watchlist. Usa el formulario de arriba para agregar una.")
    else:
        COLS_PER_ROW = 3
        for row_start in range(0, len(watchlist), COLS_PER_ROW):
            row_items = watchlist[row_start : row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col, item in zip(cols, row_items):
                with col:
                    wl_tk = item["ticker"]
                    wl_nm = item.get("nombre", "")
                    wl_dt = item.get("agregado", "")[:10]

                    nombre_html = (
                        f'<div class="wl-nombre">{wl_nm}</div>'
                        if wl_nm else ""
                    )
                    st.markdown(
                        f'<div class="wl-card">'
                        f'<div class="wl-ticker">{wl_tk}</div>'
                        f'{nombre_html}'
                        f'<div class="wl-fecha">Agregado: {wl_dt}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    btn_a, btn_d = st.columns([3, 1])
                    with btn_a:
                        if st.button(
                            "🔍 Analizar",
                            key=f"wl_analyze_{wl_tk}",
                            use_container_width=True,
                            type="primary",
                        ):
                            # Redirigir a Live Scanning con este ticker
                            st.session_state["ticker_input"] = wl_tk
                            st.session_state["nav_radio"] = "🔍 Live Scanning"
                            st.session_state.ticker_anterior = ""
                            st.session_state.trigger_scan = True
                            st.session_state.alertas_actuales = []
                            st.session_state.datos_completos = []
                            st.session_state.clusters_detectados = []
                            st.session_state.barchart_data = None
                            st.session_state.scan_error = None
                            st.rerun()
                    with btn_d:
                        if st.button(
                            "🗑️",
                            key=f"wl_del_{wl_tk}",
                            use_container_width=True,
                            help=f"Eliminar {wl_tk} de la Watchlist",
                        ):
                            _eliminar_de_watchlist(wl_tk)
                            st.rerun()
