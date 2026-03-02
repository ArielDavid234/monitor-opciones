# -*- coding: utf-8 -*-
"""
Componentes de visualización avanzados — OPTIONSKING Analytics.

Gauges, heatmaps, superficies de volatilidad, Monte Carlo charts.
Se complementan con ui/components.py (metric cards, tables).
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ============================================================================
#                    PUT/CALL RATIO GAUGE
# ============================================================================

_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="white", family="Inter, sans-serif"),
)


def render_pcr_gauge(pc_ratio: float, title: str = "Put/Call Ratio") -> go.Figure:
    """Genera un gauge semicircular para el Put/Call Ratio.

    Escala: 0 → 2.0
    - < 0.7  → Alcista  (verde)
    - 0.7-1.0 → Neutral (amarillo)
    - > 1.0  → Bajista  (rojo, apuestas defensivas)
    """
    if pc_ratio < 0.7:
        label = "ALCISTA"
    elif pc_ratio <= 1.0:
        label = "NEUTRAL"
    else:
        label = "BAJISTA"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pc_ratio,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"{title} — {label}", "font": {"size": 15, "color": "white"}},
        number={"font": {"size": 38, "color": "white"}, "valueformat": ".3f"},
        gauge={
            "axis": {
                "range": [0, 2],
                "tickwidth": 1,
                "tickcolor": "#475569",
                "tickfont": {"color": "#94a3b8", "size": 10},
                "dtick": 0.25,
            },
            "bar": {"color": "#00ff88", "thickness": 0.25},
            "bgcolor": "#0f172a",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 0.7], "color": "rgba(16, 185, 129, 0.2)"},
                {"range": [0.7, 1.0], "color": "rgba(245, 158, 11, 0.15)"},
                {"range": [1.0, 1.5], "color": "rgba(239, 68, 68, 0.2)"},
                {"range": [1.5, 2.0], "color": "rgba(239, 68, 68, 0.35)"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": pc_ratio,
            },
        },
    ))
    fig.update_layout(
        **_DARK_LAYOUT,
        height=280,
        margin=dict(l=25, r=25, t=50, b=10),
    )
    return fig


# ============================================================================
#                    IV RANK / PERCENTILE GAUGE
# ============================================================================

def render_iv_gauge(
    iv_rank: float,
    iv_percentile: float,
    iv_actual: float,
    title: str = "IV Rank",
) -> go.Figure:
    """Genera un gauge dual para IV Rank y IV Percentile.

    Escala: 0 → 100
    - < 30  → IV Baja  (verde → bueno para comprar opciones)
    - 30-60 → IV Media (amarillo)
    - > 60  → IV Alta  (rojo → bueno para vender opciones)
    """
    if iv_rank < 30:
        label = "IV BAJA"
    elif iv_rank <= 60:
        label = "IV MEDIA"
    else:
        label = "IV ALTA"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=iv_rank,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"{title} — {label}", "font": {"size": 15, "color": "white"}},
        number={"font": {"size": 38, "color": "white"}, "suffix": "%"},
        delta={
            "reference": 50,
            "increasing": {"color": "#ef4444"},
            "decreasing": {"color": "#10b981"},
            "suffix": " vs 50",
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#475569",
                "tickfont": {"color": "#94a3b8", "size": 10},
            },
            "bar": {"color": "#3b82f6", "thickness": 0.25},
            "bgcolor": "#0f172a",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30], "color": "rgba(16, 185, 129, 0.2)"},
                {"range": [30, 60], "color": "rgba(245, 158, 11, 0.15)"},
                {"range": [60, 80], "color": "rgba(239, 68, 68, 0.2)"},
                {"range": [80, 100], "color": "rgba(239, 68, 68, 0.35)"},
            ],
            "threshold": {
                "line": {"color": "#f59e0b", "width": 3},
                "thickness": 0.8,
                "value": iv_percentile,
            },
        },
    ))
    fig.update_layout(
        **_DARK_LAYOUT,
        height=280,
        margin=dict(l=25, r=25, t=50, b=10),
        annotations=[
            dict(
                text=f"IV Percentile: {iv_percentile:.0f}% | IV Actual: {iv_actual:.1f}%",
                xref="paper", yref="paper",
                x=0.5, y=-0.05,
                showarrow=False,
                font=dict(size=11, color="#94a3b8"),
            )
        ],
    )
    return fig


# ============================================================================
#                    OI HEATMAP — Strike × Expiration
# ============================================================================

def render_oi_heatmap(
    datos: list,
    tipo: str = "ALL",
    value_col: str = "OI",
    title: Optional[str] = None,
) -> Optional[go.Figure]:
    """Genera un heatmap de OI (o volumen) por Strike × Vencimiento.

    Args:
        datos: Lista de dicts del scanner.
        tipo: "CALL", "PUT", o "ALL".
        value_col: Columna a visualizar ("OI", "Volumen", "Prima_Vol", "IV").
        title: Título del gráfico.

    Returns:
        go.Figure o None si no hay datos.
    """
    if not datos:
        return None

    df = pd.DataFrame(datos)
    if "Prima_Volumen" in df.columns and "Prima_Vol" not in df.columns:
        df = df.rename(columns={"Prima_Volumen": "Prima_Vol"})

    if tipo != "ALL" and "Tipo" in df.columns:
        df = df[df["Tipo"] == tipo]

    if df.empty or value_col not in df.columns:
        return None

    # Pivot: filas = Strike (descendente), columnas = Vencimiento
    pivot = df.pivot_table(
        index="Strike",
        columns="Vencimiento",
        values=value_col,
        aggfunc="sum",
        fill_value=0,
    )

    if pivot.empty or pivot.shape[0] < 2 or pivot.shape[1] < 1:
        return None

    # Limitar a top strikes con más actividad
    strike_totals = pivot.sum(axis=1)
    top_n = min(40, len(strike_totals))
    top_strikes = strike_totals.nlargest(top_n).index
    pivot = pivot.loc[pivot.index.isin(top_strikes)].sort_index(ascending=False)

    title = title or f"🗺️ Heatmap de {value_col} — {tipo if tipo != 'ALL' else 'CALL + PUT'}"

    # Color scale
    if value_col == "IV":
        colorscale = "YlOrRd"
    elif value_col in ("Prima_Vol",):
        colorscale = "Viridis"
    else:
        colorscale = [[0, "#0f172a"], [0.25, "#1e3a5f"], [0.5, "#2563eb"],
                       [0.75, "#7c3aed"], [1.0, "#f43f5e"]]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[str(c) for c in pivot.columns],
        y=[f"${s:,.0f}" for s in pivot.index],
        colorscale=colorscale,
        hoverongaps=False,
        hovertemplate=(
            "Strike: %{y}<br>"
            "Vencimiento: %{x}<br>"
            f"{value_col}: " + "%{z:,.0f}<extra></extra>"
        ),
        colorbar=dict(
            title=dict(text=value_col, font=dict(color="#94a3b8", size=11)),
            tickfont=dict(color="#94a3b8", size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="white")),
        **_DARK_LAYOUT,
        height=max(400, min(700, top_n * 18)),
        margin=dict(l=80, r=20, t=50, b=60),
        xaxis=dict(
            title="Vencimiento",
            color="#94a3b8",
            tickangle=-45,
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title="Strike",
            color="#94a3b8",
            tickfont=dict(size=10),
        ),
    )
    return fig


# ============================================================================
#                    VOLATILITY SURFACE — 3D Strike × Expiration × IV
# ============================================================================

def render_vol_surface(
    datos: list,
    spot_price: float = 0,
    title: str = "🌋 Superficie de Volatilidad Implícita",
) -> Optional[go.Figure]:
    """Genera una superficie 3D de IV por Strike × Vencimiento.

    Args:
        datos: Lista de dicts del scanner.
        spot_price: Precio actual para marcar ATM.
        title: Título del gráfico.

    Returns:
        go.Figure o None.
    """
    if not datos:
        return None

    df = pd.DataFrame(datos)
    if "IV" not in df.columns or "Strike" not in df.columns or "Vencimiento" not in df.columns:
        return None

    df = df[df["IV"] > 0].copy()
    if len(df) < 10:
        return None

    # Pivot IV promedio por Strike × Vencimiento
    pivot = df.pivot_table(
        index="Strike",
        columns="Vencimiento",
        values="IV",
        aggfunc="mean",
    )

    if pivot.empty or pivot.shape[0] < 3 or pivot.shape[1] < 2:
        return None

    # Limitar strikes cerca del ATM para limpieza visual
    if spot_price > 0:
        low = spot_price * 0.85
        high = spot_price * 1.15
        pivot = pivot[(pivot.index >= low) & (pivot.index <= high)]

    if pivot.shape[0] < 3:
        return None

    # Rellenar NaN con interpolación
    pivot = pivot.interpolate(method="linear", axis=0).bfill().ffill()

    x_labels = [str(c) for c in pivot.columns]
    y_values = pivot.index.values
    z_values = pivot.values

    fig = go.Figure(data=[go.Surface(
        z=z_values,
        x=list(range(len(x_labels))),
        y=y_values,
        colorscale="Plasma",
        colorbar=dict(
            title=dict(text="IV %", font=dict(color="#94a3b8", size=11)),
            tickfont=dict(color="#94a3b8", size=10),
        ),
        hovertemplate=(
            "Vencimiento: %{text}<br>"
            "Strike: $%{y:,.0f}<br>"
            "IV: %{z:.1f}%<extra></extra>"
        ),
        text=[[x_labels[j] for j in range(len(x_labels))] for _ in range(len(y_values))],
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="white")),
        **_DARK_LAYOUT,
        height=550,
        margin=dict(l=0, r=0, t=50, b=0),
        scene=dict(
            xaxis=dict(
                title="Vencimiento",
                tickvals=list(range(len(x_labels))),
                ticktext=x_labels,
                backgroundcolor="#0f172a",
                gridcolor="#1e293b",
                color="#94a3b8",
            ),
            yaxis=dict(
                title="Strike ($)",
                backgroundcolor="#0f172a",
                gridcolor="#1e293b",
                color="#94a3b8",
            ),
            zaxis=dict(
                title="IV (%)",
                backgroundcolor="#0f172a",
                gridcolor="#1e293b",
                color="#94a3b8",
            ),
            camera=dict(eye=dict(x=1.5, y=-1.5, z=0.9)),
        ),
    )
    return fig


# ============================================================================
#                    MONTE CARLO FAN CHART
# ============================================================================

def render_monte_carlo_chart(
    mc_result: dict,
    spot_price: float,
    ticker: str = "",
    max_paths_shown: int = 100,
) -> go.Figure:
    """Genera un fan chart de Monte Carlo con intervalos de confianza.

    Args:
        mc_result: Resultado de simular_monte_carlo().
        spot_price: Precio actual.
        ticker: Símbolo para el título.
        max_paths_shown: Máx. trayectorias individuales a dibujar.

    Returns:
        go.Figure
    """
    paths = mc_result["paths"]
    days = mc_result["days"]
    percentiles = mc_result["percentiles"]
    num_sims = paths.shape[0]

    t = list(range(days + 1))

    fig = go.Figure()

    # Fan: P5-P95 (banda exterior)
    p5_line = np.percentile(paths, 5, axis=0)
    p95_line = np.percentile(paths, 95, axis=0)
    p25_line = np.percentile(paths, 25, axis=0)
    p75_line = np.percentile(paths, 75, axis=0)
    mean_line = mc_result["mean_path"]

    # Banda 90% (P5-P95)
    fig.add_trace(go.Scatter(
        x=t, y=p95_line.tolist(),
        mode="lines", line=dict(width=0),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=t, y=p5_line.tolist(),
        mode="lines", line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(59, 130, 246, 0.1)",
        name="IC 90% (P5-P95)",
    ))

    # Banda 50% (P25-P75)
    fig.add_trace(go.Scatter(
        x=t, y=p75_line.tolist(),
        mode="lines", line=dict(width=0),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=t, y=p25_line.tolist(),
        mode="lines", line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(59, 130, 246, 0.25)",
        name="IC 50% (P25-P75)",
    ))

    # Trayectorias individuales (sample)
    n_show = min(max_paths_shown, num_sims)
    indices = np.linspace(0, num_sims - 1, n_show, dtype=int)
    for i in indices:
        fig.add_trace(go.Scatter(
            x=t, y=paths[i].tolist(),
            mode="lines",
            line=dict(width=0.3, color="rgba(148,163,184,0.15)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Media
    fig.add_trace(go.Scatter(
        x=t, y=mean_line.tolist(),
        mode="lines",
        line=dict(color="#00ff88", width=2),
        name=f"Media: ${mc_result['expected_price']:,.2f}",
    ))

    # Línea del spot
    fig.add_hline(
        y=spot_price,
        line=dict(color="#f59e0b", width=1, dash="dash"),
        annotation_text=f"Spot: ${spot_price:,.2f}",
        annotation_font=dict(color="#f59e0b", size=11),
    )

    title_text = f"🎲 Monte Carlo — {ticker} ({num_sims:,} simulaciones, {days} días)"
    fig.update_layout(
        title=dict(text=title_text, font=dict(size=14, color="white")),
        **_DARK_LAYOUT,
        height=450,
        margin=dict(l=60, r=20, t=50, b=40),
        xaxis=dict(
            title="Día",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        yaxis=dict(
            title="Precio ($)",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=10, color="#94a3b8"),
        ),
    )

    return fig


# ============================================================================
#                    ANOMALY SCATTER
# ============================================================================

def render_anomaly_scatter(
    df_anomalies: pd.DataFrame,
    title: str = "🔍 Detector de Anomalías — Actividad Inusual",
) -> Optional[go.Figure]:
    """Scatter plot de anomalías: Vol vs Prima, tamaño = score, color = anomaly.

    Args:
        df_anomalies: DataFrame con columnas anomaly_score, is_anomaly.
        title: Título del gráfico.

    Returns:
        go.Figure o None.
    """
    if df_anomalies is None or df_anomalies.empty:
        return None

    if "anomaly_score" not in df_anomalies.columns:
        return None

    df = df_anomalies.copy()
    if "Prima_Volumen" in df.columns and "Prima_Vol" not in df.columns:
        df = df.rename(columns={"Prima_Volumen": "Prima_Vol"})

    required = {"Volumen", "Prima_Vol", "anomaly_score", "is_anomaly"}
    if not required.issubset(df.columns):
        return None

    # Color por anomalía
    colors = df["is_anomaly"].map({True: "#ef4444", False: "#3b82f6"}).tolist()
    sizes = (df["anomaly_score"] / 100 * 20 + 4).clip(4, 24).tolist()

    hover_parts = ["Volumen: %{x:,.0f}", "Prima: $%{y:,.0f}"]
    if "Tipo" in df.columns:
        hover_parts.append("Tipo: %{customdata[0]}")
    if "Strike" in df.columns:
        hover_parts.append("Strike: $%{customdata[1]:,.0f}")

    custom_data = []
    for _, row in df.iterrows():
        custom_data.append([
            row.get("Tipo", ""),
            row.get("Strike", 0),
            row.get("anomaly_score", 0),
        ])

    fig = go.Figure(go.Scatter(
        x=df["Volumen"],
        y=df["Prima_Vol"],
        mode="markers",
        marker=dict(
            color=colors,
            size=sizes,
            opacity=0.7,
            line=dict(width=0.5, color="rgba(255,255,255,0.3)"),
        ),
        customdata=custom_data,
        hovertemplate=(
            "Volumen: %{x:,.0f}<br>"
            "Prima: $%{y:,.0f}<br>"
            "Score: %{customdata[2]:.0f}/100<br>"
            "<extra></extra>"
        ),
    ))

    n_anomalies = df["is_anomaly"].sum()
    fig.update_layout(
        title=dict(
            text=f"{title} ({n_anomalies} anomalías detectadas)",
            font=dict(size=14, color="white"),
        ),
        **_DARK_LAYOUT,
        height=420,
        margin=dict(l=60, r=20, t=50, b=50),
        xaxis=dict(
            title="Volumen",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
            type="log",
        ),
        yaxis=dict(
            title="Prima ($)",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
            type="log",
        ),
        annotations=[
            dict(
                text="🔴 Anomalía  |  🔵 Normal",
                xref="paper", yref="paper",
                x=0.5, y=-0.12,
                showarrow=False,
                font=dict(size=11, color="#94a3b8"),
            )
        ],
    )

    return fig


# ============================================================================
#               IV FORECAST CHART  (predicción de volatilidad)
# ============================================================================

def render_iv_forecast_chart(
    df_historical: pd.DataFrame,
    forecast: dict,
    ticker: str,
) -> Optional[go.Figure]:
    """Gráfico de línea IV histórica + forecast con banda de confianza.

    Muestra la evolución de IV proxy (hv_20d × 0.6 + vix × 0.4) y
    proyecta la predicción del modelo de regresión lineal a N días.

    Args:
        df_historical: DataFrame de get_historical_iv() con [date, iv_mean, hv_20d, vix_close].
        forecast: dict retornado por predict_implied_volatility().
        ticker: Símbolo para el título.

    Returns:
        go.Figure o None si datos insuficientes.
    """
    if df_historical.empty or "error" in forecast:
        return None

    fig = go.Figure()

    dates = pd.to_datetime(df_historical["date"])
    iv_vals = df_historical["iv_mean"]

    # ── IV histórica (línea principal) ───────────────────────────
    fig.add_trace(go.Scatter(
        x=dates,
        y=iv_vals,
        mode="lines",
        name="IV Proxy (HV+VIX)",
        line=dict(color="#00ff88", width=2),
        hovertemplate="Fecha: %{x|%Y-%m-%d}<br>IV: %{y:.1f}%<extra></extra>",
    ))

    # ── HV 20d (línea secundaria más tenue) ──────────────────────
    if "hv_20d" in df_historical.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df_historical["hv_20d"],
            mode="lines",
            name="HV 20d",
            line=dict(color="#64748b", width=1, dash="dot"),
            hovertemplate="HV 20d: %{y:.1f}%<extra></extra>",
        ))

    # ── VIX overlay ──────────────────────────────────────────────
    if "vix_close" in df_historical.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df_historical["vix_close"],
            mode="lines",
            name="VIX",
            line=dict(color="#f59e0b", width=1, dash="dashdot"),
            opacity=0.6,
            hovertemplate="VIX: %{y:.1f}<extra></extra>",
        ))

    # ── Forecast: línea punteada desde último dato → predicción ──
    last_date = dates.iloc[-1]
    forecast_days = forecast.get("forecast_days", 5)
    forecast_date = last_date + pd.Timedelta(days=forecast_days)
    current_iv = forecast["current_iv"]
    predicted_iv = forecast["predicted_iv"]
    iv_low, iv_high = forecast["forecast_range"]

    # Línea de forecast
    direction = forecast.get("direction", "stable")
    fc_color = (
        "#10b981" if direction == "down" else
        "#ef4444" if direction == "up" else
        "#f59e0b"
    )

    fig.add_trace(go.Scatter(
        x=[last_date, forecast_date],
        y=[current_iv, predicted_iv],
        mode="lines+markers",
        name=f"Forecast {forecast_days}d",
        line=dict(color=fc_color, width=3, dash="dash"),
        marker=dict(size=[6, 12], color=fc_color, symbol=["circle", "diamond"]),
        hovertemplate=(
            "Fecha: %{x|%Y-%m-%d}<br>"
            "IV: %{y:.1f}%<extra></extra>"
        ),
    ))

    # Banda de confianza (marcadores ±1σ)
    fig.add_trace(go.Scatter(
        x=[forecast_date, forecast_date],
        y=[iv_low, iv_high],
        mode="markers+text",
        name="Rango ±1σ",
        marker=dict(size=10, color=[fc_color, fc_color], symbol=["triangle-down", "triangle-up"]),
        text=[f"{iv_low:.1f}%", f"{iv_high:.1f}%"],
        textposition=["bottom center", "top center"],
        textfont=dict(size=10, color="#94a3b8"),
        hovertemplate="Rango: %{y:.1f}%<extra></extra>",
    ))

    # Rectángulo de banda entre iv_low e iv_high
    fig.add_shape(
        type="rect",
        x0=last_date, x1=forecast_date,
        y0=iv_low, y1=iv_high,
        fillcolor=fc_color,
        opacity=0.08,
        line=dict(width=0),
    )

    # ── Layout ───────────────────────────────────────────────────
    r2 = forecast.get("r2_score", 0)
    r2_color = "#10b981" if r2 >= 0.5 else "#f59e0b" if r2 >= 0.2 else "#ef4444"
    r2_label = "bueno" if r2 >= 0.5 else "moderado" if r2 >= 0.2 else "bajo"

    fig.update_layout(
        title=dict(
            text=(
                f"Forecast IV — {ticker} "
                f"(R²={r2:.3f} <span style='color:{r2_color}'>{r2_label}</span>)"
            ),
            font=dict(size=14, color="white"),
        ),
        **_DARK_LAYOUT,
        height=420,
        margin=dict(l=60, r=20, t=50, b=50),
        xaxis=dict(
            title="Fecha",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        yaxis=dict(
            title="Volatilidad (%)",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10, color="#94a3b8"),
        ),
    )

    return fig


# ============================================================================
#         MC OPTION PRICING — Fan chart + Payoff histogram
# ============================================================================

def render_mc_option_paths(
    mc_result: dict,
    ticker: str = "",
    max_paths_shown: int = 150,
) -> Optional[go.Figure]:
    """Fan chart de paths del subyacente con strike line para opción MC.

    Muestra trayectorias GBM simuladas, banda de confianza P5-P95/P25-P75,
    línea de strike, media, y break-even.

    Args:
        mc_result: dict de monte_carlo_option_pricing().
        ticker: Símbolo para título.
        max_paths_shown: Trayectorias individuales a dibujar.

    Returns:
        go.Figure o None si error.
    """
    if "error" in mc_result:
        return None

    paths = mc_result["paths_sample"]
    mean_path = mc_result["mean_path"]
    params = mc_result["params"]
    n_steps = paths.shape[1] - 1
    t = list(range(n_steps + 1))
    otype = params["option_type"]

    fig = go.Figure()

    # ── Bandas de confianza ──────────────────────────────────────
    p5 = np.percentile(paths, 5, axis=0)
    p95 = np.percentile(paths, 95, axis=0)
    p25 = np.percentile(paths, 25, axis=0)
    p75 = np.percentile(paths, 75, axis=0)

    # Banda 90%
    fig.add_trace(go.Scatter(
        x=t, y=p95.tolist(), mode="lines", line=dict(width=0), showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=t, y=p5.tolist(), mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(59,130,246,0.08)", name="IC 90%",
    ))

    # Banda 50%
    fig.add_trace(go.Scatter(
        x=t, y=p75.tolist(), mode="lines", line=dict(width=0), showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=t, y=p25.tolist(), mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(59,130,246,0.2)", name="IC 50%",
    ))

    # ── Trayectorias individuales ────────────────────────────────
    n_show = min(max_paths_shown, paths.shape[0])
    for i in range(n_show):
        fig.add_trace(go.Scatter(
            x=t, y=paths[i].tolist(), mode="lines",
            line=dict(width=0.3, color="rgba(148,163,184,0.12)"),
            showlegend=False, hoverinfo="skip",
        ))

    # ── Media ────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=t, y=mean_path.tolist(), mode="lines",
        line=dict(color="#00ff88", width=2),
        name=f"Media: ${mc_result['mean_path'][-1]:,.2f}",
    ))

    # ── Strike line ──────────────────────────────────────────────
    fig.add_hline(
        y=params["K"], line=dict(color="#ef4444", width=2, dash="dash"),
        annotation_text=f"Strike ${params['K']:,.1f}",
        annotation_font=dict(color="#ef4444", size=11),
    )

    # ── Break-even line ──────────────────────────────────────────
    fig.add_hline(
        y=mc_result["breakeven"],
        line=dict(color="#f59e0b", width=1.5, dash="dot"),
        annotation_text=f"B/E ${mc_result['breakeven']:,.2f}",
        annotation_font=dict(color="#f59e0b", size=10),
        annotation_position="bottom right",
    )

    # ── Spot line ────────────────────────────────────────────────
    fig.add_hline(
        y=params["S0"],
        line=dict(color="#64748b", width=1, dash="dashdot"),
        annotation_text=f"Spot ${params['S0']:,.2f}",
        annotation_font=dict(color="#64748b", size=10),
        annotation_position="top left",
    )

    tipo_label = "CALL" if otype == "call" else "PUT"
    fig.update_layout(
        title=dict(
            text=(
                f"🎲 MC {tipo_label} ${params['K']:,.0f} — {ticker} "
                f"({params['n_sims']:,} sims, σ={params['sigma']*100:.1f}%)"
            ),
            font=dict(size=14, color="white"),
        ),
        **_DARK_LAYOUT,
        height=450,
        margin=dict(l=60, r=20, t=50, b=40),
        xaxis=dict(
            title="Paso temporal",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        yaxis=dict(
            title="Precio Subyacente ($)",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=10, color="#94a3b8"),
        ),
    )

    return fig


def render_mc_payoff_histogram(
    mc_result: dict,
    ticker: str = "",
) -> Optional[go.Figure]:
    """Histograma de payoffs al vencimiento de la simulación MC.

    Muestra la distribución completa de resultados posibles,
    con líneas verticales en la media, mediana, y percentiles clave.
    Los payoffs = 0 (OTM) se agrupan en el primer bin para visualizar
    claramente la probabilidad de pérdida total.

    Args:
        mc_result: dict de monte_carlo_option_pricing().
        ticker: Símbolo.

    Returns:
        go.Figure o None.
    """
    if "error" in mc_result:
        return None

    payoffs = mc_result["payoffs"]
    params = mc_result["params"]
    otype = params["option_type"]
    tipo_label = "CALL" if otype == "call" else "PUT"

    # Separar ITM vs OTM para color distinto
    itm_payoffs = payoffs[payoffs > 0]
    otm_count = int(np.sum(payoffs == 0))

    fig = go.Figure()

    # Histograma principal (solo ITM payoffs)
    if len(itm_payoffs) > 0:
        fig.add_trace(go.Histogram(
            x=itm_payoffs,
            nbinsx=50,
            name=f"ITM ({mc_result['itm_probability']:.0f}%)",
            marker_color="#10b981",
            opacity=0.85,
            hovertemplate="Payoff: $%{x:.2f}<br>Frecuencia: %{y}<extra></extra>",
        ))

    # Barra OTM (payoff = 0)
    if otm_count > 0:
        otm_pct = 100 - mc_result["itm_probability"]
        fig.add_trace(go.Bar(
            x=[0], y=[otm_count],
            name=f"OTM / $0 ({otm_pct:.0f}%)",
            marker_color="#ef4444",
            opacity=0.85,
            width=max(0.5, float(np.max(payoffs)) * 0.015) if np.max(payoffs) > 0 else 0.5,
            hovertemplate=f"Payoff: $0 (OTM)<br>Paths: {otm_count:,}<extra></extra>",
        ))

    # ── Líneas de referencia ─────────────────────────────────────
    mean_po = mc_result["expected_payoff"]
    median_po = mc_result["median_payoff"]

    fig.add_vline(
        x=mean_po, line=dict(color="#00ff88", width=2, dash="dash"),
        annotation_text=f"Media ${mean_po:.2f}",
        annotation_font=dict(color="#00ff88", size=10),
        annotation_position="top right",
    )

    if median_po > 0:
        fig.add_vline(
            x=median_po, line=dict(color="#3b82f6", width=1.5, dash="dot"),
            annotation_text=f"Mediana ${median_po:.2f}",
            annotation_font=dict(color="#3b82f6", size=10),
            annotation_position="top left",
        )

    # P95 payoff
    p95 = mc_result["payoff_percentiles"]["p95"]
    if p95 > 0:
        fig.add_vline(
            x=p95, line=dict(color="#f59e0b", width=1, dash="dashdot"),
            annotation_text=f"P95 ${p95:.2f}",
            annotation_font=dict(color="#f59e0b", size=9),
            annotation_position="top right",
        )

    fig.update_layout(
        title=dict(
            text=(
                f"📊 Distribución Payoffs — {tipo_label} ${params['K']:,.0f} {ticker} "
                f"(MC ${mc_result['mc_price']:.2f})"
            ),
            font=dict(size=14, color="white"),
        ),
        **_DARK_LAYOUT,
        height=380,
        margin=dict(l=60, r=20, t=50, b=50),
        xaxis=dict(
            title="Payoff al Vencimiento ($)",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        yaxis=dict(
            title="Frecuencia (paths)",
            color="#94a3b8",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        barmode="overlay",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=10, color="#94a3b8"),
        ),
    )

    return fig