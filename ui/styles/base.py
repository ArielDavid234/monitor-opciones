"""Fuentes, variables root y base global."""
BASE_CSS = r"""

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

"""
