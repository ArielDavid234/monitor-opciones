# -*- coding: utf-8 -*-
"""
Sistema centralizado de tema Plotly profesional — OptionsKing Analytics.

Estilo: institucional oscuro (inspirado en TradingView Pro / Bloomberg Terminal).

Uso:
    from ui.plotly_professional_theme import apply_theme, COLORS

    fig = go.Figure(...)
    apply_theme(fig, title="Mi Gráfico", height=420)
    st.plotly_chart(fig, use_container_width=True)

Paleta institucional:
    VERDE  #00C853  → ganancia, alcista, bueno para venta de prima
    ROJO   #FF1744  → riesgo, bajista, pérdida
    AZUL   #2962FF  → acento primario, calls, señal
    CYAN   #00BCD4  → acento secundario, métricas neutras positivas
    AMBER  #FFD600  → advertencia, neutral, break-even
    PÚRPURA #7C4DFF → superficie, Fase 3, gamma
    GRIS   #546E7A  → datos neutros, historial
    TEXTO  #E2E8F0  → texto principal
    MUTED  #64748B  → texto secundario, ejes
    BG     #0D1117  → fondo principal
    SURFACE #161B22 → fondo de cards/paneles
"""
from __future__ import annotations

import plotly.graph_objects as go

# ────────────────────────────────────────────────────────────────────────────
#  Paleta institucional
# ────────────────────────────────────────────────────────────────────────────

COLORS = {
    # Semáforo financiero
    "positive":   "#00C853",   # verde vivo — positivo, alcista
    "negative":   "#FF1744",   # rojo vivo — negativo, bajista
    "warning":    "#FFD600",   # ámbar — neutral, advertencia
    "accent":     "#2962FF",   # azul institucional — calls, primario
    "cyan":       "#00BCD4",   # cian — secundario, métricas neutras
    "purple":     "#7C4DFF",   # púrpura — surface, gamma, Fase 3
    "neutral":    "#546E7A",   # gris azulado — datos históricos

    # Texto
    "text":       "#E2E8F0",   # texto principal
    "muted":      "#64748B",   # texto secundario / ejes
    "faint":      "#334155",   # gridlines, bordes sutiles

    # Fondos
    "bg":         "#0D1117",   # fondo principal Plotly
    "surface":    "#161B22",   # fondo de cards / paneles
    "transparent": "rgba(0,0,0,0)",  # paper transparente para cards HTML
}

# Secuencias de color para trazas múltiples (orden institucional)
COLOR_SEQUENCE = [
    COLORS["positive"], COLORS["accent"], COLORS["cyan"],
    COLORS["purple"],   COLORS["warning"], COLORS["negative"],
    COLORS["neutral"],  "#F06292",         "#80CBC4",
]

# Escala divergente profesional para heatmaps (rojo → blanco → verde)
DIVERGING_SCALE = [
    [0.0,   COLORS["negative"]],
    [0.25,  "rgba(180, 30, 60, 0.6)"],
    [0.45,  COLORS["faint"]],
    [0.5,   COLORS["surface"]],
    [0.55,  COLORS["faint"]],
    [0.75,  "rgba(0, 140, 60, 0.6)"],
    [1.0,   COLORS["positive"]],
]

# Escala secuencial para OI / flujo (neutro → intenso)
SEQUENTIAL_BLUE = [
    [0.0,  "#0D1117"],
    [0.2,  "#0A2463"],
    [0.5,  "#1565C0"],
    [0.8,  "#1976D2"],
    [1.0,  COLORS["accent"]],
]

SEQUENTIAL_PURPLE = [
    [0.0,  "#0D1117"],
    [0.2,  "#1A0050"],
    [0.5,  "#4527A0"],
    [0.8,  "#7C4DFF"],
    [1.0,  "#E040FB"],
]


# ────────────────────────────────────────────────────────────────────────────
#  Layout base
# ────────────────────────────────────────────────────────────────────────────

def _base_layout(
    title: str = "",
    height: int = 420,
    transparent_paper: bool = True,
    show_legend: bool = False,
    hovermode: str = "closest",
    margin: dict | None = None,
) -> dict:
    """Retorna un dict de kwargs para fig.update_layout() con el tema base."""
    _margin = margin or dict(l=55, r=20, t=45, b=40)
    _paper_bg = COLORS["transparent"] if transparent_paper else COLORS["bg"]

    layout: dict = dict(
        paper_bgcolor=_paper_bg,
        plot_bgcolor=COLORS["bg"],
        height=height,
        margin=_margin,
        font=dict(
            family="Inter, system-ui, -apple-system, sans-serif",
            color=COLORS["text"],
            size=12,
        ),
        showlegend=show_legend,
        hovermode=hovermode,
        hoverlabel=dict(
            bgcolor=COLORS["surface"],
            bordercolor=COLORS["faint"],
            font=dict(
                family="Inter, system-ui, sans-serif",
                size=12,
                color=COLORS["text"],
            ),
        ),
    )

    if title:
        layout["title"] = dict(
            text=title,
            font=dict(size=14, color=COLORS["text"], family="Inter, system-ui, sans-serif"),
            x=0,
            xanchor="left",
            pad=dict(l=4),
        )

    return layout


def _axis_style(
    title: str = "",
    tickformat: str = "",
    showgrid: bool = True,
    dtick: float | None = None,
    log_scale: bool = False,
    range_: list | None = None,
) -> dict:
    """Retorna un dict de configuración de eje con estilo institucional."""
    ax: dict = dict(
        title=dict(text=title, font=dict(size=11, color=COLORS["muted"])),
        color=COLORS["muted"],
        tickfont=dict(size=10, color=COLORS["muted"]),
        showgrid=showgrid,
        gridcolor=COLORS["faint"],
        gridwidth=0.5,
        zeroline=True,
        zerolinecolor=COLORS["faint"],
        zerolinewidth=1,
        linecolor=COLORS["faint"],
        showline=False,
        ticks="",
        tickcolor=COLORS["faint"],
    )
    if tickformat:
        ax["tickformat"] = tickformat
    if dtick is not None:
        ax["dtick"] = dtick
    if log_scale:
        ax["type"] = "log"
    if range_:
        ax["range"] = range_
    return ax


# ────────────────────────────────────────────────────────────────────────────
#  Función pública principal
# ────────────────────────────────────────────────────────────────────────────

def apply_theme(
    fig: go.Figure,
    title: str = "",
    height: int = 420,
    transparent_paper: bool = True,
    show_legend: bool = False,
    hovermode: str = "closest",
    margin: dict | None = None,
    xaxis_title: str = "",
    yaxis_title: str = "",
    xaxis_tickformat: str = "",
    yaxis_tickformat: str = "",
    xaxis_showgrid: bool = True,
    yaxis_showgrid: bool = True,
    legend_h: bool = False,
) -> go.Figure:
    """Aplica el tema institucional a un go.Figure existente.

    Siempre retorna la figura para permitir encadenado:
        fig = go.Figure(...); apply_theme(fig, title="X")

    Args:
        fig:               Figura Plotly a modificar in-place.
        title:             Título del gráfico (español).
        height:            Altura en píxeles.
        transparent_paper: True = paper transparente (para cards HTML), False = bg oscuro.
        show_legend:       Mostrar leyenda.
        hovermode:         "closest" | "x unified" | "y unified".
        margin:            Dict LRTB o None para usar defaults.
        xaxis_title:       Etiqueta eje X.
        yaxis_title:       Etiqueta eje Y.
        xaxis_tickformat:  Formato Plotly eje X (ej. "%Y-%m-%d", ",.0f", ".1%").
        yaxis_tickformat:  Formato Plotly eje Y.
        xaxis_showgrid:    Mostrar grid X.
        yaxis_showgrid:    Mostrar grid Y.
        legend_h:          True = leyenda horizontal encima del gráfico.

    Returns:
        La misma figura modificada.
    """
    layout = _base_layout(
        title=title,
        height=height,
        transparent_paper=transparent_paper,
        show_legend=show_legend,
        hovermode=hovermode,
        margin=margin,
    )

    layout["xaxis"] = _axis_style(
        title=xaxis_title,
        tickformat=xaxis_tickformat,
        showgrid=xaxis_showgrid,
    )
    layout["yaxis"] = _axis_style(
        title=yaxis_title,
        tickformat=yaxis_tickformat,
        showgrid=yaxis_showgrid,
    )

    if show_legend and legend_h:
        layout["legend"] = dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)",
            bordercolor=COLORS["faint"],
            font=dict(size=10, color=COLORS["muted"]),
        )
    elif show_legend:
        layout["legend"] = dict(
            bgcolor=COLORS["surface"],
            bordercolor=COLORS["faint"],
            borderwidth=1,
            font=dict(size=10, color=COLORS["muted"]),
        )

    fig.update_layout(**layout)
    return fig


# ────────────────────────────────────────────────────────────────────────────
#  Utilidades de construcción rápida de trazas
# ────────────────────────────────────────────────────────────────────────────

def pro_line(
    x, y,
    name: str = "",
    color: str = COLORS["positive"],
    width: int = 2,
    dash: str = "solid",
    fill: str = "none",
    fill_color: str = "",
    hover_template: str = "",
    show_legend: bool = False,
) -> go.Scatter:
    """Retorna un go.Scatter de línea profesional."""
    trace = go.Scatter(
        x=x, y=y,
        mode="lines",
        name=name,
        line=dict(color=color, width=width, dash=dash),
        showlegend=show_legend,
        hovertemplate=hover_template or f"{name}: %{{y:,.2f}}<extra></extra>",
    )
    if fill != "none":
        trace.update(fill=fill, fillcolor=fill_color or f"{color}22")
    return trace


def pro_bar(
    x, y,
    name: str = "",
    color: str | list = COLORS["accent"],
    hover_template: str = "",
    show_legend: bool = False,
    text: list | None = None,
) -> go.Bar:
    """Retorna un go.Bar con estilo profesional."""
    bar = go.Bar(
        x=x, y=y,
        name=name,
        marker_color=color,
        marker_line=dict(width=0),
        showlegend=show_legend,
        hovertemplate=hover_template or f"{name}: %{{y:,.2f}}<extra></extra>",
        opacity=0.88,
    )
    if text is not None:
        bar.update(text=text, textposition="auto",
                   textfont=dict(color=COLORS["text"], size=11))
    return bar


def pro_gauge_layout(height: int = 260) -> dict:
    """Layout base para figuras go.Indicator gauge."""
    return dict(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"]),
        height=height,
        margin=dict(l=20, r=20, t=30, b=10),
    )
