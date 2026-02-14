"""
Utilidades para el calendario financiero
"""
from datetime import datetime
from typing import Dict, List, Any
from config.app_settings import CALENDAR_CONFIG, EVENT_TYPES, IMPORTANCE_LEVELS


def _get_fallback_events() -> List[Dict[str, Any]]:
    """Eventos de ejemplo en caso de fallo de datos reales"""
    return [
        {
            "fecha": "2026-02-25",
            "titulo": "Jerome Powell - Testimonio ante el Congreso", 
            "descripcion": "Comunicado del Presidente de la Reserva Federal",
            "hora": "10:00 EST",
            "tipo": "Fed",
            "importancia": "Alta"
        }
    ]


def prepare_events_for_calendar(eventos_economicos: List[Dict]) -> Dict[str, List[Dict]]:
    """Convierte eventos a formato del calendario"""
    eventos_financieros = {}
    for evento in eventos_economicos:
        fecha = evento.get("fecha")
        if fecha:
            if fecha not in eventos_financieros:
                eventos_financieros[fecha] = []
            eventos_financieros[fecha].append(evento)
    return eventos_financieros


def get_events_for_month(eventos_financieros: Dict[str, List], year: int, month: int) -> Dict[int, List]:
    """Obtiene eventos para un mes específico"""
    eventos_del_mes = {}
    for fecha_str, eventos in eventos_financieros.items():
        try:
            fecha_evento = datetime.strptime(fecha_str, "%Y-%m-%d")
            if fecha_evento.month == month and fecha_evento.year == year:
                eventos_del_mes[fecha_evento.day] = eventos
        except ValueError:
            continue
    return eventos_del_mes


def sort_events_by_priority(eventos: List[Dict]) -> List[Dict]:
    """Ordena eventos por prioridad (importancia + tipo)"""
    def _prioridad_evento(ev):
        imp_priority = IMPORTANCE_LEVELS.get(ev.get("importancia", "Media"), {}).get("priority", 1)
        tipo_priority = {"Fed": 0, "CEO": 1, "Inversor": 2, "Earnings": 3}.get(ev.get("tipo", ""), 3)
        return (imp_priority, tipo_priority)
    
    return sorted(eventos, key=_prioridad_evento)


def generate_calendar_header_html(dias_semana: List[str]) -> str:
    """Genera el HTML del encabezado del calendario"""
    header_html = '<div class="calendar-header">'
    for dia in dias_semana:
        header_html += f'<div class="calendar-day-header">{dia}</div>'
    header_html += '</div>'
    return header_html


def generate_calendar_cell_content(dia: int, eventos_dia: List[Dict], today: datetime, 
                                 mes_actual: int, anio_actual: int) -> tuple:
    """Genera el contenido HTML de una celda del calendario"""
    # Determinar si es hoy
    es_hoy = (dia == today.day and mes_actual == today.month and anio_actual == today.year)
    day_style = 'color: #ef4444; font-weight: 800;' if es_hoy else ''
    hoy_border = 'border: 2px solid #ef4444;' if es_hoy else ''
    
    cell_content = f'<div class="calendar-day-number" style="{day_style}">{dia}</div>'
    
    # Agregar eventos (máximo 3 por celda)
    max_events_per_cell = CALENDAR_CONFIG["max_events_per_cell"]
    for evento in eventos_dia[:max_events_per_cell]:
        tipo_class = f"event-{evento['tipo'].lower()}"
        importancia_emoji = IMPORTANCE_LEVELS.get(evento.get("importancia", "Media"), {}).get("emoji", "🟡")
        
        titulo_corto = evento["titulo"][:20]
        if len(evento["titulo"]) > 20:
            titulo_corto += "..."
            
        cell_content += f'<div class="calendar-event {tipo_class}" title="{evento["titulo"]} - {evento["descripcion"]}">{importancia_emoji} {titulo_corto}</div>'
    
    # Si hay más eventos, mostrar "+X más"
    if len(eventos_dia) > max_events_per_cell:
        extras = len(eventos_dia) - max_events_per_cell
        cell_content += f'<div class="calendar-event" style="background: #374151; color: #9ca3af;">+{extras} más</div>'
    
    return cell_content, hoy_border


def generate_day_detail_html(dia: int, eventos_dia: List[Dict], fecha_obj: datetime, 
                           today: datetime, nombre_dia_semana: str) -> str:
    """Genera el HTML de detalles para un día específico"""
    dias_desde_hoy = (fecha_obj - today).days
    
    if dias_desde_hoy < 0:
        tiempo_rel = f"Hace {abs(dias_desde_hoy)} días"
    elif dias_desde_hoy == 0:
        tiempo_rel = "🔴 HOY"
    else:
        tiempo_rel = f"En {dias_desde_hoy} días"
    
    fecha_formateada = f"{nombre_dia_semana} {dia}"
    
    # Ordenar eventos por prioridad
    eventos_ordenados = sort_events_by_priority(eventos_dia)
    max_eventos_detalle = CALENDAR_CONFIG["max_events_per_day"]
    eventos_mostrar = eventos_ordenados[:max_eventos_detalle]
    eventos_ocultos = len(eventos_dia) - len(eventos_mostrar)
    
    # Crear HTML
    dia_html = f'<div class="day-detail-section" style="border: 2px solid #3b82f6;">'
    dia_html += f'<div style="font-size: 1.1rem; font-weight: 700; color: #e2e8f0; padding: 16px; background: rgba(59, 130, 246, 0.1);">📅 {fecha_formateada} — {tiempo_rel} — {len(eventos_dia)} evento(s)</div>'
    dia_html += '<div class="day-detail-content">'
    
    for evento in eventos_mostrar:
        tipo_emoji = EVENT_TYPES.get(evento["tipo"], {}).get("emoji", "📅")
        importancia_emoji = IMPORTANCE_LEVELS.get(evento.get("importancia", "Media"), {}).get("emoji", "🟡")
        
        dia_html += f'''<div class="day-detail-event">
            <div class="day-detail-event-title">{tipo_emoji} {evento["titulo"]} {importancia_emoji}</div>
            <div class="day-detail-event-desc">{evento["descripcion"]}</div>
            <div class="day-detail-event-meta">🕰️ {evento["hora"]} | Tipo: {evento["tipo"]} | Importancia: {evento.get("importancia", "Media")}</div>
        </div>'''
    
    if eventos_ocultos > 0:
        dia_html += f'<div style="text-align:center; color:#64748b; padding:8px; font-size:0.85rem;">... y {eventos_ocultos} evento(s) más</div>'
    
    dia_html += '</div></div>'
    return dia_html


def count_events_in_month(eventos_financieros: Dict[str, List], year: int, month: int) -> int:
    """Cuenta eventos en un mes específico"""
    return sum(1 for fecha_evento in eventos_financieros.keys() 
              if fecha_evento.startswith(f"{year:04d}-{month:02d}"))