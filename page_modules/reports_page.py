# -*- coding: utf-8 -*-
"""Página: 📋 Reports — Centro de descargas de reportes DOCX."""
import streamlit as st
from datetime import datetime

from reports.generators import (
    _generar_reporte_live_scanning,
    _generar_reporte_open_interest,
    _generar_reporte_important_companies,
    _generar_reporte_data_analysis,
    _generar_reporte_range,
)


def _track_report_download() -> None:
    """Callback: registra un reporte generado en las estadísticas del usuario."""
    try:
        from core.container import get_container
        _c = get_container()
        _u = _c.auth.get_current_user()
        if _u:
            _c.user_service.increment_report_count(_u["id"])
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Error tracking report: %s", _e)


def render(ticker_symbol, **kwargs):
    st.markdown("### 📋 Reports")
    st.markdown(
        """
        <div class="watchlist-info">
            💾 <b>Centro de Reportes</b> — Descarga reportes detallados en formato DOCX.
            Los reportes se generan con los datos cargados en cada sección.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =============================================
    # BOTONES DE DESCARGA
    # =============================================
    st.markdown("---")
    st.markdown("#### 📥 Descargar Reportes")
    st.caption("Genera reportes detallados en formato DOCX con los datos cargados en cada sección.")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Verificar disponibilidad de datos
    tiene_scanning = st.session_state.scan_count > 0 and st.session_state.datos_completos
    tiene_oi = tiene_scanning and st.session_state.barchart_data is not None and not st.session_state.barchart_data.empty
    tiene_analysis = ("proyecciones_resultados" in st.session_state and st.session_state.proyecciones_resultados) or \
                     ("emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados)
    tiene_range = st.session_state.rango_resultado is not None

    # Botón 1: Live Scanning
    if tiene_scanning:
        ticker_name = st.session_state.get("ticker_anterior", "SCAN")
        with st.spinner("📊 Generando reporte de Live Scanning..."):
            try:
                docx_scanning = _generar_reporte_live_scanning()
                st.download_button(
                    "📊 Descargar Reporte Live Scanning (DOCX)",
                    docx_scanning,
                    f"reporte_live_scanning_{ticker_name}_{timestamp}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_scanning",
                    on_click=_track_report_download,
                    help="Descarga todos los datos escaneados: alertas, clusters, y todas las opciones analizadas.",
                )
            except Exception as e:
                st.error(f"⚠️ Error al generar reporte de Live Scanning: {e}")
    else:
        st.info("📊 **Reporte Live Scanning** — Ejecuta un escaneo primero en 🔍 Live Scanning")

    # Botón 2: Open Interest
    if tiene_oi:
        ticker_name = st.session_state.get("ticker_anterior", "SCAN")
        with st.spinner("📊 Generando reporte de Open Interest..."):
            try:
                docx_oi = _generar_reporte_open_interest()
                st.download_button(
                    "📊 Descargar Reporte Open Interest (DOCX)",
                    docx_oi,
                    f"reporte_open_interest_{ticker_name}_{timestamp}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_oi",
                    on_click=_track_report_download,
                    help="Descarga el análisis completo de cambios en Open Interest (OI positivo y negativo).",
                )
            except Exception as e:
                st.error(f"⚠️ Error al generar reporte de Open Interest: {e}")
    else:
        st.info("📊 **Reporte Open Interest** — Ejecuta un escaneo primero en 🔍 Live Scanning")

    # Botón 3: Important Companies
    if tiene_analysis:
        with st.spinner("📊 Generando reporte de Important Companies..."):
            try:
                docx_important = _generar_reporte_important_companies()
                st.download_button(
                    "🏢 Descargar Reporte Important Companies (DOCX)",
                    docx_important,
                    f"reporte_important_companies_{timestamp}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_important",
                    on_click=_track_report_download,
                    help="Descarga el análisis completo de Important Companies: fundamental, técnico, sentimiento y veredicto.",
                )
            except Exception as e:
                st.error(f"⚠️ Error al generar reporte de Important Companies: {e}")
    else:
        st.info("🏢 **Reporte Important Companies** — Ejecuta el análisis en 🏢 Important Companies primero")

    # Botón 4: Data Analysis
    if tiene_scanning:
        ticker_name = st.session_state.get("ticker_anterior", "ANALYSIS")
        with st.spinner("📊 Generando reporte de Data Analysis..."):
            try:
                docx_analysis = _generar_reporte_data_analysis()
                st.download_button(
                    "📈 Descargar Reporte Data Analysis (DOCX)",
                    docx_analysis,
                    f"reporte_data_analysis_{ticker_name}_{timestamp}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_analysis",
                    on_click=_track_report_download,
                    help="Descarga el análisis de sentimiento, soportes y resistencias basado en el Live Scanning.",
                )
            except Exception as e:
                st.error(f"⚠️ Error al generar reporte de Data Analysis: {e}")
    else:
        st.info("📈 **Reporte Data Analysis** — Ejecuta un escaneo primero en 🔍 Live Scanning")

    # Botón 5: Range
    if tiene_range:
        ticker_name = st.session_state.rango_resultado.get("symbol", "RANGE")
        with st.spinner("📊 Generando reporte de Rango Esperado..."):
            try:
                docx_range = _generar_reporte_range()
                st.download_button(
                    "📐 Descargar Reporte Rango Esperado (DOCX)",
                    docx_range,
                    f"reporte_rango_{ticker_name}_{timestamp}.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_range",
                    on_click=_track_report_download,
                    help="Descarga el cálculo detallado del rango esperado con explicación e interpretación.",
                )
            except Exception as e:
                st.error(f"⚠️ Error al generar reporte de Rango: {e}")
    else:
        st.info("📐 **Reporte Rango Esperado** — Calcula el rango en 📐 Range primero")

    st.markdown("---")
    st.success("✅ Selecciona los reportes que deseas descargar. Los archivos .docx son editables y tienen estructura profesional.")
