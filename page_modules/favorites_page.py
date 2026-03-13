# -*- coding: utf-8 -*-
"""Página: ⭐ Favorites — Contratos y Spreads Favoritos."""
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.formatters import (
    _fmt_monto, _fmt_lado, _fmt_oi_chg, _fmt_delta,
)
from utils.favorites import _eliminar_favorito, _guardar_favoritos, _sync_to_supabase
from ui.components import (
    render_metric_card, render_metric_row, render_pro_table,
    _sentiment_badge, _type_badge,
)
from core.scanner import obtener_historial_contrato


def _first_non_empty(data: dict, keys: list[str], default=None):
    for k in keys:
        if k in data and data.get(k) not in (None, ""):
            return data.get(k)
    return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _is_spread_favorite(fav: dict) -> bool:
    if not isinstance(fav, dict):
        return False

    if fav.get("source") == "alert_10_rules":
        return True
    if str(fav.get("Lado", "")).upper() == "CREDIT_SPREAD":
        return True
    if any(k in fav for k in ["strike_vendido", "strike_comprado", "Strike Vendido", "Strike Comprado"]):
        return True

    tipo = str(_first_non_empty(fav, ["tipo", "Tipo"], "")).lower()
    if "bull put" in tipo or "bear call" in tipo:
        return True

    return False


def _split_favorites(favoritos: list[dict]) -> tuple[list[tuple[int, dict]], list[tuple[int, dict]]]:
    contracts: list[tuple[int, dict]] = []
    spreads: list[tuple[int, dict]] = []

    for idx, fav in enumerate(favoritos):
        if _is_spread_favorite(fav):
            spreads.append((idx, fav))
        elif isinstance(fav, dict) and fav.get("Contrato"):
            contracts.append((idx, fav))
        else:
            # Entradas legacy o incompletas: se tratan como spread para evitar detalle N/A de contrato.
            spreads.append((idx, fav if isinstance(fav, dict) else {}))

    return contracts, spreads


def _delete_favorite_by_index(favoritos: list[dict], idx_to_delete: int) -> None:
    nuevos = [f for i, f in enumerate(favoritos) if i != idx_to_delete]
    st.session_state.favoritos = nuevos
    _guardar_favoritos(nuevos)
    _sync_to_supabase("favoritos", nuevos)


def _render_contracts_section(favoritos: list[dict], contract_items: list[tuple[int, dict]]) -> None:
    st.markdown("### ⭐ Contratos Favoritos")

    contracts_only = [fav for _, fav in contract_items]
    if not contracts_only:
        st.info("No hay contratos en favoritos.")
        return

    # Métricas rápidas (sin cambios para contratos)
    n_calls_fav = sum(1 for f in contracts_only if f.get("Tipo_Opcion") == "CALL")
    n_puts_fav = sum(1 for f in contracts_only if f.get("Tipo_Opcion") == "PUT")
    prima_total_fav = sum(f.get("Prima_Volumen", 0) for f in contracts_only)
    st.markdown(render_metric_row([
        render_metric_card("Total Favoritos", f"{len(contracts_only)}"),
        render_metric_card("Calls", f"{n_calls_fav}"),
        render_metric_card("Puts", f"{n_puts_fav}"),
        render_metric_card("Prima Total", _fmt_monto(prima_total_fav)),
    ]), unsafe_allow_html=True)

    # Tabla resumen
    fav_df = pd.DataFrame(contracts_only)
    cols_tabla_fav = ["Contrato", "Ticker", "Tipo_Opcion", "Strike", "Vencimiento",
                      "Volumen", "OI", "Delta", "Ask", "Bid", "Ultimo", "Lado", "Prima_Volumen"]
    cols_disp_fav = [c for c in cols_tabla_fav if c in fav_df.columns]
    display_fav_df = fav_df[cols_disp_fav].copy()
    if "Tipo_Opcion" in display_fav_df.columns and "Lado" in display_fav_df.columns:
        display_fav_df.insert(0, "Sentimiento", display_fav_df.apply(
            lambda row: _sentiment_badge(row["Tipo_Opcion"], row.get("Lado", "N/A")), axis=1
        ))
    if "Tipo_Opcion" in display_fav_df.columns:
        display_fav_df["Tipo_Opcion"] = display_fav_df["Tipo_Opcion"].apply(_type_badge)
    if "Delta" in display_fav_df.columns:
        display_fav_df["Delta"] = display_fav_df["Delta"].apply(_fmt_delta)
    if "Lado" in display_fav_df.columns:
        display_fav_df["Lado"] = display_fav_df["Lado"].apply(_fmt_lado)
    if "Prima_Volumen" in display_fav_df.columns:
        display_fav_df = display_fav_df.rename(columns={"Prima_Volumen": "Prima Total"})
        display_fav_df["Prima Total"] = display_fav_df["Prima Total"].apply(_fmt_monto)
    st.markdown(
        render_pro_table(display_fav_df, title="⭐ Favoritos (Contratos)", badge_count=f"{len(contracts_only)}"),
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("#### 🔍 Detalle de Contratos")

    for idx_fav, fav in contract_items:
        fav_sym = fav.get("Contrato", "N/A")
        fav_tipo = fav.get("Tipo_Opcion", "N/A")
        fav_strike = fav.get("Strike", 0)
        fav_venc = fav.get("Vencimiento", "N/A")
        fav_prima = fav.get("Prima_Volumen", 0)

        try:
            dias_venc = (datetime.strptime(fav_venc, "%Y-%m-%d") - datetime.now()).days
            dias_str = f"{dias_venc}d" if dias_venc >= 0 else "EXPIRADO"
        except Exception:
            dias_str = "N/A"

        fav_label = (
            f"⭐ {fav_tipo} ${fav_strike} | Venc: {fav_venc} ({dias_str}) | "
            f"Prima: ${fav_prima:,.0f} | {fav_sym}"
        )

        with st.expander(fav_label, expanded=False):
            col_fav_info, col_fav_chart = st.columns([1, 2])

            with col_fav_info:
                st.markdown("**📄 Información del Contrato**")
                st.markdown(f"- **Símbolo:** `{fav_sym}`")
                st.markdown(f"- **Ticker:** {fav.get('Ticker', 'N/A')}")
                st.markdown(f"- **Tipo:** {fav_tipo}")
                st.markdown(f"- **Strike:** ${fav_strike}")
                st.markdown(f"- **Vencimiento:** {fav_venc} ({dias_str})")
                st.markdown(f"- **Volumen:** {fav.get('Volumen', 0):,}")
                st.markdown(f"- **OI:** {fav.get('OI', 0):,}")
                oi_chg_val = fav.get('OI_Chg', 0)
                st.markdown(f"- **OI Chg:** {_fmt_oi_chg(oi_chg_val)}")
                st.markdown(f"- **Ask:** ${fav.get('Ask', 0)}")
                st.markdown(f"- **Bid:** ${fav.get('Bid', 0)}")
                st.markdown(f"- **Último:** ${fav.get('Ultimo', 0)}")
                st.markdown(f"- **Lado:** {_fmt_lado(fav.get('Lado', 'N/A'))}")
                iv_fav = fav.get('IV', 0)
                st.markdown(f"- **IV:** {iv_fav:.1f}%" if iv_fav > 0 else "- **IV:** N/A")
                st.markdown(f"- **Prima Total:** {_fmt_monto(fav.get('Prima_Volumen', 0))}")
                st.markdown(f"- **Tipo Alerta:** {fav.get('Tipo_Alerta', 'N/A')}")
                st.markdown(f"- **Guardado:** {fav.get('Guardado_En', 'N/A')}")

                if st.button("🗑️ Eliminar de Favoritos", key=f"del_fav_{idx_fav}_{fav_sym}", use_container_width=True):
                    if fav_sym and fav_sym != "N/A":
                        _eliminar_favorito(fav_sym)
                    else:
                        _delete_favorite_by_index(favoritos, idx_fav)
                    st.success(f"🗑️ {fav_sym} eliminado de Favoritos")
                    st.rerun()

            with col_fav_chart:
                if fav_sym and fav_sym != "N/A":
                    with st.spinner("Cargando gráfica del contrato..."):
                        hist_fav, err_fav = obtener_historial_contrato(fav_sym)

                    if err_fav:
                        st.warning(f"⚠️ Error al cargar historial: {err_fav}")
                    elif hist_fav.empty:
                        st.info("ℹ️ No hay datos históricos disponibles.")
                    else:
                        st.markdown(f"**Precio del contrato** — `{fav_sym}`")
                        chart_fav_price = hist_fav[["Close"]].copy()
                        chart_fav_price.columns = ["Precio"]
                        st.line_chart(chart_fav_price, height=280)

                        if "Volume" in hist_fav.columns:
                            chart_fav_vol = hist_fav[["Volume"]].copy()
                            chart_fav_vol.columns = ["Volumen"]
                            st.bar_chart(chart_fav_vol, height=160)


def _render_spreads_section(favoritos: list[dict], spread_items: list[tuple[int, dict]]) -> None:
    st.markdown("### 🧠 Spreads Favoritos")

    spreads_only = [fav for _, fav in spread_items]
    if not spreads_only:
        st.info("No hay spreads guardados.")
        return

    n_bull = 0
    n_bear = 0
    credito_total = 0.0
    for fav in spreads_only:
        tipo = str(_first_non_empty(fav, ["tipo", "Tipo"], ""))
        if "Bull Put" in tipo:
            n_bull += 1
        elif "Bear Call" in tipo:
            n_bear += 1
        credito = _safe_float(_first_non_empty(fav, ["credito", "Crédito"], 0))
        if credito <= 0:
            credito = _safe_float(fav.get("Prima_Volumen", 0)) / 100.0
        credito_total += credito

    st.markdown(render_metric_row([
        render_metric_card("Total Spreads", f"{len(spreads_only)}"),
        render_metric_card("Bull Put", f"{n_bull}"),
        render_metric_card("Bear Call", f"{n_bear}"),
        render_metric_card("Crédito Total", f"${credito_total:,.2f}"),
    ]), unsafe_allow_html=True)

    st.markdown("#### 🔍 Detalle de Spreads")

    for idx_fav, fav in spread_items:
        ticker = str(_first_non_empty(fav, ["ticker", "Ticker"], "N/A")).upper()
        tipo = str(_first_non_empty(fav, ["tipo", "Tipo"], "N/A"))

        strike_vendido = _safe_float(_first_non_empty(fav, ["strike_vendido", "Strike Vendido", "Strike"], 0))
        strike_comprado = _safe_float(_first_non_empty(fav, ["strike_comprado", "Strike Comprado"], 0))
        dte = _safe_int(_first_non_empty(fav, ["dte", "DTE"], 0))
        credito = _safe_float(_first_non_empty(fav, ["credito", "Crédito"], 0))
        if credito <= 0:
            credito = _safe_float(fav.get("Prima_Volumen", 0)) / 100.0

        riesgo = _safe_float(_first_non_empty(fav, ["riesgo", "Riesgo Máx"], 0))
        retorno_pct = _safe_float(_first_non_empty(fav, ["retorno_pct", "Retorno %"], 0))
        pop_pct = _safe_float(_first_non_empty(fav, ["pop_pct", "POP %"], 0))
        iv_rank = _safe_float(_first_non_empty(fav, ["iv_rank", "IV Rank", "IV"], 0))
        dist_pct = _safe_float(_first_non_empty(fav, ["dist_pct", "Dist Strike %"], 0))
        score = _safe_float(_first_non_empty(fav, ["score", "Score Oportunidad"], 0))
        spot = _safe_float(_first_non_empty(fav, ["spot", "Spot"], 0))

        guardado = _first_non_empty(fav, ["Guardado_En", "saved_at"], "N/A")
        source = _first_non_empty(fav, ["source", "Tipo_Alerta"], "N/A")

        label = (
            f"💸 {ticker} — {tipo} | {strike_vendido:.0f}/{strike_comprado:.0f} | "
            f"Crédito ${credito:.2f} | POP {pop_pct:.0f}%"
        )

        with st.expander(label, expanded=False):
            st.markdown("**📄 Información del Spread**")
            st.markdown(f"- **Ticker:** {ticker}")
            st.markdown(f"- **Tipo:** {tipo}")
            st.markdown(f"- **Spot:** ${spot:.2f}" if spot > 0 else "- **Spot:** N/A")
            st.markdown(f"- **Strike Vendido:** {strike_vendido:.1f}" if strike_vendido > 0 else "- **Strike Vendido:** N/A")
            st.markdown(f"- **Strike Comprado:** {strike_comprado:.1f}" if strike_comprado > 0 else "- **Strike Comprado:** N/A")
            st.markdown(f"- **DTE:** {dte}d" if dte > 0 else "- **DTE:** N/A")
            st.markdown(f"- **Crédito:** ${credito:.2f}" if credito > 0 else "- **Crédito:** N/A")
            st.markdown(f"- **Riesgo Máx:** ${riesgo:.2f}" if riesgo > 0 else "- **Riesgo Máx:** N/A")
            st.markdown(f"- **Retorno:** {retorno_pct:.1f}%" if retorno_pct > 0 else "- **Retorno:** N/A")
            st.markdown(f"- **POP:** {pop_pct:.1f}%" if pop_pct > 0 else "- **POP:** N/A")
            st.markdown(f"- **IV Rank:** {iv_rank:.1f}%" if iv_rank > 0 else "- **IV Rank:** N/A")
            st.markdown(f"- **Distancia al Strike:** {dist_pct:.1f}%" if dist_pct > 0 else "- **Distancia al Strike:** N/A")
            st.markdown(f"- **Score:** {score:.0f}/100" if score > 0 else "- **Score:** N/A")
            st.markdown(f"- **Fuente:** {source}")
            st.markdown(f"- **Guardado:** {guardado}")

            if st.button("🗑️ Eliminar Spread", key=f"del_spread_{idx_fav}", use_container_width=True):
                _delete_favorite_by_index(favoritos, idx_fav)
                st.success(f"🗑️ Spread {ticker} eliminado")
                st.rerun()


def render(ticker_symbol, **kwargs):
    favoritos = st.session_state.get("favoritos", [])

    if not favoritos:
        st.markdown("### ⭐ Favorites")
        st.info("No hay favoritos guardados. Ejecuta un escaneo y usa el botón de guardado.")
        return

    contract_items, spread_items = _split_favorites(favoritos)

    _render_contracts_section(favoritos, contract_items)
    st.markdown("---")
    _render_spreads_section(favoritos, spread_items)

    st.markdown("---")
    col_limpiar, _ = st.columns([1, 3])
    with col_limpiar:
        if st.button("🗑️ Limpiar todos los favoritos", use_container_width=True, type="secondary"):
            st.session_state.favoritos = []
            _guardar_favoritos([])
            _sync_to_supabase("favoritos", [])
            st.success("Se eliminaron todos los favoritos")
            st.rerun()
