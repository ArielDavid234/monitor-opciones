# -*- coding: utf-8 -*-
"""
Elementos compartidos de UI: CSS, sidebar logo, footer.
Extraídos de app_web.py — cero cambios de lógica.
"""
import streamlit as st

from ui.styles import CSS_STYLES


# ============================================================================
#                    CSS COMPLEMENTARIO (DARK THEME)
# ============================================================================
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


def inject_all_css():
    """Inyecta todo el CSS (custom + avanzado), viewport meta y fuerza dark mode."""
    st.markdown(_CUSTOM_CSS + CSS_STYLES, unsafe_allow_html=True)
    st.markdown(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, '
        'maximum-scale=5.0, user-scalable=yes">'
        '<meta name="color-scheme" content="dark">'
        '<script>document.documentElement.setAttribute("data-theme","dark");'
        'document.documentElement.style.colorScheme="dark";</script>',
        unsafe_allow_html=True,
    )


def render_sidebar_logo():
    """Renderiza el logo SVG de OPTIONSKING en el sidebar."""
    st.markdown("""
            <div style="text-align: center; padding: 1rem 0;">
            <div style="width: 64px; height: 64px; margin: 0 auto 12px auto;">
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


def render_sidebar_avatar():
    """Renderiza el avatar / sección de usuario en el sidebar."""
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


def render_footer():
    """Renderiza el footer profesional."""
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
