"""
Estilos CSS personalizados del Monitor de Opciones.
Se inyectan vía st.markdown(CSS_STYLES, unsafe_allow_html=True).
"""

CSS_STYLES = """
<style>
    /* ====== FUENTES ====== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* ====== BASE ====== */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ====== MÉTRICAS ====== */
    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(99, 179, 237, 0.15);
        border-radius: 16px;
        padding: 20px 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ====== SISTEMA DE COLORES POR PRIORIDAD ====== */

    /* 🟢 VERDE — Mayor prima (TOP) */
    .alerta-top {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 78, 59, 0.25));
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-left: 5px solid #10b981;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        color: #f0fdf4;
        box-shadow: 0 0 25px rgba(16, 185, 129, 0.15), 0 4px 16px rgba(0,0,0,0.2);
        position: relative;
        backdrop-filter: blur(8px);
        transition: transform 0.15s ease;
    }
    .alerta-top:hover { transform: translateX(4px); }
    .alerta-top::after {
        content: '⭐ MAYOR PRIMA';
        position: absolute;
        top: 10px;
        right: 14px;
        background: linear-gradient(135deg, #10b981, #059669);
        color: #fff;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
    }

    /* 🔴 ROJO — Actividad institucional */
    .alerta-principal {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(127, 29, 29, 0.2));
        border: 1px solid rgba(239, 68, 68, 0.25);
        border-left: 5px solid #ef4444;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        color: #fef2f2;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        backdrop-filter: blur(8px);
        transition: transform 0.15s ease;
    }
    .alerta-principal:hover { transform: translateX(4px); }

    /* 🟠 NARANJA — Prima Alta */
    .alerta-prima {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(120, 53, 15, 0.2));
        border: 1px solid rgba(245, 158, 11, 0.25);
        border-left: 5px solid #f59e0b;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        color: #fffbeb;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        backdrop-filter: blur(8px);
        transition: transform 0.15s ease;
    }
    .alerta-prima:hover { transform: translateX(4px); }

    /* Leyenda de colores */
    .leyenda-colores {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 16px;
        padding: 18px 24px;
        margin-bottom: 18px;
    }
    .leyenda-item {
        display: block;
        margin-bottom: 6px;
        font-size: 0.82rem;
        line-height: 1.5;
        color: #cbd5e1;
    }
    .leyenda-item b { color: #f1f5f9; }
    .dot-green { color: #10b981; font-size: 1.1rem; }
    .dot-red { color: #ef4444; font-size: 1.1rem; }
    .dot-orange { color: #f59e0b; font-size: 1.1rem; }

    /* Etiqueta de razón */
    .razon-alerta {
        display: inline-block;
        background: rgba(255,255,255,0.06);
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.72rem;
        margin-top: 6px;
        color: #94a3b8;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.01em;
    }

    /* ====== HEADER ====== */
    .scanner-header {
        background: linear-gradient(135deg, #0a0e17 0%, #111827 40%, #1e293b 100%);
        padding: 32px 40px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 28px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    .scanner-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #10b981, #3b82f6, #8b5cf6, #f59e0b);
    }
    .scanner-header h1 {
        margin: 0;
        color: #f1f5f9;
        font-weight: 700;
        font-size: 2rem;
        letter-spacing: -0.02em;
    }
    .scanner-header .subtitle {
        margin: 8px 0 0 0;
        color: #64748b;
        font-size: 1rem;
        font-weight: 400;
    }
    .scanner-header .badge {
        display: inline-block;
        background: linear-gradient(135deg, #10b981, #059669);
        color: #fff;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-top: 10px;
    }

    /* ====== SIDEBAR ====== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0e17 0%, #111827 50%, #0f172a 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.08);
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #f1f5f9;
        font-size: 1.1rem;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(148, 163, 184, 0.1);
        margin: 16px 0;
    }

    /* ====== TABS — COMPONENTE PROFESIONAL ACCESIBLE ====== */
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        flex-wrap: wrap;
        gap: 2px;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.7), rgba(30, 41, 59, 0.5));
        border-radius: 14px;
        padding: 5px 6px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255,255,255,0.03);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        position: relative;
        overflow-x: auto;
        scrollbar-width: none;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
        display: none;
    }
    .stTabs [data-baseweb="tab"] {
        position: relative;
        padding: 11px 22px;
        border-radius: 10px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-weight: 500;
        font-size: 0.85rem;
        color: #94a3b8;
        letter-spacing: 0.01em;
        white-space: nowrap;
        cursor: pointer;
        user-select: none;
        transition: color 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                    background 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                    box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                    transform 0.15s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid transparent;
        outline: none;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #e2e8f0;
        background: rgba(99, 179, 237, 0.08);
        border-color: rgba(99, 179, 237, 0.1);
    }
    .stTabs [data-baseweb="tab"]:focus-visible {
        outline: 2px solid #60a5fa;
        outline-offset: 2px;
        border-radius: 10px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), rgba(99, 102, 241, 0.12)) !important;
        color: #93c5fd !important;
        font-weight: 600;
        border-color: rgba(59, 130, 246, 0.25) !important;
        box-shadow: 0 0 12px rgba(59, 130, 246, 0.15),
                    inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    .stTabs [aria-selected="true"]::after {
        content: '';
        position: absolute;
        bottom: 3px;
        left: 50%;
        transform: translateX(-50%);
        width: 40%;
        height: 3px;
        border-radius: 2px;
        background: linear-gradient(90deg, #3b82f6, #818cf8);
        box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
        animation: tabIndicatorIn 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    @keyframes tabIndicatorIn {
        from { width: 0%; opacity: 0; }
        to { width: 40%; opacity: 1; }
    }
    .stTabs [data-baseweb="tab-panel"] {
        animation: tabFadeIn 0.35s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    @keyframes tabFadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* ====== BOTONES ====== */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em;
        padding: 10px 24px !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
        transform: translateY(-1px);
    }

    /* ====== CHARTS - SCROLL INDEPENDIENTE ====== */
    [data-testid="stVegaLiteChart"] {
        max-height: 420px;
        overflow-y: auto;
        overflow-x: hidden;
        border-radius: 12px;
        scrollbar-width: thin;
        scrollbar-color: rgba(148, 163, 184, 0.2) transparent;
    }
    [data-testid="stVegaLiteChart"]::-webkit-scrollbar {
        width: 6px;
    }
    [data-testid="stVegaLiteChart"]::-webkit-scrollbar-track {
        background: transparent;
    }
    [data-testid="stVegaLiteChart"]::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.25);
        border-radius: 3px;
    }

    /* ====== DATAFRAMES ====== */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    /* ====== EXPANDER ====== */
    .stExpander {
        border: 1px solid rgba(148, 163, 184, 0.1) !important;
        border-radius: 12px !important;
        background: rgba(15, 23, 42, 0.4) !important;
    }

    /* ====== FOOTER ====== */
    .footer-pro {
        text-align: center;
        padding: 24px 0 8px 0;
        color: #475569;
        font-size: 0.75rem;
        letter-spacing: 0.02em;
    }
    .footer-pro a {
        color: #64748b;
        text-decoration: none;
    }
    .footer-pro .footer-badges {
        margin-top: 8px;
    }
    .footer-pro .footer-badge {
        display: inline-block;
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.1);
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.68rem;
        margin: 0 3px;
        color: #64748b;
    }

    /* ====== STATUS INDICATOR ====== */
    .status-bar {
        display: flex;
        align-items: center;
        gap: 16px;
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 12px;
        padding: 10px 20px;
        margin-bottom: 16px;
        font-size: 0.82rem;
        color: #94a3b8;
    }
    .status-bar .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10b981;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
        animation: pulse-dot 2s ease-in-out infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(16, 185, 129, 0.5); }
        50% { opacity: 0.6; box-shadow: 0 0 16px rgba(16, 185, 129, 0.8); }
    }

    /* ====== SECTION TITLES ====== */
    .section-title {
        font-family: 'Inter', sans-serif;
        font-size: 1.15rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }

    /* ====== CARD ====== */
    .info-card {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 16px;
        padding: 20px 24px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    }

    /* ====== ALERTA COMPRA CONTINUA (CLUSTER) ====== */
    .alerta-cluster {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(76, 29, 149, 0.22));
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-left: 5px solid #8b5cf6;
        padding: 18px 22px;
        border-radius: 14px;
        margin-bottom: 14px;
        color: #f5f3ff;
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.15), 0 4px 16px rgba(0,0,0,0.2);
        backdrop-filter: blur(8px);
    }
    .cluster-badge {
        display: inline-block;
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
        color: #fff;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-left: 8px;
        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.4);
    }
    .cluster-detail {
        background: rgba(139, 92, 246, 0.08);
        border: 1px solid rgba(139, 92, 246, 0.15);
        border-radius: 10px;
        padding: 10px 16px;
        margin-top: 8px;
        font-size: 0.78rem;
        color: #c4b5fd;
        font-family: 'JetBrains Mono', monospace;
    }
    .dot-purple { color: #8b5cf6; font-size: 1.1rem; }

    /* ====== PROYECCIONES / WATCHLIST ====== */
    .empresa-card {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .empresa-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
        border-color: rgba(59, 130, 246, 0.3);
    }
    .empresa-card-bull {
        border-left: 5px solid #10b981;
    }
    .empresa-card-neutral {
        border-left: 5px solid #f59e0b;
    }
    .empresa-card-bear {
        border-left: 5px solid #ef4444;
    }
    .empresa-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 10px;
    }
    .empresa-ticker {
        font-size: 1.5rem;
        font-weight: 800;
        color: #f1f5f9;
        font-family: 'JetBrains Mono', monospace;
    }
    .empresa-nombre {
        font-size: 0.82rem;
        color: #94a3b8;
        margin-top: 2px;
    }
    .empresa-desc {
        font-size: 0.78rem;
        color: #cbd5e1;
        margin: 8px 0;
        line-height: 1.5;
        padding: 10px 14px;
        background: rgba(99, 179, 237, 0.04);
        border-radius: 10px;
        border: 1px solid rgba(99, 179, 237, 0.08);
    }
    .empresa-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 12px;
    }
    .empresa-metric {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 10px;
        padding: 10px 16px;
        min-width: 120px;
        text-align: center;
    }
    .empresa-metric-label {
        font-size: 0.62rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .empresa-metric-value {
        font-size: 1rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: #f1f5f9;
    }
    .empresa-score {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
    }
    .score-alta {
        background: linear-gradient(135deg, #10b981, #059669);
        color: #fff;
    }
    .score-media {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: #fff;
    }
    .score-baja {
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: #fff;
    }

    /* ====== NEWS CARDS ====== */
    .news-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 12px;
    }
    .news-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-left: 4px solid #3b82f6;
        border-radius: 12px;
        padding: 16px 20px;
        transition: all 0.2s ease;
    }
    .news-card:hover {
        background: rgba(30, 41, 59, 0.7);
        border-color: rgba(148, 163, 184, 0.2);
        transform: translateX(3px);
    }
    .news-card.news-earnings {
        border-left-color: #f59e0b;
    }
    .news-card.news-fed {
        border-left-color: #ef4444;
    }
    .news-card.news-economy {
        border-left-color: #10b981;
    }
    .news-card.news-crypto {
        border-left-color: #8b5cf6;
    }
    .news-card.news-commodities {
        border-left-color: #f97316;
    }
    .news-card.news-geopolitics {
        border-left-color: #ec4899;
    }
    .news-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
    }
    .news-title {
        font-family: 'Inter', sans-serif;
        font-size: 0.92rem;
        font-weight: 600;
        color: #e2e8f0;
        line-height: 1.4;
        flex: 1;
    }
    .news-title a {
        color: #e2e8f0;
        text-decoration: none;
    }
    .news-title a:hover {
        color: #60a5fa;
        text-decoration: underline;
    }
    .news-meta {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 8px;
        font-size: 0.72rem;
        color: #64748b;
    }
    .news-source {
        display: inline-block;
        background: rgba(59, 130, 246, 0.12);
        color: #60a5fa;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 0.68rem;
        font-weight: 600;
    }
    .news-time {
        color: #64748b;
        font-size: 0.72rem;
    }
    .news-category-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.62rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .news-cat-earnings {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
    }
    .news-cat-fed {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
    }
    .news-cat-economy {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
    }
    .news-cat-crypto {
        background: rgba(139, 92, 246, 0.15);
        color: #a78bfa;
    }
    .news-cat-commodities {
        background: rgba(249, 115, 22, 0.15);
        color: #fb923c;
    }
    .news-cat-geopolitics {
        background: rgba(236, 72, 153, 0.15);
        color: #f472b6;
    }
    .news-cat-markets {
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
    }
    .news-cat-trading {
        background: rgba(6, 182, 212, 0.15);
        color: #22d3ee;
    }
    .news-desc {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 8px;
        line-height: 1.5;
    }
    .news-refresh-bar {
        display: flex;
        align-items: center;
        gap: 16px;
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 12px;
        padding: 10px 20px;
        margin-bottom: 16px;
        font-size: 0.82rem;
        color: #94a3b8;
    }
    .news-refresh-bar .refresh-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #06b6d4;
        box-shadow: 0 0 8px rgba(6, 182, 212, 0.5);
        animation: pulse-dot 2s ease-in-out infinite;
    }
    .news-stats {
        display: flex;
        gap: 16px;
        margin-bottom: 16px;
    }
    .news-stat-card {
        flex: 1;
        background: rgba(15, 23, 42, 0.4);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 12px;
        padding: 14px 18px;
        text-align: center;
    }
    .news-stat-number {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.3rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .news-stat-label {
        font-size: 0.68rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }

    .empresa-card-emergente {
        border-left: 5px solid #06b6d4;
        position: relative;
    }
    .empresa-card-emergente::after {
        content: '🚀';
        position: absolute;
        top: 12px;
        right: 16px;
        font-size: 1.4rem;
        opacity: 0.3;
    }
    .emergente-badge {
        display: inline-block;
        background: linear-gradient(135deg, #06b6d4, #0891b2);
        color: #fff;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-left: 8px;
        box-shadow: 0 2px 8px rgba(6, 182, 212, 0.3);
    }
    .por-que-grande {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.06), rgba(6, 182, 212, 0.02));
        border: 1px solid rgba(6, 182, 212, 0.15);
        border-radius: 10px;
        padding: 12px 16px;
        margin-top: 10px;
        font-size: 0.76rem;
        color: #67e8f9;
        line-height: 1.6;
    }
    .watchlist-info {
        background: rgba(59, 130, 246, 0.06);
        border: 1px solid rgba(59, 130, 246, 0.12);
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 18px;
        font-size: 0.82rem;
        color: #93c5fd;
    }

    /* ====== RANGO ESPERADO ====== */
    .rango-card {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(6, 78, 130, 0.18));
        border: 1px solid rgba(14, 165, 233, 0.2);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 16px;
        box-shadow: 0 4px 24px rgba(14, 165, 233, 0.1), 0 0 0 1px rgba(14, 165, 233, 0.05);
        backdrop-filter: blur(12px);
    }
    .rango-titulo {
        font-size: 1.2rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 4px;
    }
    .rango-subtitulo {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-bottom: 18px;
    }
    .rango-barra-container {
        position: relative;
        background: rgba(15, 23, 42, 0.6);
        border-radius: 12px;
        height: 56px;
        margin: 20px 0;
        border: 1px solid rgba(148, 163, 184, 0.1);
        overflow: visible;
    }
    .rango-barra-fill {
        position: absolute;
        top: 0;
        height: 100%;
        border-radius: 12px;
    }
    .rango-barra-down {
        left: 0;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.35), rgba(239, 68, 68, 0.08));
        border-right: 2px solid rgba(239, 68, 68, 0.5);
    }
    .rango-barra-up {
        right: 0;
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.08), rgba(16, 185, 129, 0.35));
        border-left: 2px solid rgba(16, 185, 129, 0.5);
    }
    .rango-precio-actual {
        position: absolute;
        top: -8px;
        transform: translateX(-50%);
        background: #3b82f6;
        color: #fff;
        padding: 2px 12px;
        border-radius: 10px;
        font-size: 0.72rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        white-space: nowrap;
        z-index: 10;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
    }
    .rango-label-low {
        position: absolute;
        bottom: -22px;
        left: 8px;
        font-size: 0.72rem;
        color: #ef4444;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    .rango-label-high {
        position: absolute;
        bottom: -22px;
        right: 8px;
        font-size: 0.72rem;
        color: #10b981;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    .rango-stat {
        display: inline-block;
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 14px 20px;
        margin: 6px 6px 6px 0;
        min-width: 140px;
        text-align: center;
    }
    .rango-stat-label {
        font-size: 0.68rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .rango-stat-value {
        font-size: 1.3rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    .rango-stat-value.up { color: #10b981; }
    .rango-stat-value.down { color: #ef4444; }
    .rango-stat-value.neutral { color: #60a5fa; }
    .rango-info {
        background: rgba(14, 165, 233, 0.06);
        border: 1px solid rgba(14, 165, 233, 0.12);
        border-radius: 10px;
        padding: 12px 16px;
        margin-top: 16px;
        font-size: 0.78rem;
        color: #7dd3fc;
    }

    /* ==========================================================================
       RESPONSIVE — SIDEBAR AUTO-ADJUST + DISPOSITIVOS
       ========================================================================== */

    /* Transiciones suaves al colapsar/expandir sidebar */
    .stMain, section[data-testid="stMain"],
    [data-testid="stAppViewBlockContainer"],
    .stMainBlockContainer {
        transition: margin-left 0.3s ease, width 0.3s ease !important;
        max-width: 100% !important;
    }

    /* --- TABLET (≤ 1024px) --- */
    @media (max-width: 1024px) {
        .scanner-header h1 { font-size: 1.6rem !important; }
        .scanner-header .subtitle { font-size: 0.85rem; }

        div[data-testid="stMetric"] {
            padding: 14px 16px;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }

        .empresa-card { padding: 16px 18px; }
        .empresa-ticker { font-size: 1.25rem; }
        .empresa-metric { min-width: 100px; padding: 8px 12px; }

        .rango-stat { min-width: 110px; padding: 10px 14px; }
        .rango-stat-value { font-size: 1.1rem; }

        .news-stat-card { padding: 10px 12px; }
        .news-stat-number { font-size: 1.1rem; }
    }

    /* --- MOBILE (≤ 768px) --- */
    @media (max-width: 768px) {
        /* Contenido: padding reducido en mobile */
        .stMainBlockContainer,
        .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-left: 8px !important;
            padding-right: 8px !important;
        }

        /* Header */
        .scanner-header {
            padding: 16px !important;
            border-radius: 12px !important;
        }
        .scanner-header h1 { font-size: 1.3rem !important; }
        .scanner-header .subtitle { font-size: 0.78rem; }
        .scanner-header .badge { font-size: 0.62rem; padding: 3px 10px; }

        /* Métricas: 2 columnas en mobile */
        [data-testid="column"] {
            min-width: 45% !important;
        }
        div[data-testid="stMetric"] {
            padding: 12px 14px;
            border-radius: 12px;
        }
        div[data-testid="stMetric"] label {
            font-size: 0.68rem !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }

        /* Status bar: wrap */
        .status-bar {
            flex-wrap: wrap;
            gap: 8px;
            padding: 8px 14px;
            font-size: 0.72rem;
        }
        .status-bar span { white-space: nowrap; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            padding: 4px;
            border-radius: 10px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
        .stTabs [data-baseweb="tab"] {
            padding: 9px 12px;
            font-size: 0.72rem;
            min-width: fit-content;
            white-space: nowrap;
        }

        /* Alertas */
        .alerta-top, .alerta-principal, .alerta-prima, .alerta-cluster {
            padding: 12px 14px;
            border-radius: 10px;
            font-size: 0.78rem;
        }
        .alerta-top::after, .alerta-principal::after {
            font-size: 0.55rem;
            padding: 2px 8px;
            top: 6px;
            right: 8px;
        }
        .razon-alerta { font-size: 0.68rem; }
        .cluster-detail { font-size: 0.7rem; padding: 8px 12px; }

        /* Leyenda de colores */
        .leyenda-colores {
            padding: 10px 14px !important;
            font-size: 0.72rem !important;
        }
        .leyenda-colores .leyenda-item { font-size: 0.7rem !important; }

        /* Empresa cards */
        .empresa-card { padding: 14px 16px; border-radius: 12px; }
        .empresa-ticker { font-size: 1.15rem; }
        .empresa-nombre { font-size: 0.75rem; }
        .empresa-desc { font-size: 0.72rem; padding: 8px 12px; }
        .empresa-metrics {
            flex-direction: column;
            gap: 6px;
        }
        .empresa-metric {
            min-width: unset;
            width: 100%;
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .empresa-metric-label { font-size: 0.6rem; }
        .empresa-metric-value { font-size: 0.88rem; }

        .empresa-header {
            flex-direction: column;
            gap: 6px;
        }

        /* Noticias */
        .news-card { padding: 12px 14px; }
        .news-title { font-size: 0.82rem; }
        .news-desc { font-size: 0.72rem; }
        .news-meta { flex-wrap: wrap; gap: 6px; }
        .news-stats { flex-wrap: wrap; gap: 8px; }
        .news-stat-card {
            flex: 1 1 45%;
            min-width: 120px;
            padding: 10px 12px;
        }
        .news-stat-number { font-size: 1rem; }

        /* Rango */
        .rango-stat {
            min-width: unset;
            width: 100%;
            margin: 4px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 14px;
        }
        .rango-stat-value { font-size: 1rem; }
        .rango-info { font-size: 0.72rem; padding: 10px 14px; }

        /* Watchlist info */
        .watchlist-info { font-size: 0.75rem; padding: 12px 16px; }

        /* Footer */
        .footer-pro { padding: 16px 0 6px 0; }
        .footer-pro .footer-badge {
            font-size: 0.6rem;
            padding: 2px 8px;
            margin: 2px;
        }

        /* DataFrames: scroll horizontal */
        .stDataFrame {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
        }

        /* Botones */
        .stButton > button {
            width: 100% !important;
            font-size: 0.82rem !important;
        }

        /* Expander */
        .stExpander { border-radius: 10px !important; }

        /* Cards info */
        .info-card { padding: 14px 16px; border-radius: 12px; }
    }

    /* --- SMALL MOBILE (≤ 480px) --- */
    @media (max-width: 480px) {
        .stMainBlockContainer,
        .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-left: 4px !important;
            padding-right: 4px !important;
        }

        .scanner-header h1 { font-size: 1.1rem !important; }
        .scanner-header .subtitle { font-size: 0.7rem; }

        [data-testid="column"] {
            min-width: 100% !important;
        }

        div[data-testid="stMetric"] {
            padding: 10px 12px;
        }
        div[data-testid="stMetric"] label {
            font-size: 0.62rem !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.1rem !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            flex-wrap: nowrap;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 7px 8px;
            font-size: 0.65rem;
        }

        .alerta-top, .alerta-principal, .alerta-prima, .alerta-cluster {
            padding: 10px 12px;
            font-size: 0.72rem;
        }
        .alerta-top::after, .alerta-principal::after {
            display: none;
        }

        .empresa-card { padding: 12px 14px; }
        .empresa-ticker { font-size: 1rem; }
        .empresa-score { font-size: 0.62rem; padding: 3px 10px; }

        .news-stat-card { flex: 1 1 100%; }

        .footer-pro .footer-badges {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 4px;
        }
        .footer-pro .footer-badge {
            font-size: 0.56rem;
            padding: 2px 6px;
        }

        .rango-barra-container { height: 44px; }
        .rango-precio-actual { font-size: 0.62rem; padding: 2px 8px; }
        .rango-label-low, .rango-label-high { font-size: 0.62rem; }
    }

    /* --- Landscape phones --- */
    @media (max-height: 500px) and (orientation: landscape) {
        .scanner-header { padding: 10px 16px !important; }
        .scanner-header h1 { font-size: 1.2rem !important; margin: 0 !important; }
        div[data-testid="stMetric"] { padding: 8px 12px; }
    }

    /* --- Print --- */
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        .stMain { margin-left: 0 !important; width: 100% !important; }
        .stButton, .stTabs [data-baseweb="tab-list"] { display: none !important; }
    }
</style>
"""
