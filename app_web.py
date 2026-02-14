"""
Monitor de Opciones — Punto de entrada para Streamlit Cloud.
Orquesta la UI importando lógica desde config/, core/ y ui/.
"""
import calendar
import io
import json
import os
import logging
import time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn

# --- Logging ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Importar módulos del proyecto ---
from config.constants import (
    DEFAULT_MIN_VOLUME, DEFAULT_MIN_OI, DEFAULT_MIN_PRIMA, DEFAULT_QUICK_FILTER,
    DEFAULT_TARGET_DELTA, AUTO_REFRESH_INTERVAL,
)
from config.watchlists import WATCHLIST_EMPRESAS, WATCHLIST_EMERGENTES

from core.scanner import (
    BROWSER_PROFILES, crear_sesion_nueva, obtener_historial_contrato,
    ejecutar_escaneo, cargar_historial_csv,
)
from core.projections import analizar_proyeccion_empresa
from core.range_calc import calcular_rango_esperado
from core.clusters import detectar_compras_continuas
from core.news import obtener_noticias_financieras, filtrar_noticias
from core.oi_tracker import calcular_cambios_oi, resumen_oi, filtrar_contratos_oi
from core.barchart_oi import obtener_top_oi_changes, obtener_oi_simbolo
from core.economic_calendar import obtener_eventos_economicos

from ui.styles import CSS_STYLES
from ui.components import (
    format_market_cap, render_empresa_card, render_tabla_comparativa,
    analizar_watchlist, render_watchlist_preview, render_empresa_descriptions,
    render_metric_card, render_metric_row, render_plotly_sparkline,
    render_pro_table, _sentiment_badge, _type_badge, _priority_badge, _badge_html,
)


# ============================================================================
#                    HELPERS DE FORMATEO REUTILIZABLES
# ============================================================================
def _fmt_dolar(x):
    """Formatea un valor como moneda: $1,234."""
    return f"${x:,.0f}" if x > 0 else "$0"


def _fmt_iv(x):
    """Formatea IV como porcentaje: 25.3%."""
    return f"{x:.1f}%" if x > 0 else "-"


def _fmt_precio(x):
    """Formatea un precio: $1.23."""
    return f"${x:.2f}" if x > 0 else "-"


def _fmt_entero(x):
    """Formatea un entero con separadores: 1,234."""
    return f"{int(x):,}"


def _fmt_monto(v):
    """Formatea un monto grande: $1.2M, $50K, $1,234."""
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    elif v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,.0f}"


def _fmt_oi_chg(x):
    """Formatea OI Change con signo: +1,234 o -567."""
    return f"+{int(x):,}" if x > 0 else f"{int(x):,}" if x < 0 else "0"


def _fmt_lado(lado):
    """Formatea el lado de ejecución con emoji indicador."""
    if lado == "Ask":
        return "🟢 Ask"   # Compra agresiva
    elif lado == "Bid":
        return "🔴 Bid"   # Venta agresiva
    elif lado == "Mid":
        return "⚪ Mid"
    return "➖ N/A"


def determinar_sentimiento(tipo_opcion, lado):
    """
    Determina el sentimiento de la operación según el tipo de opción y lado de ejecución.
    
    Alcista (Verde) - Apuesta a que el precio suba:
    - CALL + Ask (compra de CALL)
    - PUT + Bid (venta de PUT)
    
    Bajista (Rojo) - Apuesta a que el precio baje:
    - PUT + Ask (compra de PUT)
    - CALL + Bid (venta de CALL)
    
    Returns:
        tuple: (sentimiento_texto, emoji, color_hex)
    """
    if tipo_opcion == "CALL" and lado == "Ask":
        return "ALCISTA", "🟢", "#10b981"
    elif tipo_opcion == "PUT" and lado == "Bid":
        return "ALCISTA", "🟢", "#10b981"
    elif tipo_opcion == "PUT" and lado == "Ask":
        return "BAJISTA", "🔴", "#ef4444"
    elif tipo_opcion == "CALL" and lado == "Bid":
        return "BAJISTA", "🔴", "#ef4444"
    else:
        return "NEUTRAL", "⚪", "#94a3b8"


# ============================================================================
#                    SISTEMA DE FAVORITOS (persistencia JSON)
# ============================================================================
_FAVORITOS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "favoritos.json")


def _cargar_favoritos():
    """Carga favoritos desde archivo JSON. Purga contratos expirados."""
    try:
        if os.path.exists(_FAVORITOS_PATH):
            with open(_FAVORITOS_PATH, "r", encoding="utf-8") as f:
                favoritos = json.load(f)
            # Purgar contratos expirados
            hoy = datetime.now().strftime("%Y-%m-%d")
            favoritos = [fav for fav in favoritos if fav.get("Vencimiento", "9999-12-31") >= hoy]
            _guardar_favoritos(favoritos)  # persistir la limpieza
            return favoritos
    except Exception as e:
        logger.warning("Error cargando favoritos: %s", e)
    return []


def _guardar_favoritos(favoritos):
    """Guarda la lista de favoritos en archivo JSON."""
    try:
        os.makedirs(os.path.dirname(_FAVORITOS_PATH), exist_ok=True)
        with open(_FAVORITOS_PATH, "w", encoding="utf-8") as f:
            json.dump(favoritos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error guardando favoritos: %s", e)


def _agregar_favorito(contrato_data):
    """Agrega un contrato a favoritos si no existe ya."""
    favoritos = st.session_state.get("favoritos", [])
    contrato_id = contrato_data.get("Contrato", "")
    if not contrato_id:
        return False
    # Verificar que no exista ya
    if any(f.get("Contrato") == contrato_id for f in favoritos):
        return False
    # Agregar timestamp de cuando se marcó
    contrato_data["Guardado_En"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    favoritos.append(contrato_data)
    st.session_state.favoritos = favoritos
    _guardar_favoritos(favoritos)
    return True


def _eliminar_favorito(contrato_id):
    """Elimina un contrato de favoritos por su símbolo."""
    favoritos = st.session_state.get("favoritos", [])
    favoritos = [f for f in favoritos if f.get("Contrato") != contrato_id]
    st.session_state.favoritos = favoritos
    _guardar_favoritos(favoritos)


def _es_favorito(contrato_id):
    """Verifica si un contrato ya está en favoritos."""
    favoritos = st.session_state.get("favoritos", [])
    return any(f.get("Contrato") == contrato_id for f in favoritos)


def _fetch_barchart_oi(simbolo):
    """Obtiene datos de OI de Barchart para un símbolo y actualiza session_state."""
    try:
        df_calls, err_c = obtener_oi_simbolo(simbolo, tipo="call")
        df_puts, err_p = obtener_oi_simbolo(simbolo, tipo="put")

        frames = []
        if df_calls is not None and not df_calls.empty:
            df_calls["Tipo"] = "CALL"
            frames.append(df_calls)
        if df_puts is not None and not df_puts.empty:
            df_puts["Tipo"] = "PUT"
            frames.append(df_puts)

        if frames:
            combined = pd.concat(frames, ignore_index=True)
            combined = combined.sort_values("OI_Chg", ascending=False).reset_index(drop=True)
            st.session_state.barchart_data = combined
            st.session_state.barchart_error = None
        else:
            err_msg = err_c or err_p or "Sin datos de Barchart"
            st.session_state.barchart_data = None
            st.session_state.barchart_error = err_msg
    except Exception as e:
        st.session_state.barchart_data = None
        st.session_state.barchart_error = f"Error Barchart: {e}"


def _inyectar_oi_chg_barchart():
    """Inyecta OI_Chg real de Barchart en datos_completos, alertas_actuales y clusters."""
    bc = st.session_state.get("barchart_data")
    if bc is None or bc.empty:
        return

    # Crear mapa (Vencimiento, Tipo, Strike) → OI_Chg de Barchart
    bc_map = {}
    for _, row in bc.iterrows():
        tipo = row.get("Tipo", "")
        strike = row.get("Strike", 0)
        venc = row.get("Vencimiento", "")
        oi_chg = int(row.get("OI_Chg", 0) or 0)
        key = (str(venc), tipo, float(strike))
        # Si hay duplicados, sumar o quedarnos con el de mayor magnitud
        if key not in bc_map or abs(oi_chg) > abs(bc_map[key]):
            bc_map[key] = oi_chg

    if not bc_map:
        return

    # Inyectar en datos_completos
    for d in st.session_state.datos_completos:
        key = (str(d.get("Vencimiento", "")), d.get("Tipo", ""), float(d.get("Strike", 0)))
        if key in bc_map:
            d["OI_Chg"] = bc_map[key]

    # Inyectar en alertas_actuales
    for a in st.session_state.alertas_actuales:
        key = (str(a.get("Vencimiento", "")), a.get("Tipo_Opcion", ""), float(a.get("Strike", 0)))
        if key in bc_map:
            a["OI_Chg"] = bc_map[key]

    # Inyectar en clusters (detalle)
    for c in st.session_state.clusters_detectados:
        total_chg = 0
        for det in c.get("Detalle", []):
            key = (str(det.get("Vencimiento", "")), det.get("Tipo_Opcion", c.get("Tipo_Opcion", "")), float(det.get("Strike", 0)))
            if key in bc_map:
                det["OI_Chg"] = bc_map[key]
                total_chg += bc_map[key]
        if total_chg != 0:
            c["OI_Chg_Total"] = total_chg


def _enriquecer_datos_opcion(datos, precio_subyacente=None):
    """Enriquece datos de opciones con métricas derivadas calculadas."""
    if not isinstance(datos, (list, pd.DataFrame)):
        return datos
    
    # Si es DataFrame, convertir a lista de dicts
    if isinstance(datos, pd.DataFrame):
        datos_lista = datos.to_dict('records')
    else:
        datos_lista = datos.copy()
    
    for item in datos_lista:
        try:
            # Básicos
            ask = float(item.get('Ask', 0) or 0)
            bid = float(item.get('Bid', 0) or 0) 
            strike = float(item.get('Strike', 0) or 0)
            volumen = int(item.get('Volumen', 0) or 0)
            oi = int(item.get('OI', 0) or 0)
            iv = float(item.get('IV', 0) or 0)
            
            # Bid/Ask Spread
            if ask > 0 and bid > 0:
                spread = ask - bid
                spread_pct = (spread / ask) * 100 if ask > 0 else 0
                item['Spread'] = spread
                item['Spread_Pct'] = spread_pct
                item['Mid_Price'] = (ask + bid) / 2
            else:
                item['Spread'] = 0
                item['Spread_Pct'] = 0
                item['Mid_Price'] = ask or bid or 0
            
            # Volume/OI Ratio (liquidez relativa)
            item['Vol_OI_Ratio'] = volumen / oi if oi > 0 else 0
            
            # Liquidity Score (0-100)
            # Basado en: volumen, OI, spread estrechamente
            vol_score = min(volumen / 100, 1) * 40  # max 40 pts por volumen
            oi_score = min(oi / 500, 1) * 30        # max 30 pts por OI
            spread_score = max(0, 1 - item.get('Spread_Pct', 100)/10) * 30  # max 30 pts por spread estrecho
            item['Liquidity_Score'] = vol_score + oi_score + spread_score
            
            # Moneyness (si tenemos precio subyacente)
            if precio_subyacente and strike > 0:
                if item.get('Tipo_Opcion', '') == 'CALL' or item.get('Tipo', '') == 'CALL':
                    moneyness = strike / precio_subyacente
                    if moneyness < 0.95:
                        item['Moneyness'] = 'ITM'
                    elif moneyness > 1.05:
                        item['Moneyness'] = 'OTM'
                    else:
                        item['Moneyness'] = 'ATM'
                else:  # PUT
                    moneyness = precio_subyacente / strike
                    if moneyness < 0.95:
                        item['Moneyness'] = 'ITM' 
                    elif moneyness > 1.05:
                        item['Moneyness'] = 'OTM'
                    else:
                        item['Moneyness'] = 'ATM'
                
                # Distancia porcentual del precio actual
                item['Distance_Pct'] = abs(strike - precio_subyacente) / precio_subyacente * 100
            else:
                item['Moneyness'] = 'N/A'
                item['Distance_Pct'] = 0
            
            # Premium/Underlying Ratio
            mid_price = item.get('Mid_Price', 0)
            if precio_subyacente and mid_price > 0:
                item['Premium_Ratio'] = (mid_price / precio_subyacente) * 100
            else:
                item['Premium_Ratio'] = 0
            
            # Time Value (si no tenemos valor intrínseco exacto, aproximamos)
            if precio_subyacente and strike > 0 and mid_price > 0:
                tipo = item.get('Tipo_Opcion', item.get('Tipo', ''))
                if tipo == 'CALL':
                    intrinsic = max(precio_subyacente - strike, 0)
                else:  # PUT
                    intrinsic = max(strike - precio_subyacente, 0)
                item['Time_Value'] = max(mid_price - intrinsic, 0)
                item['Time_Value_Pct'] = (item['Time_Value'] / mid_price * 100) if mid_price > 0 else 0
            else:
                item['Time_Value'] = 0
                item['Time_Value_Pct'] = 0
                
        except (ValueError, TypeError, KeyError) as e:
            # Si hay error en algún cálculo, continuar con valores por defecto
            continue
    
    return datos_lista if not isinstance(datos, pd.DataFrame) else pd.DataFrame(datos_lista)


# ============================================================================
#                    CONFIGURACIÓN DE PÁGINA
# ============================================================================
st.set_page_config(
    page_title="OPTIONSKING Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
#                    ESTILOS CSS
# ============================================================================
# CSS complementario para reforzar el tema oscuro profesional
_CUSTOM_CSS = """
<style>
    /* Fondo general ultra oscuro */
    .stApp { background-color: #0f172a; color: white; }

    /* Sidebar custom */
    section[data-testid="stSidebar"] {
        background-color: #1e293b;
        border-right: 1px solid #334155;
    }

    /* Cards y containers */
    .metric-card, .stAlert, div.block-container {
        background-color: #1e293b !important;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        border: 1px solid #334155;
    }

    /* Métricas superiores */
    .stMetric { background-color: #1e293b; border-radius: 12px; padding: 1rem; }
    .stMetric > label { color: #94a3b8; }
    .stMetric > div { color: white; font-size: 1.8rem; }

    /* Tablas pro */
    table { background-color: #1e293b; }
    thead tr { background-color: #0f172a !important; }
    tbody tr:hover { background-color: #334155 !important; }

    /* Verde neón y rojo */
    .positive { color: #00ff88; }
    .negative { color: #ef4444; }
    .badge-green { background-color: #10b981; color: white; padding: 4px 10px; border-radius: 8px; }
    .badge-red { background-color: #ef4444; color: white; padding: 4px 10px; border-radius: 8px; }

    /* Gauge y charts */
    .js-plotly-plot { background-color: #1e293b !important; }
</style>
"""

# Combina CUSTOM_CSS (base) + CSS_STYLES (avanzado — tiene !important, gana donde corresponda)
st.markdown(_CUSTOM_CSS + CSS_STYLES, unsafe_allow_html=True)

# Forzar dark mode en <html> para navegadores y componentes internos
st.markdown(
    '<script>document.documentElement.setAttribute("data-theme","dark");'
    'document.documentElement.style.colorScheme="dark";</script>'
    '<meta name="color-scheme" content="dark">',
    unsafe_allow_html=True,
)

# ============================================================================
#                    INICIALIZAR SESSION STATE
# ============================================================================
_DEFAULTS = {
    "alertas_actuales": [],
    "datos_completos": [],
    "scan_count": 0,
    "last_scan_time": None,
    "last_perfil": None,
    "scan_error": None,
    "datos_anteriores": [],
    "oi_cambios": None,
    "fechas_escaneadas": [],
    "auto_scan": False,
    "clusters_detectados": [],
    "ticker_anterior": "SPY",
    "trigger_scan": False,
    "todas_las_fechas": [],
    "rango_resultado": None,
    "rango_error": None,
    "noticias_data": [],
    "noticias_last_refresh": None,
    "barchart_data": None,
    "barchart_error": None,
    "noticias_auto_refresh": False,
    "noticias_filtro": "Todas",
    "favoritos": [],
    "eventos_economicos": [],
    "eventos_last_refresh": None,
}
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# Cargar favoritos desde disco al inicio
if not st.session_state.favoritos:
    st.session_state.favoritos = _cargar_favoritos()

# ============================================================================
#                    SIDEBAR - CONFIGURACIÓN
# ============================================================================
with st.sidebar:
    # -- OPTIONSKING Analytics Logo --
    st.markdown("""
        <div style="text-align: center; padding: 2rem 0 1rem;">
            <div style="display:inline-block;width:56px;height:56px;margin-bottom:10px;">
                <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stop-color="#00ff88"/><stop offset="100%" stop-color="#10b981"/>
                    </linearGradient></defs>
                    <path d="M8 48h48l-6-28-10 12-10-20-10 20-10-12z" fill="url(#cg)" stroke="#00ff88" stroke-width="1.5"/>
                    <rect x="8" y="48" width="48" height="6" rx="2" fill="url(#cg)"/>
                    <circle cx="32" cy="12" r="3" fill="#00ff88"/>
                    <circle cx="12" cy="22" r="2.5" fill="#10b981"/>
                    <circle cx="52" cy="22" r="2.5" fill="#10b981"/>
                </svg>
            </div>
            <h1 style="color: #00ff88; font-size: 36px; margin:0; font-weight:800; letter-spacing:-0.02em;">OPTIONSKING</h1>
            <p style="color: white; font-size: 22px; margin:4px 0 0 0; font-weight:500;">Analytics</p>
        </div>
        <hr style="border-color: #334155; margin: 0.5rem 0 1rem 0;">
    """, unsafe_allow_html=True)

    # -- Menú de navegación con emojis --
    pagina = st.radio(
        "Navegación",
        ["🏠 Dashboard", "📊 Market Overview", "🔍 Options Screener",
         "⚠️ Unusual Activity", "🔔 Smart Alerts", "📰 News & Calendar", "⚙️ Settings"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # -- Ticker Input --
    ticker_symbol = st.text_input(
        "🔍 Símbolo del Ticker", value="SPY", max_chars=10,
        help="Ingresa el símbolo de la acción (ej: SPY, AAPL, TSLA, QQQ)"
    ).strip().upper()

    # Detectar cambio de ticker → auto-escanear
    if ticker_symbol and ticker_symbol != st.session_state.ticker_anterior:
        st.session_state.ticker_anterior = ticker_symbol
        st.session_state.alertas_actuales = []
        st.session_state.datos_completos = []
        st.session_state.datos_anteriores = []
        st.session_state.oi_cambios = None
        st.session_state.barchart_data = None
        st.session_state.barchart_error = None
        st.session_state.clusters_detectados = []
        st.session_state.rango_resultado = None
        st.session_state.rango_error = None
        st.session_state.scan_error = None
        st.session_state.fechas_escaneadas = []
        st.session_state.trigger_scan = True
        st.rerun()

    with st.expander("📊 Umbrales", expanded=False):
        umbral_vol = st.number_input("Volumen mínimo", value=DEFAULT_MIN_VOLUME, step=1_000, format="%d",
                                      help="Solo muestra contratos con volumen ≥ este valor")
        umbral_oi = st.number_input("Open Interest mínimo", value=DEFAULT_MIN_OI, step=1_000, format="%d",
                                     help="Solo muestra contratos con OI ≥ este valor")
        umbral_prima = st.number_input(
            "Prima Total mínima ($)", value=DEFAULT_MIN_PRIMA, step=500_000, format="%d",
            help="Prima Total = Volumen × Precio × 100 (dinero que entró en el contrato ese día)"
        )
        st.caption("💡 **Prima Total** = Volumen × Precio × 100 — Representa el flujo de dinero total del contrato basado en el volumen transaccionado del día.")
        umbral_filtro = st.number_input("Filtro rápido (vol/oi mín.)", value=DEFAULT_QUICK_FILTER, step=100, format="%d",
                                         help="Ignora opciones con vol Y oi debajo de este umbral en el análisis")

    # Guardado automático siempre activo
    csv_carpeta = "alertas"
    guardar_csv = True

    with st.expander("📐 Rango Esperado", expanded=False):
        rango_delta = st.slider(
            "Delta objetivo (σ)", min_value=0.01, max_value=1.00, value=DEFAULT_TARGET_DELTA, step=0.01,
            help="0.16 ≈ 1σ (68%). 0.05 ≈ 2σ (95%). Menor delta = rango más amplio."
        )

    with st.expander("🛡️ Anti-Ban", expanded=False):
        st.markdown(
            f"""
            <div class="info-card">
                <div style="font-size: 0.82rem; color: #94a3b8;">
                    <b style="color: #10b981;">{len(BROWSER_PROFILES)}</b> perfiles TLS<br>
                    <span style="font-size: 0.72rem;">Chrome · Edge · Safari<br>
                    JA3/JA4 fingerprinting via curl_cffi</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -- Avatar / User Section --
    st.markdown(
        '<div style="text-align:center; margin-top:2rem; padding:1rem 0;">'
        '<div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#00ff88,#10b981);'
        'display:inline-flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;color:#0f172a;'
        'margin-bottom:8px;box-shadow:0 0 16px rgba(0,255,136,0.2);">AD</div>'
        '<div style="color:white;font-weight:600;font-size:0.9rem;">Ariel David</div>'
        '<div style="color:#64748b;font-size:0.75rem;">● Pro Plan</div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ============================================================================
#                    ENCABEZADO PRINCIPAL
# ============================================================================
# Header superior: search + upgrade
col_search, col_upgrade = st.columns([5, 1])
with col_search:
    _search_query = st.text_input("🔍 Search...", placeholder="Buscar ticker, contrato, strike...", label_visibility="collapsed")
with col_upgrade:
    st.button("Upgrade 💎", type="primary", use_container_width=True)

st.markdown(
    f"""
    <div class="scanner-header">
        <h1>👑 OPTIONS<span style="color: #00ff88;">KING</span> Analytics</h1>
        <p class="subtitle">
            Escáner institucional de actividad inusual en opciones — <b style="color: #00ff88;">{ticker_symbol}</b>
        </p>
        <span class="badge">● LIVE • Anti-Ban • Análisis Avanzado</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
#                    NAVEGACIÓN POR RADIO (SIDEBAR)
# ============================================================================

# ============================================================================
#   🏠 DASHBOARD — ESCÁNER EN VIVO
# ============================================================================
if pagina == "🏠 Dashboard":
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        scan_btn = st.button("🚀 Escanear Ahora", type="primary", use_container_width=True)
    with col_btn2:
        auto_scan = st.checkbox("🔄 Auto-escaneo (5 min)")

    if st.session_state.last_scan_time:
        st.markdown(
            f"""
            <div class="status-bar">
                <div class="status-dot"></div>
                <span>Último escaneo: <b>{st.session_state.last_scan_time}</b></span>
                <span>Perfil TLS: <b>{st.session_state.last_perfil}</b></span>
                <span>Ciclos: <b>{st.session_state.scan_count}</b></span>
                <span>Fechas: <b>{len(st.session_state.fechas_escaneadas)}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Ejecutar escaneo ---
    auto_trigger = st.session_state.trigger_scan
    if auto_trigger:
        st.session_state.trigger_scan = False

    if scan_btn or auto_trigger or (auto_scan and st.session_state.auto_scan):
        with st.status("🔍 Escaneando opciones...", expanded=True) as status:
            st.write(f"Creando sesión TLS anti-ban...")
            st.write(f"Descargando cadena de opciones de **{ticker_symbol}**...")
            st.write(f"Analizando **todas** las fechas de vencimiento disponibles...")

            # Guardar datos anteriores para comparar OI
            if st.session_state.datos_completos:
                st.session_state.datos_anteriores = st.session_state.datos_completos.copy()

            alertas, datos, error, perfil, fechas = ejecutar_escaneo(
                ticker_symbol,
                umbral_vol,
                umbral_oi,
                umbral_prima,
                umbral_filtro,
                csv_carpeta,
                guardar_csv,
            )

            if error:
                status.update(label=f"❌ Error: {error}", state="error")
                st.session_state.scan_error = error
            else:
                st.session_state.alertas_actuales = alertas
                st.session_state.datos_completos = datos
                st.session_state.scan_count += 1
                st.session_state.last_scan_time = datetime.now().strftime("%H:%M:%S")
                
                # Capturar precio subyacente para cálculos de reportes
                try:
                    ticker_info = yf.Ticker(ticker_symbol)
                    hist = ticker_info.history(period="1d")
                    if not hist.empty:
                        st.session_state.precio_subyacente = hist['Close'].iloc[-1]
                    else:
                        # Fallback: usar precio de las opciones si está disponible
                        if datos and len(datos) > 0:
                            # Buscar en los datos si hay algún precio underlyingPrice
                            prices = [d.get('underlyingPrice') for d in datos if d.get('underlyingPrice')]
                            if prices:
                                st.session_state.precio_subyacente = prices[0]
                except Exception:
                    # Si no se puede obtener, mantener el anterior o None
                    pass
                st.session_state.last_perfil = perfil
                st.session_state.scan_error = None
                st.session_state.fechas_escaneadas = fechas
                n_alertas = len(alertas)
                n_opciones = len(datos)

                # Calcular cambios en OI entre escaneos (para oi_tracker)
                if st.session_state.datos_anteriores:
                    st.session_state.oi_cambios = calcular_cambios_oi(
                        datos, st.session_state.datos_anteriores
                    )

                # Inicializar OI_Chg en 0 (será sobrescrito por Barchart)
                for d in st.session_state.datos_completos:
                    d["OI_Chg"] = 0
                for a in st.session_state.alertas_actuales:
                    a["OI_Chg"] = 0

                # Auto-fetch Barchart OI Changes (fuente real de OI_Chg)
                st.write("Obteniendo datos de Open Interest de Barchart...")
                _fetch_barchart_oi(ticker_symbol)

                # Inyectar OI_Chg real de Barchart en datos_completos y alertas
                _inyectar_oi_chg_barchart()

                # Detectar clusters DESPUÉS de inyectar OI_Chg
                clusters = detectar_compras_continuas(alertas, umbral_prima)
                st.session_state.clusters_detectados = clusters

                status.update(
                    label=f"✅ Escaneo completado — {n_alertas} alertas en {n_opciones:,} opciones",
                    state="complete",
                )

    st.session_state.auto_scan = auto_scan

    # --- Market Overview ---
    st.markdown("### 📊 Market Overview")

    if st.session_state.datos_completos:
        datos_df = pd.DataFrame(st.session_state.datos_completos)
        _n_calls = len(datos_df[datos_df["Tipo"] == "CALL"])
        _n_puts = len(datos_df[datos_df["Tipo"] == "PUT"])
        _n_alertas = len(st.session_state.alertas_actuales)
        _n_clusters = len(st.session_state.clusters_detectados)
        _total = len(datos_df)
        _call_pct = (_n_calls / _total * 100) if _total else 0
        _put_pct = (_n_puts / _total * 100) if _total else 0
        _pc_ratio = _n_puts / _n_calls if _n_calls > 0 else 0
        _total_vol = int(datos_df["Volumen"].sum()) if "Volumen" in datos_df.columns else 0
        _total_oi = int(datos_df["OI"].sum()) if "OI" in datos_df.columns else 0
        _total_prima = datos_df["Prima_Volumen"].sum() if "Prima_Volumen" in datos_df.columns else 0
        _flow_pct = _call_pct - _put_pct  # positive = bullish flow
        _spk = sorted(datos_df["Volumen"].dropna().tail(12).tolist()) if "Volumen" in datos_df.columns else None
        _spk_oi = sorted(datos_df["OI"].dropna().tail(12).tolist()) if "OI" in datos_df.columns else None

        st.markdown(render_metric_row([
            render_metric_card("Flow Sentiment", f"{_flow_pct:+.1f}%", delta=_flow_pct, sparkline_data=_spk),
            render_metric_card("Total Volume", f"{_total_vol:,}", delta=_call_pct, delta_suffix="% calls"),
            render_metric_card("Gamma Exposure", _fmt_monto(_total_prima), sparkline_data=_spk_oi),
            render_metric_card("Put/Call Ratio", f"{_pc_ratio:.2f}", delta=-(_pc_ratio - 1) * 100 if _pc_ratio != 0 else 0, color_override="#ef4444" if _pc_ratio > 1 else "#00ff88"),
            render_metric_card("Unusual Alerts", f"{_n_alertas}", delta=float(_n_clusters), delta_suffix=" clusters"),
        ]), unsafe_allow_html=True)

        # Mini Plotly sparkline charts debajo de las cards
        _spark_cols = st.columns(5)
        _vol_spark = render_plotly_sparkline(_spk, color="#00ff88", height=50)
        _oi_spark = render_plotly_sparkline(_spk_oi, color="#3b82f6", height=50)
        if _vol_spark:
            with _spark_cols[0]:
                st.plotly_chart(_vol_spark, use_container_width=True, config={"displayModeBar": False})
        if _oi_spark:
            with _spark_cols[2]:
                st.plotly_chart(_oi_spark, use_container_width=True, config={"displayModeBar": False})

    # --- Mostrar alertas ---
    if st.session_state.alertas_actuales:
        st.markdown("### 🚨 Alertas Detectadas")

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
        st.info("💡 **Prima Total** = Volumen × Precio × 100 — Representa el flujo de dinero total del contrato basado en el volumen transaccionado del día (no del Open Interest).")

        alertas_sorted = sorted(
            st.session_state.alertas_actuales,
            key=lambda a: a["Prima_Volumen"],
            reverse=True,
        )
        max_prima = max(a["Prima_Volumen"] for a in alertas_sorted)

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

            # Determinar sentimiento para colorear
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

            expander_label = (
                f"{emoji} {etiqueta} — {alerta['Tipo_Opcion']} Strike ${alerta['Strike']} | "
                f"Venc: {alerta['Vencimiento']} | Vol: {alerta['Volumen']:,} | "
                f"Prima: ${prima_mayor:,.0f}"
            )

            with st.expander(expander_label, expanded=False):
                # ⭐ Botón de favorito rápido (arriba del detalle)
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
                        <span class="razon-alerta">📌 {razon_html}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # --- Detalles + Gráfica del contrato ---
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
                        st.markdown(f"- **Prima Total:** ${prima_mayor:,.0f}")

                        # Botón de favorito
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
                                display_hist.index = display_hist.index.strftime("%Y-%m-%d %H:%M")
                                for col in ["Open", "High", "Low", "Close"]:
                                    if col in display_hist.columns:
                                        display_hist[col] = display_hist[col].apply(
                                            lambda x: f"${x:.2f}" if pd.notna(x) else "-"
                                        )
                                st.dataframe(display_hist, width="stretch", hide_index=False)
                else:
                    st.info("ℹ️ No se encontró el símbolo del contrato.")

        # ── Two-column dashboard layout ──────────────────────────────
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
        if "Tipo_Opcion" in alertas_df.columns:
            alertas_df["Tipo_Opcion"] = alertas_df["Tipo_Opcion"].apply(_type_badge)
        if "Lado" in alertas_df.columns:
            alertas_df["Lado"] = alertas_df["Lado"].apply(_fmt_lado)
        alertas_df = alertas_df.rename(columns={"Prima_Volumen": "Prima Total"})
        alertas_df["Prima Total"] = alertas_df["Prima Total"].apply(_fmt_dolar)
        cols_ocultar = [c for c in ["OI", "OI_Chg"] if c in alertas_df.columns]
        _tbl_df = alertas_df.drop(columns=cols_ocultar, errors="ignore")

        _col_left, _col_right = st.columns([1, 1], gap="medium")

        # ── LEFT COLUMN: Unusual Activity + Net Flow + Clusters ──
        with _col_left:
            st.markdown(
                render_pro_table(
                    _tbl_df,
                    title="📋 Unusual Activity — Alertas",
                    badge_count=f"{len(_tbl_df)} alertas",
                    footer_text=f"Ordenadas por prima · {len(_tbl_df)} resultados",
                    special_format={"Prioridad": _priority_badge},
                ),
                unsafe_allow_html=True,
            )

            # --- Net Flow bar chart (Calls vs Puts) ---
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
                    marker_color="#00ff88", name="Calls",
                    text=[f"${_calls_prima:,.0f}"], textposition="auto",
                    textfont=dict(color="#ffffff", size=12),
                ))
                _net_fig.add_trace(go.Bar(
                    x=["PUTS"], y=[_puts_prima],
                    marker_color="#ef4444", name="Puts",
                    text=[f"${_puts_prima:,.0f}"], textposition="auto",
                    textfont=dict(color="#ffffff", size=12),
                ))
                _net_fig.update_layout(
                    title=dict(text="Net Premium Flow", font=dict(color="#e2e8f0", size=14)),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8", family="Inter"),
                    height=260, margin=dict(l=10, r=10, t=40, b=10),
                    showlegend=False,
                    yaxis=dict(gridcolor="rgba(51,65,85,0.4)", tickformat="$,.0f"),
                    xaxis=dict(showgrid=False),
                    bargap=0.35,
                )
                st.plotly_chart(_net_fig, use_container_width=True, config={"displayModeBar": False})

            # --- CLUSTERS ---
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

        # ── RIGHT COLUMN: Options Flow Screener ──
        with _col_right:
            st.markdown(
                '<div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;">'
                '🔍 Options Flow Screener</div>',
                unsafe_allow_html=True,
            )
            if st.session_state.datos_completos:
                datos_df = pd.DataFrame(st.session_state.datos_completos)

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

                cols_ocultar_df = [c for c in ["OI", "OI_Chg"] if c in display_df.columns]
                st.dataframe(
                    display_df.drop(columns=cols_ocultar_df, errors="ignore").sort_values("Volumen", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    height=600,
                )
                st.caption(f"Mostrando {len(df_filtered):,} de {len(datos_df):,} opciones")
            else:
                st.info("Ejecuta un escaneo para ver el flujo de opciones.")

    elif st.session_state.scan_count > 0 and not st.session_state.scan_error:
        st.success("✅ Sin alertas relevantes en este ciclo.")

    # --- Options Flow Screener (when no alerts but data exists) ---
    if not st.session_state.alertas_actuales and st.session_state.datos_completos:
        st.markdown(
            '<div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;">'
            '🔍 Options Flow Screener</div>',
            unsafe_allow_html=True,
        )
        datos_df = pd.DataFrame(st.session_state.datos_completos)

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

        cols_ocultar_df = [c for c in ["OI", "OI_Chg"] if c in display_df.columns]
        st.dataframe(
            display_df.drop(columns=cols_ocultar_df, errors="ignore").sort_values("Volumen", ascending=False),
            use_container_width=True,
            hide_index=True,
            height=500,
        )
        st.caption(f"Mostrando {len(df_filtered):,} de {len(datos_df):,} opciones")

    # Auto-refresh con countdown visual
    if auto_scan and st.session_state.scan_count > 0:
        countdown = AUTO_REFRESH_INTERVAL  # Configurable desde constants.py
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
        st.rerun()


# ============================================================================
#   📊 MARKET OVERVIEW — OPEN INTEREST
# ============================================================================
elif pagina == "📊 Market Overview":
    st.markdown("### 📊 Open Interest")

    # ================================================================
    #  TOP OI CHANGES (Barchart) — Auto-cargado al escanear
    # ================================================================
    st.markdown("#### 🔥 Top Cambios en OI — Barchart")
    st.caption("Se actualiza automáticamente con cada escaneo • Fuente: Barchart.com")

    # Filtro tipo + OI Chg mínimo
    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        bc_tipo_filtro = st.radio(
            "Filtrar por tipo", ["Todos", "📞 CALL", "📋 PUT"],
            horizontal=True, key="bc_tipo_filtro", index=0,
        )
    with col_f2:
        bc_min_chg = st.number_input(
            "OI Chg mínimo", value=0, step=5, min_value=0, key="bc_min_chg",
        )

    # Botón para recarga manual (sin necesidad de re-escanear)
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        bc_refresh = st.button("🔄 Actualizar OI", key="bc_refresh")

    if bc_refresh:
        with st.spinner("🌐 Consultando Barchart.com..."):
            sim_bc = st.session_state.get("ticker_anterior", "SPY")
            _fetch_barchart_oi(sim_bc)
            _inyectar_oi_chg_barchart()

    # Mostrar error
    if st.session_state.barchart_error:
        st.warning(f"⚠️ {st.session_state.barchart_error}")

    # Mostrar datos
    if st.session_state.barchart_data is not None and not st.session_state.barchart_data.empty:
        df_bc_all = st.session_state.barchart_data.copy()

        # Aplicar filtro tipo
        if bc_tipo_filtro == "📞 CALL":
            df_bc_all = df_bc_all[df_bc_all["Tipo"] == "CALL"]
        elif bc_tipo_filtro == "📋 PUT":
            df_bc_all = df_bc_all[df_bc_all["Tipo"] == "PUT"]

        # Aplicar filtro OI Chg mínimo (valor absoluto)
        if bc_min_chg > 0:
            df_bc_all = df_bc_all[df_bc_all["OI_Chg"].abs() >= bc_min_chg]

        n_total = len(df_bc_all)

        if n_total == 0:
            st.info("Sin contratos que cumplan los filtros seleccionados.")
        else:
            # Separar positivos y negativos
            df_positivos = df_bc_all[df_bc_all["OI_Chg"] > 0].sort_values("OI_Chg", ascending=False).reset_index(drop=True)
            df_negativos = df_bc_all[df_bc_all["OI_Chg"] < 0].sort_values("OI_Chg", ascending=True).reset_index(drop=True)

            n_pos = len(df_positivos)
            n_neg = len(df_negativos)
            n_calls = len(df_bc_all[df_bc_all["Tipo"] == "CALL"]) if "Tipo" in df_bc_all.columns else 0
            n_puts = len(df_bc_all[df_bc_all["Tipo"] == "PUT"]) if "Tipo" in df_bc_all.columns else 0

            # Calcular contratos cerrados (OI_Chg negativo)
            contratos_cerrados_total = int(df_negativos["OI_Chg"].sum()) if n_neg > 0 else 0
            calls_cerrados = int(df_negativos[df_negativos["Tipo"] == "CALL"]["OI_Chg"].sum()) if n_neg > 0 and "Tipo" in df_negativos.columns else 0
            puts_cerrados = int(df_negativos[df_negativos["Tipo"] == "PUT"]["OI_Chg"].sum()) if n_neg > 0 and "Tipo" in df_negativos.columns else 0

            # Calcular contratos abiertos (OI_Chg positivo)
            contratos_abiertos_total = int(df_positivos["OI_Chg"].sum()) if n_pos > 0 else 0
            calls_abiertos = int(df_positivos[df_positivos["Tipo"] == "CALL"]["OI_Chg"].sum()) if n_pos > 0 and "Tipo" in df_positivos.columns else 0
            puts_abiertos = int(df_positivos[df_positivos["Tipo"] == "PUT"]["OI_Chg"].sum()) if n_pos > 0 and "Tipo" in df_positivos.columns else 0

            # Métricas rápidas
            _pos_pct = (n_pos / n_total * 100) if n_total else 0
            _neg_pct = (n_neg / n_total * 100) if n_total else 0
            st.markdown(render_metric_row([
                render_metric_card("Total Contratos", f"{n_total:,}"),
                render_metric_card("CALLs", f"{n_calls:,}", delta=(n_calls / n_total * 100) if n_total else 0),
                render_metric_card("PUTs", f"{n_puts:,}", delta=(n_puts / n_total * 100) if n_total else 0, color_override="#ef4444"),
                render_metric_card("Señales Positivas", f"{n_pos:,}", delta=_pos_pct),
                render_metric_card("Señales Negativas", f"{n_neg:,}", delta=_neg_pct, color_override="#ef4444"),
            ]), unsafe_allow_html=True)

            # Segunda fila de métricas: Contratos abiertos vs cerrados
            st.markdown("---")
            st.markdown("##### 📈 Flujo de Contratos")
            _net_flow = contratos_abiertos_total + contratos_cerrados_total
            _open_spk = [max(0, v) for v in df_positivos["OI_Chg"].head(10).tolist()] if n_pos > 1 else None
            _close_spk = [abs(v) for v in df_negativos["OI_Chg"].head(10).tolist()] if n_neg > 1 else None
            st.markdown(render_metric_row([
                render_metric_card("Contratos Abiertos", f"{contratos_abiertos_total:,}", delta="Nuevas posiciones", sparkline_data=_open_spk),
                render_metric_card("CALLs Abiertos", f"{calls_abiertos:,}"),
                render_metric_card("PUTs Abiertos", f"{puts_abiertos:,}"),
                render_metric_card("Contratos Cerrados", f"{contratos_cerrados_total:,}", delta="Posiciones cerradas", sparkline_data=_close_spk, color_override="#ef4444"),
                render_metric_card("CALLs Cerrados", f"{calls_cerrados:,}"),
                render_metric_card("PUTs Cerrados", f"{puts_cerrados:,}"),
            ]), unsafe_allow_html=True)

            st.markdown("---")

            # --- Columnas de tabla ---
            display_cols = ["Tipo", "Ticker", "Strike", "Vencimiento", "DTE",
                            "Volumen", "OI", "OI_Chg", "IV", "Delta", "Último"]

            def _formatear_tabla_oi(df_raw):
                """Formatea un DataFrame de OI para mostrar."""
                cols = [c for c in display_cols if c in df_raw.columns]
                df_fmt = df_raw[cols].copy()
                df_fmt["OI_Chg"] = df_fmt["OI_Chg"].apply(
                    lambda x: f"+{int(x):,}" if x > 0 else f"{int(x):,}" if x < 0 else "0"
                )
                df_fmt["Volumen"] = df_fmt["Volumen"].apply(lambda x: f"{int(x):,}")
                df_fmt["OI"] = df_fmt["OI"].apply(lambda x: f"{int(x):,}")
                df_fmt["IV"] = df_fmt["IV"].apply(lambda x: f"{x:.1f}%" if x > 0 else "-")
                df_fmt["Delta"] = df_fmt["Delta"].apply(lambda x: f"{x:.3f}" if x != 0 else "-")
                df_fmt["Último"] = df_fmt["Último"].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
                df_fmt["Strike"] = df_fmt["Strike"].apply(lambda x: f"${x:,.1f}")
                return df_fmt

            def _mostrar_tabla_paginada(df_raw, df_fmt, key_prefix, emoji_func):
                """Muestra tabla con paginación y emojis."""
                n = len(df_fmt)
                if n == 0:
                    st.info("Sin contratos en esta categoría.")
                    return

                # Indicador visual
                df_show = df_fmt.copy()
                df_show.insert(0, "", df_raw["OI_Chg"].apply(emoji_func))

                contratos_por_grupo = 20
                if n > contratos_por_grupo:
                    rangos = []
                    for i in range(0, n, contratos_por_grupo):
                        inicio_r = i + 1
                        fin_r = min(i + contratos_por_grupo, n)
                        rangos.append(f"{inicio_r}-{fin_r}")
                    rango_sel = st.selectbox(
                        f"Rango de contratos (Total: {n:,})",
                        rangos, key=f"{key_prefix}_rango",
                    )
                    inicio_idx, fin_idx = map(int, rango_sel.split("-"))
                else:
                    inicio_idx, fin_idx = 1, n

                df_pagina = df_show.iloc[inicio_idx - 1 : fin_idx]
                st.dataframe(
                    df_pagina,
                    use_container_width=True,
                    hide_index=True,
                    height=min(500, 35 * len(df_pagina) + 38),
                )
                st.caption(f"Mostrando {inicio_idx}-{fin_idx} de {n:,} contratos")

            # ========================================
            # TABLA 1: OI Chg POSITIVO (Abriendo posiciones)
            # ========================================
            st.markdown("#### 🟢 OI Chg Positivo — Abriendo Posiciones")
            st.caption("Contratos donde el Open Interest aumentó → nuevas posiciones abiertas")

            if n_pos > 0:
                df_pos_fmt = _formatear_tabla_oi(df_positivos)
                _mostrar_tabla_paginada(
                    df_positivos, df_pos_fmt, "oi_pos",
                    lambda x: "🔥" if x >= 50 else ("🟢" if x >= 20 else "")
                )
            else:
                st.info("Sin contratos con OI Chg positivo.")

            st.markdown("---")

            # ========================================
            # TABLA 2: OI Chg NEGATIVO (Cerrando posiciones)
            # ========================================
            st.markdown("#### 🔴 OI Chg Negativo — Cerrando Posiciones")
            st.caption("Contratos donde el Open Interest disminuyó → posiciones cerradas o ejercidas")

            if n_neg > 0:
                df_neg_fmt = _formatear_tabla_oi(df_negativos)
                _mostrar_tabla_paginada(
                    df_negativos, df_neg_fmt, "oi_neg",
                    lambda x: "🔥" if x <= -50 else ("🔴" if x <= -20 else "")
                )
            else:
                st.info("Sin contratos con OI Chg negativo.")
    elif st.session_state.scan_count == 0:
        st.info("⏳ **Ejecutá un escaneo** en 🏠 Dashboard para cargar los datos de Open Interest automáticamente.")


# ============================================================================
#   ⚠️ UNUSUAL ACTIVITY — HISTORIAL DE ALERTAS
# ============================================================================
elif pagina == "⚠️ Unusual Activity":
    st.markdown("### 📜 Historial de Alertas y Datos Guardados")
    st.markdown(
        """
        <div class="watchlist-info">
            💾 <b>Centro de Datos</b> — Todas las alertas se guardan automáticamente al escanear.
            Aquí puedes ver el historial completo, filtrar, y descargar reportes detallados
            de alertas, opciones escaneadas, clusters y rango esperado.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- SECCIÓN 1: HISTORIAL CSV ---
    st.markdown("#### 📁 Historial de Alertas Guardadas")
    historial_df = cargar_historial_csv(csv_carpeta)
    
    # Agregar columna de sentimiento al historial
    if not historial_df.empty and "Tipo_Opcion" in historial_df.columns and "Lado" in historial_df.columns:
        historial_df.insert(0, "Sentimiento", historial_df.apply(
            lambda row: f"{determinar_sentimiento(row['Tipo_Opcion'], row.get('Lado', 'N/A'))[1]} {determinar_sentimiento(row['Tipo_Opcion'], row.get('Lado', 'N/A'))[0]}",
            axis=1
        ))
    
    # Renombrar Prima_Total (CSV) a "Prima Total" (UI con espacio) para mejor visualización
    # También maneja CSVs antiguos que puedan tener Prima_Volumen
    if not historial_df.empty:
        if "Prima_Total" in historial_df.columns:
            historial_df = historial_df.rename(columns={"Prima_Total": "Prima Total"})
        elif "Prima_Volumen" in historial_df.columns:
            historial_df = historial_df.rename(columns={"Prima_Volumen": "Prima Total"})

    if historial_df.empty:
        st.info(
            "No se encontraron alertas guardadas aún.\n\n"
            "Las alertas se guardan automáticamente cada vez que ejecutas un escaneo."
        )
    else:
        _h_total = len(historial_df)
        n_principal = len(
            historial_df[historial_df["Tipo_Alerta"] == "PRINCIPAL"]
        ) if "Tipo_Alerta" in historial_df.columns else 0
        n_prima = len(
            historial_df[historial_df["Tipo_Alerta"] == "PRIMA_ALTA"]
        ) if "Tipo_Alerta" in historial_df.columns else 0
        tickers_unicos = (
            historial_df["Ticker"].nunique()
            if "Ticker" in historial_df.columns
            else 0
        )
        _inst_pct = (n_principal / _h_total * 100) if _h_total else 0
        _prima_pct = (n_prima / _h_total * 100) if _h_total else 0
        st.markdown(render_metric_row([
            render_metric_card("Total de Alertas", f"{_h_total:,}"),
            render_metric_card("Institucional", f"{n_principal:,}", delta=_inst_pct, color_override="#ef4444"),
            render_metric_card("Prima Alta", f"{n_prima:,}", delta=_prima_pct, color_override="#f59e0b"),
            render_metric_card("Tickers Únicos", f"{tickers_unicos}"),
        ]), unsafe_allow_html=True)

        st.markdown("##### 🔎 Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            if "Tipo_Alerta" in historial_df.columns:
                tipos_disponibles = ["Todos"] + historial_df["Tipo_Alerta"].unique().tolist()
            else:
                tipos_disponibles = ["Todos"]
            filtro_tipo_hist = st.selectbox(
                "Tipo de Alerta", tipos_disponibles, key="hist_tipo"
            )

        with col_f2:
            if "Tipo_Opcion" in historial_df.columns:
                opciones_disponibles = ["Todos"] + historial_df["Tipo_Opcion"].unique().tolist()
            else:
                opciones_disponibles = ["Todos"]
            filtro_opcion_hist = st.selectbox(
                "Tipo de Opción", opciones_disponibles, key="hist_opcion"
            )

        with col_f3:
            if "Ticker" in historial_df.columns:
                tickers_disponibles = ["Todos"] + sorted(
                    historial_df["Ticker"].unique().tolist()
                )
            else:
                tickers_disponibles = ["Todos"]
            filtro_ticker_hist = st.selectbox(
                "Ticker", tickers_disponibles, key="hist_ticker"
            )

        df_hist_filtered = historial_df.copy()
        if filtro_tipo_hist != "Todos" and "Tipo_Alerta" in df_hist_filtered.columns:
            df_hist_filtered = df_hist_filtered[
                df_hist_filtered["Tipo_Alerta"] == filtro_tipo_hist
            ]
        if filtro_opcion_hist != "Todos" and "Tipo_Opcion" in df_hist_filtered.columns:
            df_hist_filtered = df_hist_filtered[
                df_hist_filtered["Tipo_Opcion"] == filtro_opcion_hist
            ]
        if filtro_ticker_hist != "Todos" and "Ticker" in df_hist_filtered.columns:
            df_hist_filtered = df_hist_filtered[
                df_hist_filtered["Ticker"] == filtro_ticker_hist
            ]

        _hist_sorted = (
            df_hist_filtered.sort_values("Fecha_Hora", ascending=False)
            if "Fecha_Hora" in df_hist_filtered.columns else df_hist_filtered
        )
        # Format columns for pro table
        _hist_show = _hist_sorted.copy()
        if "Tipo_Opcion" in _hist_show.columns:
            _hist_show["Tipo_Opcion"] = _hist_show["Tipo_Opcion"].apply(_type_badge)
        if "Tipo_Alerta" in _hist_show.columns:
            _hist_show["Tipo_Alerta"] = _hist_show["Tipo_Alerta"].apply(_priority_badge)
        if "Prima Total" in _hist_show.columns:
            _hist_show["Prima Total"] = _hist_show["Prima Total"].apply(
                lambda x: _fmt_dolar(x) if isinstance(x, (int, float)) else x
            )
        if "Lado" in _hist_show.columns:
            _hist_show["Lado"] = _hist_show["Lado"].apply(_fmt_lado)
        st.markdown(
            render_pro_table(
                _hist_show,
                title="📜 Historial de Alertas",
                badge_count=f"{len(df_hist_filtered):,} de {len(historial_df):,}",
                footer_text=f"Mostrando {len(df_hist_filtered):,} de {len(historial_df):,} alertas",
            ),
            unsafe_allow_html=True,
        )

        csv_download = df_hist_filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Alertas CSV",
            csv_download,
            f"alertas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            key="dl_alertas_hist",
        )

    # --- SECCIÓN 2: DATOS DEL ÚLTIMO ESCANEO ---
    st.markdown("---")
    st.markdown("#### 📊 Datos del Último Escaneo")

    if not st.session_state.datos_completos:
        st.info("Ejecuta un escaneo en 🏠 **Dashboard** para ver los datos aquí.")
    else:
        datos_df = pd.DataFrame(st.session_state.datos_completos)
        _a_calls = len(datos_df[datos_df["Tipo"] == "CALL"])
        _a_puts = len(datos_df[datos_df["Tipo"] == "PUT"])
        _a_total = len(datos_df)
        _a_alertas = len(st.session_state.alertas_actuales)
        _a_clusters = len(st.session_state.clusters_detectados)
        _a_cpct = (_a_calls / _a_total * 100) if _a_total else 0
        _a_ppct = (_a_puts / _a_total * 100) if _a_total else 0
        _a_spk = sorted(datos_df["Volumen"].dropna().tail(12).tolist()) if "Volumen" in datos_df.columns else None
        st.markdown(render_metric_row([
            render_metric_card("Opciones", f"{_a_total:,}", sparkline_data=_a_spk),
            render_metric_card("Calls", f"{_a_calls:,}", delta=_a_cpct),
            render_metric_card("Puts", f"{_a_puts:,}", delta=_a_ppct, color_override="#ef4444"),
            render_metric_card("Alertas", f"{_a_alertas}"),
            render_metric_card("Clusters", f"{_a_clusters}"),
        ]), unsafe_allow_html=True)

        with st.expander("🔍 Ver todas las opciones escaneadas", expanded=False):
            # Enriquecer datos para mejores métricas
            datos_enriquecidos = _enriquecer_datos_opcion(
                st.session_state.datos_completos, 
                precio_subyacente=st.session_state.get('precio_subyacente')
            )
            display_scan = pd.DataFrame(datos_enriquecidos)
            
            # Aplicar formateo para visualización
            if 'Prima_Vol' in display_scan.columns:
                display_scan["Prima Total"] = display_scan["Prima_Vol"].apply(_fmt_monto)
            if 'IV' in display_scan.columns:
                display_scan["IV_F"] = display_scan["IV"].apply(_fmt_iv)
            if 'Spread_Pct' in display_scan.columns:
                display_scan["Spread_%"] = display_scan["Spread_Pct"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
            if 'Liquidity_Score' in display_scan.columns:
                display_scan["Liquidez"] = display_scan["Liquidity_Score"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "-")
            if 'Lado' in display_scan.columns:
                display_scan["Lado_F"] = display_scan["Lado"].apply(_fmt_lado)
            
            # Agregar columna de sentimiento
            if 'Tipo' in display_scan.columns and 'Lado' in display_scan.columns:
                display_scan["Sentimiento"] = display_scan.apply(
                    lambda row: f"{determinar_sentimiento(row['Tipo'], row.get('Lado', 'N/A'))[1]} {determinar_sentimiento(row['Tipo'], row.get('Lado', 'N/A'))[0]}",
                    axis=1
                )
            
            # Seleccionar columnas relevantes para mostrar
            cols_mostrar = ['Sentimiento', 'Tipo', 'Strike', 'Vencimiento', 'Volumen', 'Ask', 'Bid', 'Spread_%', 
                           'Ultimo', 'Lado_F', 'IV_F', 'Moneyness', 'Prima Total', 'Liquidez']
            cols_disponibles = [c for c in cols_mostrar if c in display_scan.columns]
            
            # Ocultar OI y OI_Chg como antes pero mostrar nuevas métricas
            cols_ocultar_h = [c for c in ["OI", "OI_Chg"] if c in display_scan.columns]
            display_final = display_scan.drop(columns=cols_ocultar_h, errors="ignore")
            
            st.dataframe(
                display_final[cols_disponibles] if cols_disponibles else display_final,
                width="stretch", hide_index=True, height=400,
            )
            
            # Botón descarga datos enriquecidos
            csv_enriquecido = pd.DataFrame(datos_enriquecidos).to_csv(index=False).encode("utf-8")
            st.download_button(
                "📈 Descargar Datos Enriquecidos (CSV)",
                csv_enriquecido,
                f"opciones_enriquecidas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                key="dl_datos_enriquecidos",
                help="Incluye métricas adicionales: spread, moneyness, liquidez, ratios, etc."
            )

        # --- Clusters detectados ---
        if st.session_state.clusters_detectados:
            st.markdown("##### 🔗 Clusters de Compra Continua")
            clusters_table = []
            for c in st.session_state.clusters_detectados:
                clusters_table.append({
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
                render_pro_table(pd.DataFrame(clusters_table),
                                 title="🔗 Clusters de Compra Continua",
                                 badge_count=f"{len(clusters_table)}"),
                unsafe_allow_html=True,
            )

        # --- Rango esperado ---
        if st.session_state.rango_resultado:
            r = st.session_state.rango_resultado
            st.markdown("##### 📐 Rango Esperado Calculado")
            rango_table = pd.DataFrame({
                "Campo": [
                    "Símbolo", "Precio Actual", "Rango Inferior (1σ)", "Rango Superior (1σ)",
                    "Bajada Esperada", "Subida Esperada", "Rango Total",
                    "Call Strike", "Call Delta", "Call IV",
                    "Put Strike", "Put Delta", "Put IV",
                    "Expiración", "Días Restantes",
                ],
                "Valor": [
                    r["symbol"],
                    _fmt_precio(r['underlying_price']),
                    _fmt_precio(r['expected_range_low']),
                    _fmt_precio(r['expected_range_high']),
                    f"-{_fmt_precio(r['downside_points'])} ({r['downside_percent']:.2f}%)",
                    f"+{_fmt_precio(r['upside_points'])} (+{r['upside_percent']:.2f}%)",
                    f"{_fmt_precio(r['total_range_points'])} ({r['total_range_pct']:.2f}%)",
                    _fmt_precio(r['call_strike']),
                    f"{r['call_delta']}",
                    _fmt_iv(r['call_iv']),
                    _fmt_precio(r['put_strike']),
                    f"{r['put_delta']}",
                    _fmt_iv(r['put_iv']),
                    r["expiration"],
                    r["dias_restantes"] if r["dias_restantes"] else "N/A",
                ]
            })
            st.markdown(
                render_pro_table(rango_table, title="📐 Rango Esperado Calculado"),
                unsafe_allow_html=True,
            )

        # --- BOTÓN DE DESCARGA COMPLETA ---
        st.markdown("---")
        st.markdown("#### 📥 Descargar Reportes")
        st.caption("Genera reportes detallados con toda la información recopilada (alertas, opciones, clusters, rango). Excluye noticias y proyecciones.")

        ticker_name = ticker_symbol if ticker_symbol else "SCAN"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        fecha_legible = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        # =============================================
        # HELPERS PARA DOCX
        # =============================================
        def _estilo_celda(cell, texto, negrita=False, color_fondo=None, color_texto=None, size=9, align="left"):
            """Aplica formato a una celda de tabla Word."""
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = {
                "left": WD_ALIGN_PARAGRAPH.LEFT,
                "center": WD_ALIGN_PARAGRAPH.CENTER,
                "right": WD_ALIGN_PARAGRAPH.RIGHT,
            }.get(align, WD_ALIGN_PARAGRAPH.LEFT)
            p.space_before = Pt(1)
            p.space_after = Pt(1)
            run = p.add_run(str(texto))
            run.bold = negrita
            run.font.size = Pt(size)
            run.font.name = "Calibri"
            if color_texto:
                run.font.color.rgb = color_texto
            if color_fondo:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                shading = tcPr.makeelement(qn("w:shd"), {
                    qn("w:fill"): color_fondo,
                    qn("w:val"): "clear",
                })
                tcPr.append(shading)

        def _agregar_titulo_seccion(doc, texto, level=2):
            """Agrega un título de sección con formato."""
            heading = doc.add_heading(texto, level=level)
            for run in heading.runs:
                run.font.name = "Calibri"
                run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

        def _tabla_info(doc, datos_dict, titulo=None):
            """Tabla de 2 columnas Campo/Valor para info resumida."""
            if titulo:
                p = doc.add_paragraph()
                run = p.add_run(titulo)
                run.bold = True
                run.font.size = Pt(11)
                run.font.name = "Calibri"
            table = doc.add_table(rows=0, cols=2)
            table.style = "Light List Accent 1"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for campo, valor in datos_dict.items():
                row = table.add_row()
                _estilo_celda(row.cells[0], campo, negrita=True, size=10)
                _estilo_celda(row.cells[1], str(valor), size=10)
            doc.add_paragraph("")

        def _tabla_datos(doc, headers, rows_data, col_colors=None):
            """Tabla con encabezados y filas de datos."""
            table = doc.add_table(rows=1, cols=len(headers))
            table.style = "Light List Accent 1"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            # Encabezados
            for i, h in enumerate(headers):
                _estilo_celda(
                    table.rows[0].cells[i], h,
                    negrita=True, size=9,
                    color_fondo="1E3A5F",
                    color_texto=RGBColor(0xFF, 0xFF, 0xFF),
                    align="center",
                )
            # Datos
            for row_idx, row_data in enumerate(rows_data):
                row = table.add_row()
                bg = "F0F4F8" if row_idx % 2 == 0 else None
                for i, val in enumerate(row_data):
                    _estilo_celda(row.cells[i], str(val), size=9, color_fondo=bg)
            doc.add_paragraph("")

        # =============================================
        # FUNCIÓN: Generar DOCX completo
        # =============================================
        def _generar_docx(solo_relevante=False):
            """Genera un documento Word (.docx) profesional y detallado."""
            doc = Document()

            # --- Configurar página ---
            section = doc.sections[0]
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width = Cm(29.7)
            section.page_height = Cm(21.0)
            section.left_margin = Cm(1.5)
            section.right_margin = Cm(1.5)
            section.top_margin = Cm(1.5)
            section.bottom_margin = Cm(1.5)

            # --- Portada ---
            doc.add_paragraph("")
            titulo = doc.add_heading(
                f"REPORTE {'RELEVANTE' if solo_relevante else 'COMPLETO'} DE OPCIONES",
                level=0,
            )
            titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in titulo.runs:
                run.font.name = "Calibri"
                run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

            subtitulo = doc.add_paragraph()
            subtitulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_sub = subtitulo.add_run(f"Ticker: {ticker_name}")
            run_sub.font.size = Pt(18)
            run_sub.font.color.rgb = RGBColor(0x3B, 0x82, 0xF6)
            run_sub.font.name = "Calibri"
            run_sub.bold = True

            fecha_p = doc.add_paragraph()
            fecha_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_fecha = fecha_p.add_run(f"Generado: {fecha_legible}")
            run_fecha.font.size = Pt(11)
            run_fecha.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
            run_fecha.font.name = "Calibri"

            doc.add_paragraph("")

            # --- Resumen Ejecutivo ---
            n_alertas = len(st.session_state.alertas_actuales)
            n_opciones = len(st.session_state.datos_completos)
            n_clusters = len(st.session_state.clusters_detectados)
            tiene_rango = st.session_state.rango_resultado is not None

            principales = [a for a in st.session_state.alertas_actuales if a.get("Tipo_Alerta") == "PRINCIPAL"]
            prima_alta = [a for a in st.session_state.alertas_actuales if a.get("Tipo_Alerta") == "PRIMA_ALTA"]

            # Obtener información de contexto
            precio_subyacente = st.session_state.get('precio_subyacente', 0)
            vol_promedio = np.mean([d.get('Volumen', 0) for d in st.session_state.datos_completos]) if st.session_state.datos_completos else 0
            oi_promedio = np.mean([d.get('OI', 0) for d in st.session_state.datos_completos]) if st.session_state.datos_completos else 0
            iv_promedio = np.mean([d.get('IV', 0) for d in st.session_state.datos_completos if d.get('IV', 0) > 0]) if st.session_state.datos_completos else 0
            
            # Estadísticas de mercado
            datos_calls = [d for d in st.session_state.datos_completos if d.get('Tipo', '') == 'CALL']
            datos_puts = [d for d in st.session_state.datos_completos if d.get('Tipo', '') == 'PUT']
            
            _agregar_titulo_seccion(doc, "RESUMEN EJECUTIVO", level=1)
            _tabla_info(doc, {
                "Ticker Analizado": ticker_name,
                "Precio Subyacente": f"${precio_subyacente:,.2f}" if precio_subyacente > 0 else "N/D",
                "Fecha del Reporte": fecha_legible,
                "Total Opciones Escaneadas": f"{n_opciones:,}",
                "Calls vs Puts": f"{len(datos_calls):,} calls / {len(datos_puts):,} puts",
                "Volumen Promedio": f"{vol_promedio:,.0f}",
                "OI Promedio": f"{oi_promedio:,.0f}",
                "IV Promedio": f"{iv_promedio:.1f}%" if iv_promedio > 0 else "N/D",
            })
            
            _tabla_info(doc, {
                "Alertas Detectadas": f"{n_alertas} ({len(principales)} institucionales, {len(prima_alta)} prima alta)",
                "Clusters de Compra": f"{n_clusters}",
                "Rango Esperado": "Calculado" if tiene_rango else "No calculado",
                "Tipo de Reporte": "Solo Información Relevante" if solo_relevante else "Completo con todos los datos",
            })

            # --- ALERTAS INSTITUCIONALES ---
            if principales:
                _agregar_titulo_seccion(doc, f"ALERTAS INSTITUCIONALES ({len(principales)})", level=1)
                p_desc = doc.add_paragraph()
                run_d = p_desc.add_run(
                    "Operaciones con prima significativa que sugieren actividad institucional. "
                    "Primas que superan el umbral configurado."
                )
                run_d.font.size = Pt(10)
                run_d.font.italic = True
                run_d.font.name = "Calibri"

                headers = ["#", "Tipo", "Strike", "Vencimiento", "Volumen", "OI", "OI Chg",
                           "Ask", "Bid", "Spread %", "Último", "Sentimiento", "Lado", "Moneyness", "Prima Total", "Liquidity", "Contrato", "Hora"]
                rows = []
                # Enriquecer datos con métricas derivadas
                principales_enriq = _enriquecer_datos_opcion(principales, precio_subyacente=st.session_state.get('precio_subyacente'))
                
                for i, a in enumerate(principales_enriq, 1):
                    prima_max = a.get("Prima_Volumen", 0)
                    sent_txt, sent_emoji, _ = determinar_sentimiento(a["Tipo_Opcion"], a.get("Lado", "N/A"))
                    rows.append([
                        i, a["Tipo_Opcion"], _fmt_precio(a['Strike']), a["Vencimiento"],
                        _fmt_entero(a['Volumen']), _fmt_entero(a['OI']), _fmt_oi_chg(a.get('OI_Chg', 0)),
                        _fmt_precio(a['Ask']), _fmt_precio(a['Bid']), f"{a.get('Spread_Pct', 0):.1f}%", _fmt_precio(a['Ultimo']),
                        f"{sent_emoji} {sent_txt}", _fmt_lado(a.get('Lado', 'N/A')), a.get('Moneyness', 'N/A'), _fmt_monto(a['Prima_Volumen']),
                        f"{a.get('Liquidity_Score', 0):.0f}", a.get("Contrato", "N/A"), a.get("Fecha_Hora", ""),
                    ])
                _tabla_datos(doc, headers, rows)

            # --- ALERTAS PRIMA ALTA (solo reporte completo) ---
            if prima_alta and not solo_relevante:
                _agregar_titulo_seccion(doc, f"ALERTAS PRIMA ALTA ({len(prima_alta)})", level=1)
                p_desc = doc.add_paragraph()
                run_d = p_desc.add_run(
                    "Opciones con volumen y open interest por encima de los umbrales mínimos configurados."
                )
                run_d.font.size = Pt(10)
                run_d.font.italic = True
                run_d.font.name = "Calibri"

                headers = ["#", "Tipo", "Strike", "Vencimiento", "Volumen", "OI", "OI Chg",
                           "Ask", "Bid", "Spread %", "Último", "Sentimiento", "Lado", "Moneyness", "Prima Total", "Vol/OI"]
                rows = []
                # Enriquecer datos con métricas derivadas
                prima_alta_enriq = _enriquecer_datos_opcion(prima_alta, precio_subyacente=st.session_state.get('precio_subyacente'))
                
                for i, a in enumerate(prima_alta_enriq, 1):
                    vol_oi_ratio = a.get('Vol_OI_Ratio', 0)
                    sent_txt, sent_emoji, _ = determinar_sentimiento(a["Tipo_Opcion"], a.get("Lado", "N/A"))
                    rows.append([
                        i, a["Tipo_Opcion"], _fmt_precio(a['Strike']), a["Vencimiento"],
                        _fmt_entero(a['Volumen']), _fmt_entero(a['OI']), _fmt_oi_chg(a.get('OI_Chg', 0)),
                        _fmt_precio(a['Ask']), _fmt_precio(a['Bid']), f"{a.get('Spread_Pct', 0):.1f}%", _fmt_precio(a['Ultimo']),
                        f"{sent_emoji} {sent_txt}", _fmt_lado(a.get('Lado', 'N/A')), a.get('Moneyness', 'N/A'), _fmt_monto(a['Prima_Volumen']),
                        f"{vol_oi_ratio:.2f}",
                    ])
                _tabla_datos(doc, headers, rows)

            # --- CLUSTERS ---
            if st.session_state.clusters_detectados:
                _agregar_titulo_seccion(doc, f"CLUSTERS DE COMPRA CONTINUA ({n_clusters})", level=1)
                p_desc = doc.add_paragraph()
                run_d = p_desc.add_run(
                    "Grupos de contratos con strikes cercanos y primas similares en la misma expiración. "
                    "Patrón típico de compra institucional fragmentada."
                )
                run_d.font.size = Pt(10)
                run_d.font.italic = True
                run_d.font.name = "Calibri"

                headers_cl = ["#", "Tipo", "Vencimiento", "Contratos", "Rango Strikes",
                              "Prima Total", "Prima Prom.", "Vol Total", "OI Total", "OI Chg"]
                rows_cl = []
                for i, c in enumerate(st.session_state.clusters_detectados, 1):
                    rows_cl.append([
                        i, c["Tipo_Opcion"], c["Vencimiento"], c["Contratos"],
                        f"${c['Strike_Min']} — ${c['Strike_Max']}",
                        _fmt_monto(c['Prima_Total']), _fmt_monto(c['Prima_Promedio']),
                        _fmt_entero(c['Vol_Total']), _fmt_entero(c['OI_Total']), _fmt_oi_chg(c.get('OI_Chg_Total', 0)),
                    ])
                _tabla_datos(doc, headers_cl, rows_cl)

                # Detalle individual de cada cluster (solo completo)
                if not solo_relevante:
                    for i, c in enumerate(st.session_state.clusters_detectados, 1):
                        if c.get("Detalle"):
                            p_cl = doc.add_paragraph()
                            run_cl = p_cl.add_run(f"Detalle Cluster #{i} — {c['Tipo_Opcion']} Venc. {c['Vencimiento']}")
                            run_cl.bold = True
                            run_cl.font.size = Pt(10)
                            run_cl.font.name = "Calibri"

                            headers_det = ["#", "Strike", "Volumen", "OI", "OI Chg", "Prima Total"]
                            rows_det = []
                            for j, d in enumerate(c["Detalle"], 1):
                                rows_det.append([
                                    j, _fmt_precio(d['Strike']),
                                    _fmt_entero(d['Volumen']), _fmt_entero(d['OI']), _fmt_oi_chg(d.get('OI_Chg', 0)),
                                    _fmt_monto(d['Prima_Volumen']),
                                ])
                            _tabla_datos(doc, headers_det, rows_det)

            # --- RANGO ESPERADO ---
            if st.session_state.rango_resultado:
                r = st.session_state.rango_resultado
                _agregar_titulo_seccion(doc, "RANGO ESPERADO (1 Desviación Estándar)", level=1)

                dias = r.get('dias_restantes')
                _tabla_info(doc, {
                    "Símbolo": r["symbol"],
                    "Precio Actual": f"${r['underlying_price']:,.2f}",
                    "Expiración": r["expiration"],
                    "Días Restantes": dias if dias else "N/A",
                    "Delta Objetivo": f"±{r.get('target_delta', 'N/A')}",
                }, titulo="Parámetros")

                _tabla_info(doc, {
                    "Rango Inferior (1σ)": f"${r['expected_range_low']:,.2f}",
                    "Precio Actual": f"${r['underlying_price']:,.2f}",
                    "Rango Superior (1σ)": f"${r['expected_range_high']:,.2f}",
                    "Bajada Esperada": f"-${r['downside_points']:,.2f} (-{r['downside_percent']:.2f}%)",
                    "Subida Esperada": f"+${r['upside_points']:,.2f} (+{r['upside_percent']:.2f}%)",
                    "Rango Total": f"${r['total_range_points']:,.2f} ({r['total_range_pct']:.2f}%)",
                }, titulo="Rango de Precios")

                _tabla_info(doc, {
                    "Call Strike": f"${r['call_strike']}",
                    "Call Delta": f"{r['call_delta']}",
                    "Call IV": f"{r['call_iv']:.1f}%",
                    "Put Strike": f"${r['put_strike']}",
                    "Put Delta": f"{r['put_delta']}",
                    "Put IV": f"{r['put_iv']:.1f}%",
                }, titulo="Contratos Utilizados")

            # --- OPCIONES ESCANEADAS (solo reporte completo) ---
            if not solo_relevante and st.session_state.datos_completos:
                _agregar_titulo_seccion(doc, "OPCIONES ESCANEADAS", level=1)

                datos_sorted = sorted(
                    st.session_state.datos_completos,
                    key=lambda x: x.get("Prima_Volumen", 0), reverse=True,
                )
                limite = min(len(datos_sorted), 200)

                p_info = doc.add_paragraph()
                run_info = p_info.add_run(
                    f"Total de opciones escaneadas: {len(datos_sorted):,}. "
                    f"Mostrando: {'Todas' if len(datos_sorted) <= 200 else f'Top {limite} por Prima de Volumen'}."
                )
                run_info.font.size = Pt(10)
                run_info.font.italic = True
                run_info.font.name = "Calibri"

                headers_opt = ["Tipo", "Vencimiento", "Strike", "Volumen", "OI", "OI Chg",
                               "Ask", "Bid", "Spread %", "Último", "Lado", "IV", "Moneyness", "Dist %", "Prima Total"]
                rows_opt = []
                # Enriquecer todos los datos de opciones
                datos_enriquecidos = _enriquecer_datos_opcion(datos_sorted[:limite], precio_subyacente=st.session_state.get('precio_subyacente'))
                
                for d in datos_enriquecidos:
                    rows_opt.append([
                        d["Tipo"], d["Vencimiento"], _fmt_precio(d['Strike']),
                        _fmt_entero(d['Volumen']), _fmt_entero(d['OI']), _fmt_oi_chg(d.get('OI_Chg', 0)),
                        _fmt_precio(d['Ask']), _fmt_precio(d['Bid']), f"{d.get('Spread_Pct', 0):.1f}%", _fmt_precio(d['Ultimo']),
                        _fmt_lado(d.get('Lado', 'N/A')), _fmt_iv(d['IV']), d.get('Moneyness', 'N/A'), f"{d.get('Distance_Pct', 0):.1f}%",
                        _fmt_monto(d.get('Prima_Volumen', 0)),
                    ])
                _tabla_datos(doc, headers_opt, rows_opt)

            # --- PIE DE PÁGINA ---
            doc.add_paragraph("")
            pie = doc.add_paragraph()
            pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_pie = pie.add_run(
                f"Monitor de Opciones v2.0 — Datos de Yahoo Finance — {fecha_legible}"
            )
            run_pie.font.size = Pt(8)
            run_pie.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)
            run_pie.font.name = "Calibri"

            # Generar bytes
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer.getvalue()

        # =============================================
        # BOTONES DE DESCARGA
        # =============================================
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            docx_completo = _generar_docx(solo_relevante=False)
            st.download_button(
                "📄 Reporte Completo (DOCX)",
                docx_completo,
                f"reporte_completo_{ticker_name}_{timestamp}.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_reporte_docx",
                help="Documento Word con toda la información: alertas institucionales y prima alta, clusters con detalle, rango esperado y todas las opciones escaneadas.",
            )

        with col_dl2:
            docx_relevante = _generar_docx(solo_relevante=True)
            st.download_button(
                "⭐ Solo Lo Más Relevante (DOCX)",
                docx_relevante,
                f"reporte_relevante_{ticker_name}_{timestamp}.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_reporte_relevante",
                help="Solo lo más importante: alertas institucionales, clusters y rango esperado. Sin opciones individuales ni alertas menores.",
            )

        st.success(
            f"✅ Reportes listos — {len(st.session_state.alertas_actuales)} alertas, "
            f"{len(st.session_state.datos_completos):,} opciones, "
            f"{len(st.session_state.clusters_detectados)} clusters"
        )


# ============================================================================
#   🔍 OPTIONS SCREENER — ANÁLISIS
# ============================================================================
elif pagina == "🔍 Options Screener":
    st.markdown("### 📈 Análisis de Datos")

    if not st.session_state.datos_completos:
        st.info("Ejecuta un escaneo primero para ver los análisis.")
    else:
        df_analisis = pd.DataFrame(st.session_state.datos_completos)
        # Renombrar columna para consistencia en esta sección
        if "Prima_Volumen" in df_analisis.columns:
            df_analisis = df_analisis.rename(columns={"Prima_Volumen": "Prima_Vol"})
        
        titulo_datos = f"Datos del último escaneo — {ticker_symbol}"
        
        st.caption(f"*{titulo_datos}* — {len(df_analisis):,} registros")

        # ================================================================
        # DESGLOSE DE SENTIMIENTO POR PRIMAS
        # ================================================================
        st.markdown("### 💰 Desglose de Sentimiento por Primas")
        st.markdown("---")

        # Clasificar opciones por lado de ejecución (Bid vs Ask)
        df_sent = df_analisis.copy()
        df_sent["_mid"] = (df_sent["Ask"] + df_sent["Bid"]) / 2

        mask_call = df_sent["Tipo"] == "CALL"
        mask_put = df_sent["Tipo"] == "PUT"
        mask_ask = df_sent["Ultimo"] >= df_sent["_mid"]
        mask_bid = df_sent["Ultimo"] < df_sent["_mid"]

        # CALL Ask = compra agresiva de calls → ALCISTA
        # CALL Bid = venta agresiva de calls → BAJISTA
        # PUT Ask = compra agresiva de puts → BAJISTA
        # PUT Bid = venta agresiva de puts → ALCISTA
        call_ask_val = df_sent.loc[mask_call & mask_ask, "Prima_Vol"].sum()
        call_bid_val = df_sent.loc[mask_call & mask_bid, "Prima_Vol"].sum()
        put_ask_val = df_sent.loc[mask_put & mask_ask, "Prima_Vol"].sum()
        put_bid_val = df_sent.loc[mask_put & mask_bid, "Prima_Vol"].sum()

        total_sent = call_ask_val + call_bid_val + put_ask_val + put_bid_val

        if total_sent > 0:
            # Porcentajes con signo: + alcista, - bajista
            rows_data = [
                ("📞 CALL Ask", "Compra agresiva", call_ask_val, +(call_ask_val / total_sent * 100), True),
                ("📞 CALL Bid", "Venta agresiva", call_bid_val, -(call_bid_val / total_sent * 100), False),
                ("📋 PUT Ask", "Compra agresiva", put_ask_val, -(put_ask_val / total_sent * 100), False),
                ("📋 PUT Bid", "Venta agresiva", put_bid_val, +(put_bid_val / total_sent * 100), True),
            ]

            bullish_total = call_ask_val + put_bid_val
            bearish_total = call_bid_val + put_ask_val
            net_pct = ((bullish_total - bearish_total) / total_sent) * 100

            max_abs = max(abs(r[3]) for r in rows_data)
            if max_abs == 0:
                max_abs = 1

            # Generar HTML compacto con clases CSS para evitar truncamiento
            rows_html = ""
            for label, desc, amount, pct, is_bull in rows_data:
                cc = "g" if is_bull else "r"
                pct_str = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
                bar_w = abs(pct) / max_abs * 44

                if is_bull:
                    fill_s = f"left:50%;width:{bar_w:.1f}%;background:linear-gradient(90deg,rgba(16,185,129,.6),rgba(5,150,105,.2));border-radius:0 6px 6px 0"
                else:
                    fill_s = f"right:50%;width:{bar_w:.1f}%;background:linear-gradient(270deg,rgba(239,68,68,.6),rgba(185,28,28,.2));border-radius:6px 0 0 6px"

                rows_html += (
                    f'<div class="sr"><div class="sl"><div class="slt">{label}</div>'
                    f'<div class="sld">{desc}</div></div>'
                    f'<div class="sa {cc}">{_fmt_monto(amount)}</div>'
                    f'<div class="sb"><div class="sm"></div>'
                    f'<div class="sf" style="{fill_s}"></div></div>'
                    f'<div class="sp {cc}">{pct_str}</div></div>'
                )

            # Barra de sentimiento neto
            net_color = "#10b981" if net_pct >= 0 else "#ef4444"
            net_label = "ALCISTA" if net_pct >= 0 else "BAJISTA"
            net_emoji = "🟢" if net_pct >= 0 else "🔴"
            net_pct_str = f"+{net_pct:.1f}%" if net_pct >= 0 else f"{net_pct:.1f}%"
            bull_pct = bullish_total / total_sent * 100
            bear_pct = bearish_total / total_sent * 100
            net_bar_w = max(abs(bull_pct - bear_pct) / 100 * 44, 8)
            nc = "g" if net_pct >= 0 else "r"

            if net_pct >= 0:
                net_fill = f"left:50%;width:{net_bar_w:.1f}%;background:linear-gradient(90deg,rgba(16,185,129,.8),rgba(5,150,105,.3));border-radius:0 6px 6px 0"
            else:
                net_fill = f"right:50%;width:{net_bar_w:.1f}%;background:linear-gradient(270deg,rgba(239,68,68,.8),rgba(185,28,28,.3));border-radius:6px 0 0 6px"

            # --- OKA Sentiment Gauge (Plotly) ---
            gauge_score = max(0, min(100, 50 + net_pct / 2))  # Normalizar a 0-100
            if net_pct >= 10:
                gauge_lbl = "ALCISTA"
            elif net_pct <= -10:
                gauge_lbl = "BAJISTA"
            else:
                gauge_lbl = "NEUTRAL"

            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=gauge_score,
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": f"OKA Sentiment Index — {gauge_lbl}", "font": {"size": 16, "color": "white"}},
                number={"font": {"size": 42, "color": "white"}, "suffix": "/100"},
                delta={"reference": 50, "increasing": {"color": "#00ff88"}, "decreasing": {"color": "#ef4444"}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#475569", "tickfont": {"color": "#94a3b8", "size": 11}},
                    "bar": {"color": "#00ff88", "thickness": 0.3},
                    "bgcolor": "#0f172a",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 30], "color": "rgba(239, 68, 68, 0.25)"},
                        {"range": [30, 50], "color": "rgba(245, 158, 11, 0.15)"},
                        {"range": [50, 70], "color": "rgba(16, 185, 129, 0.15)"},
                        {"range": [70, 100], "color": "rgba(0, 255, 136, 0.2)"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 3},
                        "thickness": 0.8,
                        "value": gauge_score,
                    },
                },
            ))
            fig_gauge.update_layout(
                paper_bgcolor="#1e293b",
                plot_bgcolor="#1e293b",
                font={"color": "white", "family": "Inter, sans-serif"},
                height=400,
                margin=dict(l=30, r=30, t=60, b=10),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

            # Bullish / Bearish / Neutral label debajo del gauge
            _gauge_color = "#00ff88" if gauge_lbl == "ALCISTA" else "#ef4444" if gauge_lbl == "BAJISTA" else "#f59e0b"
            st.markdown(
                f'<h3 style="text-align:center;color:{_gauge_color};margin:-10px 0 8px;font-weight:800;">{gauge_lbl}</h3>',
                unsafe_allow_html=True,
            )

            # Footer stats below gauge
            st.markdown(
                f'<div style="display:flex;justify-content:space-around;padding:8px 0 12px;'
                f'background:#1e293b;border-radius:0 0 12px 12px;margin-top:-10px;">'
                f'<div style="text-align:center"><div style="color:#94a3b8;font-size:.75rem">Bullish</div>'
                f'<div style="color:#10b981;font-weight:700">{bull_pct:.1f}%</div></div>'
                f'<div style="text-align:center"><div style="color:#94a3b8;font-size:.75rem">Score</div>'
                f'<div style="color:white;font-weight:700">{gauge_score:.0f}/100</div></div>'
                f'<div style="text-align:center"><div style="color:#94a3b8;font-size:.75rem">Bearish</div>'
                f'<div style="color:#ef4444;font-weight:700">{bear_pct:.1f}%</div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="sp0">'
                f'<div class="tt">💰 Desglose de Sentimiento por Primas</div>'
                f'<div class="ts">Prima ejecutada por lado del order book — Compras vs Ventas agresivas</div>'
                f'{rows_html}'
                f'<div class="sn"><div class="snr">'
                f'<div class="snl"><div class="snt">{net_emoji} NETO</div><div class="snd {nc}">{net_label}</div></div>'
                f'<div class="sa {nc}">{_fmt_monto(abs(bullish_total - bearish_total))}</div>'
                f'<div class="sb"><div class="sm"></div><div class="sf" style="{net_fill}"></div></div>'
                f'<div class="sp {nc}">{net_pct_str}</div>'
                f'</div></div>'
                f'<div class="ssum">'
                f'<div class="ssi"><div class="ssh">🟢 Alcista</div><div class="ssv g">{_fmt_monto(bullish_total)}</div><div class="ssp g">{bull_pct:.1f}%</div></div>'
                f'<div class="ssi"><div class="ssh">📊 Total</div><div class="ssv w">{_fmt_monto(total_sent)}</div><div class="ssp gy">100%</div></div>'
                f'<div class="ssi"><div class="ssh">🔴 Bajista</div><div class="ssv r">{_fmt_monto(bearish_total)}</div><div class="ssp r">{bear_pct:.1f}%</div></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Sin datos suficientes para calcular el sentimiento por primas.")

        st.markdown("---")

        # ================================================================
        # SOPORTES Y RESISTENCIAS POR VOLUMEN DE OPCIONES
        # ================================================================
        st.markdown("### 🛡️ Soportes y Resistencias por Opciones")
        st.markdown(
            """
            <div style="background: rgba(59, 130, 246, 0.06); border: 1px solid rgba(59, 130, 246, 0.15); 
                 border-radius: 12px; padding: 12px 18px; margin-bottom: 14px; font-size: 0.82rem; color: #93c5fd;">
                📊 <b>¿Cómo se determinan?</b> Los strikes con mayor volumen en <b>CALLs</b> actúan como 
                <b style="color:#ef4444">resistencias</b> (techos) y los strikes con mayor volumen en <b>PUTs</b> 
                actúan como <b style="color:#10b981">soportes</b> (pisos). Donde se concentra el volumen, 
                hay mayor interés institucional y es probable que el precio reaccione.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Obtener precio actual
        precio_actual = st.session_state.get('precio_subyacente', None)

        # Separar CALLs y PUTs con volumen > 0
        df_calls_sr = df_analisis[(df_analisis["Tipo"] == "CALL") & (df_analisis["Volumen"] > 0)].copy()
        df_puts_sr = df_analisis[(df_analisis["Tipo"] == "PUT") & (df_analisis["Volumen"] > 0)].copy()

        if not df_calls_sr.empty and not df_puts_sr.empty:
            # Top 5 strikes con más volumen en CALLs → Resistencias
            top_calls = df_calls_sr.groupby("Strike").agg(
                Vol_Total=("Volumen", "sum"),
                OI_Total=("OI", "sum"),
                Prima_Total=("Prima_Vol", "sum"),
                Contratos=("Volumen", "count"),
            ).sort_values("Vol_Total", ascending=False).head(5).reset_index()

            # Top 5 strikes con más volumen en PUTs → Soportes
            top_puts = df_puts_sr.groupby("Strike").agg(
                Vol_Total=("Volumen", "sum"),
                OI_Total=("OI", "sum"),
                Prima_Total=("Prima_Vol", "sum"),
                Contratos=("Volumen", "count"),
            ).sort_values("Vol_Total", ascending=False).head(5).reset_index()

            col_sr1, col_sr2 = st.columns(2)

            with col_sr1:
                st.markdown("#### 🔴 Resistencias (CALLs más tradeados)")
                for idx_r, row_r in top_calls.iterrows():
                    pct_dist = ""
                    if precio_actual and precio_actual > 0:
                        dist = ((row_r["Strike"] - precio_actual) / precio_actual) * 100
                        pct_dist = f" ({'+' if dist >= 0 else ''}{dist:.1f}%)"
                    st.markdown(
                        f"""
                        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); 
                             border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <span style="font-size: 1.1rem; font-weight: 700; color: #ef4444;">
                                        R{idx_r + 1}: ${row_r['Strike']:,.1f}
                                    </span>
                                    <span style="font-size: 0.8rem; color: #94a3b8;">{pct_dist}</span>
                                </div>
                                <div style="text-align: right;">
                                    <span style="font-size: 0.82rem; color: #f1f5f9;">
                                        Vol: <b>{row_r['Vol_Total']:,.0f}</b>
                                    </span>
                                </div>
                            </div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">
                                OI: {row_r['OI_Total']:,.0f} | Prima: {_fmt_monto(row_r['Prima_Total'])} | {int(row_r['Contratos'])} contratos
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with col_sr2:
                st.markdown("#### 🟢 Soportes (PUTs más tradeados)")
                for idx_s, row_s in top_puts.iterrows():
                    pct_dist = ""
                    if precio_actual and precio_actual > 0:
                        dist = ((row_s["Strike"] - precio_actual) / precio_actual) * 100
                        pct_dist = f" ({'+' if dist >= 0 else ''}{dist:.1f}%)"
                    st.markdown(
                        f"""
                        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); 
                             border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <span style="font-size: 1.1rem; font-weight: 700; color: #10b981;">
                                        S{idx_s + 1}: ${row_s['Strike']:,.1f}
                                    </span>
                                    <span style="font-size: 0.8rem; color: #94a3b8;">{pct_dist}</span>
                                </div>
                                <div style="text-align: right;">
                                    <span style="font-size: 0.82rem; color: #f1f5f9;">
                                        Vol: <b>{row_s['Vol_Total']:,.0f}</b>
                                    </span>
                                </div>
                            </div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">
                                OI: {row_s['OI_Total']:,.0f} | Prima: {_fmt_monto(row_s['Prima_Total'])} | {int(row_s['Contratos'])} contratos
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # Barra visual de niveles
            if precio_actual and precio_actual > 0:
                st.markdown("---")
                st.markdown("#### 📍 Mapa de Niveles vs Precio Actual")

                # Combinar todos los niveles
                niveles_r = [(s, "R", v) for s, v in zip(top_calls["Strike"], top_calls["Vol_Total"])]
                niveles_s = [(s, "S", v) for s, v in zip(top_puts["Strike"], top_puts["Vol_Total"])]
                todos_niveles = sorted(niveles_r + niveles_s, key=lambda x: x[0])

                max_vol_nivel = max(n[2] for n in todos_niveles) if todos_niveles else 1
                all_strikes = [n[0] for n in todos_niveles] + [precio_actual]
                rango_min = min(all_strikes) * 0.998
                rango_max = max(all_strikes) * 1.002
                rango_total = rango_max - rango_min if rango_max > rango_min else 1

                mapa_html = '<div style="position:relative; height:60px; background:#0f172a; border-radius:10px; margin:10px 0 20px 0; border:1px solid #1e293b;">'

                # Líneas de niveles
                for strike_n, tipo_n, vol_n in todos_niveles:
                    pos_pct = ((strike_n - rango_min) / rango_total) * 100
                    pos_pct = max(2, min(98, pos_pct))
                    color = "#ef4444" if tipo_n == "R" else "#10b981"
                    opacity = 0.4 + 0.6 * (vol_n / max_vol_nivel)
                    label = tipo_n
                    mapa_html += (
                        f'<div style="position:absolute; left:{pos_pct:.1f}%; top:0; bottom:0; '
                        f'width:2px; background:{color}; opacity:{opacity:.2f};"></div>'
                        f'<div style="position:absolute; left:{pos_pct:.1f}%; top:2px; transform:translateX(-50%); '
                        f'font-size:0.65rem; font-weight:700; color:{color};">{label} ${strike_n:,.0f}</div>'
                        f'<div style="position:absolute; left:{pos_pct:.1f}%; bottom:2px; transform:translateX(-50%); '
                        f'font-size:0.6rem; color:#64748b;">{vol_n:,.0f}</div>'
                    )

                # Línea del precio actual
                pos_precio = ((precio_actual - rango_min) / rango_total) * 100
                pos_precio = max(2, min(98, pos_precio))
                mapa_html += (
                    f'<div style="position:absolute; left:{pos_precio:.1f}%; top:0; bottom:0; '
                    f'width:3px; background:#f59e0b; z-index:5;"></div>'
                    f'<div style="position:absolute; left:{pos_precio:.1f}%; top:50%; transform:translate(-50%,-50%); '
                    f'background:#f59e0b; color:#000; font-size:0.7rem; font-weight:800; padding:2px 6px; '
                    f'border-radius:4px; z-index:6; white-space:nowrap;">📍 ${precio_actual:,.2f}</div>'
                )

                mapa_html += '</div>'
                st.markdown(mapa_html, unsafe_allow_html=True)

                # Resumen de niveles cercanos
                resistencias_arriba = sorted([n for n in niveles_r if n[0] > precio_actual], key=lambda x: x[0])
                soportes_abajo = sorted([n for n in niveles_s if n[0] < precio_actual], key=lambda x: x[0], reverse=True)

                col_near1, col_near2 = st.columns(2)
                with col_near1:
                    if resistencias_arriba:
                        r_cercana = resistencias_arriba[0]
                        dist_r = ((r_cercana[0] - precio_actual) / precio_actual) * 100
                        st.metric("🔴 Resistencia más cercana", f"${r_cercana[0]:,.1f}", 
                                 delta=f"+{dist_r:.2f}% arriba", delta_color="inverse")
                    else:
                        st.info("Sin resistencias por encima del precio actual")
                with col_near2:
                    if soportes_abajo:
                        s_cercano = soportes_abajo[0]
                        dist_s = ((s_cercano[0] - precio_actual) / precio_actual) * 100
                        st.metric("🟢 Soporte más cercano", f"${s_cercano[0]:,.1f}", 
                                 delta=f"{dist_s:.2f}% abajo", delta_color="normal")
                    else:
                        st.info("Sin soportes por debajo del precio actual")
        else:
            st.info("No hay suficientes datos de CALLs y PUTs para calcular soportes y resistencias.")

        st.markdown("---")

        col_a1, col_a2 = st.columns(2)

        with col_a1:
            st.markdown("#### 📊 Distribución CALL vs PUT")
            tipo_counts = df_analisis["Tipo"].value_counts()
            st.bar_chart(tipo_counts)

            n_calls = tipo_counts.get("CALL", 0)
            n_puts = tipo_counts.get("PUT", 0)
            ratio_pc = n_puts / n_calls if n_calls > 0 else 0
            st.metric("Put/Call Ratio", f"{ratio_pc:.3f}")
            if ratio_pc > 1:
                st.warning("⚠️ Ratio > 1: Mayor actividad en PUTs (sentimiento bajista)")
            elif ratio_pc < 0.7:
                st.success("📈 Ratio < 0.7: Mayor actividad en CALLs (sentimiento alcista)")
            else:
                st.info("↔️ Ratio neutral")

        with col_a2:
            st.markdown("#### 📅 Volumen por Vencimiento")
            vol_by_date = (
                df_analisis.groupby("Vencimiento")["Volumen"]
                .sum()
                .sort_index()
            )
            st.bar_chart(vol_by_date)

        st.markdown("#### 🎯 Top 20 Strikes por Volumen")
        vol_cols = ["Vencimiento", "Tipo", "Strike", "Volumen", "IV", "Ultimo", "Prima_Vol", "Lado"]
        top_vol = (
            df_analisis.nlargest(20, "Volumen")[[c for c in vol_cols if c in df_analisis.columns]]
            .reset_index(drop=True)
        )
        top_vol_display = top_vol.copy()
        top_vol_display = top_vol_display.rename(columns={"Prima_Vol": "Prima Total"})
        if "Tipo" in top_vol_display.columns and "Lado" in top_vol_display.columns:
            top_vol_display.insert(0, "Sentimiento", top_vol_display.apply(
                lambda row: _sentiment_badge(row["Tipo"], row.get("Lado", "N/A")), axis=1
            ))
        if "Tipo" in top_vol_display.columns:
            top_vol_display["Tipo"] = top_vol_display["Tipo"].apply(_type_badge)
        top_vol_display["Prima Total"] = top_vol_display["Prima Total"].apply(_fmt_dolar)
        if "Lado" in top_vol_display.columns:
            top_vol_display["Lado"] = top_vol_display["Lado"].apply(_fmt_lado)
        st.markdown(
            render_pro_table(top_vol_display, title="🎯 Top 20 por Volumen", badge_count="20"),
            unsafe_allow_html=True,
        )

        st.markdown("#### 🏛️ Top 20 Strikes por Open Interest")
        oi_cols = ["Vencimiento", "Tipo", "Strike", "Volumen", "IV", "Ultimo", "Prima_Vol", "Lado"]
        top_oi = (
            df_analisis.nlargest(20, "OI")[[c for c in oi_cols if c in df_analisis.columns]]
            .reset_index(drop=True)
        )
        top_oi_display = top_oi.copy()
        top_oi_display = top_oi_display.rename(columns={"Prima_Vol": "Prima Total"})
        if "Tipo" in top_oi_display.columns and "Lado" in top_oi_display.columns:
            top_oi_display.insert(0, "Sentimiento", top_oi_display.apply(
                lambda row: _sentiment_badge(row["Tipo"], row.get("Lado", "N/A")), axis=1
            ))
        if "Tipo" in top_oi_display.columns:
            top_oi_display["Tipo"] = top_oi_display["Tipo"].apply(_type_badge)
        top_oi_display["Prima Total"] = top_oi_display["Prima Total"].apply(_fmt_dolar)
        if "Lado" in top_oi_display.columns:
            top_oi_display["Lado"] = top_oi_display["Lado"].apply(_fmt_lado)
        st.markdown(
            render_pro_table(top_oi_display, title="🏛️ Top 20 por Open Interest", badge_count="20"),
            unsafe_allow_html=True,
        )

        col_iv1, col_iv2 = st.columns(2)
        with col_iv1:
            st.markdown("#### 📉 Volatilidad Implícita por Strike (CALLs)")
            calls_iv = df_analisis[
                (df_analisis["Tipo"] == "CALL") & (df_analisis["IV"] > 0)
            ].sort_values("Strike")
            if not calls_iv.empty:
                chart_data_calls = calls_iv[["Strike", "IV"]].set_index("Strike")
                st.line_chart(chart_data_calls)
        with col_iv2:
            st.markdown("#### 📉 Volatilidad Implícita por Strike (PUTs)")
            puts_iv = df_analisis[
                (df_analisis["Tipo"] == "PUT") & (df_analisis["IV"] > 0)
            ].sort_values("Strike")
            if not puts_iv.empty:
                chart_data_puts = puts_iv[["Strike", "IV"]].set_index("Strike")
                st.line_chart(chart_data_puts)

        # Desglose por vencimiento
        df_calls_s = df_analisis[df_analisis["Tipo"] == "CALL"]
        df_puts_s = df_analisis[df_analisis["Tipo"] == "PUT"]
        col_pv1, col_pv2 = st.columns(2)

        with col_pv1:
            st.markdown("#### 📞 Prima Total en CALLs por Vencimiento")
            if not df_calls_s.empty:
                prima_calls_venc = df_calls_s.groupby("Vencimiento").agg(
                    Prima_Total=("Prima_Vol", "sum"),
                    Contratos=("Volumen", "count"),
                    Volumen_Total=("Volumen", "sum"),
                ).sort_values("Prima_Total", ascending=False).reset_index()

                display_pc = prima_calls_venc.copy()
                display_pc["Prima_Total"] = display_pc["Prima_Total"].apply(_fmt_dolar)
                display_pc["Volumen_Total"] = display_pc["Volumen_Total"].apply(_fmt_entero)
                st.markdown(
                    render_pro_table(display_pc, title="📞 CALLs por Vencimiento"),
                    unsafe_allow_html=True,
                )
            else:
                st.info("Sin datos de CALLs.")

        with col_pv2:
            st.markdown("#### 📋 Prima Total en PUTs por Vencimiento")
            if not df_puts_s.empty:
                prima_puts_venc = df_puts_s.groupby("Vencimiento").agg(
                    Prima_Total=("Prima_Vol", "sum"),
                    Contratos=("Volumen", "count"),
                    Volumen_Total=("Volumen", "sum"),
                ).sort_values("Prima_Total", ascending=False).reset_index()

                display_pp = prima_puts_venc.copy()
                display_pp["Prima_Total"] = display_pp["Prima_Total"].apply(_fmt_dolar)
                display_pp["Volumen_Total"] = display_pp["Volumen_Total"].apply(_fmt_entero)
                st.markdown(
                    render_pro_table(display_pp, title="📋 PUTs por Vencimiento"),
                    unsafe_allow_html=True,
                )
            else:
                st.info("Sin datos de PUTs.")

        # Top strikes donde se concentra el dinero
        st.markdown("#### 🎯 Top 15 Strikes con Mayor Prima Total Ejecutada")
        df_prima_strike = df_analisis.copy()
        prima_cols = ["Tipo", "Strike", "Vencimiento", "Volumen", "Prima_Vol", "IV", "Ultimo", "Lado"]
        top_prima = df_prima_strike.nlargest(15, "Prima_Vol")[
            [c for c in prima_cols if c in df_prima_strike.columns]
        ].reset_index(drop=True)

        top_prima_display = top_prima.copy()
        top_prima_display = top_prima_display.rename(columns={"Prima_Vol": "Prima Total"})
        if "Tipo" in top_prima_display.columns and "Lado" in top_prima_display.columns:
            top_prima_display.insert(0, "Sentimiento", top_prima_display.apply(
                lambda row: _sentiment_badge(row["Tipo"], row.get("Lado", "N/A")), axis=1
            ))
        if "Tipo" in top_prima_display.columns:
            top_prima_display["Tipo"] = top_prima_display["Tipo"].apply(_type_badge)
        top_prima_display["Prima Total"] = top_prima_display["Prima Total"].apply(_fmt_dolar)
        top_prima_display["Volumen"] = top_prima_display["Volumen"].apply(_fmt_entero)
        top_prima_display["IV"] = top_prima_display["IV"].apply(_fmt_iv)
        top_prima_display["Ultimo"] = top_prima_display["Ultimo"].apply(_fmt_precio)
        top_prima_display["Strike"] = top_prima_display["Strike"].apply(lambda x: f"${x:,.1f}")
        if "Lado" in top_prima_display.columns:
            top_prima_display["Lado"] = top_prima_display["Lado"].apply(_fmt_lado)

        st.markdown(
            render_pro_table(top_prima_display, title="🎯 Top 15 Mayor Prima Ejecutada", badge_count="15"),
            unsafe_allow_html=True,
        )

        # Gráfica de prima por strike
        st.markdown("#### 📊 Flujo de Prima por Strike (CALL vs PUT)")
        pivot_prima = df_analisis.pivot_table(
            index="Strike", columns="Tipo",
            values="Prima_Vol", aggfunc="sum", fill_value=0,
        )
        pivot_prima = pivot_prima[pivot_prima.sum(axis=1) > 0]
        if not pivot_prima.empty:
            pivot_prima = pivot_prima.nlargest(30, pivot_prima.columns.tolist()[0] if len(pivot_prima.columns) > 0 else pivot_prima.index).sort_index()
            st.bar_chart(pivot_prima)
        st.caption("Prima por Volumen distribuida por strike — muestra dónde se concentran las apuestas más grandes")


# ============================================================================
#   🔔 SMART ALERTS — FAVORITOS + RANGO
# ============================================================================
elif pagina == "🔔 Smart Alerts":
    st.markdown("### ⭐ Contratos Favoritos")
    st.markdown(
        """
        <div style="background: rgba(250, 204, 21, 0.06); border: 1px solid rgba(250, 204, 21, 0.15); 
             border-radius: 12px; padding: 12px 18px; margin-bottom: 14px; font-size: 0.82rem; color: #fde68a;">
            📌 <b>Contratos guardados para seguimiento.</b> Marcá cualquier contrato como favorito desde las alertas del Escáner. 
            Se guardan entre sesiones y se eliminan automáticamente cuando expiran.
        </div>
        """,
        unsafe_allow_html=True,
    )

    favoritos = st.session_state.get("favoritos", [])

    if not favoritos:
        st.info("No hay contratos en favoritos. Ejecutá un escaneo y usá el botón ☆ **Guardar en Favoritos** en cualquier alerta.")
    else:
        # Métricas rápidas
        n_calls_fav = sum(1 for f in favoritos if f.get("Tipo_Opcion") == "CALL")
        n_puts_fav = sum(1 for f in favoritos if f.get("Tipo_Opcion") == "PUT")
        prima_total_fav = sum(f.get("Prima_Volumen", 0) for f in favoritos)
        st.markdown(render_metric_row([
            render_metric_card("Total Favoritos", f"{len(favoritos)}"),
            render_metric_card("Calls", f"{n_calls_fav}"),
            render_metric_card("Puts", f"{n_puts_fav}"),
            render_metric_card("Prima Total", _fmt_monto(prima_total_fav)),
        ]), unsafe_allow_html=True)

        # Tabla resumen
        fav_df = pd.DataFrame(favoritos)
        cols_tabla_fav = ["Contrato", "Ticker", "Tipo_Opcion", "Strike", "Vencimiento", 
                          "Volumen", "OI", "Ask", "Bid", "Ultimo", "Lado", "Prima_Volumen"]
        cols_disp_fav = [c for c in cols_tabla_fav if c in fav_df.columns]
        display_fav_df = fav_df[cols_disp_fav].copy()
        if "Tipo_Opcion" in display_fav_df.columns and "Lado" in display_fav_df.columns:
            display_fav_df.insert(0, "Sentimiento", display_fav_df.apply(
                lambda row: _sentiment_badge(row["Tipo_Opcion"], row.get("Lado", "N/A")), axis=1
            ))
        if "Tipo_Opcion" in display_fav_df.columns:
            display_fav_df["Tipo_Opcion"] = display_fav_df["Tipo_Opcion"].apply(_type_badge)
        if "Lado" in display_fav_df.columns:
            display_fav_df["Lado"] = display_fav_df["Lado"].apply(_fmt_lado)
        if "Prima_Volumen" in display_fav_df.columns:
            display_fav_df = display_fav_df.rename(columns={"Prima_Volumen": "Prima Total"})
            display_fav_df["Prima Total"] = display_fav_df["Prima Total"].apply(_fmt_monto)
        st.markdown(
            render_pro_table(display_fav_df, title="⭐ Favoritos", badge_count=f"{len(favoritos)}"),
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Detalle individual de cada favorito
        st.markdown("#### 🔍 Detalle de Contratos")
        for idx_fav, fav in enumerate(favoritos):
            fav_sym = fav.get("Contrato", "N/A")
            fav_tipo = fav.get("Tipo_Opcion", "N/A")
            fav_strike = fav.get("Strike", 0)
            fav_venc = fav.get("Vencimiento", "N/A")
            fav_prima = fav.get("Prima_Volumen", 0)

            # Calcular días para vencimiento
            try:
                dias_venc = (datetime.strptime(fav_venc, "%Y-%m-%d") - datetime.now()).days
                dias_str = f"{dias_venc}d" if dias_venc >= 0 else "EXPIRADO"
            except Exception:
                dias_str = "N/A"

            fav_label = (
                f"⭐ {fav_tipo} ${fav_strike} | Venc: {fav_venc} ({dias_str}) | "
                f"Prima: ${fav_prima:,.0f} | {fav_sym}"
            )

            with st.expander(fav_label, expanded=False):
                col_fav_info, col_fav_chart = st.columns([1, 2])

                with col_fav_info:
                    st.markdown("**📄 Información del Contrato**")
                    st.markdown(f"- **Símbolo:** `{fav_sym}`")
                    st.markdown(f"- **Ticker:** {fav.get('Ticker', 'N/A')}")
                    st.markdown(f"- **Tipo:** {fav_tipo}")
                    st.markdown(f"- **Strike:** ${fav_strike}")
                    st.markdown(f"- **Vencimiento:** {fav_venc} ({dias_str})")
                    st.markdown(f"- **Volumen:** {fav.get('Volumen', 0):,}")
                    st.markdown(f"- **OI:** {fav.get('OI', 0):,}")
                    oi_chg_val = fav.get('OI_Chg', 0)
                    st.markdown(f"- **OI Chg:** {_fmt_oi_chg(oi_chg_val)}")
                    st.markdown(f"- **Ask:** ${fav.get('Ask', 0)}")
                    st.markdown(f"- **Bid:** ${fav.get('Bid', 0)}")
                    st.markdown(f"- **Último:** ${fav.get('Ultimo', 0)}")
                    st.markdown(f"- **Lado:** {_fmt_lado(fav.get('Lado', 'N/A'))}")
                    iv_fav = fav.get('IV', 0)
                    st.markdown(f"- **IV:** {iv_fav:.1f}%" if iv_fav > 0 else "- **IV:** N/A")
                    st.markdown(f"- **Prima Total:** {_fmt_monto(fav.get('Prima_Volumen', 0))}")
                    st.markdown(f"- **Tipo Alerta:** {fav.get('Tipo_Alerta', 'N/A')}")
                    st.markdown(f"- **Guardado:** {fav.get('Guardado_En', 'N/A')}")

                    # Botón eliminar
                    if st.button(f"🗑️ Eliminar de Favoritos", key=f"del_fav_{idx_fav}_{fav_sym}", use_container_width=True):
                        _eliminar_favorito(fav_sym)
                        st.success(f"🗑️ {fav_sym} eliminado de Favoritos")
                        st.rerun()

                with col_fav_chart:
                    if fav_sym and fav_sym != "N/A":
                        with st.spinner("Cargando gráfica del contrato..."):
                            hist_fav, err_fav = obtener_historial_contrato(fav_sym)

                        if err_fav:
                            st.warning(f"⚠️ Error al cargar historial: {err_fav}")
                        elif hist_fav.empty:
                            st.info("ℹ️ No hay datos históricos disponibles.")
                        else:
                            st.markdown(f"**Precio del contrato** — `{fav_sym}`")
                            chart_fav_price = hist_fav[["Close"]].copy()
                            chart_fav_price.columns = ["Precio"]
                            st.line_chart(chart_fav_price, height=280)

                            if "Volume" in hist_fav.columns:
                                chart_fav_vol = hist_fav[["Volume"]].copy()
                                chart_fav_vol.columns = ["Volumen"]
                                st.bar_chart(chart_fav_vol, height=160)

        # Botón limpiar todos
        st.markdown("---")
        col_limpiar, _ = st.columns([1, 3])
        with col_limpiar:
            if st.button("🗑️ Limpiar todos los favoritos", use_container_width=True, type="secondary"):
                st.session_state.favoritos = []
                _guardar_favoritos([])
                st.success("Se eliminaron todos los favoritos")
                st.rerun()


    # ============================================================================
    #   RANGO ESPERADO (1σ) — Sub-sección de Smart Alerts
    # ============================================================================
    st.markdown("---")
    st.markdown("### 📐 Rango Esperado de Movimiento (1σ)")
    st.markdown(
        """
        <div class="rango-info">
            📊 <b>¿Qué es esto?</b> Usando opciones reales del mercado y el modelo <b>Black-Scholes</b>
            para calcular delta (≈ 0.16), determina el rango de precio donde la acción tiene ~68%
            de probabilidad de permanecer hasta la fecha de expiración (<b>1 desviación estándar</b>).<br>
            🆓 <b>100% gratuito</b> — Datos de Yahoo Finance + cálculo matemático de greeks.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    fechas_exp_disponibles = []
    try:
        session_rango, _ = crear_sesion_nueva()
        ticker_rango = yf.Ticker(ticker_symbol, session=session_rango)
        fechas_exp_disponibles = list(ticker_rango.options)
    except Exception as e:
        logger.warning("Error obteniendo fechas de expiración para rango: %s", e)

    col_r1, col_r2, col_r3 = st.columns([2, 2, 1])
    with col_r1:
        rango_symbol = st.text_input(
            "Símbolo", value=ticker_symbol, max_chars=10,
            key="rango_symbol", help="Ticker de la acción (ej: SPY, META, AAPL)"
        ).upper()
    with col_r2:
        if fechas_exp_disponibles:
            rango_exp_date = st.selectbox(
                "Fecha de Expiración",
                fechas_exp_disponibles,
                key="rango_exp",
                help="Fechas de expiración disponibles para este ticker",
            )
        else:
            rango_exp_date = st.text_input(
                "Fecha de Expiración (YYYY-MM-DD)",
                value=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                key="rango_exp",
                help="Fecha de expiración de las opciones a analizar",
            )
    with col_r3:
        st.markdown("<br>", unsafe_allow_html=True)
        calc_btn = st.button("📐 Calcular Rango", type="primary", use_container_width=True)

    if calc_btn:
        with st.spinner(f"Calculando rango esperado para {rango_symbol} al {rango_exp_date}..."):
            resultado, error = calcular_rango_esperado(
                rango_symbol, rango_exp_date,
                target_delta=rango_delta,
            )
        st.session_state.rango_resultado = resultado
        st.session_state.rango_error = error

    if st.session_state.rango_error:
        st.error(f"❌ {st.session_state.rango_error}")

    if st.session_state.rango_resultado:
        r = st.session_state.rango_resultado

        total_range = r["downside_points"] + r["upside_points"]
        if total_range > 0:
            down_pct_bar = (r["downside_points"] / total_range) * 100
            up_pct_bar = (r["upside_points"] / total_range) * 100
        else:
            down_pct_bar = 50
            up_pct_bar = 50

        full_range = r["expected_range_high"] - r["expected_range_low"]
        if full_range > 0:
            precio_pos = ((r["underlying_price"] - r["expected_range_low"]) / full_range) * 100
        else:
            precio_pos = 50

        dias_str = f" ({r['dias_restantes']} días)" if r['dias_restantes'] is not None else ""

        st.markdown(f"#### 📐 {r['symbol']} — Rango Esperado 1σ")
        st.caption(f"Expiración: {r['expiration']}{dias_str} · Delta objetivo: ±{r['target_delta']}")

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            st.metric("💵 Precio Actual", f"${r['underlying_price']:,.2f}")
        with col_r2:
            st.metric("📈 Subida Esperada", f"+${r['upside_points']:,.2f}", f"+{r['upside_percent']:.2f}%")
        with col_r3:
            st.metric("📉 Bajada Esperada", f"-${r['downside_points']:,.2f}", f"-{r['downside_percent']:.2f}%", delta_color="inverse")
        with col_r4:
            st.metric("↔️ Rango Total", f"${r['total_range_points']:,.2f}", f"{r['total_range_pct']:.2f}%", delta_color="off")

        st.markdown("")
        bar_col1, bar_col2, bar_col3 = st.columns([1, 6, 1])
        with bar_col1:
            st.markdown(f"**▼ ${r['expected_range_low']:,.2f}**")
        with bar_col2:
            progress_val = max(0.0, min(1.0, precio_pos / 100.0))
            st.progress(progress_val, text=f"● Precio actual: ${r['underlying_price']:,.2f}  —  Rango: ${r['expected_range_low']:,.2f} a ${r['expected_range_high']:,.2f}")
        with bar_col3:
            st.markdown(f"**▲ ${r['expected_range_high']:,.2f}**")

        st.divider()

        st.markdown("#### 🎯 Contratos Usados para el Cálculo")
        col_d1, col_d2 = st.columns(2)

        with col_d1:
            st.success(f"""
**📈 CALL (límite superior)**
- Strike: **${r['call_strike']}**
- Delta: **{r['call_delta']}**
- IV: **{r['call_iv']:.1f}%**
- _Precio debe superar ${r['call_strike']} para salir del rango_
""")

        with col_d2:
            st.error(f"""
**📉 PUT (límite inferior)**
- Strike: **${r['put_strike']}**
- Delta: **{r['put_delta']}**
- IV: **{r['put_iv']:.1f}%**
- _Precio debe caer bajo ${r['put_strike']} para salir del rango_
""")

        with st.expander("📋 Ver datos completos del cálculo"):
            resumen_data = {
                "Campo": [
                    "Símbolo", "Precio Actual", "Expiración", "Días Restantes",
                    "Delta Objetivo", "Subida Esperada (pts)", "Subida Esperada (%)",
                    "Bajada Esperada (pts)", "Bajada Esperada (%)", "Rango Inferior",
                    "Rango Superior", "Rango Total (pts)", "Rango Total (%)",
                    "Call Strike", "Call Delta", "Call IV",
                    "Put Strike", "Put Delta", "Put IV",
                    "Calls Analizadas", "Puts Analizadas",
                ],
                "Valor": [
                    r["symbol"], f"${r['underlying_price']:,.2f}", r["expiration"],
                    r["dias_restantes"] if r["dias_restantes"] else "N/A",
                    f"±{r['target_delta']}",
                    f"+${r['upside_points']:,.2f}", f"+{r['upside_percent']:.2f}%",
                    f"-${r['downside_points']:,.2f}", f"-{r['downside_percent']:.2f}%",
                    f"${r['expected_range_low']:,.2f}", f"${r['expected_range_high']:,.2f}",
                    f"${r['total_range_points']:,.2f}", f"{r['total_range_pct']:.2f}%",
                    f"${r['call_strike']}", f"{r['call_delta']}", f"{r['call_iv']:.1f}%",
                    f"${r['put_strike']}", f"{r['put_delta']}", f"{r['put_iv']:.1f}%",
                    r["n_calls"], r["n_puts"],
                ]
            }
            st.markdown(
                render_pro_table(pd.DataFrame(resumen_data), title="📋 Datos del Cálculo"),
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="rango-info">
                🧠 <b>Interpretación:</b> El mercado de opciones estima que <b>{r['symbol']}</b>
                se moverá entre <b>${r['expected_range_low']:,.2f}</b> y <b>${r['expected_range_high']:,.2f}</b>
                (un rango de <b>${r['total_range_points']:,.2f}</b> / <b>{r['total_range_pct']:.2f}%</b>)
                hasta el <b>{r['expiration']}</b> con ~68% de probabilidad.
                Esto equivale a ±1 desviación estándar implícita del mercado.<br>
                <span style="font-size: 0.72rem; color: #7dd3fc;">
                    📌 Método: IV de Yahoo Finance + Black-Scholes para cálculo de delta · Perfil TLS: {r.get('perfil_tls', 'N/A')}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================================
#   ⚙️ SETTINGS — PROYECCIONES
# ============================================================================
elif pagina == "⚙️ Settings":
    st.markdown("### 🏢 Proyecciones de Crecimiento a 10 Años")
    st.markdown(
        """
        <div class="watchlist-info">
            📊 <b>Monitor de Proyecciones</b> — Analiza empresas con potencial de crecimiento
            a largo plazo usando datos fundamentales de Yahoo Finance. El score evalúa:
            crecimiento de ingresos, márgenes, consenso de analistas, flujo de caja y valuación PEG.<br>
            🆓 <b>100% gratuito</b> — Todos los datos provienen de Yahoo Finance.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ==============================================================
    #  SECCIÓN 1: EMPRESAS CONSOLIDADAS
    # ==============================================================
    st.markdown("---")
    st.markdown("## 🏢 Empresas Consolidadas — Top Corporations")
    st.caption("Grandes corporaciones con historial probado y proyección de crecimiento sostenido a 10 años.")

    col_btn_c, col_info_c = st.columns([1, 3])
    with col_btn_c:
        analizar_consol_btn = st.button(
            "📊 Analizar Consolidadas en Vivo",
            type="primary",
            use_container_width=True,
            key="btn_analizar_consolidadas",
        )
    with col_info_c:
        if "proyecciones_resultados" in st.session_state and st.session_state.proyecciones_resultados:
            st.success(f"✅ Datos en vivo cargados — {len(st.session_state.proyecciones_resultados)} empresas analizadas")
        else:
            st.caption("Presiona para obtener métricas financieras en tiempo real de Yahoo Finance.")

    if analizar_consol_btn:
        analizar_watchlist(WATCHLIST_EMPRESAS, "proyecciones_resultados", "consolidadas")

    if "proyecciones_resultados" in st.session_state and st.session_state.proyecciones_resultados:
        resultados = st.session_state.proyecciones_resultados

        col_s1, col_s2, col_s3 = st.columns(3)
        alta_count = sum(1 for r in resultados if r["clasificacion"] == "ALTA")
        media_count = sum(1 for r in resultados if r["clasificacion"] == "MEDIA")
        baja_count = sum(1 for r in resultados if r["clasificacion"] == "BAJA")
        st.markdown(render_metric_row([
            render_metric_card("Proyección Alta", f"{alta_count}"),
            render_metric_card("Proyección Media", f"{media_count}", color_override="#f59e0b"),
            render_metric_card("Proyección Baja", f"{baja_count}", color_override="#ef4444"),
        ]), unsafe_allow_html=True)

        for r in resultados:
            info_emp = WATCHLIST_EMPRESAS.get(r["symbol"])
            st.html(render_empresa_card(r, info_emp, WATCHLIST_EMPRESAS))

        st.markdown("#### 📋 Tabla Comparativa")
        df_tabla = render_tabla_comparativa(resultados)
        st.markdown(
            render_pro_table(df_tabla, title="📋 Tabla Comparativa Consolidadas", badge_count=f"{len(df_tabla)}"),
            unsafe_allow_html=True,
        )
        csv_proy = df_tabla.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar análisis CSV",
            csv_proy,
            f"proyecciones_consolidadas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            key="dl_consolidadas",
        )

    else:
        st.markdown("#### 🏢 18 Empresas Consolidadas Monitoreadas")
        render_watchlist_preview(WATCHLIST_EMPRESAS)

    with st.expander("📝 Ver todas las empresas consolidadas y sus descripciones", expanded=True):
        render_empresa_descriptions(WATCHLIST_EMPRESAS, "59, 130, 246", "#3b82f6")

    # ==============================================================
    #  SECCIÓN 2: EMPRESAS EMERGENTES
    # ==============================================================
    st.markdown("---")
    st.markdown("## 🚀 Empresas Emergentes — Futuras Transnacionales")
    st.caption("Empresas de menor capitalización con tecnologías disruptivas y potencial de convertirse en gigantes. Mayor riesgo, mayor recompensa.")

    col_btn_e, col_info_e = st.columns([1, 3])
    with col_btn_e:
        analizar_emerg_btn = st.button(
            "🚀 Analizar Emergentes en Vivo",
            type="primary",
            use_container_width=True,
            key="btn_analizar_emergentes",
        )
    with col_info_e:
        if "emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados:
            st.success(f"✅ Datos en vivo cargados — {len(st.session_state.emergentes_resultados)} empresas analizadas")
        else:
            st.caption("Presiona para obtener métricas financieras en tiempo real de Yahoo Finance.")

    if analizar_emerg_btn:
        analizar_watchlist(WATCHLIST_EMERGENTES, "emergentes_resultados", "emergentes")

    if "emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados:
        resultados_em = st.session_state.emergentes_resultados

        col_e1, col_e2, col_e3 = st.columns(3)
        alta_em = sum(1 for r in resultados_em if r["clasificacion"] == "ALTA")
        media_em = sum(1 for r in resultados_em if r["clasificacion"] == "MEDIA")
        baja_em = sum(1 for r in resultados_em if r["clasificacion"] == "BAJA")
        st.markdown(render_metric_row([
            render_metric_card("Proyección Alta", f"{alta_em}"),
            render_metric_card("Proyección Media", f"{media_em}", color_override="#f59e0b"),
            render_metric_card("Proyección Baja", f"{baja_em}", color_override="#ef4444"),
        ]), unsafe_allow_html=True)

        for r in resultados_em:
            info_emp = WATCHLIST_EMERGENTES.get(r["symbol"])
            st.html(render_empresa_card(r, info_emp, WATCHLIST_EMERGENTES, es_emergente=True))

        st.markdown("#### 📋 Tabla Comparativa Emergentes")
        df_emerg = render_tabla_comparativa(resultados_em, es_emergente=True)
        st.markdown(
            render_pro_table(df_emerg, title="📋 Tabla Comparativa Emergentes", badge_count=f"{len(df_emerg)}"),
            unsafe_allow_html=True,
        )
        csv_emerg = df_emerg.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar análisis Emergentes CSV",
            csv_emerg,
            f"emergentes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            key="dl_emergentes",
        )

    else:
        st.markdown("#### 🚀 18 Empresas Emergentes Monitoreadas")
        render_watchlist_preview(WATCHLIST_EMERGENTES)

    with st.expander("📝 Ver todas las empresas emergentes y por qué pueden ser gigantes", expanded=True):
        render_empresa_descriptions(WATCHLIST_EMERGENTES, "6, 182, 212", "#06b6d4", es_emergente=True)

    # ==============================================================
    #  SECCIÓN 3: ANÁLISIS DETALLADO DE EMPRESAS EMERGENTES
    # ==============================================================
    st.markdown("---")
    st.markdown("## 🔬 Análisis Detallado — Empresas Emergentes")
    st.caption(
        "Desglose individual de cada empresa emergente: qué hacen, por qué pueden ser gigantes, "
        "su sector, y las razones de su proyección a 10 años."
    )

    for sym, info in WATCHLIST_EMERGENTES.items():
        datos_vivo = None
        if "emergentes_resultados" in st.session_state and st.session_state.emergentes_resultados:
            for r in st.session_state.emergentes_resultados:
                if r["symbol"] == sym:
                    datos_vivo = r
                    break

        with st.container(border=True):
            if datos_vivo:
                if datos_vivo["clasificacion"] == "ALTA":
                    badge_text = "🟢 ALTA"
                elif datos_vivo["clasificacion"] == "MEDIA":
                    badge_text = "🟡 MEDIA"
                else:
                    badge_text = "🔴 BAJA"
                col_h1, col_h2 = st.columns([3, 1])
                with col_h1:
                    st.markdown(f"**{sym}** — {info['nombre']} · ${datos_vivo['precio']:,.2f}")
                with col_h2:
                    st.markdown(f"**{badge_text} — {datos_vivo['score']}/100**")
            else:
                st.markdown(f"**{sym}** — {info['nombre']}  ⏳ *Sin analizar*")

            st.caption(f"**Sector:** {info['sector']}")
            st.markdown(f"📝 {info['descripcion']}")
            st.info(f"🌟 **¿Por qué puede ser una empresa gigante?**\n\n{info['por_que_grande']}")

        if datos_vivo:
            mc_str = format_market_cap(datos_vivo["market_cap"])

            col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)
            with col_d1:
                st.metric("Market Cap", mc_str)
            with col_d2:
                growth_val = f"{'+' if datos_vivo['revenue_growth']>0 else ''}{datos_vivo['revenue_growth']*100:.1f}%"
                st.metric("Crec. Ingresos", growth_val)
            with col_d3:
                st.metric("Margen Op.", f"{datos_vivo['operating_margins']*100:.1f}%")
            with col_d4:
                upside_val = f"{'+' if datos_vivo['upside_pct']>0 else ''}{datos_vivo['upside_pct']:.1f}%"
                st.metric("Upside Analistas", upside_val)
            with col_d5:
                st.metric("Recomendación", datos_vivo["recommendation"])

# ============================================================================
#   📰 NEWS & CALENDAR — NOTICIAS
# ============================================================================
elif pagina == "📰 News & Calendar":
    st.markdown("### 📰 Noticias Financieras en Tiempo Real")
    st.markdown(
        """
        <div class="watchlist-info">
            📡 <b>Centro de Noticias</b> — Noticias financieras de
            Yahoo Finance, MarketWatch, CNBC, Reuters e Investing.com.
            Filtra por relevancia, tendencia mundial o categoría. 🆓 100% gratuito vía RSS.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- CONTROLES SIEMPRE VISIBLES ---
    col_load, col_refresh, col_auto = st.columns([1.5, 1.5, 2])

    with col_load:
        cargar_noticias_btn = st.button(
            "📡 Cargar Noticias" if not st.session_state.noticias_data else "📡 Recargar Todo",
            type="primary",
            use_container_width=True,
            key="btn_cargar_noticias_main",
        )
    with col_refresh:
        refresh_noticias_btn = st.button(
            "🔄 Refrescar",
            use_container_width=True,
            key="btn_refresh_noticias",
            disabled=not st.session_state.noticias_data,
        )
    with col_auto:
        auto_refresh_noticias = st.checkbox(
            "⏱️ Auto-refresco cada 5 min",
            value=st.session_state.noticias_auto_refresh,
            key="chk_auto_refresh_noticias",
            help="Actualiza las noticias automáticamente cada 5 minutos",
        )
        st.session_state.noticias_auto_refresh = auto_refresh_noticias

    # --- FILTROS ---
    col_filtro1, col_filtro2 = st.columns([3, 2])
    with col_filtro1:
        filtro_noticias = st.selectbox(
            "🏷️ Filtrar por:",
            [
                "Todas",
                "🔥 Más relevantes",
                "🌍 Más vistas a nivel mundial",
                "Más relevantes para trading",
                "Top Stories",
                "Earnings",
                "Fed / Tasas",
                "Economía",
                "Trading",
                "Crypto",
                "Commodities",
                "Geopolítica",
            ],
            index=0,
            key="sel_filtro_noticias",
        )
    with col_filtro2:
        ordenar_por = st.selectbox(
            "📊 Ordenar por:",
            ["Más recientes", "Más relevantes primero"],
            index=0,
            key="sel_orden_noticias",
        )

    # --- CARGAR / REFRESCAR ---
    necesita_refresh = False
    if auto_refresh_noticias:
        last = st.session_state.noticias_last_refresh
        if last is None:
            necesita_refresh = True
        else:
            elapsed = (datetime.now() - last).total_seconds()
            if elapsed >= AUTO_REFRESH_INTERVAL:
                necesita_refresh = True

    if cargar_noticias_btn or refresh_noticias_btn or necesita_refresh:
        with st.spinner("📡 Obteniendo noticias de múltiples fuentes..."):
            noticias = obtener_noticias_financieras()
            if noticias:
                st.session_state.noticias_data = noticias
                st.session_state.noticias_last_refresh = datetime.now()
                if cargar_noticias_btn or refresh_noticias_btn:
                    st.rerun()

    # --- AUTO-REFRESH COUNTDOWN ---
    if auto_refresh_noticias and st.session_state.noticias_last_refresh:
        elapsed = (datetime.now() - st.session_state.noticias_last_refresh).total_seconds()
        remaining = max(0, AUTO_REFRESH_INTERVAL - elapsed)
        mins_left = int(remaining // 60)
        secs_left = int(remaining % 60)
        st.caption(
            f"🔄 Auto-refresco activo — Próxima actualización en **{mins_left}:{secs_left:02d}** · "
            f"Último: **{st.session_state.noticias_last_refresh.strftime('%H:%M:%S')}**"
        )

    # --- CONTENIDO ---
    if not st.session_state.noticias_data:
        st.info(
            "👆 Presiona **Cargar Noticias** para obtener las últimas noticias financieras "
            "de Yahoo Finance, MarketWatch, CNBC, Reuters e Investing.com."
        )
    else:
        # Métricas
        col_status1, col_status2, col_status3 = st.columns(3)
        with col_status1:
            st.metric("🕐 Última actualización", st.session_state.noticias_last_refresh.strftime('%H:%M:%S'))
        with col_status2:
            st.metric("📰 Total noticias", len(st.session_state.noticias_data))
        with col_status3:
            st.metric("🏷️ Filtro activo", filtro_noticias)

        # Distribución por categoría
        cat_counts = {}
        for n in st.session_state.noticias_data:
            cat = n["categoria"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        if top_cats:
            stat_cols = st.columns(len(top_cats))
            for i, (cat_name, cat_count) in enumerate(top_cats):
                with stat_cols[i]:
                    st.metric(cat_name, cat_count)

        st.divider()

        # Filtrar y ordenar
        noticias_filtradas = filtrar_noticias(st.session_state.noticias_data, filtro_noticias)

        if ordenar_por == "Más relevantes primero" and filtro_noticias not in ("🔥 Más relevantes", "🌍 Más vistas a nivel mundial"):
            from core.news import calcular_relevancia
            noticias_filtradas = sorted(noticias_filtradas, key=calcular_relevancia, reverse=True)

        if not noticias_filtradas:
            st.info(f"No hay noticias para el filtro '{filtro_noticias}'. Prueba con 'Todas'.")
        else:
            st.markdown(f"#### 📋 {len(noticias_filtradas)} noticias — {filtro_noticias}")

            cat_emoji_map = {
                "Earnings": "💰",
                "Fed / Tasas": "🏛️",
                "Economía": "📊",
                "Trading": "📈",
                "Crypto": "₿",
                "Commodities": "🛢️",
                "Geopolítica": "🌍",
                "Top Stories": "⭐",
                "Mercados": "📈",
            }

            for n in noticias_filtradas:
                cat = n["categoria"]
                emoji = cat_emoji_map.get(cat, "📰")

                with st.container():
                    col_noticia, col_cat = st.columns([5, 1])
                    with col_noticia:
                        if n["url"]:
                            st.markdown(f"**[{n['titulo']}]({n['url']})**")
                        else:
                            st.markdown(f"**{n['titulo']}**")

                        if n["descripcion"]:
                            st.caption(n["descripcion"])

                        meta_parts = []
                        if n["fuente"]:
                            meta_parts.append(f"📰 {n['fuente']}")
                        if n["tiempo"]:
                            meta_parts.append(f"🕐 {n['tiempo']}")
                        if meta_parts:
                            st.caption(" · ".join(meta_parts))

                    with col_cat:
                        st.markdown(f"**{emoji} {cat}**")

                    st.divider()

        # Auto-rerun si toca
        if auto_refresh_noticias and st.session_state.noticias_last_refresh:
            elapsed = (datetime.now() - st.session_state.noticias_last_refresh).total_seconds()
            if elapsed >= AUTO_REFRESH_INTERVAL:
                st.rerun()


    # ============================================================================
    #   CALENDARIO FINANCIERO — Sub-sección de News & Calendar
    # ============================================================================
    st.markdown("---")
    from ui.tabs.calendar_tab import render_calendar_tab
    render_calendar_tab()

# ============================================================================
#                    FOOTER
# ============================================================================
st.markdown(
    """
    <div class="footer-pro">
        <div>👑 OPTIONS<span style="color: #00ff88;">KING</span> Analytics v5.0 — Datos de Yahoo Finance</div>
        <div class="footer-badges">
            <span class="footer-badge">🔒 curl_cffi TLS</span>
            <span class="footer-badge">📊 Yahoo Finance</span>
            <span class="footer-badge">📐 Black-Scholes</span>
            <span class="footer-badge">📰 RSS Feeds</span>
            <span class="footer-badge">🎨 Streamlit</span>
            <span class="footer-badge">🐍 Python</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
