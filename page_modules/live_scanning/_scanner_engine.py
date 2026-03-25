"""Scan execution engine for the Live Scanning page."""
import logging
import time
from datetime import datetime

import streamlit as st

from core.scanner import (
    ejecutar_escaneo,
    get_last_scan_runtime_meta,
    obtener_precio_actual,
)
from core.clusters import detectar_compras_continuas
from core.oi_tracker import calcular_cambios_oi
from infrastructure.data.provider_runtime import get_budget_manager, get_refresh_priority_registry
from infrastructure.platform.business_value import (
    assign_ab_variant,
    check_scan_limit,
    record_ab_assignment,
    record_ab_conversion,
    record_product_event,
    record_scan_metering,
)
from utils.helpers import _fetch_barchart_oi, _inyectar_oi_chg_barchart

logger = logging.getLogger(__name__)


def render_plan_usage(auth, user_id, user_plan, plan_policy, plan_sla):
    """Render per-user plan usage caption."""
    if user_id:
        _usage_stats = auth.load_user_data(user_id, "usage_stats") or {}
        _today = datetime.utcnow().strftime("%Y-%m-%d")
        _scans_today = (
            int(_usage_stats.get("scans_today", 0))
            if _usage_stats.get("scans_today_date") == _today
            else 0
        )
        st.caption(
            f"Plan {str(plan_policy.name).title()} | uso diario: {_scans_today}/{plan_policy.scans_per_day} scans "
            f"| intervalo minimo: {plan_policy.min_seconds_between_scans}s "
            f"| cola: {plan_sla.get('queue')} | SLA latencia objetivo: {plan_sla.get('latency_target_ms')} ms"
        )
        if user_plan == "free":
            st.caption("Plan Free usa cola compartida. Alertas avanzadas disponibles en Pro/Enterprise.")


def run_scan(
    *,
    ticker_symbol,
    umbral_vol,
    umbral_oi,
    umbral_prima,
    umbral_delta,
    user_id,
    user_plan,
    plan_policy,
    auth,
    container,
    auto_trigger,
):
    """Execute a scan cycle, honouring cooldown and plan limits.

    All results are stored in st.session_state.  Returns True if a scan
    was actually executed, False if blocked (cooldown / limit).
    """
    csv_carpeta = "alertas"
    guardar_csv = True

    if user_id:
        record_product_event(
            auth,
            user_id,
            "user_scan_started",
            {
                "ticker": ticker_symbol,
                "plan": user_plan,
                "trigger": "auto" if auto_trigger else "manual",
            },
        )
        get_refresh_priority_registry().register_demand(ticker_symbol, user_plan)

    ahora = datetime.now()
    _can_scan = True

    cooldown_segundos = max(75, int(plan_policy.min_seconds_between_scans))

    if user_plan == "free":
        _budget_ratio = float(get_budget_manager().snapshot().get("usage_ratio", 0.0))
        if _budget_ratio >= 0.75:
            time.sleep(min(2.0, _budget_ratio))

    if user_id:
        _limit = check_scan_limit(auth, user_id, user_plan)
        if not _limit.get("allowed", True):
            st.session_state.scan_error = _limit.get("friendly_message")
            _can_scan = False
            record_product_event(
                auth,
                user_id,
                "user_hit_plan_limit",
                {
                    "reason": _limit.get("reason"),
                    "usage": _limit.get("usage"),
                    "limit": _limit.get("limit"),
                    "plan": user_plan,
                },
            )
            record_product_event(
                auth,
                user_id,
                "user_opened_upgrade_prompt",
                {"reason": _limit.get("reason"), "plan": user_plan},
            )
            _ab_exp = "upgrade_prompt_copy_v1"
            _variant = assign_ab_variant(user_id, _ab_exp)
            record_ab_assignment(auth, user_id, _ab_exp, _variant)
            _copy = (
                "Upgrade sugerido: Pro reduce esperas y habilita reportes extendidos."
                if _variant == "A"
                else "Escala a Pro/Enterprise para mas velocidad, stress tests y mayor capacidad diaria."
            )
            st.info(_copy)
            if st.button("Ver opciones de upgrade", key=f"upgrade_cta_{ticker_symbol}", use_container_width=False):
                record_ab_conversion(auth, user_id, _ab_exp, converted=True)
                st.session_state["_page_override"] = "📋 Reports"
                st.rerun()

    if st.session_state.get("last_full_scan") is not None:
        try:
            transcurrido = (ahora - st.session_state.last_full_scan).total_seconds()
            if transcurrido < cooldown_segundos:
                segundos_faltan = int(cooldown_segundos - transcurrido)
                st.warning(
                    f"⏳ Espera {segundos_faltan} segundos entre escaneos completos para controlar cuota de proveedor."
                )
                _can_scan = False
        except TypeError:
            st.session_state.last_full_scan = None

    if not _can_scan:
        return False

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
            _is_rl = any(
                kw in str(error).lower()
                for kw in ["429", "rate limit", "too many requests", "cuota", "quota", "límite"]
            )
            if _is_rl:
                if auto_trigger:
                    logger.info("Auto-trigger rate-limited — omitiendo sin error visible")
                elif st.session_state.get("datos_completos"):
                    st.session_state.scan_error = (
                        "⚠️ datos parciales: cuota temporal alta del proveedor. "
                        "mostrando último snapshot en cache. reintentar en 60 segundos."
                    )
                else:
                    st.session_state.scan_error = (
                        "⚠️ datos parciales: cuota temporal alta del proveedor. "
                        "reintentar en 60 segundos."
                    )
            else:
                if st.session_state.get("datos_completos"):
                    st.session_state.scan_error = (
                        "⚠️ datos parciales: mostrando último snapshot en cache. "
                        "reintentar en 30 segundos."
                    )
                else:
                    st.session_state.scan_error = (
                        "⚠️ datos parciales: servicio temporalmente no disponible. "
                        "reintentar en 30 segundos."
                    )
            st.session_state.scanning_active = False
            return False

        st.session_state.alertas_actuales = alertas
        st.session_state.datos_completos = datos
        st.session_state.scan_count += 1
        st.session_state.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            if user_id:
                container.user_service.increment_scan_count(user_id)
        except Exception as _track_err:
            logger.warning("Error tracking scan: %s", _track_err)

        try:
            if user_id:
                _runtime = get_last_scan_runtime_meta()
                _metering = record_scan_metering(auth, user_id, user_plan, _runtime)
                st.session_state["last_scan_cost_usd"] = float(_metering.get("scan_cost_usd", 0.0))
                record_product_event(
                    auth,
                    user_id,
                    "user_scan_completed",
                    {
                        "ticker": ticker_symbol,
                        "plan": user_plan,
                        "cost_usd": _metering.get("scan_cost_usd", 0.0),
                        "provider_calls": _metering.get("provider_calls", 0),
                    },
                )
        except Exception as _meter_err:
            logger.warning("Error metering scan: %s", _meter_err)

        precio, _err_precio = obtener_precio_actual(ticker_symbol)
        if precio is not None:
            st.session_state.precio_subyacente = precio
        st.session_state.last_perfil = perfil
        st.session_state.scan_error = None
        st.session_state.fechas_escaneadas = fechas
        st.session_state["live_last_ticker"] = ticker_symbol

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

    st.session_state.scanning_active = False
    st.rerun()
    return True
