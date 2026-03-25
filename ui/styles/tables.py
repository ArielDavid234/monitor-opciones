"""Pro dataframes y HTML pro table."""
TABLES_CSS = r"""
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
    /* Flow Type badges */
    .ok-badge-hedge {
        background: rgba(245,158,11,0.13); color: #f59e0b;
        border: 1px solid rgba(245,158,11,0.25);
    }
    .ok-badge-sellprem {
        background: rgba(59,130,246,0.13); color: #60a5fa;
        border: 1px solid rgba(59,130,246,0.25);
    }
    .ok-badge-spread {
        background: rgba(148,163,184,0.12); color: #94a3b8;
        border: 1px solid rgba(148,163,184,0.18);
    }
    .ok-badge-unclass {
        background: rgba(100,116,139,0.10); color: #64748b;
        border: 1px solid rgba(100,116,139,0.15);
    }
    /* Hedge institutional alert badges */
    .ok-badge-hedgecrit {
        background: rgba(220,53,69,0.18); color: #ff4d5e;
        border: 1px solid rgba(220,53,69,0.35);
        font-weight: 800; font-size: 0.74rem;
    }
    .ok-badge-hedgewarn {
        background: rgba(255,167,38,0.15); color: #ffa726;
        border: 1px solid rgba(255,167,38,0.30);
        font-weight: 800; font-size: 0.74rem;
    }
    /* Hedge alert banner */
    .hedge-banner {
        padding: 14px 20px; border-radius: 12px;
        margin: 12px 0 16px 0; font-size: 0.88rem;
        display: flex; align-items: center; gap: 10px;
        font-weight: 600;
    }
    .hedge-banner-critical {
        background: rgba(220,53,69,0.12); color: #ff4d5e;
        border: 1px solid rgba(220,53,69,0.30);
    }
    .hedge-banner-warning {
        background: rgba(255,167,38,0.10); color: #ffa726;
        border: 1px solid rgba(255,167,38,0.25);
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

"""
