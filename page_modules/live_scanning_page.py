import logging
import time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from ui.plotly_professional_theme import apply_theme, COLORS

from config.constants import AUTO_REFRESH_INTERVAL
from core.scanner import ejecutar_escaneo, obtener_historial_contrato, obtener_precio_actual
from core.clusters import detectar_compras_continuas
from core.gamma_exposure import calcular_gex_desde_scanner
from core.oi_tracker import calcular_cambios_oi
from utils.formatters import (
    _fmt_dolar, _fmt_monto, _fmt_entero, _fmt_iv,
    _fmt_oi, _fmt_oi_chg, _fmt_delta, _fmt_gamma, _fmt_theta, _fmt_rho,
    _fmt_lado, determinar_sentimiento,
)
from utils.favorites import _es_favorito, _agregar_favorito
from utils.helpers import _fetch_barchart_oi, _inyectar_oi_chg_barchart, _enriquecer_datos_opcion
from core.flow_classifier import classify_flow_type, flow_badge, detect_institutional_hedge, hedge_alert_badge, detect_hedge_bulk
from ui.components import (
    render_metric_card, render_metric_row,
    render_pro_table, _sentiment_badge, _type_badge, _priority_badge,
    institutional_flow_legend,
)

logger = logging.getLogger(__name__)


def render(ticker_symbol, **kwargs):
    csv_carpeta = "alertas"
    guardar_csv = True

    # ── Thresholds expander ──────────────────────────────────────────────
    umbral_vol = kwargs.get("umbral_vol", st.session_state.umbral_vol)
    umbral_oi = kwargs.get("umbral_oi", st.session_state.umbral_oi)
    umbral_prima = kwargs.get("umbral_prima", st.session_state.umbral_prima)
    umbral_delta = kwargs.get("umbral_delta", st.session_state.umbral_delta)

    # ── Side-by-side filter expanders ────────────────────────────────────
    _fcol_left, _fcol_right = st.columns(2)

    with _fcol_left:
        with st.expander("⚙️ Umbrales de Filtrado", expanded=False):
            _umb_c1, _umb_c2 = st.columns(2)
            with _umb_c1:
                umbral_vol = st.number_input("Volumen mínimo", value=st.session_state.umbral_vol, step=500, format="%d",
                                              help="Solo muestra opciones con Volumen ≥ este valor", key="inp_umbral_vol")
                umbral_oi = st.number_input("Open Interest mínimo", value=st.session_state.umbral_oi, step=1_000, format="%d",
                                             help="Solo muestra contratos con OI ≥ este valor", key="inp_umbral_oi")
            with _umb_c2:
                umbral_prima = st.number_input("Prima Total mínima ($)", value=st.session_state.umbral_prima, step=500_000, format="%d",
                                                help="Prima Total = Volumen × Precio × 100", key="inp_umbral_prima")
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

    # ── Scan button + auto-scan checkbox ─────────────────────────────────
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        scan_btn = st.button("🚀 Escanear Ahora", type="primary", use_container_width=True)
    with col_btn2:
        auto_scan = st.checkbox("🔄 Auto-escaneo (5 min)")

    # ── Status bar ───────────────────────────────────────────────────────
    if st.session_state.last_scan_time:
        scan_date = st.session_state.last_scan_time.split()[0] if ' ' in st.session_state.last_scan_time else ''
        hoy = datetime.now().strftime("%Y-%m-%d")
        es_hoy = (scan_date == hoy)

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

    # ── Scan execution (synchronous) ─────────────────────────────────────
    auto_trigger = st.session_state.trigger_scan
    if auto_trigger:
        st.session_state.trigger_scan = False

    cooldown_segundos = 75

    # Solo escanear si el usuario pulsa el botón o si hay un auto-trigger
    # (del countdown timer). NO escanear por mero rerun de widgets.
    if scan_btn or auto_trigger:
        ahora = datetime.now()

        if st.session_state.get("last_full_scan") is not None:
            try:
                transcurrido = (ahora - st.session_state.last_full_scan).total_seconds()
                if transcurrido < cooldown_segundos:
                    segundos_faltan = int(cooldown_segundos - transcurrido)
                    st.warning(f"⏳ Espera {segundos_faltan} segundos entre escaneos completos para evitar el rate-limit de Yahoo.")
                    st.stop()
            except TypeError:
                # last_full_scan tiene tipo inesperado; ignorar cooldown y resetear
                st.session_state.last_full_scan = None

        st.session_state.last_full_scan = ahora
        st.session_state.scanning_active = True

        if st.session_state.datos_completos:
            st.session_state.datos_anteriores = st.session_state.datos_completos.copy()

        with st.spinner("Cargando..."):
            try:
                alertas, datos, error, perfil, fechas = ejecutar_escaneo(
                    ticker_symbol,
                    umbral_vol,
                    umbral_oi,
                    umbral_prima,
                    0,
                    csv_carpeta,
                    guardar_csv,
                    paralelo=True,
                )
            except Exception as e:
                error = str(e)
                alertas, datos, perfil, fechas = [], [], None, []
                logger.error("Error crítico en escaneo: %s", e)

            if error:
                st.session_state.scan_error = error
                st.session_state.scanning_active = False
            else:
                st.session_state.alertas_actuales = alertas
                st.session_state.datos_completos = datos
                st.session_state.scan_count += 1
                st.session_state.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # ── Registrar scan en estadísticas de usuario ──────────
                try:
                    from core.container import get_container as _gc
                    _cu = _gc().auth.get_current_user()
                    if _cu:
                        _gc().user_service.increment_scan_count(_cu["id"])
                except Exception as _track_err:
                    logger.warning("Error tracking scan: %s", _track_err)

                precio, _err_precio = obtener_precio_actual(ticker_symbol)
                if precio is not None:
                    st.session_state.precio_subyacente = precio
                st.session_state.last_perfil = perfil
                st.session_state.scan_error = None
                st.session_state.fechas_escaneadas = fechas

                if st.session_state.datos_anteriores:
                    st.session_state.oi_cambios = calcular_cambios_oi(
                        datos, st.session_state.datos_anteriores
                    )

                for d in st.session_state.datos_completos:
                    d["OI_Chg"] = 0
                for a in st.session_state.alertas_actuales:
                    a["OI_Chg"] = 0

                progress_bar = st.progress(0, text="Cargando datos...")
                _fetch_barchart_oi(ticker_symbol, progress_bar=progress_bar)
                progress_bar.empty()

                _inyectar_oi_chg_barchart()

                clusters = detectar_compras_continuas(alertas, umbral_prima)
                st.session_state.clusters_detectados = clusters
                st.session_state.scan_error = None

        if not st.session_state.scan_error:
            st.session_state.scanning_active = False
            st.rerun()

    st.session_state.auto_scan = auto_scan

    if st.session_state.get("scan_error"):
        st.error(f"❌ Error en el escaneo: {st.session_state.scan_error}")
        if st.button("✖ Descartar error", key="dismiss_scan_error"):
            st.session_state.scan_error = None
            st.rerun()

    # ── Build datos_df ONCE + cache enrichment ─────────────────────────
    # All downstream sections reuse _datos_df instead of re-creating it.
    _datos_df: pd.DataFrame | None = None
    _datos_enriquecidos_cache: list | None = None

    if st.session_state.datos_completos:
        _datos_df = pd.DataFrame(st.session_state.datos_completos)

        # Enrichment cache — only recompute when scan data changes
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

    # ── Metrics row ──────────────────────────────────────────────────────
    if _datos_df is not None:
        st.markdown("### 📊 Métricas del Escaneo")
        datos_df = _datos_df
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
            # Cache GEX — same key as enrichment (data hasn't changed)
            if st.session_state.get("_gex_cache_key") != _enrich_key:
                _gex_result = calcular_gex_desde_scanner(
                    st.session_state.datos_completos, spot_price=_precio_sub_gex, mode="standard"
                )
                st.session_state["_gex_cache"] = _gex_result
                st.session_state["_gex_cache_key"] = _enrich_key
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
            render_metric_card("Gamma Exposure", _gex_fmt, sparkline_data=_spk_oi, color_override="#00ff88" if _gex_total >= 0 else "#ef4444"),
            render_metric_card("Put/Call Ratio", f"{_pc_ratio:.2f}", delta=-(_pc_ratio - 1) * 100 if _pc_ratio != 0 else 0, color_override="#ef4444" if _pc_ratio > 1 else "#00ff88"),
            render_metric_card("Unusual Alerts", f"{_n_alertas}", delta=float(_n_clusters), delta_suffix=" clusters"),
        ]), unsafe_allow_html=True)

        if _precio_sub_gex and _gex_total != 0:
            st.markdown(render_metric_row([
                render_metric_card("Zero Gamma", f"${_gex_zero:,.2f}"),
                render_metric_card("Call Wall", f"${_gex_cw:,.2f}", color_override="#00ff88"),
                render_metric_card("Put Wall", f"${_gex_pw:,.2f}", color_override="#ef4444"),
                render_metric_card("Spot Price", f"${_precio_sub_gex:,.2f}"),
            ]), unsafe_allow_html=True)

        # ── IV Rank quick indicator (cached) ─────────────────────────
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

    # ── Alerts section ───────────────────────────────────────────────────
    if st.session_state.alertas_actuales:
        st.markdown("### 🚨 Alertas Detectadas")
        # ── Smart Money Hedge Alert Banner ───────────────────────────────
        _hedge_alerts = []
        for _a in st.session_state.alertas_actuales:
            _h = detect_institutional_hedge(_a)
            if _h:
                _h["_ticker"] = _a.get("Ticker", ticker_symbol)
                _h["_strike"] = _a.get("Strike", "")
                _h["_venc"] = _a.get("Vencimiento", "")
                _h["_prima"] = _a.get("Prima_Volumen", 0)
                _hedge_alerts.append(_h)

        if _hedge_alerts:
            _has_critical = any(h["nivel"] == "critical" for h in _hedge_alerts)
            _banner_css = "hedge-banner-critical" if _has_critical else "hedge-banner-warning"
            _banner_icon = "🚨" if _has_critical else "⚠️"
            _banner_title = (
                "ALERTA ROJA: Protección institucional pesada detectada — instituciones con miedo real al downside"
                if _has_critical else
                "Protección institucional detectada — cobertura de riesgo significativa"
            )
            _banner_details = []
            for _h in _hedge_alerts:
                _banner_details.append(
                    f"<div style='margin-top:6px;font-size:0.8rem;opacity:0.9;'>"
                    f"• <b>{_h['_ticker']}</b> PUT ${_h['_strike']} Venc {_h['_venc']} — "
                    f"Prima ${_h['_prima']:,.0f} — {_h['explicacion']}</div>"
                )
            st.markdown(
                f'<div class="hedge-banner {_banner_css}">'
                f'<div><span style="font-size:1.3rem;">{_banner_icon}</span></div>'
                f'<div><b>{_banner_title}</b>'
                f'{"" .join(_banner_details)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            """
            <div class="leyenda-colores">
                <div style="font-weight: 600; color: #f1f5f9; margin-bottom: 8px; font-size: 0.9rem;">🎨 Guía de Prioridades</div>
                <span class="leyenda-item"><span class="dot-green">●</span> <b>VERDE</b> — Mayor prima detectada. Máxima atención: contrato con más dinero en juego.</span>
                <span class="leyenda-item"><span class="dot-red">●</span> <b>ROJO</b> — Actividad institucional. Vol <u>y</u> OI superan umbrales + prima alta.</span>
                <span class="leyenda-item"><span class="dot-orange">●</span> <b>NARANJA</b> — Actividad notable. Vol y OI superan umbrales.</span>
                <span class="leyenda-item"><span class="dot-purple">●</span> <b>MORADO</b> — Compra continua. Múltiples contratos similares cerca del umbral = posible mismo comprador institucional.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        alertas_sorted = sorted(
            st.session_state.alertas_actuales,
            key=lambda a: a["Prima_Volumen"],
            reverse=True,
        )
        if umbral_delta > 0:
            alertas_sorted = [
                a for a in alertas_sorted
                if a.get("Delta") is not None and abs(a["Delta"]) >= umbral_delta
            ]
        if not alertas_sorted:
            st.info(f"⚠️ Sin alertas con |Δ| ≥ {umbral_delta:.2f}. Reduce el filtro Delta en Umbrales de Filtrado.")
        max_prima = max((a["Prima_Volumen"] for a in alertas_sorted), default=0)

        for i, alerta in enumerate(alertas_sorted):
            tipo = alerta["Tipo_Alerta"]
            prima_mayor = alerta["Prima_Volumen"]

            es_top = (prima_mayor == max_prima) and (i == 0)
            if es_top:
                css_class = "alerta-top"
                emoji = "🟢"
                etiqueta = "MAYOR PRIMA"
            elif tipo == "PRINCIPAL":
                css_class = "alerta-principal"
                emoji = "🔴"
                etiqueta = "ACTIVIDAD INSTITUCIONAL"
            else:
                css_class = "alerta-prima"
                emoji = "🟠"
                etiqueta = "PRIMA ALTA"

            sentimiento_txt, sentimiento_emoji, sentimiento_color = determinar_sentimiento(
                alerta["Tipo_Opcion"], alerta.get("Lado", "N/A")
            )

            razones = []
            if alerta["Volumen"] >= umbral_vol:
                razones.append(f"Vol {alerta['Volumen']:,} ≥ {umbral_vol:,}")
            if alerta["OI"] >= umbral_oi:
                razones.append(f"OI {alerta['OI']:,} ≥ {umbral_oi:,}")
            if alerta["Prima_Volumen"] >= umbral_prima:
                razones.append(f"Prima Total ${alerta['Prima_Volumen']:,.0f} ≥ ${umbral_prima:,.0f}")
            if es_top:
                razones.insert(0, f"💰 Mayor prima del escaneo: ${prima_mayor:,.0f}")
            razon_html = " | ".join(razones)

            prima_vol_fmt = f"${alerta['Prima_Volumen']:,.0f}"
            contract_sym_card = alerta.get("Contrato", "")

            fecha_alerta = alerta.get("Fecha_Hora", "")
            if fecha_alerta:
                fecha_alerta_solo = fecha_alerta.split()[0]
                hoy_alerta = datetime.now().strftime("%Y-%m-%d")
                if fecha_alerta_solo == hoy_alerta:
                    badge_fecha = "🟢 HOY"
                else:
                    badge_fecha = f"📅 {fecha_alerta_solo}"
            else:
                badge_fecha = ""

            expander_label = (
                f"{emoji} {etiqueta} {badge_fecha} — {alerta['Tipo_Opcion']} Strike ${alerta['Strike']} | "
                f"Venc: {alerta['Vencimiento']} | Vol: {alerta['Volumen']:,} | "
                f"Prima: ${prima_mayor:,.0f}"
            )

            with st.expander(expander_label, expanded=False):
                # Star button
                if contract_sym_card:
                    ya_fav_top = _es_favorito(contract_sym_card)
                    star_icon = "⭐" if ya_fav_top else "☆"
                    star_label = f"{star_icon} Favorito" if ya_fav_top else f"{star_icon} Marcar Favorito"
                    col_star, _ = st.columns([1, 4])
                    with col_star:
                        if st.button(star_label, key=f"star_top_{i}_{contract_sym_card}", disabled=ya_fav_top, use_container_width=True):
                            fav_data_top = {
                                "Contrato": contract_sym_card,
                                "Ticker": alerta.get("Ticker", ticker_symbol),
                                "Tipo_Opcion": alerta["Tipo_Opcion"],
                                "Strike": alerta["Strike"],
                                "Vencimiento": alerta["Vencimiento"],
                                "Volumen": alerta["Volumen"],
                                "OI": alerta["OI"],
                                "OI_Chg": alerta.get("OI_Chg", 0),
                                "Ask": alerta["Ask"],
                                "Bid": alerta["Bid"],
                                "Ultimo": alerta["Ultimo"],
                                "Lado": alerta.get("Lado", "N/A"),
                                "IV": alerta.get("IV", 0),
                                "Prima_Volumen": alerta["Prima_Volumen"],
                                "Tipo_Alerta": alerta["Tipo_Alerta"],
                            }
                            if _agregar_favorito(fav_data_top):
                                st.rerun()

                # HTML card with details
                st.markdown(
                    f"""
                    <div class="{css_class}" style="margin-bottom: 0; border-left: 5px solid {sentimiento_color} !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong>{emoji} {etiqueta}</strong> — 
                                <b>{alerta['Tipo_Opcion']}</b> | 
                                Strike: <b>${alerta['Strike']}</b> | 
                                Venc: <b>{alerta['Vencimiento']}</b>
                            </div>
                            <div style="padding: 4px 12px; border-radius: 8px; background: {sentimiento_color}20; border: 1px solid {sentimiento_color}; font-size: 0.75rem; font-weight: 700;">
                                {sentimiento_emoji} {sentimiento_txt}
                            </div>
                        </div>
                        Vol: <b>{alerta['Volumen']:,}</b> | 
                        Prima Total: <b>{prima_vol_fmt}</b> |
                        Ask: ${alerta['Ask']} | Bid: ${alerta['Bid']} | Último: ${alerta['Ultimo']} |
                        <b>Lado: {_fmt_lado(alerta.get('Lado', 'N/A'))}</b><br>
                        Δ: <b>{_fmt_delta(alerta.get('Delta'))}</b> | 
                        Γ: <b>{_fmt_gamma(alerta.get('Gamma'))}</b> | 
                        Θ: <b>{_fmt_theta(alerta.get('Theta'))}</b> | 
                        ρ: <b>{_fmt_rho(alerta.get('Rho'))}</b><br>
                        <span class="razon-alerta">📌 {razon_html}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Chart + Details columns
                if contract_sym_card:
                    col_chart, col_details = st.columns([3, 1])

                    with col_details:
                        st.markdown("**Detalles del contrato:**")
                        st.markdown(f"- **Símbolo:** `{contract_sym_card}`")
                        st.markdown(f"- **Tipo:** {alerta['Tipo_Opcion']}")
                        st.markdown(f"- **Strike:** ${alerta['Strike']}")
                        st.markdown(f"- **Vencimiento:** {alerta['Vencimiento']}")
                        st.markdown(f"- **Volumen:** {alerta['Volumen']:,}")
                        st.markdown(f"- **Ask:** ${alerta['Ask']}")
                        st.markdown(f"- **Bid:** ${alerta['Bid']}")
                        st.markdown(f"- **Último:** ${alerta['Ultimo']}")
                        st.markdown(f"- **Lado:** {_fmt_lado(alerta.get('Lado', 'N/A'))}")
                        st.markdown(f"- **Delta:** {_fmt_delta(alerta.get('Delta'))}")
                        st.markdown(f"- **Gamma:** {_fmt_gamma(alerta.get('Gamma'))}")
                        st.markdown(f"- **Theta:** {_fmt_theta(alerta.get('Theta'))}")
                        st.markdown(f"- **Rho:** {_fmt_rho(alerta.get('Rho'))}")
                        st.markdown(f"- **Prima Total:** ${prima_mayor:,.0f}")

                        ya_fav = _es_favorito(contract_sym_card)
                        btn_label = "⭐ Ya en Favoritos" if ya_fav else "☆ Guardar en Favoritos"
                        if st.button(btn_label, key=f"fav_btn_{i}_{contract_sym_card}", disabled=ya_fav, use_container_width=True):
                            fav_data = {
                                "Contrato": contract_sym_card,
                                "Ticker": alerta.get("Ticker", ticker_symbol),
                                "Tipo_Opcion": alerta["Tipo_Opcion"],
                                "Strike": alerta["Strike"],
                                "Vencimiento": alerta["Vencimiento"],
                                "Volumen": alerta["Volumen"],
                                "OI": alerta["OI"],
                                "OI_Chg": alerta.get("OI_Chg", 0),
                                "Ask": alerta["Ask"],
                                "Bid": alerta["Bid"],
                                "Ultimo": alerta["Ultimo"],
                                "Lado": alerta.get("Lado", "N/A"),
                                "IV": alerta.get("IV", 0),
                                "Prima_Volumen": alerta["Prima_Volumen"],
                                "Tipo_Alerta": alerta["Tipo_Alerta"],
                            }
                            if _agregar_favorito(fav_data):
                                st.success(f"⭐ {contract_sym_card} guardado en Favoritos")
                                st.rerun()

                    with col_chart:
                        with st.spinner("Cargando gráfica..."):
                            hist_df_card, hist_err_card = obtener_historial_contrato(contract_sym_card)

                        if hist_err_card:
                            st.warning(f"⚠️ Error al cargar historial: {hist_err_card}")
                        elif hist_df_card.empty:
                            st.info("ℹ️ No hay datos históricos disponibles para este contrato.")
                        else:
                            st.markdown(f"**Precio del contrato** — `{contract_sym_card}`")
                            chart_price = hist_df_card[["Close"]].copy()
                            chart_price.columns = ["Precio"]
                            st.line_chart(chart_price, height=300)

                            if "Volume" in hist_df_card.columns:
                                chart_vol = hist_df_card[["Volume"]].copy()
                                chart_vol.columns = ["Volumen"]
                                st.bar_chart(chart_vol, height=180)

                            with st.expander("🗓️ Datos históricos completos"):
                                display_hist = hist_df_card.copy()
                                cols_to_drop = [c for c in ["Dividends", "Stock Splits", "Capital Gains"] if c in display_hist.columns]
                                if cols_to_drop:
                                    display_hist = display_hist.drop(columns=cols_to_drop)

                                display_hist.index = display_hist.index.strftime("%Y-%m-%d %H:%M")
                                for col in ["Open", "High", "Low", "Close"]:
                                    if col in display_hist.columns:
                                        display_hist[col] = display_hist[col].apply(
                                            lambda x: f"${x:.2f}" if pd.notna(x) else "-"
                                        )
                                if "Volume" in display_hist.columns:
                                    display_hist["Volume"] = display_hist["Volume"].apply(
                                        lambda x: f"{int(x):,}" if pd.notna(x) and x > 0 else "-"
                                    )
                                st.dataframe(display_hist, width="stretch", hide_index=False)
                else:
                    st.info("ℹ️ No se encontró el símbolo del contrato.")

        # ── Two-column dashboard ─────────────────────────────────────────
        alertas_df = pd.DataFrame(alertas_sorted)

        def asignar_prioridad(row):
            prima_m = row["Prima_Volumen"]
            if prima_m == max_prima:
                return "TOP"
            elif row["Tipo_Alerta"] == "PRINCIPAL":
                return "INSTITUCIONAL"
            else:
                return "PRIMA ALTA"

        def _sent_badge_row(row):
            return _sentiment_badge(row["Tipo_Opcion"], row.get("Lado", "N/A"))

        alertas_df.insert(0, "Prioridad", alertas_df.apply(asignar_prioridad, axis=1))
        alertas_df.insert(1, "Sentimiento", alertas_df.apply(_sent_badge_row, axis=1))
        # Flow Type — clasificación institucional del flujo
        if "Flow_Type" not in alertas_df.columns:
            alertas_df["Flow_Type"] = alertas_df.apply(classify_flow_type, axis=1)
        alertas_df["Flow_Type"] = alertas_df["Flow_Type"].apply(flow_badge)
        # Hedge Alert column for alertas table
        # Raw alertas lack Moneyness, Distance_Pct and OI_Chg — compute them here
        # before running the bulk detector, which gates on those columns.
        if "Hedge_Alert" not in alertas_df.columns:
            _spot = st.session_state.get("precio_subyacente") or 0.0
            # 1. Moneyness + Distance_Pct
            if _spot > 0 and "Moneyness" not in alertas_df.columns:
                _tipo_m = alertas_df["Tipo_Opcion"].str.upper() if "Tipo_Opcion" in alertas_df.columns else pd.Series([""] * len(alertas_df))
                _strike_m = pd.to_numeric(alertas_df["Strike"], errors="coerce").fillna(0)
                _ratio_m = np.where(_tipo_m == "CALL", _strike_m / _spot, _spot / _strike_m)
                alertas_df["Moneyness"] = np.where(
                    _strike_m <= 0, "N/A",
                    np.where(_ratio_m < 0.95, "ITM", np.where(_ratio_m > 1.05, "OTM", "ATM"))
                )
                alertas_df["Distance_Pct"] = np.where(
                    _strike_m > 0, np.abs(_strike_m - _spot) / _spot * 100, 0.0
                )
            # 2. OI_Chg — try Barchart data, fall back to 0
            if "OI_Chg" not in alertas_df.columns:
                _bc = st.session_state.get("barchart_data")
                if _bc is not None and not _bc.empty and "Contrato" in _bc.columns and "OI_Chg" in _bc.columns:
                    _oi_map = _bc.set_index("Contrato")["OI_Chg"].to_dict()
                    alertas_df["OI_Chg"] = alertas_df["Contrato"].map(_oi_map).fillna(0)
                else:
                    alertas_df["OI_Chg"] = 0
            # 3. Run vectorized detector — also stores Hedge_Level for badge color
            _ha, _hl, _hd = detect_hedge_bulk(alertas_df)
            alertas_df["Hedge_Alert"] = _ha
            alertas_df["Hedge_Level"] = _hl
        if "Tipo_Opcion" in alertas_df.columns:
            alertas_df["Tipo_Opcion"] = alertas_df["Tipo_Opcion"].apply(_type_badge)
        if "Lado" in alertas_df.columns:
            alertas_df["Lado"] = alertas_df["Lado"].apply(_fmt_lado)
        if "OI" in alertas_df.columns:
            alertas_df["OI"] = alertas_df["OI"].apply(_fmt_oi)
        if "OI_Chg" in alertas_df.columns:
            alertas_df["OI_Chg"] = alertas_df["OI_Chg"].apply(_fmt_oi_chg)
        if "Delta" in alertas_df.columns:
            alertas_df["Delta"] = alertas_df["Delta"].apply(_fmt_delta)
        alertas_df = alertas_df.rename(columns={"Prima_Volumen": "Prima Total"})
        alertas_df["Prima Total"] = alertas_df["Prima Total"].apply(_fmt_dolar)

        _col_left, _col_right = st.columns([1, 1], gap="medium")

        # Column order for the alertas table — excludes internal helper columns
        # Hedge_Level is included (hidden column) so the badge can use the correct color
        _ALERTAS_COLS = [
            "Prioridad", "Sentimiento", "Flow_Type", "Hedge_Alert", "Hedge_Level",
            "Tipo_Opcion", "Vencimiento", "Strike",
            "Volumen", "OI", "OI_Chg", "Delta",
            "Ask", "Bid", "Ultimo", "IV",
            "Lado", "Prima Total", "Contrato",
        ]
        _alertas_display = alertas_df[[c for c in _ALERTAS_COLS if c in alertas_df.columns]]

        with _col_left:
            st.markdown(
                render_pro_table(
                    _alertas_display,
                    title="📋 Unusual Activity — Alertas",
                    badge_count=f"{len(_alertas_display)} alertas",
                    footer_text=f"Ordenadas por prima · {len(_alertas_display)} resultados",
                    special_format={"Prioridad": _priority_badge},
                ),
                unsafe_allow_html=True,
            )

            # Net Flow bar chart
            _calls_prima = sum(
                d.get("Prima_Volumen", 0) for d in alertas_sorted
                if d.get("Tipo_Opcion") == "CALL"
            )
            _puts_prima = sum(
                d.get("Prima_Volumen", 0) for d in alertas_sorted
                if d.get("Tipo_Opcion") == "PUT"
            )
            if _calls_prima > 0 or _puts_prima > 0:
                _net_fig = go.Figure()
                _net_fig.add_trace(go.Bar(
                    x=["CALLS"], y=[_calls_prima],
                    marker_color=COLORS["positive"], name="Calls",
                    text=[f"${_calls_prima:,.0f}"], textposition="auto",
                    textfont=dict(color="#ffffff", size=12),
                ))
                _net_fig.add_trace(go.Bar(
                    x=["PUTS"], y=[_puts_prima],
                    marker_color=COLORS["negative"], name="Puts",
                    text=[f"${_puts_prima:,.0f}"], textposition="auto",
                    textfont=dict(color="#ffffff", size=12),
                ))
                apply_theme(
                    _net_fig,
                    title="Net Premium Flow",
                    height=260,
                    margin=dict(l=10, r=10, t=40, b=10),
                    yaxis_tickformat="$,.0f",
                    xaxis_showgrid=False,
                )
                _net_fig.update_layout(bargap=0.35)
                st.plotly_chart(_net_fig, use_container_width=True, config={"displayModeBar": False})

            # Clusters
            if st.session_state.clusters_detectados:
                st.markdown("#### 🔗 Compras Continuas")
                st.markdown(
                    '<div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.15);'
                    'border-radius:12px;padding:10px 14px;margin-bottom:12px;font-size:0.78rem;color:#c4b5fd;">'
                    '⚠️ <b>Actividad institucional fragmentada</b> — Múltiples contratos similares con strikes '
                    'cercanos y primas cerca del umbral.</div>',
                    unsafe_allow_html=True,
                )

                for idx_c, cluster in enumerate(st.session_state.clusters_detectados):
                    rango_str = (
                        f"${cluster['Strike_Min']} - ${cluster['Strike_Max']}"
                        if cluster["Strike_Min"] != cluster["Strike_Max"]
                        else f"${cluster['Strike_Min']}"
                    )
                    st.markdown(
                        f'<div class="alerta-cluster">'
                        f'<strong>🟣 COMPRA CONTINUA</strong> '
                        f'<span class="cluster-badge">{cluster["Contratos"]} contratos</span><br>'
                        f'<b>{cluster["Tipo_Opcion"]}</b> | Venc: <b>{cluster["Vencimiento"]}</b> | '
                        f'Rango: <b>{rango_str}</b><br>'
                        f'Prima: <b>${cluster["Prima_Total"]:,.0f}</b> | '
                        f'Vol: <b>{cluster["Vol_Total"]:,}</b></div>',
                        unsafe_allow_html=True,
                    )

                if len(st.session_state.clusters_detectados) > 0:
                    clusters_table = []
                    for c in st.session_state.clusters_detectados:
                        clusters_table.append({
                            "Tipo": c["Tipo_Opcion"],
                            "Vencimiento": c["Vencimiento"],
                            "Contratos": c["Contratos"],
                            "Rango Strikes": f"${c['Strike_Min']} - ${c['Strike_Max']}",
                            "Prima Total": f"${c['Prima_Total']:,.0f}",
                            "Vol Total": f"{c['Vol_Total']:,}",
                        })
                    st.markdown(
                        render_pro_table(pd.DataFrame(clusters_table),
                                         title="🔗 Clusters Detectados",
                                         badge_count=f"{len(clusters_table)}"),
                        unsafe_allow_html=True,
                    )

        # RIGHT COLUMN — Options Flow Screener
        with _col_right:
            st.markdown(
                '<div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;">'
                '🔍 Options Flow Screener</div>',
                unsafe_allow_html=True,
            )
            if _datos_df is not None:
                datos_df = _datos_df

                _rf1, _rf2 = st.columns(2)
                with _rf1:
                    filtro_tipo = st.selectbox(
                        "Tipo", ["Todos", "CALL", "PUT"], key="filtro_tipo_scanner"
                    )
                with _rf2:
                    filtro_fecha = st.selectbox(
                        "Vencimiento",
                        ["Todos"] + sorted(datos_df["Vencimiento"].unique().tolist()),
                        key="filtro_fecha_scanner",
                    )
                min_vol_filtro = st.number_input(
                    "Volumen mínimo", value=0, step=100, key="min_vol_scanner"
                )

                df_filtered = datos_df.copy()
                if filtro_tipo != "Todos":
                    df_filtered = df_filtered[df_filtered["Tipo"] == filtro_tipo]
                if filtro_fecha != "Todos":
                    df_filtered = df_filtered[df_filtered["Vencimiento"] == filtro_fecha]
                if min_vol_filtro > 0:
                    df_filtered = df_filtered[df_filtered["Volumen"] >= min_vol_filtro]

                display_df = df_filtered.copy()
                if "Prima_Vol" in display_df.columns:
                    display_df = display_df.rename(columns={"Prima_Vol": "Prima Total"})
                    display_df["Prima Total"] = display_df["Prima Total"].apply(_fmt_dolar)
                display_df["IV"] = display_df["IV"].apply(_fmt_iv)
                if "Delta" in display_df.columns:
                    if umbral_delta > 0:
                        display_df = display_df[display_df["Delta"].apply(lambda d: d is not None and abs(d) >= umbral_delta)]
                    display_df["Delta"] = display_df["Delta"].apply(_fmt_delta)
                if "Gamma" in display_df.columns:
                    display_df["Gamma"] = display_df["Gamma"].apply(_fmt_gamma)
                if "Theta" in display_df.columns:
                    display_df["Theta"] = display_df["Theta"].apply(_fmt_theta)
                if "Rho" in display_df.columns:
                    display_df["Rho"] = display_df["Rho"].apply(_fmt_rho)
                # Flow Type badge
                if "Flow_Type" not in display_df.columns:
                    display_df["Flow_Type"] = display_df.apply(classify_flow_type, axis=1)

                cols_ocultar_df = [c for c in ["OI", "OI_Chg"] if c in display_df.columns]
                cols_order = ["Flow_Type"] + [c for c in display_df.columns if c != "Flow_Type" and c not in cols_ocultar_df]
                cols_order = [c for c in cols_order if c in display_df.columns]
                st.dataframe(
                    display_df[cols_order].sort_values("Volumen", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    height=600,
                )
                st.caption(f"Mostrando {len(df_filtered):,} de {len(datos_df):,} opciones")
            else:
                st.info("Ejecuta un escaneo para ver el flujo de opciones.")

    # ── No alerts but scan completed ─────────────────────────────────────
    elif st.session_state.scan_count > 0 and not st.session_state.scan_error:
        st.success("✅ Sin alertas relevantes en este ciclo.")

    # ── Options Flow Screener (no alerts) ────────────────────────────────
    if not st.session_state.alertas_actuales and _datos_df is not None:
        st.markdown(
            '<div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;">'
            '🔍 Options Flow Screener</div>',
            unsafe_allow_html=True,
        )
        datos_df = _datos_df

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filtro_tipo = st.selectbox(
                "Tipo", ["Todos", "CALL", "PUT"], key="filtro_tipo_scanner_noalert"
            )
        with col_f2:
            filtro_fecha = st.selectbox(
                "Vencimiento",
                ["Todos"] + sorted(datos_df["Vencimiento"].unique().tolist()),
                key="filtro_fecha_scanner_noalert",
            )
        with col_f3:
            min_vol_filtro = st.number_input(
                "Volumen mínimo", value=0, step=100, key="min_vol_scanner_noalert"
            )

        df_filtered = datos_df.copy()
        if filtro_tipo != "Todos":
            df_filtered = df_filtered[df_filtered["Tipo"] == filtro_tipo]
        if filtro_fecha != "Todos":
            df_filtered = df_filtered[df_filtered["Vencimiento"] == filtro_fecha]
        if min_vol_filtro > 0:
            df_filtered = df_filtered[df_filtered["Volumen"] >= min_vol_filtro]

        display_df = df_filtered.copy()
        if "Prima_Vol" in display_df.columns:
            display_df = display_df.rename(columns={"Prima_Vol": "Prima Total"})
            display_df["Prima Total"] = display_df["Prima Total"].apply(_fmt_dolar)
        display_df["IV"] = display_df["IV"].apply(_fmt_iv)
        if "Delta" in display_df.columns:
            if umbral_delta > 0:
                display_df = display_df[display_df["Delta"].apply(lambda d: d is not None and abs(d) >= umbral_delta)]
            display_df["Delta"] = display_df["Delta"].apply(_fmt_delta)
        if "Gamma" in display_df.columns:
            display_df["Gamma"] = display_df["Gamma"].apply(_fmt_gamma)
        if "Theta" in display_df.columns:
            display_df["Theta"] = display_df["Theta"].apply(_fmt_theta)
        if "Rho" in display_df.columns:
            display_df["Rho"] = display_df["Rho"].apply(_fmt_rho)
        # Flow Type badge
        if "Flow_Type" not in display_df.columns:
            display_df["Flow_Type"] = display_df.apply(classify_flow_type, axis=1)

        cols_ocultar_df = [c for c in ["OI", "OI_Chg"] if c in display_df.columns]
        cols_order = ["Flow_Type"] + [c for c in display_df.columns if c != "Flow_Type" and c not in cols_ocultar_df]
        cols_order = [c for c in cols_order if c in display_df.columns]
        st.dataframe(
            display_df[cols_order].sort_values("Volumen", ascending=False),
            use_container_width=True,
            hide_index=True,
            height=500,
        )
        st.caption(f"Mostrando {len(df_filtered):,} de {len(datos_df):,} opciones")

    # ── Scan data viewer ─────────────────────────────────────────────────
    if _datos_df is not None:
        st.markdown("---")
        st.markdown("#### 📊 Datos del Último Escaneo")
        datos_df_esc = _datos_df
        _a_calls = len(datos_df_esc[datos_df_esc["Tipo"] == "CALL"])
        _a_puts = len(datos_df_esc[datos_df_esc["Tipo"] == "PUT"])
        _a_total = len(datos_df_esc)
        _a_alertas = len(st.session_state.alertas_actuales)
        _a_clusters = len(st.session_state.clusters_detectados)
        _a_cpct = (_a_calls / _a_total * 100) if _a_total else 0
        _a_ppct = (_a_puts / _a_total * 100) if _a_total else 0
        _a_spk = sorted(datos_df_esc["Volumen"].dropna().tail(12).tolist()) if "Volumen" in datos_df_esc.columns else None
        st.markdown(render_metric_row([
            render_metric_card("Opciones", f"{_a_total:,}", sparkline_data=_a_spk),
            render_metric_card("Calls", f"{_a_calls:,}", delta=_a_cpct),
            render_metric_card("Puts", f"{_a_puts:,}", delta=_a_ppct, color_override="#ef4444"),
            render_metric_card("Alertas", f"{_a_alertas}"),
            render_metric_card("Clusters", f"{_a_clusters}"),
        ]), unsafe_allow_html=True)

        with st.expander("🔍 Ver todas las opciones escaneadas", expanded=False):
            datos_enriquecidos = _datos_enriquecidos_cache or []
            display_scan = pd.DataFrame(datos_enriquecidos) if datos_enriquecidos else pd.DataFrame()

            if 'Prima_Vol' in display_scan.columns:
                display_scan["Prima Total"] = display_scan["Prima_Vol"].apply(_fmt_monto)
            if 'IV' in display_scan.columns:
                display_scan["IV_F"] = display_scan["IV"].apply(_fmt_iv)
            if 'Spread_Pct' in display_scan.columns:
                display_scan["Spread_%"] = display_scan["Spread_Pct"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) and x > 0 else "N/D")
            if 'Liquidity_Score' in display_scan.columns:
                display_scan["Liquidez"] = display_scan["Liquidity_Score"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "-")
            if 'Lado' in display_scan.columns:
                display_scan["Lado_F"] = display_scan["Lado"].apply(_fmt_lado)
            if 'Ask' in display_scan.columns:
                display_scan["Ask_F"] = display_scan["Ask"].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "N/D")
            if 'Bid' in display_scan.columns:
                display_scan["Bid_F"] = display_scan["Bid"].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "N/D")
            if 'OI' in display_scan.columns:
                display_scan["OI_F"] = display_scan["OI"].apply(_fmt_oi)
            if 'OI_Chg' in display_scan.columns:
                display_scan["OI_Chg_F"] = display_scan["OI_Chg"].apply(_fmt_oi_chg)
            if 'Delta' in display_scan.columns:
                display_scan["Delta"] = display_scan["Delta"].apply(_fmt_delta)
            if 'Gamma' in display_scan.columns:
                display_scan["Gamma"] = display_scan["Gamma"].apply(_fmt_gamma)
            if 'Theta' in display_scan.columns:
                display_scan["Theta"] = display_scan["Theta"].apply(_fmt_theta)
            if 'Rho' in display_scan.columns:
                display_scan["Rho"] = display_scan["Rho"].apply(_fmt_rho)

            if 'Tipo' in display_scan.columns and 'Lado' in display_scan.columns:
                display_scan["Sentimiento"] = display_scan.apply(
                    lambda row: f"{determinar_sentimiento(row['Tipo'], row.get('Lado', 'N/A'))[1]} {determinar_sentimiento(row['Tipo'], row.get('Lado', 'N/A'))[0]}",
                    axis=1
                )

            if 'sm_flow_score' in display_scan.columns:
                display_scan["SM Flow"] = display_scan["sm_flow_score"].apply(
                    lambda x: f"{float(x):.1f}" if pd.notna(x) else "-"
                )
            if 'smart_money_tier' in display_scan.columns:
                display_scan["SM Tier"] = display_scan["smart_money_tier"]
            if 'inst_flow_score' in display_scan.columns:
                display_scan["Inst Flow"] = display_scan["inst_flow_score"].apply(
                    lambda x: f"{float(x):.1f}" if pd.notna(x) else "-"
                )
            if 'inst_tier' in display_scan.columns:
                display_scan["Inst Tier"] = display_scan["inst_tier"]

            # Apply Min SM Flow Score filter (slider in ⚙️ Umbrales de Filtrado)
            _min_sm = int(st.session_state.get("min_sm_flow_score", 0))
            if _min_sm > 0 and 'sm_flow_score' in display_scan.columns:
                _scores = pd.to_numeric(display_scan['sm_flow_score'], errors='coerce').fillna(0)
                display_scan = display_scan[_scores >= _min_sm]

            # Apply Institutional Flow filters (🏦 Institutional Flow Filter)
            _min_inst = int(st.session_state.get("min_inst_flow_score", 0))
            if _min_inst > 0 and 'inst_flow_score' in display_scan.columns:
                _iscores = pd.to_numeric(display_scan['inst_flow_score'], errors='coerce').fillna(0)
                display_scan = display_scan[_iscores >= _min_inst]
            if st.session_state.get("ck_inst_whale") and 'inst_tier' in display_scan.columns:
                display_scan = display_scan[display_scan['inst_tier'].isin(['Institutional', 'Whale'])]
            if st.session_state.get("ck_delta_60_80") and 'abs_delta' in display_scan.columns:
                _ad = pd.to_numeric(display_scan['abs_delta'], errors='coerce').fillna(0)
                display_scan = display_scan[(_ad >= 0.60) & (_ad <= 0.80)]
            if st.session_state.get("ck_stock_sub") and 'abs_delta' in display_scan.columns:
                _ad2 = pd.to_numeric(display_scan['abs_delta'], errors='coerce').fillna(0)
                display_scan = display_scan[_ad2 >= 0.80]

            if display_scan.empty:
                st.info("⚠️ Sin opciones con los filtros actuales. Reduce los umbrales para ver resultados.")

            cols_mostrar = ['Sentimiento', 'Inst Flow', 'Inst Tier', 'SM Flow', 'SM Tier', 'Flow_Type', 'Hedge_Alert', 'Tipo', 'Strike', 'Vencimiento', 'Volumen', 'OI_F', 'OI_Chg_F', 'Delta', 'Gamma', 'Theta', 'Rho', 'Ask_F', 'Bid_F', 'Spread_%',
                           'Ultimo', 'Lado_F', 'IV_F', 'Moneyness', 'Prima Total', 'Liquidez']
            cols_disponibles = [c for c in cols_mostrar if c in display_scan.columns]

            st.dataframe(
                display_scan[cols_disponibles] if cols_disponibles else display_scan,
                use_container_width=True, hide_index=True, height=400,
            )

            csv_enriquecido = pd.DataFrame(datos_enriquecidos).to_csv(index=False).encode("utf-8")
            st.download_button(
                "📈 Descargar Datos Enriquecidos (CSV)",
                csv_enriquecido,
                f"opciones_enriquecidas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                key="dl_datos_enriquecidos_escaneo",
                help="Incluye métricas adicionales: spread, moneyness, liquidez, ratios, etc."
            )

        # ── Clusters table ───────────────────────────────────────────────
        if st.session_state.clusters_detectados:
            st.markdown("##### 🔗 Clusters de Compra Continua")
            clusters_table_esc = []
            for c in st.session_state.clusters_detectados:
                clusters_table_esc.append({
                    "Tipo": c["Tipo_Opcion"],
                    "Vencimiento": c["Vencimiento"],
                    "Contratos": c["Contratos"],
                    "Rango Strikes": f"${c['Strike_Min']} - ${c['Strike_Max']}",
                    "Prima Total": _fmt_monto(c['Prima_Total']),
                    "Prima Prom.": _fmt_monto(c['Prima_Promedio']),
                    "Vol Total": _fmt_entero(c['Vol_Total']),
                    "OI Total": _fmt_entero(c['OI_Total']),
                    "OI Chg": _fmt_oi_chg(c.get('OI_Chg_Total', 0)),
                })
            st.markdown(
                render_pro_table(pd.DataFrame(clusters_table_esc),
                                 title="🔗 Clusters de Compra Continua",
                                 badge_count=f"{len(clusters_table_esc)}"),
                unsafe_allow_html=True,
            )

    # ── Auto-refresh countdown ───────────────────────────────────────────
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
                f'{mins}:{secs:02d}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            progress_bar.progress(pct)
            time.sleep(1)
        placeholder.empty()
        progress_bar.empty()
        st.session_state.trigger_scan = True
        st.rerun()
