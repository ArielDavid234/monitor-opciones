"""
Utilidades de formateo y componentes SVG comunes — sin dependencias internas.
"""
import logging
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

logger = logging.getLogger(__name__)


def format_market_cap(value):
    """Formatea un valor numérico como capitalización de mercado legible."""
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    elif value >= 1e9:
        return f"${value/1e9:.1f}B"
    elif value >= 1e6:
        return f"${value/1e6:.0f}M"
    return f"${value:,.0f}"


def format_cashflow(value):
    """Formatea un valor de flujo de caja en formato legible."""
    if value >= 1e9:
        return f"${value/1e9:.1f}B"
    elif value >= 1e6:
        return f"${value/1e6:.0f}M"
    elif value > 0:
        return f"${value:,.0f}"
    return "N/A"


def _generate_sparkline_svg(data, color="#00ff88"):
    """Generate an inline SVG sparkline from data points."""
    if not data or len(data) < 2:
        return ""
    width, height = 120, 32
    min_val = min(data)
    max_val = max(data)
    val_range = max_val - min_val if max_val != min_val else 1
    points = []
    for i, val in enumerate(data):
        x = (i / (len(data) - 1)) * width
        y = height - ((val - min_val) / val_range) * (height - 4) - 2
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    fill_points = f"0,{height} " + polyline + f" {width},{height}"
    uid = abs(hash(tuple(data))) % 100000
    return (
        f'<div class="ok-metric-sparkline">'
        f'<svg width="100%" height="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<defs><linearGradient id="sg{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.3"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{fill_points}" fill="url(#sg{uid})"/>'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg></div>'
    )


def _format_large_number(val):
    """Formatea números grandes a B/M/K."""
    if not val or val == 0:
        return "N/D"
    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.0f}M"
    if abs(val) >= 1e3:
        return f"${val/1e3:.0f}K"
    return f"${val:,.0f}"


def render_oi_heatmap(
    df: pd.DataFrame,
    min_oi_threshold: int = 1000,
    tipo_filter: str = "ALL",
    key_suffix: str = "",
) -> None:
    """Heatmap interactivo de Open Interest con transparencia total.

    Cómo ayuda a decisiones de inversión
    ------------------------------------
    * **Clusters de OI alto (rojo)** → muros de resistencia / soporte gamma
      donde creadores de mercado tienen exposición concentrada.  Funcionan
      como niveles donde el precio tiende a frenarse (pin risk).
    * **Zonas verdes / vacías** → baja concentración de OI; el precio puede
      moverse libremente a través de esos strikes sin resistencia.
    * **Expiración dominante** → fila con mayor OI total indica el
      vencimiento con mayor *gamma exposure* concentrada.
    * **Hover enriquecido (5 campos)** → cada celda muestra **OI + Volumen
      + Delta + Gamma + IV + Prima**, permitiendo distinguir:
      - Actividad fresca (volumen alto vs. OI alto)
      - Dirección (delta positivo = alcista, negativo = bajista)
      - Sensibilidad (gamma alto = movimiento rápido en delta)
      - Volatilidad implícita y costo de la prima

    Args:
        df: DataFrame con columnas ``OI``, ``Volumen``, ``Delta``,
            ``Gamma``, ``IV``, ``Ultimo``, ``Strike``, ``Vencimiento``
            y opcionalmente ``Tipo``.
        min_oi_threshold: Umbral mínimo de OI; filtra ruido retail.
        tipo_filter: ``"ALL"``, ``"CALL"`` o ``"PUT"``.
        key_suffix: Sufijo para el ``st.plotly_chart`` key (evita
            colisiones si se renderiza más de una vez).

    Example (pytest-compatible)::

        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'OI': [5000, 1500, 200], 'Volumen': [300, 100, 10],
        ...     'Delta': [0.50, -0.30, 0.10], 'Gamma': [0.02, 0.01, 0.005],
        ...     'IV': [25.0, 30.0, 15.0], 'Ultimo': [5.10, 3.00, 0.50],
        ...     'Strike': [590.0, 600.0, 610.0],
        ...     'Vencimiento': ['2026-03-20', '2026-03-20', '2026-03-20'],
        ...     'Tipo': ['CALL', 'PUT', 'CALL'],
        ... })
        >>> # render_oi_heatmap(df, min_oi_threshold=1000)  # renders 2 cells
    """
    if df is None or df.empty:
        st.info("No hay datos con el filtro actual.")
        return

    try:
        _df = df.copy()

        # Normalizar Prima
        if "Prima_Volumen" in _df.columns and "Prima_Vol" not in _df.columns:
            _df = _df.rename(columns={"Prima_Volumen": "Prima_Vol"})

        # Filtro por tipo
        if tipo_filter != "ALL" and "Tipo" in _df.columns:
            _df = _df[_df["Tipo"] == tipo_filter]

        # Filtro OI mínimo
        if "OI" not in _df.columns:
            st.warning("El DataFrame no contiene la columna 'OI'.")
            return
        _df = _df[_df["OI"] >= min_oi_threshold]

        if _df.empty:
            st.info(f"No hay contratos con OI ≥ {min_oi_threshold:,} para el filtro actual.")
            return

        # Rellenar Nones en columnas numéricas para que pivot_table no falle
        for col in ("Delta", "Gamma", "IV", "Ultimo"):
            if col in _df.columns:
                _df[col] = pd.to_numeric(_df[col], errors="coerce").fillna(0)

        # ── Matrices pivotadas (mismas dimensiones) ──────────────────
        oi_matrix = _df.pivot_table(
            values="OI", index="Vencimiento", columns="Strike", aggfunc="sum",
        ).fillna(0)

        vol_matrix = _df.pivot_table(
            values="Volumen", index="Vencimiento", columns="Strike", aggfunc="sum",
        ).reindex_like(oi_matrix).fillna(0)

        delta_matrix = _df.pivot_table(
            values="Delta", index="Vencimiento", columns="Strike", aggfunc="mean",
        ).reindex_like(oi_matrix).fillna(0)

        gamma_matrix = _df.pivot_table(
            values="Gamma", index="Vencimiento", columns="Strike", aggfunc="mean",
        ).reindex_like(oi_matrix).fillna(0)

        iv_matrix = _df.pivot_table(
            values="IV", index="Vencimiento", columns="Strike", aggfunc="mean",
        ).reindex_like(oi_matrix).fillna(0)

        prima_matrix = _df.pivot_table(
            values="Ultimo", index="Vencimiento", columns="Strike", aggfunc="mean",
        ).reindex_like(oi_matrix).fillna(0)

        # Limitar a top 40 strikes con mayor OI total (evita chart ilegible)
        all_matrices = [oi_matrix, vol_matrix, delta_matrix, gamma_matrix, iv_matrix, prima_matrix]
        if oi_matrix.shape[1] > 40:
            top_cols = oi_matrix.sum(axis=0).nlargest(40).index
            all_matrices = [m[top_cols] for m in all_matrices]
        oi_matrix, vol_matrix, delta_matrix, gamma_matrix, iv_matrix, prima_matrix = all_matrices

        # Ordenar strikes ascendente
        sorted_cols = sorted(oi_matrix.columns)
        oi_matrix = oi_matrix[sorted_cols]
        vol_matrix = vol_matrix[sorted_cols]
        delta_matrix = delta_matrix[sorted_cols]
        gamma_matrix = gamma_matrix[sorted_cols]
        iv_matrix = iv_matrix[sorted_cols]
        prima_matrix = prima_matrix[sorted_cols]

        # ── customdata: (rows × cols × 5) → Vol, Delta, Gamma, IV, Prima
        customdata = np.stack([
            vol_matrix.values,
            delta_matrix.values,
            gamma_matrix.values,
            iv_matrix.values,
            prima_matrix.values,
        ], axis=-1)

        x_labels = [f"${s:,.0f}" for s in oi_matrix.columns]
        y_labels = oi_matrix.index.tolist()

        # Texto en celdas solo si la matriz es manejable (≤ 400 celdas)
        n_cells = oi_matrix.shape[0] * oi_matrix.shape[1]
        _text_fmt: str | bool = ".0f" if n_cells <= 400 else False

        fig = px.imshow(
            oi_matrix.values,
            x=x_labels,
            y=y_labels,
            aspect="auto",
            color_continuous_scale="RdYlGn_r",
            labels=dict(x="Strike", y="Expiración", color="Open Interest"),
            text_auto=_text_fmt,
        )

        fig.update_traces(
            customdata=customdata,
            hovertemplate=(
                "Strike: %{x}<br>"
                "Expiración: %{y}<br>"
                "OI: %{z:,.0f}<br>"
                "Volumen: %{customdata[0]:,.0f}<br>"
                "Delta: %{customdata[1]:.3f}<br>"
                "Gamma: %{customdata[2]:.4f}<br>"
                "IV: %{customdata[3]:.1f}%<br>"
                "Prima: $%{customdata[4]:.2f}"
                "<extra></extra>"
            ),
        )

        _tipo_label = tipo_filter if tipo_filter != "ALL" else "CALL + PUT"
        n_exps = len(oi_matrix)
        _height = max(650, min(750, n_exps * 55 + 150))

        fig.update_layout(
            title=dict(
                text=(
                    f"Heatmap de Open Interest — {_tipo_label}"
                    f"  (umbral ≥ {min_oi_threshold:,})"
                ),
                font=dict(size=15, color="white"),
                subtitle=dict(
                    text="Clusters altos de OI suelen indicar niveles clave de soporte/resistencia",
                    font=dict(size=11, color="#94a3b8"),
                ),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white", family="Inter, sans-serif"),
            height=_height,
            margin=dict(l=120, r=20, t=75, b=80),
            xaxis=dict(
                title="Strike Price",
                color="#94a3b8",
                tickangle=-45,
                tickfont=dict(size=10),
                side="bottom",
            ),
            yaxis=dict(
                title="Expiración",
                color="#94a3b8",
                tickfont=dict(size=11),
            ),
            coloraxis_colorbar=dict(
                title=dict(text="Open Interest", font=dict(color="#94a3b8", size=11)),
                tickfont=dict(color="#94a3b8", size=10),
            ),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"oi_heatmap_interactive{key_suffix}",
        )

    except Exception as exc:
        logger.error("Error renderizando OI heatmap: %s", exc, exc_info=True)
        st.error(f"Error al generar el heatmap de OI: {exc}")


def render_bias_gauge(
    bias_score: float,
    oi_calls: int = 0,
    oi_puts: int = 0,
    ticker: str = "",
    height: int = 300,
    key_suffix: str = "",
) -> None:
    """Gauge de sesgo alcista/bajista basado en el ratio Call/Put de OI.

    Cómo ayuda a decisiones de inversión
    ------------------------------------
    * **Lectura instantánea**: un vistazo revela si las opciones están
      posicionadas para subida (calls dominan) o bajada (puts dominan).
    * **Delta respecto a neutral (1.0)** → indica la magnitud de la
      desviación y si está aumentando o disminuyendo entre escaneos.
    * **Contexto numérico en hover y caption** → el usuario ve
      OI total calls vs puts, no solo un número abstracto.

    Escala:
        - 0.0 → Fuertemente bajista (solo puts)
        - 1.0 → Neutral (equilibrio)
        - 2.0 → Fuertemente alcista (solo calls)

    Args:
        bias_score: Valor 0–2 calculado por ``calculate_call_put_bias``.
        oi_calls: OI total de calls (para el caption).
        oi_puts: OI total de puts (para el caption).
        ticker: Símbolo del activo.
        height: Altura del gráfico en píxeles.
        key_suffix: Sufijo para evitar colisiones de key.

    Example (pytest-compatible)::

        >>> # render_bias_gauge(1.35, oi_calls=50000, oi_puts=30000, ticker="SPY")
    """
    import plotly.graph_objects as go

    if bias_score < 0 or bias_score > 2:
        st.error("Score de bias inválido (debe estar entre 0 y 2).")
        return

    try:
        # Interpretación textual
        if bias_score < 0.6:
            interpretation = "Sesgo Bajista Fuerte"
            bar_color = "#dc2626"  # rojo intenso
        elif bias_score < 0.8:
            interpretation = "Sesgo Bajista Moderado"
            bar_color = "#ef4444"  # rojo
        elif bias_score < 1.2:
            interpretation = "Sesgo Neutral"
            bar_color = "#64748b"  # gris azulado
        elif bias_score < 1.4:
            interpretation = "Sesgo Alcista Moderado"
            bar_color = "#22c55e"  # verde
        else:
            interpretation = "Sesgo Alcista Fuerte"
            bar_color = "#16a34a"  # verde intenso

        _title_ticker = f" — {ticker}" if ticker else ""

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=bias_score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": f"Sesgo Call/Put{_title_ticker}",
                "font": {"size": 16, "color": "white"},
            },
            number={
                "font": {"size": 42, "color": bar_color},
                "valueformat": ".2f",
            },
            delta={
                "reference": 1.0,
                "increasing": {"color": "#22c55e"},
                "decreasing": {"color": "#ef4444"},
                "valueformat": ".2f",
                "prefix": "Δ vs neutral: ",
            },
            gauge={
                "axis": {
                    "range": [0, 2],
                    "tickwidth": 1,
                    "tickcolor": "#475569",
                    "tickfont": {"color": "#94a3b8", "size": 10},
                    "dtick": 0.25,
                },
                "bar": {"color": bar_color, "thickness": 0.25},
                "bgcolor": "#0f172a",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 0.6], "color": "rgba(220, 38, 38, 0.30)"},
                    {"range": [0.6, 0.8], "color": "rgba(239, 68, 68, 0.18)"},
                    {"range": [0.8, 1.2], "color": "rgba(100, 116, 139, 0.15)"},
                    {"range": [1.2, 1.4], "color": "rgba(34, 197, 94, 0.18)"},
                    {"range": [1.4, 2.0], "color": "rgba(22, 163, 74, 0.30)"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 3},
                    "thickness": 0.8,
                    "value": bias_score,
                },
            },
        ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white", family="Inter, sans-serif"),
            height=height,
            margin=dict(l=25, r=25, t=55, b=5),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"bias_gauge{key_suffix}",
        )

        # Interpretación debajo del gráfico
        st.markdown(
            f'<div style="text-align:center;font-size:1.1rem;font-weight:700;'
            f'color:{bar_color};margin:-8px 0 4px 0;">{interpretation}</div>',
            unsafe_allow_html=True,
        )

        # Caption explicativo con datos crudos
        _calls_fmt = f"{oi_calls:,}" if oi_calls else "0"
        _puts_fmt = f"{oi_puts:,}" if oi_puts else "0"
        st.caption(
            f"{interpretation} | OI Calls: {_calls_fmt} vs OI Puts: {_puts_fmt} | "
            f"Basado en Open Interest total de la cadena actual "
            f"(fórmula: 2 × OI_calls / (OI_calls + OI_puts))"
        )

    except Exception as exc:
        logger.error("Error renderizando bias gauge: %s", exc, exc_info=True)
        st.error(f"Error al generar el gauge de sesgo: {exc}")


def render_fundamentals_card(data: dict, ticker: str) -> None:
    """Tarjeta HTML de datos fundamentales enriquecidos (Alpha Vantage).

    Muestra métricas clave de valuación, rentabilidad, earnings history,
    y señales interpretadas que ayudan a contextualizar las opciones.

    Args:
        data: dict de enrich_with_fundamentals(). Si contiene "error" muestra warning.
        ticker: Símbolo para título.
    """
    from ui.components.metric_cards import render_metric_card, render_metric_row

    if "error" in data:
        st.warning(f"📊 Fundamentales: {data['error']}")
        return

    name = data.get("name", ticker)
    source = data.get("source", "Alpha Vantage")

    # ── Señales interpretadas ────────────────────────────────────
    overall = data.get("overall_interpretation", "")
    signals = data.get("signals", [])

    if overall:
        st.markdown(overall)

    # ── Métricas en grid ─────────────────────────────────────────
    def _fmt_val(val, fmt=".2f", prefix="", suffix=""):
        """Formatea un valor para mostrar, o N/A si es None/0."""
        if val is None or val == 0:
            return "N/A"
        return f"{prefix}{val:{fmt}}{suffix}"

    def _fmt_money(val):
        if val is None or val == 0:
            return "N/A"
        if val >= 1e12:
            return f"${val/1e12:.1f}T"
        if val >= 1e9:
            return f"${val/1e9:.1f}B"
        if val >= 1e6:
            return f"${val/1e6:.0f}M"
        return f"${val:,.0f}"

    # Row 1: Valuación
    peg_val = data.get("peg_ratio")
    pe_fwd = data.get("pe_forward")
    ev_ebitda = data.get("ev_to_ebitda")
    rev_ttm = data.get("revenue_ttm", 0)

    peg_color = (
        "#10b981" if peg_val and 0 < peg_val < 1.5 else
        "#f59e0b" if peg_val and peg_val < 2.5 else
        "#ef4444" if peg_val and peg_val >= 2.5 else
        "#64748b"
    )

    cards_row1 = [
        render_metric_card("PEG Ratio", _fmt_val(peg_val), color_override=peg_color),
        render_metric_card("P/E Forward", _fmt_val(pe_fwd)),
        render_metric_card("EV/EBITDA", _fmt_val(ev_ebitda)),
        render_metric_card("Revenue TTM", _fmt_money(rev_ttm)),
    ]
    st.markdown(render_metric_row(cards_row1), unsafe_allow_html=True)

    # Row 2: Rentabilidad + Mercado
    pm = data.get("profit_margin")
    roe = data.get("roe")
    short_pct = data.get("short_interest_pct", 0)
    eps = data.get("eps_ttm")

    short_color = (
        "#ef4444" if short_pct > 15 else
        "#f59e0b" if short_pct > 5 else
        "#10b981"
    )

    cards_row2 = [
        render_metric_card("Margen Neto", _fmt_val(pm, suffix="%")),
        render_metric_card("ROE", _fmt_val(roe, suffix="%")),
        render_metric_card("Short Interest", _fmt_val(short_pct, suffix="%"), color_override=short_color),
        render_metric_card("EPS TTM", _fmt_val(eps, prefix="$")),
    ]
    st.markdown(render_metric_row(cards_row2), unsafe_allow_html=True)

    # ── Señales / bullets ────────────────────────────────────────
    if signals:
        signals_html = "".join(f"<li>{s}</li>" for s in signals)
        st.markdown(
            f'<ul style="margin:8px 0;padding-left:20px;color:#cbd5e1;'
            f'font-size:0.88rem;line-height:1.7;">{signals_html}</ul>',
            unsafe_allow_html=True,
        )

    # ── Earnings History (expandible) ────────────────────────────
    quarterly = data.get("quarterly_earnings", [])
    if quarterly:
        beat_streak = data.get("earnings_beat_streak", 0)
        streak_txt = f" — 🔥 Racha: {beat_streak} beats consecutivos" if beat_streak > 1 else ""

        with st.expander(f"📊 Historial de Earnings ({len(quarterly)} quarters){streak_txt}"):
            rows_html = ""
            for q in quarterly:
                surp = q.get("surprise_pct", 0)
                if surp > 0:
                    badge = f'<span style="color:#10b981;font-weight:700;">+{surp:.1f}% ✓</span>'
                elif surp < 0:
                    badge = f'<span style="color:#ef4444;font-weight:700;">{surp:.1f}% ✗</span>'
                else:
                    badge = '<span style="color:#64748b;">0.0%</span>'

                rows_html += (
                    f'<tr>'
                    f'<td style="padding:6px 10px;">{q.get("date", "N/A")}</td>'
                    f'<td style="padding:6px 10px;text-align:right;">${q.get("estimated_eps", 0):.2f}</td>'
                    f'<td style="padding:6px 10px;text-align:right;">${q.get("reported_eps", 0):.2f}</td>'
                    f'<td style="padding:6px 10px;text-align:right;">{badge}</td>'
                    f'</tr>'
                )

            st.markdown(f"""
<table class="ok-tbl" style="width:100%;font-size:0.85rem;">
<thead><tr>
<th style="padding:8px 10px;text-align:left;">Fecha</th>
<th style="padding:8px 10px;text-align:right;">EPS Est.</th>
<th style="padding:8px 10px;text-align:right;">EPS Rep.</th>
<th style="padding:8px 10px;text-align:right;">Surprise</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

    # ── Footer / Source ──────────────────────────────────────────
    st.caption(
        f"Fuente: {source} | Última actualización de earnings: "
        f"{data.get('last_earnings_date', 'N/A')} | "
        f"Combina con OI, IV y flujo para decisiones contextualizadas"
    )
