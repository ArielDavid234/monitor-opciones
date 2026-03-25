"""Buttons y charts."""
CHARTS_CSS = r"""
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
"""
