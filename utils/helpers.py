# -*- coding: utf-8 -*-
"""
Funciones auxiliares de datos: Barchart OI, inyección OI_Chg, enriquecimiento de datos,
y loaders de watchlist dinámicas con caché.
Extraídas de app_web.py — cero cambios de lógica.
"""
import logging
import numpy as np
import pandas as pd
import streamlit as st

from config.watchlists import WATCHLIST_EMPRESAS, WATCHLIST_EMERGENTES
from core.watchlist_builder import construir_watchlist_consolidadas, construir_watchlist_emergentes
from core.barchart_oi import obtener_oi_simbolo
from core.flow_classifier import classify_flow_bulk, detect_hedge_bulk, add_smart_money_tier
from core.smart_money import calculate_sm_flow_score

logger = logging.getLogger(__name__)


# ============================================================================
#                    WATCHLIST LOADERS (cacheadas 24h)
# ============================================================================
@st.cache_data(ttl=86400, show_spinner=False)
def _cargar_watchlist_consolidadas_dinamica():
    """
    Construye la watchlist consolidada dinámica con market caps en vivo.
    Cacheada 24 horas para no cargar yfinance en cada reinicio.
    Usa WATCHLIST_EMPRESAS estático como fallback si falla yfinance.
    """
    return construir_watchlist_consolidadas(n=18, fallback=WATCHLIST_EMPRESAS)


@st.cache_data(ttl=86400, show_spinner=False)
def _cargar_watchlist_emergentes_dinamica():
    """
    Construye la watchlist emergente dinámica ordenada por momentum de 52 semanas.
    Cacheada 24 horas para no cargar yfinance en cada reinicio.
    Usa WATCHLIST_EMERGENTES estático como fallback si falla yfinance.
    """
    return construir_watchlist_emergentes(n=18, fallback=WATCHLIST_EMERGENTES)


# ============================================================================
#                    BARCHART OI
# ============================================================================
def _fetch_barchart_oi(simbolo, progress_bar=None):
    """Obtiene datos de OI de Barchart para un símbolo y actualiza session_state.
    
    Args:
        simbolo: Ticker del símbolo
        progress_bar: (opcional) Objeto st.progress() para actualizar durante el fetch
    """
    try:
        if progress_bar:
            progress_bar.progress(0.25, text="Cargando datos...")
        
        df_calls, err_c = obtener_oi_simbolo(simbolo, tipo="call")
        
        if progress_bar:
            progress_bar.progress(0.60, text="Cargando datos...")
        
        df_puts, err_p = obtener_oi_simbolo(simbolo, tipo="put")
        
        if progress_bar:
            progress_bar.progress(0.90, text="Cargando datos...")

        frames = []
        if df_calls is not None and not df_calls.empty:
            df_calls["Tipo"] = "CALL"
            frames.append(df_calls)
        if df_puts is not None and not df_puts.empty:
            df_puts["Tipo"] = "PUT"
            frames.append(df_puts)

        if frames:
            combined = pd.concat(frames, ignore_index=True)
            # Deduplicar por símbolo OCC por si quedaron duplicados entre calls y puts
            if "Contrato" in combined.columns:
                combined = combined.drop_duplicates(subset=["Contrato"], keep="first")
            combined = combined.sort_values("OI_Chg", ascending=False).reset_index(drop=True)
            st.session_state.barchart_data = combined
            st.session_state.barchart_error = None
        else:
            err_msg = err_c or err_p or "Sin datos de Barchart"
            st.session_state.barchart_data = None
            st.session_state.barchart_error = err_msg
        
        if progress_bar:
            progress_bar.progress(1.0, text="Cargando datos...")
    except Exception as e:
        st.session_state.barchart_data = None
        st.session_state.barchart_error = f"Error Barchart: {e}"


def _inyectar_oi_chg_barchart():
    """Inyecta OI_Chg real de Barchart en datos_completos, alertas_actuales y clusters."""
    bc = st.session_state.get("barchart_data")
    if bc is None or bc.empty:
        return

    # Crear mapa (Vencimiento, Tipo, Strike) → OI_Chg de Barchart — vectorizado
    try:
        bc_clean = bc[["Vencimiento", "Tipo", "Strike", "OI_Chg"]].copy()
        bc_clean["Vencimiento"] = bc_clean["Vencimiento"].astype(str)
        bc_clean["Strike"] = bc_clean["Strike"].astype(float)
        bc_clean["OI_Chg"] = bc_clean["OI_Chg"].fillna(0).astype(int)
        bc_clean["abs_chg"] = bc_clean["OI_Chg"].abs()
        # Quedarse con el mayor |OI_Chg| por clave
        bc_dedup = bc_clean.sort_values("abs_chg", ascending=False).drop_duplicates(
            subset=["Vencimiento", "Tipo", "Strike"], keep="first"
        )
        bc_map = dict(
            zip(
                zip(bc_dedup["Vencimiento"], bc_dedup["Tipo"], bc_dedup["Strike"]),
                bc_dedup["OI_Chg"],
            )
        )
    except (KeyError, ValueError):
        return

    if not bc_map:
        return

    # Inyectar en datos_completos
    for d in st.session_state.datos_completos:
        key = (str(d.get("Vencimiento", "")), d.get("Tipo", ""), float(d.get("Strike", 0)))
        if key in bc_map:
            d["OI_Chg"] = bc_map[key]

    # Inyectar en alertas_actuales
    for a in st.session_state.alertas_actuales:
        key = (str(a.get("Vencimiento", "")), a.get("Tipo_Opcion", ""), float(a.get("Strike", 0)))
        if key in bc_map:
            a["OI_Chg"] = bc_map[key]

    # Inyectar en clusters (detalle)
    for c in st.session_state.clusters_detectados:
        total_chg = 0
        for det in c.get("Detalle", []):
            key = (str(det.get("Vencimiento", "")), det.get("Tipo_Opcion", c.get("Tipo_Opcion", "")), float(det.get("Strike", 0)))
            if key in bc_map:
                det["OI_Chg"] = bc_map[key]
                total_chg += bc_map[key]
        if total_chg != 0:
            c["OI_Chg_Total"] = total_chg


# ============================================================================
#                    ENRIQUECIMIENTO DE DATOS
# ============================================================================
def _enriquecer_datos_opcion(datos, precio_subyacente=None):
    """Enriquece datos de opciones con métricas derivadas calculadas — vectorizado."""
    if not isinstance(datos, (list, pd.DataFrame)):
        return datos

    was_list = not isinstance(datos, pd.DataFrame)
    df = pd.DataFrame(datos) if was_list else datos.copy()

    if df.empty:
        return datos

    # Extraer columnas como arrays numéricos
    ask = pd.to_numeric(df.get("Ask", 0), errors="coerce").fillna(0)
    bid = pd.to_numeric(df.get("Bid", 0), errors="coerce").fillna(0)
    strike = pd.to_numeric(df.get("Strike", 0), errors="coerce").fillna(0)
    volumen = pd.to_numeric(df.get("Volumen", 0), errors="coerce").fillna(0).astype(int)
    oi = pd.to_numeric(df.get("OI", 0), errors="coerce").fillna(0).astype(int)
    last_price = pd.to_numeric(df.get("Ultimo", 0), errors="coerce").fillna(0)

    # Bid/Ask Spread
    has_ask_bid = (ask > 0) & (bid > 0)
    spread = np.where(has_ask_bid, ask - bid, np.nan)
    spread_pct = np.where(has_ask_bid & (ask > 0), (spread / ask) * 100, np.nan)
    mid_price = np.where(has_ask_bid, (ask + bid) / 2,
                         np.where(last_price > 0, last_price, np.nan))

    df["Spread"] = spread
    df["Spread_Pct"] = spread_pct
    df["Mid_Price"] = mid_price

    # Volume/OI Ratio
    df["Vol_OI_Ratio"] = np.where(oi > 0, volumen / oi, 0)

    # Liquidity Score (0-100)
    vol_score = np.minimum(volumen / 100, 1) * 40
    oi_score = np.minimum(oi / 500, 1) * 30
    sp_arr = np.array(spread_pct, dtype=float)
    valid_sp = ~np.isnan(sp_arr) & (sp_arr > 0)
    spread_score = np.where(valid_sp, np.maximum(0, 1 - sp_arr / 10) * 30, 0)
    df["Liquidity_Score"] = vol_score + oi_score + spread_score

    # Moneyness y Distance_Pct
    if precio_subyacente and precio_subyacente > 0:
        tipo_col = df.get("Tipo_Opcion", df.get("Tipo", pd.Series([""] * len(df))))
        is_call = tipo_col.str.upper() == "CALL"
        moneyness_ratio = np.where(is_call, strike / precio_subyacente, precio_subyacente / strike)
        moneyness_label = np.where(
            strike <= 0, "N/A",
            np.where(moneyness_ratio < 0.95, "ITM",
                     np.where(moneyness_ratio > 1.05, "OTM", "ATM"))
        )
        df["Moneyness"] = moneyness_label
        df["Distance_Pct"] = np.where(
            strike > 0, np.abs(strike - precio_subyacente) / precio_subyacente * 100, 0
        )
    else:
        df["Moneyness"] = "N/A"
        df["Distance_Pct"] = 0

    # Premium/Underlying Ratio
    mid_arr = np.array(mid_price, dtype=float)
    if precio_subyacente and precio_subyacente > 0:
        valid_mid = ~np.isnan(mid_arr) & (mid_arr > 0)
        df["Premium_Ratio"] = np.where(valid_mid, (mid_arr / precio_subyacente) * 100, np.nan)
    else:
        df["Premium_Ratio"] = np.nan

    # Time Value
    if precio_subyacente and precio_subyacente > 0:
        tipo_col2 = df.get("Tipo_Opcion", df.get("Tipo", pd.Series([""] * len(df))))
        is_call2 = tipo_col2.str.upper() == "CALL"
        intrinsic = np.where(
            is_call2,
            np.maximum(precio_subyacente - strike, 0),
            np.maximum(strike - precio_subyacente, 0),
        )
        valid_tv = ~np.isnan(mid_arr) & (mid_arr > 0) & (strike > 0)
        tv = np.where(valid_tv, np.maximum(mid_arr - intrinsic, 0), np.nan)
        tv_pct = np.where(valid_tv & (mid_arr > 0), tv / mid_arr * 100, np.nan)
        df["Time_Value"] = tv
        df["Time_Value_Pct"] = tv_pct
    else:
        df["Time_Value"] = np.nan
        df["Time_Value_Pct"] = np.nan

    # Flow Type — clasificación institucional del flujo
    df["Flow_Type"] = classify_flow_bulk(df)

    # Hedge institucional — alertas de protección pesada
    h_alert, h_level, h_detail = detect_hedge_bulk(df)
    df["Hedge_Alert"] = h_alert
    df["Hedge_Level"] = h_level
    df["Hedge_Detail"] = h_detail

    # Smart Money Flow Score (0-100) — convicción institucional compuesta
    # Marcar filas con hedge activo para recibir bonus de +12% en el score
    if "Hedge_Level" in df.columns:
        df["is_smart_money_hedge"] = df["Hedge_Level"].ne("")
    spot = precio_subyacente if precio_subyacente and precio_subyacente > 0 else 0.0
    try:
        df = calculate_sm_flow_score(df, spot)
    except Exception:
        df["sm_flow_score"] = 0.0

    # Smart Money Tier — categoría cualitativa basada en el score
    df = add_smart_money_tier(df)

    return df.to_dict("records") if was_list else df
