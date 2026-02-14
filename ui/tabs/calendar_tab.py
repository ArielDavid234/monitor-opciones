"""Tab de Calendario Financiero"""
import streamlit as st
import calendar
from datetime import datetime
import logging

from core.economic_calendar import obtener_eventos_economicos
from config.app_settings import CALENDAR_CONFIG
from ui.calendar_styles import CALENDAR_CSS
from ui.calendar_utils import (
    _get_fallback_events,
    prepare_events_for_calendar,
    get_events_for_month,
    generate_calendar_header_html,
    generate_calendar_cell_content,
    generate_day_detail_html,
    count_events_in_month
)

logger = logging.getLogger(__name__)


def render_calendar_tab():
    """Renderiza el tab del calendario financiero"""
    st.markdown("### 📅 Calendario Financiero")
    
    # Información del tab
    st.markdown(
        """
        <div class="calendar-info">
            📅 <b>Eventos Financieros en Tiempo Real</b> — Calendario económico con datos reales 
            de Investing.com, Yahoo Finance y calendarios oficiales. Incluye reuniones Fed, earnings, 
            y eventos de bancos centrales actualizados automáticamente.
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Estilos CSS
    st.markdown(CALENDAR_CSS, unsafe_allow_html=True)
    
    # Controles de carga
    _render_calendar_controls()
    
    # Convertir eventos a formato del calendario
    eventos_financieros = prepare_events_for_calendar(st.session_state.eventos_economicos)
    
    # Selector de mes/año
    mes_actual, anio_actual = _render_month_year_selector(eventos_financieros)
    
    # Calendario principal
    _render_calendar_grid(eventos_financieros, mes_actual, anio_actual)
    
    # Selector de días y detalles
    _render_day_selector_and_details(eventos_financieros, mes_actual, anio_actual)
    
    # Nota sobre fuentes
    _render_data_sources_note()


def _render_calendar_controls():
    """Renderiza los controles de carga de datos"""
    col_load_cal, col_refresh_cal, col_status_cal = st.columns([1.5, 1.5, 2])
    
    with col_load_cal:
        cargar_eventos_btn = st.button(
            "📡 Cargar Eventos" if not st.session_state.eventos_economicos else "📡 Recargar",
            type="primary",
            use_container_width=True,
            key="btn_cargar_eventos"
        )
    
    with col_refresh_cal:
        force_refresh_btn = st.button(
            "🔄 Forzar Actualización",
            use_container_width=True,
            key="btn_force_refresh_eventos",
            help="Ignora cache y obtiene datos frescos (puede tardar más)"
        )
    
    with col_status_cal:
        if st.session_state.eventos_last_refresh:
            ultima_act = st.session_state.eventos_last_refresh.strftime("%H:%M:%S")
            st.caption(f"Última actualización: {ultima_act}")
        else:
            st.caption("Sin datos cargados")

    # Procesar eventos si se presionó algún botón
    if cargar_eventos_btn or force_refresh_btn:
        _load_calendar_events(force_refresh_btn)


def _load_calendar_events(force_refresh: bool = False):
    """Carga los eventos del calendario"""
    with st.spinner("Obteniendo eventos económicos en tiempo real..."):
        try:
            eventos_raw = obtener_eventos_economicos(force_refresh=force_refresh)
            if eventos_raw:
                st.session_state.eventos_economicos = eventos_raw
                st.session_state.eventos_last_refresh = datetime.now()
                st.success(f"✅ {len(eventos_raw)} eventos cargados exitosamente")
            else:
                st.warning("⚠️ No se pudieron obtener eventos. Usando datos de ejemplo.")
                st.session_state.eventos_economicos = _get_fallback_events()
                st.session_state.eventos_last_refresh = datetime.now()
        except Exception as e:
            logger.error("Error cargando eventos económicos: %s", e)
            st.error("❌ Error obteniendo datos. Usando eventos de ejemplo.")
            st.session_state.eventos_economicos = _get_fallback_events()
            st.session_state.eventos_last_refresh = datetime.now()


def _render_month_year_selector(eventos_financieros):
    """Renderiza el selector de mes y año"""
    col_nav1, col_nav2, col_nav3 = st.columns([2, 2, 1])
    
    today = datetime.now()
    meses_nombres = CALENDAR_CONFIG["months_es"]
    
    with col_nav1:
        mes_actual = st.selectbox(
            "📆 Mes:",
            options=list(range(1, 13)),
            format_func=lambda x: meses_nombres[x - 1],
            index=today.month - 1,
            key="calendario_mes_sel"
        )
    
    with col_nav2:
        anio_actual = st.selectbox(
            "📅 Año:",
            options=list(range(today.year - 1, today.year + 3)),
            index=1,
            key="calendario_anio_sel"
        )
    
    with col_nav3:
        eventos_mes = count_events_in_month(eventos_financieros, anio_actual, mes_actual)
        st.metric("📅 Eventos", eventos_mes)
    
    return mes_actual, anio_actual


def _render_calendar_grid(eventos_financieros, mes_actual, anio_actual):
    """Renderiza la grilla del calendario"""
    meses_nombres = CALENDAR_CONFIG["months_es"]
    st.markdown(f"#### Calendario de {meses_nombres[mes_actual-1]} {anio_actual}")
    
    # Obtener información del calendario
    cal = calendar.monthcalendar(anio_actual, mes_actual)
    dias_semana = CALENDAR_CONFIG["days_es"]
    today = datetime.now()
    
    # Preparar eventos del mes
    eventos_del_mes = get_events_for_month(eventos_financieros, anio_actual, mes_actual)
    
    # Encabezado de días
    header_html = generate_calendar_header_html(dias_semana)
    st.markdown(header_html, unsafe_allow_html=True)
    
    # Grid del calendario
    calendar_html = '<div class="calendar-grid">'
    
    for semana in cal:
        for dia in semana:
            if dia == 0:
                # Día vacío
                calendar_html += '<div class="calendar-cell calendar-cell-empty"></div>'
            else:
                # Día del mes actual
                eventos_dia = eventos_del_mes.get(dia, [])
                cell_content, hoy_border = generate_calendar_cell_content(
                    dia, eventos_dia, today, mes_actual, anio_actual
                )
                
                # Agregar celda
                if eventos_dia:
                    calendar_html += f'<div class="calendar-cell" style="{hoy_border}; cursor:pointer;">{cell_content}</div>'
                else:
                    calendar_html += f'<div class="calendar-cell" style="{hoy_border}">{cell_content}</div>'
    
    calendar_html += '</div>'
    st.markdown(calendar_html, unsafe_allow_html=True)


def _render_day_selector_and_details(eventos_financieros, mes_actual, anio_actual):
    """Renderiza el selector de días y los detalles"""
    eventos_del_mes = get_events_for_month(eventos_financieros, anio_actual, mes_actual)
    
    if not eventos_del_mes:
        return
        
    st.markdown("---")
    st.markdown("#### 📋 Seleccionar Día para Ver Detalles")
    
    # Botones para días con eventos
    dias_con_eventos = sorted(eventos_del_mes.keys())
    cols_dias = st.columns(min(len(dias_con_eventos), 7))
    
    for i, dia in enumerate(dias_con_eventos):
        col_idx = i % len(cols_dias)
        with cols_dias[col_idx]:
            fecha_obj = datetime(anio_actual, mes_actual, dia)
            nombre_dia_corto = CALENDAR_CONFIG["days_short_es"][fecha_obj.weekday()]
            
            if st.button(f"{nombre_dia_corto} {dia}", key=f"dia_btn_{dia}", use_container_width=True):
                st.session_state.dia_seleccionado = dia
                st.session_state.mes_seleccionado = mes_actual
                st.session_state.anio_seleccionado = anio_actual
    
    # Mostrar detalles del día seleccionado
    _render_selected_day_details(eventos_del_mes, mes_actual, anio_actual)


def _render_selected_day_details(eventos_del_mes, mes_actual, anio_actual):
    """Renderiza los detalles del día seleccionado"""
    # Verificar si hay día seleccionado válido
    if (hasattr(st.session_state, 'dia_seleccionado') and 
        getattr(st.session_state, 'mes_seleccionado', None) == mes_actual and 
        getattr(st.session_state, 'anio_seleccionado', None) == anio_actual):
        
        dia_sel = st.session_state.dia_seleccionado
        if dia_sel in eventos_del_mes:
            st.markdown("---")
            st.markdown("#### 📅 Detalles del Día Seleccionado")
            
            eventos_dia = eventos_del_mes[dia_sel]
            fecha_obj = datetime(anio_actual, mes_actual, dia_sel)
            today = datetime.now()
            
            dias_semana = CALENDAR_CONFIG["days_es"]
            nombre_dia_semana = dias_semana[fecha_obj.weekday()]
            
            # Generar y mostrar HTML de detalles
            dia_html = generate_day_detail_html(
                dia_sel, eventos_dia, fecha_obj, today, nombre_dia_semana
            )
            st.markdown(dia_html, unsafe_allow_html=True)
    else:
        st.info("💡 Selecciona un día con eventos arriba para ver los detalles")


def _render_data_sources_note():
    """Renderiza la nota sobre fuentes de datos"""
    st.markdown(
        """
        <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.2); 
             padding: 10px; border-radius: 8px; margin-top: 16px;">
            <small>📡 <b>Datos en Tiempo Real:</b> Los eventos se obtienen automáticamente de 
            Investing.com (calendario económico), Yahoo Finance (earnings), y calendarios oficiales 
            de bancos centrales. Los datos se actualizan cada 6 horas y se almacenan en cache local 
            para mejorar el rendimiento.</small>
        </div>
        """,
        unsafe_allow_html=True
    )
