"""
Estilos CSS personalizados del Monitor de Opciones — OPTIONSKING Analytics.
Tema dark profesional inspirado en plataformas de trading institucional.
Se inyectan via st.markdown(CSS_STYLES, unsafe_allow_html=True).
"""

CSS_STYLES = """
<style>
    /* ====== FUENTES ====== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* ====== ROOT VARIABLES ====== */
    :root {
        color-scheme: dark;
        --bg-deepest: #0a0d14;
        --bg-base: #0f172a;
        --bg-card: #1e293b;
        --bg-card-hover: #263549;
        --bg-elevated: #334155;
        --border-subtle: rgba(148, 163, 184, 0.08);
        --border-default: rgba(148, 163, 184, 0.12);
        --border-hover: rgba(148, 163, 184, 0.2);
        --text-primary: #ffffff;
        --text-secondary: #9ca3af;
        --text-muted: #64748b;
        --text-dim: #475569;
        --neon-green: #00ff88;
        --accent-green: #10b981;
        --accent-green-dim: rgba(16, 185, 129, 0.15);
        --accent-red: #ef4444;
        --accent-red-dim: rgba(239, 68, 68, 0.12);
        --accent-blue: #3b82f6;
        --accent-blue-dim: rgba(59, 130, 246, 0.12);
        --accent-orange: #f59e0b;
        --accent-purple: #8b5cf6;
        --accent-cyan: #06b6d4;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        --shadow-card: 0 4px 24px rgba(0,0,0,0.4);
        --shadow-glow-green: 0 0 20px rgba(0, 255, 136, 0.1);
        --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    }

    /* ====== GLOBAL BASE ====== */
    .stApp {
        font-family: var(--font-sans);
        background: var(--bg-deepest) !important;
        color: var(--text-primary);
    }
    .stMain, [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"],
    .stMainBlockContainer, .block-container {
        background: var(--bg-deepest) !important;
    }

    /* ====== SIDEBAR ====== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #060910 0%, #0a0e18 30%, #0c1220 100%) !important;
        border-right: 1px solid var(--border-subtle);
        box-shadow: 4px 0 24px rgba(0,0,0,0.5);
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        display: flex;
        flex-direction: column;
        min-height: 100vh;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: var(--text-primary);
        font-size: 0.88rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 12px 0 8px 0;
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: 12px;
    }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--text-secondary);
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    section[data-testid="stSidebar"] hr {
        border-color: var(--border-subtle);
        margin: 12px 0;
    }
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] [data-baseweb="input"] {
        background: var(--bg-card) !important;
        border-color: var(--border-default) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius-sm) !important;
    }
    section[data-testid="stSidebar"] input:focus,
    section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within {
        border-color: var(--neon-green) !important;
        box-shadow: 0 0 0 2px rgba(0, 255, 136, 0.15) !important;
    }

    /* ====== SIDEBAR LOGO ====== */
    .ok-logo {
        padding: 24px 16px 18px 16px;
        text-align: center;
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: 6px;
    }
    .ok-logo-crown {
        font-size: 2rem;
        line-height: 1;
        filter: drop-shadow(0 0 8px rgba(0,255,136,0.4));
    }
    .ok-logo-text {
        font-size: 1.1rem;
        font-weight: 800;
        color: var(--text-primary);
        letter-spacing: -0.02em;
        margin-top: 6px;
    }
    .ok-logo-text span { color: var(--neon-green); }
    .ok-logo-sub {
        font-size: 0.58rem;
        color: var(--text-dim);
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-top: 2px;
    }

    /* ====== SIDEBAR NAV MENU ====== */
    .ok-nav {
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .ok-nav-label {
        font-size: 0.60rem;
        font-weight: 700;
        color: var(--text-dim);
        text-transform: uppercase;
        letter-spacing: 0.10em;
        padding: 12px 12px 6px 12px;
    }
    .ok-nav-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 9px 14px;
        border-radius: var(--radius-sm);
        color: var(--text-secondary);
        font-size: 0.80rem;
        font-weight: 500;
        cursor: default;
        transition: all 0.15s ease;
        border: 1px solid transparent;
        text-decoration: none;
    }
    .ok-nav-item:hover {
        background: rgba(0, 255, 136, 0.04);
        color: var(--text-primary);
        border-color: rgba(0, 255, 136, 0.06);
    }
    .ok-nav-item.active {
        background: rgba(0, 255, 136, 0.08);
        color: var(--neon-green);
        font-weight: 600;
        border-color: rgba(0, 255, 136, 0.12);
        box-shadow: 0 0 12px rgba(0, 255, 136, 0.06);
    }
    .ok-nav-item .nav-icon {
        width: 18px;
        height: 18px;
        flex-shrink: 0;
        opacity: 0.7;
    }
    .ok-nav-item.active .nav-icon { opacity: 1; }
    .ok-nav-item .nav-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--neon-green);
        margin-left: auto;
        box-shadow: 0 0 6px rgba(0,255,136,0.4);
        display: none;
    }
    .ok-nav-item.active .nav-dot { display: block; }

    /* ====== SIDEBAR AVATAR ====== */
    .ok-avatar-section {
        padding: 14px 16px;
        border-top: 1px solid var(--border-subtle);
        margin-top: auto;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .ok-avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--neon-green), var(--accent-blue));
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.82rem;
        font-weight: 800;
        color: #000;
        flex-shrink: 0;
    }
    .ok-avatar-info {
        flex: 1;
        min-width: 0;
    }
    .ok-avatar-name {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .ok-avatar-plan {
        font-size: 0.62rem;
        color: var(--neon-green);
        font-weight: 600;
        letter-spacing: 0.04em;
    }

    /* ====== METRIC CARDS (Pro Dashboard) ====== */
    .ok-metric-row {
        display: grid;
        gap: 14px;
        margin-bottom: 18px;
    }
    .ok-cols-3 { grid-template-columns: repeat(3, 1fr); }
    .ok-cols-4 { grid-template-columns: repeat(4, 1fr); }
    .ok-cols-5 { grid-template-columns: repeat(5, 1fr); }
    .ok-cols-6 { grid-template-columns: repeat(6, 1fr); }
    @media (max-width: 768px) {
        .ok-metric-row { grid-template-columns: repeat(2, 1fr) !important; }
    }

    .ok-metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 20px 22px 16px;
        display: flex;
        flex-direction: column;
        gap: 2px;
        transition: all 0.25s cubic-bezier(.4,0,.2,1);
        position: relative;
        overflow: hidden;
        min-height: 100px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    .ok-metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, #00ff88, #10b981);
        opacity: 0;
        transition: opacity 0.25s ease;
    }
    .ok-metric-card:hover {
        border-color: rgba(0,255,136,0.25);
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.45), 0 0 24px rgba(0,255,136,0.08);
    }
    .ok-metric-card:hover::before { opacity: 1; }

    .ok-metric-title {
        color: #94a3b8;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .ok-metric-value {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 700;
        font-family: var(--font-mono);
        line-height: 1.15;
        letter-spacing: -0.02em;
    }
    .ok-metric-delta {
        font-size: 0.8rem;
        font-weight: 700;
        font-family: var(--font-mono);
        display: inline-flex;
        align-items: center;
        gap: 3px;
        margin-top: 4px;
    }
    .ok-delta-up  { color: #00ff88; text-shadow: 0 0 8px rgba(0,255,136,0.3); }
    .ok-delta-down { color: #ef4444; text-shadow: 0 0 8px rgba(239,68,68,0.3); }
    .ok-metric-sparkline {
        margin-top: 8px;
        height: 32px;
        width: 100%;
        opacity: 0.9;
    }
    .ok-metric-sparkline-plotly {
        margin-top: 6px;
    }

    /* Legacy st.metric fallback */
    div[data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 16px 20px;
        box-shadow: var(--shadow-card);
    }
    div[data-testid="stMetric"] label {
        color: var(--text-muted) !important;
        font-size: 0.72rem !important;
        text-transform: uppercase;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-size: 1.5rem !important;
        font-family: var(--font-mono) !important;
    }

    /* ====== ALERT PRIORITY ====== */
    .alerta-top {
        background: linear-gradient(135deg, rgba(0, 255, 136, 0.06), rgba(6, 78, 59, 0.2));
        border: 1px solid rgba(0, 255, 136, 0.2);
        border-left: 4px solid var(--neon-green);
        padding: 16px 20px;
        border-radius: var(--radius-md);
        margin-bottom: 10px;
        color: #f0fdf4;
        box-shadow: 0 0 30px rgba(0, 255, 136, 0.08), var(--shadow-card);
        position: relative;
        transition: all 0.15s ease;
    }
    .alerta-top:hover { transform: translateX(3px); box-shadow: 0 0 40px rgba(0, 255, 136, 0.12), var(--shadow-card); }
    .alerta-top::after {
        content: '\2605  TOP PRIMA';
        position: absolute; top: 10px; right: 14px;
        background: linear-gradient(135deg, var(--neon-green), #059669);
        color: #000; padding: 3px 12px; border-radius: 20px;
        font-size: 0.62rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase;
    }
    .alerta-principal {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.06), rgba(127, 29, 29, 0.15));
        border: 1px solid rgba(239, 68, 68, 0.18);
        border-left: 4px solid var(--accent-red);
        padding: 16px 20px;
        border-radius: var(--radius-md);
        margin-bottom: 10px;
        color: #fef2f2;
        box-shadow: var(--shadow-card);
        transition: all 0.15s ease;
    }
    .alerta-principal:hover { transform: translateX(3px); }
    .alerta-prima {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.06), rgba(120, 53, 15, 0.12));
        border: 1px solid rgba(245, 158, 11, 0.15);
        border-left: 4px solid var(--accent-orange);
        padding: 16px 20px;
        border-radius: var(--radius-md);
        margin-bottom: 10px;
        color: #fffbeb;
        box-shadow: var(--shadow-card);
        transition: all 0.15s ease;
    }
    .alerta-prima:hover { transform: translateX(3px); }
    .leyenda-colores {
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .leyenda-item { display: block; margin-bottom: 5px; font-size: 0.78rem; line-height: 1.5; color: #cbd5e1; }
    .leyenda-item b { color: var(--text-primary); }
    .dot-green { color: var(--neon-green); font-size: 1.1rem; }
    .dot-red { color: var(--accent-red); font-size: 1.1rem; }
    .dot-orange { color: var(--accent-orange); font-size: 1.1rem; }
    .dot-purple { color: var(--accent-purple); font-size: 1.1rem; }
    .razon-alerta {
        display: inline-block;
        background: rgba(255,255,255,0.04);
        padding: 4px 12px; border-radius: 6px;
        font-size: 0.70rem; margin-top: 6px;
        color: var(--text-secondary);
        font-family: var(--font-mono);
        letter-spacing: 0.01em;
    }

    /* ====== HEADER ====== */
    .scanner-header {
        background: linear-gradient(135deg, #070b11 0%, #0f172a 50%, #1e293b 100%);
        padding: 28px 36px;
        border-radius: var(--radius-lg);
        margin-bottom: 24px;
        border: 1px solid var(--border-subtle);
        box-shadow: var(--shadow-card);
        position: relative;
        overflow: hidden;
    }
    .scanner-header::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--neon-green), var(--accent-blue), var(--accent-purple));
    }
    .scanner-header h1 {
        margin: 0; color: var(--text-primary);
        font-weight: 800; font-size: 1.8rem; letter-spacing: -0.03em;
    }
    .scanner-header .subtitle {
        margin: 6px 0 0 0; color: var(--text-muted);
        font-size: 0.92rem; font-weight: 400;
    }
    .scanner-header .badge {
        display: inline-block;
        background: var(--neon-green); color: #000;
        padding: 4px 16px; border-radius: 20px;
        font-size: 0.68rem; font-weight: 800;
        letter-spacing: 0.06em; text-transform: uppercase;
        margin-top: 10px;
        box-shadow: 0 0 12px rgba(0, 255, 136, 0.25);
    }

    /* ====== TABS ====== */
    .stTabs [data-baseweb="tab-list"] {
        display: flex; flex-wrap: wrap; gap: 2px;
        background: var(--bg-card);
        border-radius: var(--radius-md);
        padding: 4px;
        border: 1px solid var(--border-default);
        box-shadow: var(--shadow-card);
        overflow-x: auto; scrollbar-width: none;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    .stTabs [data-baseweb="tab"] {
        position: relative; padding: 10px 20px;
        border-radius: var(--radius-sm);
        font-family: var(--font-sans);
        font-weight: 500; font-size: 0.82rem;
        color: var(--text-secondary);
        letter-spacing: 0.01em;
        white-space: nowrap; cursor: pointer;
        user-select: none; transition: all 0.2s ease;
        border: 1px solid transparent; outline: none;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text-primary);
        background: rgba(0, 255, 136, 0.05);
        border-color: rgba(0, 255, 136, 0.08);
    }
    .stTabs [data-baseweb="tab"]:focus-visible {
        outline: 2px solid var(--neon-green);
        outline-offset: 2px;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(0, 255, 136, 0.08) !important;
        color: var(--neon-green) !important;
        font-weight: 600;
        border-color: rgba(0, 255, 136, 0.15) !important;
        box-shadow: 0 0 12px rgba(0, 255, 136, 0.08);
    }
    .stTabs [aria-selected="true"]::after {
        content: ''; position: absolute;
        bottom: 2px; left: 50%; transform: translateX(-50%);
        width: 40%; height: 2px; border-radius: 2px;
        background: var(--neon-green);
        box-shadow: 0 0 8px rgba(0, 255, 136, 0.3);
        animation: tabIndicatorIn 0.25s ease forwards;
    }
    @keyframes tabIndicatorIn {
        from { width: 0%; opacity: 0; }
        to { width: 40%; opacity: 1; }
    }
    .stTabs [data-baseweb="tab-panel"] {
        animation: tabFadeIn 0.3s ease forwards;
    }
    @keyframes tabFadeIn {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ====== BUTTONS ====== */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--neon-green), #059669) !important;
        color: #000 !important; border: none !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 700 !important; letter-spacing: 0.03em;
        padding: 10px 24px !important;
        box-shadow: 0 4px 16px rgba(0, 255, 136, 0.2) !important;
        transition: all 0.2s ease !important;
        text-transform: uppercase; font-size: 0.78rem !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 24px rgba(0, 255, 136, 0.35) !important;
        transform: translateY(-1px);
    }
    .stButton > button {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-default) !important;
        color: var(--text-secondary) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        border-color: var(--neon-green) !important;
        color: var(--neon-green) !important;
        background: rgba(0, 255, 136, 0.04) !important;
    }

    /* ====== CHARTS ====== */
    [data-testid="stVegaLiteChart"] {
        max-height: 420px; overflow-y: auto;
        border-radius: var(--radius-md);
        scrollbar-width: thin;
        scrollbar-color: rgba(148, 163, 184, 0.15) transparent;
    }
    [data-testid="stVegaLiteChart"]::-webkit-scrollbar { width: 5px; }
    [data-testid="stVegaLiteChart"]::-webkit-scrollbar-track { background: transparent; }
    [data-testid="stVegaLiteChart"]::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.2); border-radius: 3px;
    }

    /* ====== PRO DATAFRAMES ====== */
    .stDataFrame {
        border-radius: 14px !important;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.06) !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    }
    .stDataFrame [data-testid="glideDataEditor"] {
        background: #0c1018 !important;
    }
    /* header row */
    .stDataFrame [data-testid="glideDataEditor"] .dvn-scroller .header-menu,
    .stDataFrame [data-testid="glideDataEditor"] header {
        background: #0a0e16 !important;
    }

    /* ====== HTML PRO TABLE (ok-table) ====== */
    .ok-table-wrap {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        margin-bottom: 18px;
    }
    .ok-table-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 14px 20px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .ok-table-title {
        font-size: 0.82rem; font-weight: 700; color: #e2e8f0;
        display: flex; align-items: center; gap: 8px;
    }
    .ok-table-badge {
        font-size: 0.62rem; font-weight: 600;
        padding: 2px 10px; border-radius: 40px;
        background: rgba(0,255,136,0.08); color: var(--neon-green);
        border: 1px solid rgba(0,255,136,0.15);
    }
    .ok-tbl {
        width: 100%; border-collapse: separate; border-spacing: 0;
        font-family: var(--font-mono);
        font-size: 0.78rem;
    }
    .ok-tbl thead th {
        background: #0f172a;
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 12px 14px;
        text-align: left;
        border-bottom: 1px solid #334155;
        white-space: nowrap;
        position: sticky; top: 0; z-index: 2;
    }
    .ok-tbl tbody tr {
        transition: background 0.18s ease;
    }
    .ok-tbl tbody tr:nth-child(even) {
        background: rgba(255,255,255,0.025);
    }
    .ok-tbl tbody tr:nth-child(odd) {
        background: transparent;
    }
    .ok-tbl tbody tr:hover {
        background: #334155 !important;
    }
    .ok-tbl tbody td {
        padding: 10px 14px;
        color: #e2e8f0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        white-space: nowrap;
    }
    /* Ticker column bold */
    .ok-tbl td.td-ticker {
        color: #f1f5f9; font-weight: 700;
    }
    /* Numeric values */
    .ok-tbl td.td-num {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    /* Badges */
    .ok-badge {
        display: inline-flex; align-items: center; gap: 3px;
        font-size: 0.72rem; font-weight: 700;
        padding: 2px 8px; border-radius: 6px;
        line-height: 1.4;
    }
    .ok-badge-bull {
        background: rgba(0,255,136,0.1); color: #00ff88;
        border: 1px solid rgba(0,255,136,0.2);
    }
    .ok-badge-bear {
        background: rgba(239,68,68,0.1); color: #ef4444;
        border: 1px solid rgba(239,68,68,0.2);
    }
    .ok-badge-neutral {
        background: rgba(148,163,184,0.1); color: #94a3b8;
        border: 1px solid rgba(148,163,184,0.15);
    }
    .ok-badge-call {
        background: rgba(59,130,246,0.1); color: #60a5fa;
        border: 1px solid rgba(59,130,246,0.2);
    }
    .ok-badge-put {
        background: rgba(245,158,11,0.1); color: #fbbf24;
        border: 1px solid rgba(245,158,11,0.2);
    }
    .ok-badge-cluster {
        background: rgba(139,92,246,0.1); color: #a78bfa;
        border: 1px solid rgba(139,92,246,0.2);
    }
    .ok-badge-top {
        background: rgba(0,255,136,0.12); color: #00ff88;
        border: 1px solid rgba(0,255,136,0.25);
    }
    .ok-badge-inst {
        background: rgba(239,68,68,0.12); color: #ef4444;
        border: 1px solid rgba(239,68,68,0.25);
    }
    .ok-badge-prima {
        background: rgba(245,158,11,0.12); color: #fbbf24;
        border: 1px solid rgba(245,158,11,0.25);
    }
    /* Up/Down delta arrows in cells */
    .ok-up { color: #00ff88; }
    .ok-down { color: #ef4444; }
    .ok-muted { color: #475569; }
    /* Scroll container for large tables */
    .ok-table-scroll {
        max-height: 520px;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: rgba(148,163,184,0.15) transparent;
    }
    .ok-table-scroll::-webkit-scrollbar { width: 5px; }
    .ok-table-scroll::-webkit-scrollbar-track { background: transparent; }
    .ok-table-scroll::-webkit-scrollbar-thumb { background: rgba(148,163,184,0.15); border-radius: 3px; }
    .ok-table-footer {
        padding: 8px 20px;
        border-top: 1px solid rgba(255,255,255,0.05);
        font-size: 0.7rem; color: #475569;
    }

    /* ====== EXPANDER ====== */
    .stExpander {
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-md) !important;
        background: var(--bg-card) !important;
    }
    .stExpander [data-testid="stExpanderToggleIcon"] {
        color: var(--neon-green) !important;
    }

    /* ====== INPUTS ====== */
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div {
        background: var(--bg-card) !important;
        border-color: var(--border-default) !important;
        border-radius: var(--radius-sm) !important;
    }
    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="input"] > div:focus-within {
        border-color: var(--neon-green) !important;
        box-shadow: 0 0 0 2px rgba(0, 255, 136, 0.1) !important;
    }

    /* ====== STATUS BAR ====== */
    .status-bar {
        display: flex; align-items: center; gap: 14px;
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 10px 18px; margin-bottom: 14px;
        font-size: 0.78rem; color: var(--text-secondary);
    }
    .status-bar .status-dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--neon-green);
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
        animation: pulse-neon 2s ease-in-out infinite;
    }
    @keyframes pulse-neon {
        0%, 100% { opacity: 1; box-shadow: 0 0 10px rgba(0, 255, 136, 0.5); }
        50% { opacity: 0.6; box-shadow: 0 0 20px rgba(0, 255, 136, 0.8); }
    }
    .section-title {
        font-family: var(--font-sans);
        font-size: 1.1rem; font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 10px; padding-bottom: 8px;
        border-bottom: 1px solid var(--border-subtle);
    }
    .info-card {
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 18px 22px;
        box-shadow: var(--shadow-card);
    }

    /* ====== CLUSTER ====== */
    .alerta-cluster {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.06), rgba(76, 29, 149, 0.15));
        border: 1px solid rgba(139, 92, 246, 0.18);
        border-left: 4px solid var(--accent-purple);
        padding: 16px 20px;
        border-radius: var(--radius-md);
        margin-bottom: 10px;
        color: #f5f3ff;
        box-shadow: var(--shadow-card);
        transition: all 0.15s ease;
    }
    .alerta-cluster:hover { transform: translateX(3px); }
    .cluster-badge {
        display: inline-block;
        background: linear-gradient(135deg, var(--accent-purple), #7c3aed);
        color: #fff; padding: 3px 10px; border-radius: 20px;
        font-size: 0.65rem; font-weight: 700;
        letter-spacing: 0.05em; text-transform: uppercase;
        margin-left: 8px;
    }
    .cluster-detail {
        background: rgba(139, 92, 246, 0.06);
        border: 1px solid rgba(139, 92, 246, 0.1);
        border-radius: var(--radius-sm);
        padding: 10px 14px; margin-top: 8px;
        font-size: 0.75rem; color: #c4b5fd;
        font-family: var(--font-mono);
    }

    /* ====== EMPRESA CARDS ====== */
    .empresa-card {
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 20px 24px;
        margin-bottom: 12px;
        box-shadow: var(--shadow-card);
        transition: all 0.2s ease;
    }
    .empresa-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-card), 0 8px 32px rgba(0,0,0,0.2);
        border-color: var(--border-hover);
    }
    .empresa-card-bull { border-left: 4px solid var(--neon-green); }
    .empresa-card-neutral { border-left: 4px solid var(--accent-orange); }
    .empresa-card-bear { border-left: 4px solid var(--accent-red); }
    .empresa-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
    .empresa-ticker { font-size: 1.4rem; font-weight: 800; color: var(--text-primary); font-family: var(--font-mono); }
    .empresa-nombre { font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px; }
    .empresa-desc {
        font-size: 0.75rem; color: #cbd5e1; margin: 8px 0; line-height: 1.5;
        padding: 10px 14px;
        background: rgba(0, 255, 136, 0.03);
        border-radius: var(--radius-sm);
        border: 1px solid rgba(0, 255, 136, 0.06);
    }
    .empresa-metrics { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .empresa-metric {
        background: var(--bg-base);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-sm);
        padding: 10px 14px; min-width: 115px; text-align: center;
    }
    .empresa-metric-label {
        font-size: 0.60rem; color: var(--text-muted);
        text-transform: uppercase; letter-spacing: 0.06em;
    }
    .empresa-metric-value {
        font-size: 0.95rem; font-weight: 700;
        font-family: var(--font-mono); color: var(--text-primary);
    }
    .empresa-score {
        display: inline-block; padding: 4px 14px; border-radius: 20px;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em;
    }
    .score-alta { background: var(--neon-green); color: #000; box-shadow: 0 0 8px rgba(0, 255, 136, 0.3); }
    .score-media { background: linear-gradient(135deg, var(--accent-orange), #d97706); color: #fff; }
    .score-baja { background: linear-gradient(135deg, var(--accent-red), #dc2626); color: #fff; }
    .empresa-card-emergente { border-left: 4px solid var(--accent-cyan); position: relative; }
    .empresa-card-emergente::after {
        content: '🚀'; position: absolute; top: 12px; right: 16px;
        font-size: 1.3rem; opacity: 0.25;
    }
    .emergente-badge {
        display: inline-block;
        background: linear-gradient(135deg, var(--accent-cyan), #0891b2);
        color: #fff; padding: 3px 10px; border-radius: 20px;
        font-size: 0.60rem; font-weight: 700;
        letter-spacing: 0.05em; text-transform: uppercase;
        margin-left: 8px;
    }
    .por-que-grande {
        background: rgba(6, 182, 212, 0.04);
        border: 1px solid rgba(6, 182, 212, 0.1);
        border-radius: var(--radius-sm);
        padding: 12px 16px; margin-top: 10px;
        font-size: 0.72rem; color: #67e8f9; line-height: 1.6;
    }
    .watchlist-info {
        background: var(--accent-blue-dim);
        border: 1px solid rgba(59, 130, 246, 0.12);
        border-radius: var(--radius-md);
        padding: 14px 20px; margin-bottom: 16px;
        font-size: 0.78rem; color: #93c5fd;
    }

    /* ====== NEWS ====== */
    .news-container { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
    .news-card {
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-left: 3px solid var(--accent-blue);
        border-radius: var(--radius-md);
        padding: 14px 18px;
        transition: all 0.2s ease;
    }
    .news-card:hover {
        background: var(--bg-card-hover);
        border-color: var(--border-hover);
        transform: translateX(2px);
    }
    .news-card.news-earnings { border-left-color: var(--accent-orange); }
    .news-card.news-fed { border-left-color: var(--accent-red); }
    .news-card.news-economy { border-left-color: var(--accent-green); }
    .news-card.news-crypto { border-left-color: var(--accent-purple); }
    .news-card.news-commodities { border-left-color: #f97316; }
    .news-card.news-geopolitics { border-left-color: #ec4899; }
    .news-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
    .news-title {
        font-family: var(--font-sans); font-size: 0.88rem; font-weight: 600;
        color: #e2e8f0; line-height: 1.4; flex: 1;
    }
    .news-title a { color: #e2e8f0; text-decoration: none; }
    .news-title a:hover { color: var(--neon-green); text-decoration: underline; }
    .news-meta {
        display: flex; align-items: center; gap: 10px;
        margin-top: 6px; font-size: 0.70rem; color: var(--text-muted);
    }
    .news-source {
        display: inline-block; background: var(--accent-blue-dim);
        color: #60a5fa; padding: 2px 8px; border-radius: 6px;
        font-size: 0.65rem; font-weight: 600;
    }
    .news-time { color: var(--text-muted); font-size: 0.68rem; }
    .news-category-badge {
        display: inline-block; padding: 2px 8px; border-radius: 10px;
        font-size: 0.58rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.04em;
    }
    .news-cat-earnings { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }
    .news-cat-fed { background: rgba(239, 68, 68, 0.12); color: #f87171; }
    .news-cat-economy { background: rgba(16, 185, 129, 0.12); color: #34d399; }
    .news-cat-crypto { background: rgba(139, 92, 246, 0.12); color: #a78bfa; }
    .news-cat-commodities { background: rgba(249, 115, 22, 0.12); color: #fb923c; }
    .news-cat-geopolitics { background: rgba(236, 72, 153, 0.12); color: #f472b6; }
    .news-cat-markets { background: var(--accent-blue-dim); color: #60a5fa; }
    .news-cat-trading { background: rgba(6, 182, 212, 0.12); color: #22d3ee; }
    .news-desc { font-size: 0.75rem; color: var(--text-secondary); margin-top: 6px; line-height: 1.5; }
    .news-refresh-bar {
        display: flex; align-items: center; gap: 14px;
        background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 10px 18px; margin-bottom: 14px;
        font-size: 0.78rem; color: var(--text-secondary);
    }
    .news-refresh-bar .refresh-dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--accent-cyan);
        box-shadow: 0 0 8px rgba(6, 182, 212, 0.5);
        animation: pulse-neon 2s ease-in-out infinite;
    }
    .news-stats { display: flex; gap: 12px; margin-bottom: 14px; }
    .news-stat-card {
        flex: 1; background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 14px 16px; text-align: center;
    }
    .news-stat-number { font-family: var(--font-mono); font-size: 1.2rem; font-weight: 700; color: var(--text-primary); }
    .news-stat-label { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }

    /* ====== RANGO ====== */
    .rango-card {
        background: linear-gradient(135deg, rgba(0, 255, 136, 0.04), rgba(6, 78, 130, 0.12));
        border: 1px solid rgba(0, 255, 136, 0.1);
        border-radius: var(--radius-lg);
        padding: 22px 26px; margin-bottom: 14px;
        box-shadow: var(--shadow-card);
    }
    .rango-titulo { font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
    .rango-subtitulo { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 16px; }
    .rango-barra-container {
        position: relative; background: var(--bg-base);
        border-radius: var(--radius-md); height: 52px;
        margin: 18px 0; border: 1px solid var(--border-subtle);
        overflow: visible;
    }
    .rango-barra-fill { position: absolute; top: 0; height: 100%; border-radius: var(--radius-md); }
    .rango-barra-down {
        left: 0;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.3), rgba(239, 68, 68, 0.05));
        border-right: 2px solid rgba(239, 68, 68, 0.4);
    }
    .rango-barra-up {
        right: 0;
        background: linear-gradient(90deg, rgba(0, 255, 136, 0.05), rgba(0, 255, 136, 0.25));
        border-left: 2px solid rgba(0, 255, 136, 0.4);
    }
    .rango-precio-actual {
        position: absolute; top: -8px; transform: translateX(-50%);
        background: var(--neon-green); color: #000;
        padding: 2px 10px; border-radius: 8px;
        font-size: 0.68rem; font-weight: 800;
        font-family: var(--font-mono);
        white-space: nowrap; z-index: 10;
        box-shadow: 0 2px 8px rgba(0, 255, 136, 0.3);
    }
    .rango-label-low {
        position: absolute; bottom: -20px; left: 8px;
        font-size: 0.68rem; color: var(--accent-red);
        font-weight: 600; font-family: var(--font-mono);
    }
    .rango-label-high {
        position: absolute; bottom: -20px; right: 8px;
        font-size: 0.68rem; color: var(--neon-green);
        font-weight: 600; font-family: var(--font-mono);
    }
    .rango-stat {
        display: inline-block; background: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: 12px 18px; margin: 4px 4px 4px 0;
        min-width: 130px; text-align: center;
    }
    .rango-stat-label {
        font-size: 0.65rem; color: var(--text-secondary);
        text-transform: uppercase; letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .rango-stat-value { font-size: 1.2rem; font-weight: 700; font-family: var(--font-mono); }
    .rango-stat-value.up { color: var(--neon-green); }
    .rango-stat-value.down { color: var(--accent-red); }
    .rango-stat-value.neutral { color: var(--accent-blue); }
    .rango-info {
        background: rgba(0, 255, 136, 0.04);
        border: 1px solid rgba(0, 255, 136, 0.08);
        border-radius: var(--radius-sm);
        padding: 12px 16px; margin-top: 14px;
        font-size: 0.75rem; color: #7dd3fc;
    }

    /* ====== SENTIMIENTO BADGES ====== */
    .badge-alcista {
        display: inline-block;
        background: rgba(0, 255, 136, 0.12); color: var(--neon-green);
        padding: 3px 10px; border-radius: 6px;
        font-size: 0.68rem; font-weight: 700;
        font-family: var(--font-mono);
        border: 1px solid rgba(0, 255, 136, 0.2);
    }
    .badge-bajista {
        display: inline-block;
        background: var(--accent-red-dim); color: var(--accent-red);
        padding: 3px 10px; border-radius: 6px;
        font-size: 0.68rem; font-weight: 700;
        font-family: var(--font-mono);
        border: 1px solid rgba(239, 68, 68, 0.2);
    }
    .badge-neutral {
        display: inline-block;
        background: rgba(148, 163, 184, 0.1); color: var(--text-secondary);
        padding: 3px 10px; border-radius: 6px;
        font-size: 0.68rem; font-weight: 700;
        font-family: var(--font-mono);
        border: 1px solid var(--border-default);
    }

    /* ====== FOOTER ====== */
    .footer-pro {
        text-align: center; padding: 20px 0 8px 0;
        color: var(--text-dim); font-size: 0.72rem;
        letter-spacing: 0.02em;
    }
    .footer-pro a { color: var(--text-muted); text-decoration: none; }
    .footer-pro .footer-badges { margin-top: 8px; }
    .footer-pro .footer-badge {
        display: inline-block; background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        padding: 3px 10px; border-radius: 6px;
        font-size: 0.62rem; margin: 0 3px;
        color: var(--text-muted);
    }

    /* ====== SENTIMIENTO DESGLOSE ====== */
    .sp0{background:var(--bg-card);border:1px solid var(--border-default);border-radius:var(--radius-lg);padding:20px 24px;margin-bottom:14px;box-shadow:var(--shadow-card)}
    .tt{font-size:1.05rem;font-weight:700;color:var(--text-primary);margin-bottom:4px}
    .ts{font-size:0.72rem;color:var(--text-muted);margin-bottom:14px}
    .sr{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border-subtle)}
    .sr:last-of-type{border-bottom:none}
    .sl{min-width:120px}
    .slt{font-size:0.78rem;font-weight:600;color:var(--text-primary)}
    .sld{font-size:0.62rem;color:var(--text-muted)}
    .sa{flex:0 0 90px;text-align:right;font-family:var(--font-mono);font-weight:700;font-size:0.82rem}
    .sb{flex:1;position:relative;height:22px;border-radius:6px;background:var(--bg-base);overflow:hidden}
    .sm{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--border-default);z-index:1}
    .sf{position:absolute;top:0;height:100%;min-width:2px;transition:width .3s ease}
    .sp{flex:0 0 60px;text-align:right;font-family:var(--font-mono);font-size:0.72rem;font-weight:600}
    .g{color:var(--neon-green)}.r{color:var(--accent-red)}
    .sn{margin-top:14px;padding-top:12px;border-top:1px solid var(--border-default)}
    .snr{display:flex;align-items:center;gap:12px}
    .snl{min-width:120px}
    .snt{font-size:0.82rem;font-weight:700}
    .snd{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em}
    .ssum{display:flex;justify-content:space-around;margin-top:14px;padding:12px;background:var(--bg-base);border-radius:var(--radius-sm);border:1px solid var(--border-subtle)}
    .ssi{text-align:center}
    .ssh{font-size:0.68rem;color:var(--text-muted);margin-bottom:4px}
    .ssv{font-family:var(--font-mono);font-weight:700;font-size:1rem}
    .ssp{font-family:var(--font-mono);font-size:0.72rem;font-weight:600;margin-top:2px}
    .gy{color:var(--text-secondary)}.w{color:var(--text-primary)}
    .nc{color:var(--neon-green)}

    /* ====== OKA SENTIMENT GAUGE ====== */
    .gauge-container {
        display: flex; flex-direction: column; align-items: center;
        background: linear-gradient(145deg, #0f1520, #131a2a);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 18px;
        padding: 32px 28px 24px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        position: relative;
        max-width: 340px;
        margin: 0 auto;
    }
    .gauge-container::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--neon-green), var(--accent-blue));
        border-radius: 18px 18px 0 0;
        opacity: 0.6;
    }
    .gauge-header {
        display: flex; align-items: center; gap: 8px;
        margin-bottom: 20px;
        align-self: flex-start;
    }
    .gauge-header-icon {
        width: 22px; height: 22px;
        background: linear-gradient(135deg, var(--neon-green), var(--accent-blue));
        border-radius: 6px;
        display: flex; align-items: center; justify-content: center;
    }
    .gauge-title {
        font-size: 0.78rem; color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.08em;
    }
    .gauge-wrap {
        position: relative;
        width: 220px; height: 130px;
        display: flex; align-items: center; justify-content: center;
    }
    .gauge-svg {
        width: 220px; height: 130px;
        overflow: visible;
    }
    .gauge-track {
        fill: none;
        stroke: rgba(255,255,255,0.04);
        stroke-width: 18;
        stroke-linecap: round;
    }
    .gauge-arc {
        fill: none;
        stroke-width: 18;
        stroke-linecap: round;
        transition: stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1);
        filter: drop-shadow(0 0 8px rgba(0,255,136,0.25));
    }
    .gauge-tick-labels {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        fill: #475569;
        font-weight: 500;
    }
    .gauge-center {
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -20%);
        text-align: center;
    }
    .gauge-value {
        font-family: var(--font-mono);
        font-size: 2.8rem;
        font-weight: 800;
        color: #f1f5f9;
        line-height: 1;
        letter-spacing: -0.03em;
    }
    .gauge-label {
        font-size: 0.82rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.12em;
        margin-top: 4px;
    }
    .gauge-label.bullish { color: var(--neon-green); text-shadow: 0 0 12px rgba(0,255,136,0.3); }
    .gauge-label.bearish { color: var(--accent-red); text-shadow: 0 0 12px rgba(239,68,68,0.3); }
    .gauge-label.neutral { color: var(--accent-orange); text-shadow: 0 0 12px rgba(245,158,11,0.3); }
    .gauge-footer {
        display: flex; justify-content: space-between; width: 100%;
        margin-top: 18px; padding-top: 14px;
        border-top: 1px solid rgba(255,255,255,0.05);
    }
    .gauge-stat {
        display: flex; flex-direction: column; align-items: center; gap: 2px;
    }
    .gauge-stat-label {
        font-size: 0.62rem; color: #475569;
        text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;
    }
    .gauge-stat-val {
        font-family: var(--font-mono); font-size: 0.88rem; font-weight: 700;
    }
    .gauge-stat-val.g { color: var(--neon-green); }
    .gauge-stat-val.r { color: var(--accent-red); }
    .gauge-stat-val.w { color: #f1f5f9; }

    /* ====== SCROLLBAR GLOBAL ====== */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.15); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.25); }

    /* ====== RESPONSIVE ====== */
    .stMain, section[data-testid="stMain"],
    [data-testid="stAppViewBlockContainer"],
    .stMainBlockContainer {
        transition: margin-left 0.3s ease, width 0.3s ease !important;
        max-width: 100% !important;
    }
    @media (max-width: 1024px) {
        .scanner-header h1 { font-size: 1.5rem !important; }
        .scanner-header .subtitle { font-size: 0.82rem; }
        div[data-testid="stMetric"] { padding: 14px 16px; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
        .empresa-card { padding: 16px 18px; }
        .empresa-ticker { font-size: 1.2rem; }
        .empresa-metric { min-width: 100px; padding: 8px 12px; }
        .rango-stat { min-width: 100px; padding: 10px 14px; }
        .rango-stat-value { font-size: 1rem; }
        .news-stat-card { padding: 10px 12px; }
        .news-stat-number { font-size: 1rem; }
        .gauge-wrap { width: 180px; height: 110px; }
        .gauge-svg { width: 180px; height: 110px; }
        .gauge-value { font-size: 2.2rem; }
    }
    @media (max-width: 768px) {
        .stMainBlockContainer, .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-left: 6px !important; padding-right: 6px !important;
        }
        .scanner-header { padding: 14px !important; border-radius: var(--radius-md) !important; }
        .scanner-header h1 { font-size: 1.2rem !important; }
        .scanner-header .subtitle { font-size: 0.75rem; }
        .scanner-header .badge { font-size: 0.58rem; padding: 3px 10px; }
        [data-testid="column"] { min-width: 45% !important; }
        div[data-testid="stMetric"] { padding: 12px 14px; border-radius: var(--radius-sm); }
        div[data-testid="stMetric"] label { font-size: 0.65rem !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        .status-bar { flex-wrap: wrap; gap: 8px; padding: 8px 12px; font-size: 0.70rem; }
        .stTabs [data-baseweb="tab-list"] { gap: 2px; padding: 3px; border-radius: var(--radius-sm); overflow-x: auto; scrollbar-width: none; }
        .stTabs [data-baseweb="tab"]::-webkit-scrollbar { display: none; }
        .stTabs [data-baseweb="tab"] { padding: 8px 10px; font-size: 0.70rem; min-width: fit-content; }
        .alerta-top, .alerta-principal, .alerta-prima, .alerta-cluster { padding: 12px 14px; font-size: 0.75rem; }
        .alerta-top::after { font-size: 0.52rem; padding: 2px 8px; top: 6px; right: 6px; }
        .razon-alerta { font-size: 0.65rem; }
        .cluster-detail { font-size: 0.68rem; }
        .leyenda-colores { padding: 10px 14px !important; }
        .leyenda-item { font-size: 0.68rem !important; }
        .empresa-card { padding: 14px 16px; }
        .empresa-ticker { font-size: 1.1rem; }
        .empresa-desc { font-size: 0.70rem; padding: 8px 12px; }
        .empresa-metrics { flex-direction: column; gap: 6px; }
        .empresa-metric { min-width: unset; width: 100%; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; }
        .empresa-header { flex-direction: column; gap: 6px; }
        .news-card { padding: 12px 14px; }
        .news-title { font-size: 0.80rem; }
        .news-desc { font-size: 0.70rem; }
        .news-meta { flex-wrap: wrap; gap: 6px; }
        .news-stats { flex-wrap: wrap; gap: 8px; }
        .news-stat-card { flex: 1 1 45%; min-width: 110px; }
        .rango-stat { min-width: unset; width: 100%; margin: 3px 0; display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; }
        .rango-stat-value { font-size: 0.95rem; }
        .watchlist-info { font-size: 0.72rem; padding: 12px 16px; }
        .stButton > button { width: 100% !important; font-size: 0.78rem !important; }
        .stExpander { border-radius: var(--radius-sm) !important; }
        .info-card { padding: 14px 16px; }
        .gauge-container { padding: 20px 16px; }
        .gauge-wrap { width: 160px; height: 100px; }
        .gauge-svg { width: 160px; height: 100px; }
        .gauge-value { font-size: 2rem; }
    }
    @media (max-width: 480px) {
        .stMainBlockContainer, .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-left: 4px !important; padding-right: 4px !important;
        }
        .scanner-header h1 { font-size: 1rem !important; }
        [data-testid="column"] { min-width: 100% !important; }
        div[data-testid="stMetric"] { padding: 10px 12px; }
        div[data-testid="stMetric"] label { font-size: 0.60rem !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1rem !important; }
        .stTabs [data-baseweb="tab-list"] { flex-wrap: nowrap; }
        .stTabs [data-baseweb="tab"] { padding: 6px 8px; font-size: 0.62rem; }
        .alerta-top::after { display: none; }
        .empresa-ticker { font-size: 0.95rem; }
        .empresa-score { font-size: 0.58rem; padding: 3px 8px; }
        .news-stat-card { flex: 1 1 100%; }
        .rango-barra-container { height: 40px; }
        .rango-precio-actual { font-size: 0.60rem; padding: 2px 6px; }
    }
    @media (max-height: 500px) and (orientation: landscape) {
        .scanner-header { padding: 8px 14px !important; }
        .scanner-header h1 { font-size: 1.1rem !important; margin: 0 !important; }
        div[data-testid="stMetric"] { padding: 8px 12px; }
    }
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        .stMain { margin-left: 0 !important; width: 100% !important; }
        .stButton, .stTabs [data-baseweb="tab-list"] { display: none !important; }
    }
</style>
"""
