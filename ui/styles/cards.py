"""Metric cards, alert priority y empresa cards."""
CARDS_CSS = r"""
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
        white-space: nowrap;
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

"""
