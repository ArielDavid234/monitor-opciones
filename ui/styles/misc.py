"""Header, tabs, expanders, inputs, misc y responsive."""
MISC_CSS = r"""
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

    /* ====== TWO-COLUMN DASHBOARD LAYOUT ====== */
    [data-testid="stColumns"] {
        gap: 18px;
    }
    [data-testid="stColumn"] {
        background: transparent;
    }

    /* ====== STREAMLIT DATAFRAME DARK ====== */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
    }

    /* ====== SELECTBOX & INPUTS DARK ====== */
    [data-testid="stSelectbox"] label,
    [data-testid="stNumberInput"] label {
        color: var(--text-secondary) !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
    }

    /* ====== DIVIDER / SEPARATOR ====== */
    hr {
        border-color: var(--border-subtle) !important;
        margin: 16px 0 !important;
    }

    /* ====== SUCCESS / INFO / WARNING MESSAGES ====== */
    [data-testid="stAlert"] {
        background: var(--bg-card) !important;
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        font-size: 0.82rem !important;
    }

    /* ====== EXPANDER DARK THEME ====== */
    [data-testid="stExpander"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }
    [data-testid="stExpander"] summary:hover {
        color: var(--neon-green) !important;
    }

    /* ====== RESPONSIVE BASE ====== */
    .stMain, section[data-testid="stMain"],
    [data-testid="stAppViewBlockContainer"],
    .stMainBlockContainer {
        transition: margin-left 0.3s ease, width 0.3s ease !important;
        max-width: 100% !important;
    }

    /* ──────────────────────────────────────────────────────────────────
       TABLET  (≤ 1024px)
       ────────────────────────────────────────────────────────────── */
    @media (max-width: 1024px) {
        .scanner-header h1 { font-size: 1.5rem !important; }
        .scanner-header .subtitle { font-size: 0.82rem; }
        div[data-testid="stMetric"] { padding: 14px 16px; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
        .empresa-card { padding: 16px 18px; }
        .empresa-ticker { font-size: 1.2rem; }
        .empresa-metric { min-width: 100px; padding: 8px 12px; }
        .empresa-metrics { grid-template-columns: repeat(3, 1fr) !important; }
        .rango-stat { min-width: 100px; padding: 10px 14px; }
        .rango-stat-value { font-size: 1rem; }
        .news-stat-card { padding: 10px 12px; }
        .news-stat-number { font-size: 1rem; }
        .gauge-wrap { width: 180px; height: 110px; }
        .gauge-svg { width: 180px; height: 110px; }
        .gauge-value { font-size: 2.2rem; }

        /* Metric cards: 3-col on tablet */
        .ok-metric-row {
            flex-wrap: wrap !important;
        }
        .ok-metric-card {
            flex: 1 1 calc(33% - 10px) !important;
            min-width: 140px !important;
        }
    }

    /* ──────────────────────────────────────────────────────────────────
       MOBILE  (≤ 768px)
       Comprehensive mobile layout: every component adapts.
       ────────────────────────────────────────────────────────────── */
    @media (max-width: 768px) {

        /* ── Global: prevent horizontal scroll ─────────────────────── */
        html, body,
        [data-testid="stAppViewContainer"],
        .stApp {
            overflow-x: hidden !important;
        }
        .stApp {
            padding: 0 !important;
        }
        .stMainBlockContainer, .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-left: 8px !important;
            padding-right: 8px !important;
            max-width: 100% !important;
        }

        /* ── Typography: readable on small screens ─────────────────── */
        h1 { font-size: 1.25rem !important; }
        h2 { font-size: 1.1rem !important; }
        h3 { font-size: 1rem !important; }
        h4 { font-size: 0.92rem !important; }
        .stMarkdown p, .stMarkdown li {
            font-size: 0.88rem !important;
            line-height: 1.55 !important;
        }
        .stCaption, [data-testid="stCaptionContainer"] {
            font-size: 0.72rem !important;
            line-height: 1.45 !important;
        }

        /* ── Sidebar: narrower, smooth collapse ────────────────────── */
        section[data-testid="stSidebar"] {
            width: 85vw !important;
            min-width: 260px !important;
            max-width: 320px !important;
        }
        section[data-testid="stSidebar"][aria-expanded="false"] {
            margin-left: -320px !important;
        }
        .ok-logo { padding: 16px 12px 12px 12px; }
        .ok-logo-text { font-size: 0.95rem; }
        .ok-nav-item { padding: 10px 12px; font-size: 0.82rem; }
        section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label {
            padding: 10px 12px !important;
            font-size: 0.84rem !important;
        }

        /* ── Header ────────────────────────────────────────────────── */
        .scanner-header {
            padding: 14px 16px !important;
            border-radius: var(--radius-md) !important;
            margin-bottom: 14px;
        }
        .scanner-header h1 { font-size: 1.2rem !important; }
        .scanner-header .subtitle { font-size: 0.75rem; }
        .scanner-header .badge { font-size: 0.58rem; padding: 3px 10px; }

        /* ── Columns: stack vertically ─────────────────────────────── */
        [data-testid="stColumns"] {
            flex-direction: column !important;
            gap: 8px !important;
        }
        [data-testid="stColumn"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        /* ── Buttons: full-width, touch-friendly (min 44px tap) ──── */
        .stButton > button {
            width: 100% !important;
            min-height: 44px !important;
            padding: 10px 16px !important;
            font-size: 0.82rem !important;
        }

        /* ── Inputs: touch-friendly sizes ──────────────────────────── */
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div {
            min-height: 44px !important;
        }
        .stSlider [data-baseweb="slider"] [role="slider"] {
            width: 24px !important;
            height: 24px !important;
        }
        .stSlider {
            padding: 0.5rem 0 !important;
        }
        [data-testid="stNumberInput"] input {
            min-height: 44px !important;
            font-size: 1rem !important;
        }
        [data-testid="stTextInput"] input {
            min-height: 44px !important;
            font-size: 1rem !important;
        }

        /* ── Metric cards: 2-col grid, compact ─────────────────────── */
        .ok-metric-row {
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 8px !important;
        }
        .ok-metric-card {
            min-width: 0 !important;
            padding: 12px 14px !important;
            min-height: 80px !important;
        }
        .ok-metric-value { font-size: 1.3rem !important; }
        .ok-metric-title { font-size: 0.68rem !important; }
        .ok-metric-delta { font-size: 0.72rem !important; }

        /* ── st.metric: compact ────────────────────────────────────── */
        div[data-testid="stMetric"] {
            padding: 12px 14px;
            border-radius: var(--radius-sm);
        }
        div[data-testid="stMetric"] label { font-size: 0.65rem !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }

        /* ── Tabs: scroll horizontally, touch pads ─────────────────── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            padding: 3px;
            border-radius: var(--radius-sm);
            overflow-x: auto;
            scrollbar-width: none;
            -webkit-overflow-scrolling: touch;
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 12px;
            font-size: 0.72rem;
            min-width: fit-content;
            min-height: 40px;
        }

        /* ── Plotly charts: full width, auto height ────────────────── */
        .js-plotly-plot,
        .js-plotly-plot .plotly,
        .js-plotly-plot .plot-container {
            width: 100% !important;
            max-width: 100vw !important;
        }
        .js-plotly-plot {
            min-height: 280px !important;
        }
        /* Plotly modebar: hide on touch (use pinch-zoom instead) */
        .js-plotly-plot .modebar { display: none !important; }

        /* ── Alerts: compact ───────────────────────────────────────── */
        .alerta-top, .alerta-principal, .alerta-prima, .alerta-cluster {
            padding: 12px 14px;
            font-size: 0.78rem;
        }
        .alerta-top::after { font-size: 0.52rem; padding: 2px 8px; top: 6px; right: 6px; }
        .razon-alerta { font-size: 0.65rem; }
        .cluster-detail { font-size: 0.68rem; }
        .leyenda-colores { padding: 10px 14px !important; }
        .leyenda-item { font-size: 0.68rem !important; }

        /* ── Tables: horizontal touch-scroll ───────────────────────── */
        .ok-table-wrap { border-radius: 10px; }
        .ok-table-scroll {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
        }
        .ok-tbl {
            min-width: 580px !important;
            font-size: 0.72rem !important;
        }
        .ok-tbl th, .ok-tbl td {
            padding: 7px 8px !important;
            white-space: nowrap !important;
        }
        .ok-table-header { padding: 10px 14px; }
        .ok-table-title { font-size: 0.78rem; }
        .ok-table-badge { font-size: 0.58rem; }

        /* ── Badges: smaller tap targets ───────────────────────────── */
        .ok-badge { font-size: 0.64rem !important; padding: 2px 6px !important; }

        /* ── Status bar ──────────────────────────────────────────── */
        .status-bar { flex-wrap: wrap; gap: 8px; padding: 8px 12px; font-size: 0.70rem; }

        /* ── Empresa cards: stacked metrics ────────────────────────── */
        .empresa-card { padding: 14px 16px; }
        .empresa-ticker { font-size: 1.1rem; }
        .empresa-desc { font-size: 0.70rem; padding: 8px 12px; }
        .empresa-header { flex-direction: column; gap: 6px; }
        .empresa-metrics {
            flex-direction: column; gap: 6px;
        }
        .empresa-metric {
            min-width: unset; width: 100%;
            padding: 8px 12px;
            display: flex; justify-content: space-between; align-items: center;
        }

        /* ── News: compact cards ───────────────────────────────────── */
        .news-card { padding: 12px 14px; }
        .news-title { font-size: 0.82rem; }
        .news-desc { font-size: 0.72rem; }
        .news-meta { flex-wrap: wrap; gap: 6px; }
        .news-stats { flex-wrap: wrap; gap: 8px; }
        .news-stat-card { flex: 1 1 45%; min-width: 110px; }

        /* ── Range: full-width stats ───────────────────────────────── */
        .rango-stat {
            min-width: unset; width: 100%; margin: 3px 0;
            display: flex; justify-content: space-between; align-items: center;
            padding: 10px 14px;
        }
        .rango-stat-value { font-size: 0.95rem; }
        .rango-barra-container { height: 44px; }

        /* ── Gauges: SVG + Plotly ──────────────────────────────────── */
        .gauge-container { padding: 18px 14px; max-width: 100%; }
        .gauge-wrap { width: 160px; height: 100px; }
        .gauge-svg { width: 160px; height: 100px; }
        .gauge-value { font-size: 2rem; }
        .gauge-footer { flex-wrap: wrap; gap: 8px; justify-content: center; }

        /* ── Sentiment breakdown: compact ──────────────────────────── */
        .sp0 { padding: 12px !important; }
        .sr { flex-wrap: wrap !important; gap: 4px !important; }
        .sa { flex: 0 0 70px; font-size: 0.78rem; }
        .sp { flex: 0 0 50px; font-size: 0.68rem; }

        /* ── Misc ──────────────────────────────────────────────────── */
        .watchlist-info { font-size: 0.72rem; padding: 12px 16px; }
        .stExpander { border-radius: var(--radius-sm) !important; }
        .info-card { padding: 14px 16px; }
        hr { margin: 10px 0 !important; }
        .footer-pro { padding: 12px 0 6px 0; font-size: 0.65rem; }
        .footer-pro .footer-badge { font-size: 0.56rem; margin: 0 2px; }
    }

    /* ──────────────────────────────────────────────────────────────────
       SMALL PHONE  (≤ 480px)
       ────────────────────────────────────────────────────────────── */
    @media (max-width: 480px) {
        .stMainBlockContainer, .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-left: 4px !important;
            padding-right: 4px !important;
        }
        .scanner-header h1 { font-size: 1rem !important; }
        .scanner-header { padding: 10px 12px !important; margin-bottom: 10px; }

        /* Stack metric cards to single column */
        .ok-metric-row {
            grid-template-columns: 1fr !important;
        }
        .ok-metric-value { font-size: 1.2rem !important; }

        /* st.metric */
        div[data-testid="stMetric"] { padding: 10px 12px; }
        div[data-testid="stMetric"] label { font-size: 0.60rem !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1rem !important; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] { flex-wrap: nowrap; }
        .stTabs [data-baseweb="tab"] { padding: 8px 8px; font-size: 0.65rem; }

        /* Alerts */
        .alerta-top::after { display: none; }

        /* Empresa cards */
        .empresa-ticker { font-size: 0.95rem; }
        .empresa-score { font-size: 0.58rem; padding: 3px 8px; }

        /* News */
        .news-stat-card { flex: 1 1 100%; }

        /* Range */
        .rango-barra-container { height: 38px; }
        .rango-precio-actual { font-size: 0.60rem; padding: 2px 6px; }

        /* Gauges */
        .gauge-container { padding: 14px 10px; }
        .gauge-wrap { width: 140px; height: 90px; }
        .gauge-svg { width: 140px; height: 90px; }
        .gauge-value { font-size: 1.7rem; }
        .gauge-label { font-size: 0.72rem; }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            width: 90vw !important;
            max-width: 300px !important;
        }
    }

    /* ──────────────────────────────────────────────────────────────────
       LANDSCAPE MOBILE  (short height)
       ────────────────────────────────────────────────────────────── */
    @media (max-height: 500px) and (orientation: landscape) {
        .scanner-header { padding: 8px 14px !important; }
        .scanner-header h1 { font-size: 1.1rem !important; margin: 0 !important; }
        div[data-testid="stMetric"] { padding: 8px 12px; }
        .ok-metric-card { padding: 8px 10px !important; min-height: 60px !important; }
        .gauge-container { padding: 12px 10px; }
    }

    /* ──────────────────────────────────────────────────────────────────
       PRINT
       ────────────────────────────────────────────────────────────── */
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        .stMain { margin-left: 0 !important; width: 100% !important; }
        .stButton, .stTabs [data-baseweb="tab-list"] { display: none !important; }
    }
"""
