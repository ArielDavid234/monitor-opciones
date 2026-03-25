# -*- coding: utf-8 -*-
"""ui.components — paquete de componentes UI. Exporta todos los símbolos públicos."""

from ui.components.common import (
    format_market_cap,
    format_cashflow,
    _generate_sparkline_svg,
    _format_large_number,
    render_oi_heatmap,
    render_bias_gauge,
    render_fundamentals_card,
)
from ui.components.score_display import (
    get_score_style,
    render_target_html,
    _rsi_label,
    _tendencia_emoji,
    _veredicto_color,
    _score_bar_html,
)
from ui.components.alert_badges import (
    _badge_html,
    _sentiment_badge,
    _type_badge,
    _priority_badge,
    _delta_cell,
    _sm_flow_badge,
    _inst_flow_badge,
    institutional_flow_legend,
)
from ui.components.metric_cards import (
    render_metric_card,
    render_metric_row,
    render_empresa_card,
    render_tabla_comparativa,
)
from ui.components.data_tables import (
    render_pro_table,
    analizar_watchlist,
    render_watchlist_preview,
    render_analisis_completo,
    _SPECIAL_COLS,
    _NUMERIC_COLS,
)
try:
    from ui.components.aggrid_credit_spreads import *  # noqa: F401,F403
except ImportError:
    pass
