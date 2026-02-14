"""
Configuración de la aplicación principal
"""

# Configuración de tabs
TAB_CONFIG = {
    "scanner": {
        "icon": "🔍",
        "name": "Escáner en Vivo",
        "enabled": True
    },
    "oi": {
        "icon": "📊", 
        "name": "Open Interest",
        "enabled": True
    },
    "analysis": {
        "icon": "📈",
        "name": "Análisis", 
        "enabled": True
    },
    "favorites": {
        "icon": "⭐",
        "name": "Favoritos",
        "enabled": True
    },
    "range": {
        "icon": "📐",
        "name": "Rango Esperado",
        "enabled": True
    },
    "projections": {
        "icon": "🏢", 
        "name": "Proyecciones",
        "enabled": True
    },
    "news": {
        "icon": "📰",
        "name": "Noticias",
        "enabled": True
    },
    "calendar": {
        "icon": "📅",
        "name": "Calendario",
        "enabled": True
    },
    "history": {
        "icon": "📜",
        "name": "Historial", 
        "enabled": True
    }
}

# Configuración del calendario
CALENDAR_CONFIG = {
    "max_events_per_day": 50,
    "max_events_per_cell": 5,
    "months_es": [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ],
    "days_es": ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
    "days_short_es": ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
}

# Configuración de eventos
EVENT_TYPES = {
    "Fed": {"emoji": "🏦", "color": "#b91c1c"},
    "Earnings": {"emoji": "📊", "color": "#047857"},
    "CEO": {"emoji": "👤", "color": "#b45309"},
    "Inversor": {"emoji": "💰", "color": "#4338ca"}
}

IMPORTANCE_LEVELS = {
    "Alta": {"emoji": "🔴", "priority": 0},
    "Media": {"emoji": "🟡", "priority": 1}, 
    "Baja": {"emoji": "🟢", "priority": 2}
}