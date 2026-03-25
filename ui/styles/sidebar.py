"""Estilos del sidebar."""
SIDEBAR_CSS = r"""
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

    /* ====== SIDEBAR RADIO NAV (Streamlit) ====== */
    section[data-testid="stSidebar"] [data-testid="stRadio"] > label {
        font-size: 0.6rem !important;
        font-weight: 700 !important;
        color: var(--text-dim) !important;
        text-transform: uppercase;
        letter-spacing: 0.10em;
        margin-bottom: 4px;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
        gap: 2px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label {
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: var(--radius-sm) !important;
        padding: 8px 14px !important;
        margin: 0 !important;
        transition: all 0.15s ease !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover {
        background: rgba(0, 255, 136, 0.04) !important;
        color: var(--text-primary) !important;
        border-color: rgba(0, 255, 136, 0.06) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-checked="true"],
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
        background: rgba(0, 255, 136, 0.08) !important;
        color: var(--neon-green) !important;
        font-weight: 600 !important;
        border-color: rgba(0, 255, 136, 0.12) !important;
        box-shadow: 0 0 12px rgba(0, 255, 136, 0.06) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p {
        color: inherit !important;
        font-size: inherit !important;
    }
    /* Hide radio circle indicator in sidebar nav */
    section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label > div:first-child {
        display: none !important;
    }

"""
