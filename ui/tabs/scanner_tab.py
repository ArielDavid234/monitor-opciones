"""Tab de Escáner en Vivo"""
import streamlit as st
from datetime import datetime
from core.scanner import obtener_datos_opciones, procesar_alertas
from ui.components import mostrar_alerta

def render_scanner_tab():
    """Renderiza el tab del escáner en vivo"""
    st.markdown("### 🔍 Escáner en Vivo")
    # TODO: Mover aquí la lógica del tab scanner
    pass
