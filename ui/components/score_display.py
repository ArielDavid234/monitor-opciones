"""
Funciones de puntuación y estilos de display — sin dependencias internas.
"""


def get_score_style(clasificacion):
    """Retorna (card_class, score_class, score_emoji) según la clasificación."""
    styles = {
        "ALTA": ("empresa-card empresa-card-bull", "score-alta", "🟢"),
        "MEDIA": ("empresa-card empresa-card-neutral", "score-media", "🟡"),
    }
    return styles.get(clasificacion, ("empresa-card empresa-card-bear", "score-baja", "🔴"))


def _rsi_label(rsi):
    if rsi >= 70:
        return "SOBRECOMPRA"
    if rsi <= 30:
        return "SOBREVENTA"
    return "NEUTRAL"


def _tendencia_emoji(t):
    if t == "ALCISTA":
        return "🟢"
    if t == "BAJISTA":
        return "🔴"
    return "🟡"


def _veredicto_color(v):
    if "COMPRA" in v:
        return "#22c55e"
    if "CONSIDERAR" in v:
        return "#f59e0b"
    if "MANTENER" in v:
        return "#3b82f6"
    return "#ef4444"


def _score_bar_html(score, max_score, label, color):
    """Genera HTML de una barra de score visual."""
    pct = min(score / max_score * 100, 100) if max_score > 0 else 0
    return f"""
    <div style="margin: 4px 0;">
        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94a3b8;">
            <span>{label}</span><span style="color:{color}; font-weight:700;">{score}/{max_score}</span>
        </div>
        <div style="background:#1e293b; border-radius:4px; height:8px; overflow:hidden;">
            <div style="width:{pct:.0f}%; height:100%; background:{color}; border-radius:4px;"></div>
        </div>
    </div>"""


def render_target_html(result):
    """Genera el HTML para la sección de target de analistas."""
    if result["target_mean"] <= 0:
        return ""
    upside_color = "#10b981" if result["upside_pct"] > 0 else "#ef4444"
    upside_sign = "+" if result["upside_pct"] > 0 else ""
    return f"""
        <div class="empresa-metric">
            <div class="empresa-metric-label">Target Analistas</div>
            <div class="empresa-metric-value">${result['target_mean']:,.0f}</div>
        </div>
        <div class="empresa-metric">
            <div class="empresa-metric-label">Upside</div>
            <div class="empresa-metric-value" style="color: {upside_color};">{upside_sign}{result['upside_pct']:.1f}%</div>
        </div>"""
