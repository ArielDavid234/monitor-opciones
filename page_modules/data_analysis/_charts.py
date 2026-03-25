"""GEX profile chart, OI heatmap, and vol-surface sections for Data Analysis."""
import logging

import plotly.graph_objects as go
import streamlit as st

from ui.plotly_professional_theme import apply_theme, COLORS
from ui.charts import render_oi_heatmap, render_vol_surface

logger = logging.getLogger(__name__)


def render_gex_section(df_analisis, spot_gex, gex_res, gex_profile, skew_res, dealer_state, squeeze, magnet):
    """Render the GEX + Volatility Engine section."""
    st.markdown("### 🧭 Gamma Exposure (GEX) & Volatility Engine")
    st.caption(
        "Perfil institucional por strike: Call GEX (+), Put GEX (-), Net GEX, "
        "Zero Gamma y skew de volatilidad 10% OTM."
    )

    if bool(squeeze.get("squeeze_alert", False)):
        st.markdown(
            """
            <style>
            @keyframes okaPulseAlert {
                0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.65); }
                70% { box-shadow: 0 0 0 12px rgba(239,68,68,0.00); }
                100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.00); }
            }
            </style>
            <div style="background:linear-gradient(135deg,#3b0a0a,#210707);
                        border:2px solid #ef4444;border-radius:12px;padding:12px 14px;
                        margin:8px 0 12px 0;animation:okaPulseAlert 1.6s infinite;">
                <div style="color:#fecaca;font-size:1rem;font-weight:800;">
                    ⚠️ ALERTA DE GAMMA SQUEEZE DETECTADA
                </div>
                <div style="color:#fca5a5;font-size:0.82rem;margin-top:4px;">
                    Los Market Makers están posicionados al descubierto y están siendo
                    forzados a comprar/vender acciones mecánicamente. Riesgo de
                    movimiento violento al alza/baja.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _dp1, _dp2, _dp3, _dp4 = st.columns(4)
    _dp1.metric("Dealer Regime", str(dealer_state.get("regime", "N/A")))
    _dp2.metric("Squeeze Score", f"{float(squeeze.get('score', 0.0)):.1f}/100")
    _dp3.metric(
        "Liquidity Magnet",
        f"{float(magnet.get('primary_magnet', 0.0)):.2f}"
        if float(magnet.get("primary_magnet", 0.0)) > 0 else "N/A",
    )
    _dp4.metric("Magnet Side", str(magnet.get("direction", "N/A")))

    st.markdown(
        f'<p style="color:#94a3b8;font-size:0.78rem;margin:0.1rem 0 1rem 0;">'
        f'Dealer positioning: <b style="color:#cbd5e1;">{dealer_state.get("regime", "N/A")}</b> '
        f"· {str(squeeze.get('explanation', ''))}"
        f"</p>",
        unsafe_allow_html=True,
    )

    if not gex_profile.empty:
        zero_gamma = float(gex_res.get("zero_gamma_level", 0.0) or 0.0)
        call_wall = gex_res.get("call_wall", {"strike": 0.0, "gex": 0.0})
        put_wall = gex_res.get("put_wall", {"strike": 0.0, "gex": 0.0})

        fig_gex = go.Figure()
        fig_gex.add_trace(go.Bar(
            x=gex_profile["strike"],
            y=gex_profile["Call GEX"],
            name="Call GEX",
            marker_color="#16a34a",
            opacity=0.85,
            hovertemplate="Strike %{x}<br>Call GEX: %{y:,.0f}<extra></extra>",
        ))
        fig_gex.add_trace(go.Bar(
            x=gex_profile["strike"],
            y=gex_profile["Put GEX"],
            name="Put GEX",
            marker_color="#ef4444",
            opacity=0.85,
            hovertemplate="Strike %{x}<br>Put GEX: %{y:,.0f}<extra></extra>",
        ))

        if spot_gex > 0:
            fig_gex.add_vline(
                x=spot_gex,
                line_width=2, line_dash="dash", line_color="#f59e0b",
                annotation_text=f"Spot {spot_gex:.2f}",
                annotation_font=dict(color="#f59e0b", size=10),
            )
        if zero_gamma > 0:
            fig_gex.add_vline(
                x=zero_gamma,
                line_width=2, line_dash="dot", line_color="#22d3ee",
                annotation_text=f"Zero Gamma {zero_gamma:.2f}",
                annotation_font=dict(color="#22d3ee", size=10),
            )

        fig_gex.update_layout(
            barmode="relative",
            title=dict(text="Perfil GEX por Strike", font=dict(size=14, color=COLORS["text"])),
            xaxis=dict(title="Strike", color=COLORS["muted"], gridcolor=COLORS["faint"]),
            yaxis=dict(title="GEX", color=COLORS["muted"], gridcolor=COLORS["faint"]),
            paper_bgcolor=COLORS["bg"],
            plot_bgcolor=COLORS["bg"],
            legend=dict(orientation="h", x=0, y=1.12, font=dict(color=COLORS["muted"], size=10)),
            margin=dict(l=30, r=20, t=50, b=30),
            height=360,
        )
        st.plotly_chart(fig_gex, use_container_width=True, key="gex_profile_chart")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Zero Gamma", f"{zero_gamma:.2f}" if zero_gamma > 0 else "N/A")
        m2.metric("Call Wall", f"{float(call_wall.get('strike', 0.0)):.2f}" if call_wall else "N/A")
        m3.metric("Put Wall", f"{float(put_wall.get('strike', 0.0)):.2f}" if put_wall else "N/A")
        m4.metric("Net GEX", f"{float(gex_profile['Net GEX'].sum()):,.0f}")
    else:
        st.info(
            "No hay datos suficientes para construir el perfil GEX. "
            "Se requieren strike + OI y al menos IV (si no hay gamma API)."
        )

    sk1, sk2, sk3 = st.columns(3)
    put_iv = float(skew_res.get("put_iv_10otm", 0.0) or 0.0)
    call_iv = float(skew_res.get("call_iv_10otm", 0.0) or 0.0)
    skew_val = float(skew_res.get("skew", 0.0) or 0.0)
    sk1.metric("IV Put 10% OTM", f"{put_iv:.2f}%")
    sk2.metric("IV Call 10% OTM", f"{call_iv:.2f}%")
    sk3.metric("Skew", f"{skew_val:+.2f} pts", help=str(skew_res.get("regime", "")))

    st.markdown(
        f'<p style="color:#94a3b8;font-size:0.78rem;margin:0.2rem 0 1rem 0;">'
        f'Régimen de volatilidad: <b style="color:#cbd5e1;">{skew_res.get("regime", "Sin datos")}</b>'
        f"</p>",
        unsafe_allow_html=True,
    )


def render_oi_heatmap_section(datos_completos):
    """Render the OI heatmap with metric/type selectors."""
    st.markdown("#### 🗺️ Heatmap de Open Interest")
    hm_col_selector = st.radio(
        "Métrica del heatmap", ["OI", "Volumen", "IV", "Prima_Vol"],
        horizontal=True, key="hm_metric", index=0,
    )
    hm_tipo = st.radio(
        "Tipo", ["ALL", "CALL", "PUT"],
        horizontal=True, key="hm_tipo", index=0,
    )
    fig_hm = render_oi_heatmap(datos_completos, tipo=hm_tipo, value_col=hm_col_selector)
    if fig_hm:
        st.plotly_chart(fig_hm, use_container_width=True, key="oi_heatmap")
    else:
        st.info("Sin datos suficientes para el heatmap.")


def render_vol_surface_section(datos_completos, precio_mc):
    """Render the 3D implied-volatility surface."""
    st.markdown("#### 🌋 Superficie de Volatilidad Implícita (3D)")
    fig_vs = render_vol_surface(datos_completos, spot_price=precio_mc)
    if fig_vs:
        st.plotly_chart(fig_vs, use_container_width=True, key="vol_surface")
        st.caption("Superficie IV por Strike × Vencimiento — Identifica skew y smile de volatilidad")
    else:
        st.info(
            "Sin datos suficientes para la superficie de volatilidad "
            "(necesita ≥2 vencimientos con IV)."
        )
