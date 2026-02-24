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

    # Crear mapa (Vencimiento, Tipo, Strike) → OI_Chg de Barchart
    bc_map = {}
    for _, row in bc.iterrows():
        tipo = row.get("Tipo", "")
        strike = row.get("Strike", 0)
        venc = row.get("Vencimiento", "")
        oi_chg = int(row.get("OI_Chg", 0) or 0)
        key = (str(venc), tipo, float(strike))
        if key not in bc_map or abs(oi_chg) > abs(bc_map[key]):
            bc_map[key] = oi_chg

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
    """Enriquece datos de opciones con métricas derivadas calculadas."""
    if not isinstance(datos, (list, pd.DataFrame)):
        return datos
    
    # Si es DataFrame, convertir a lista de dicts
    if isinstance(datos, pd.DataFrame):
        datos_lista = datos.to_dict('records')
    else:
        datos_lista = datos.copy()
    
    for item in datos_lista:
        try:
            # Básicos
            ask = float(item.get('Ask', 0) or 0)
            bid = float(item.get('Bid', 0) or 0) 
            strike = float(item.get('Strike', 0) or 0)
            volumen = int(item.get('Volumen', 0) or 0)
            oi = int(item.get('OI', 0) or 0)
            iv = float(item.get('IV', 0) or 0)
            
            # Bid/Ask Spread
            if ask > 0 and bid > 0:
                spread = ask - bid
                spread_pct = (spread / ask) * 100 if ask > 0 else 0
                item['Spread'] = spread
                item['Spread_Pct'] = spread_pct
                item['Mid_Price'] = (ask + bid) / 2
            else:
                last_price = float(item.get('Ultimo', 0) or 0)
                item['Spread'] = np.nan
                item['Spread_Pct'] = np.nan
                item['Mid_Price'] = last_price if last_price > 0 else np.nan
            
            # Volume/OI Ratio
            item['Vol_OI_Ratio'] = volumen / oi if oi > 0 else 0
            
            # Liquidity Score (0-100)
            vol_score = min(volumen / 100, 1) * 40
            oi_score = min(oi / 500, 1) * 30
            spread_pct_val = item.get('Spread_Pct')
            if pd.notna(spread_pct_val) and spread_pct_val > 0:
                spread_score = max(0, 1 - spread_pct_val/10) * 30
            else:
                spread_score = 0
            item['Liquidity_Score'] = vol_score + oi_score + spread_score
            
            # Moneyness
            if precio_subyacente and strike > 0:
                if item.get('Tipo_Opcion', '') == 'CALL' or item.get('Tipo', '') == 'CALL':
                    moneyness = strike / precio_subyacente
                    if moneyness < 0.95:
                        item['Moneyness'] = 'ITM'
                    elif moneyness > 1.05:
                        item['Moneyness'] = 'OTM'
                    else:
                        item['Moneyness'] = 'ATM'
                else:
                    moneyness = precio_subyacente / strike
                    if moneyness < 0.95:
                        item['Moneyness'] = 'ITM' 
                    elif moneyness > 1.05:
                        item['Moneyness'] = 'OTM'
                    else:
                        item['Moneyness'] = 'ATM'
                item['Distance_Pct'] = abs(strike - precio_subyacente) / precio_subyacente * 100
            else:
                item['Moneyness'] = 'N/A'
                item['Distance_Pct'] = 0
            
            # Premium/Underlying Ratio
            mid_price = item.get('Mid_Price')
            if precio_subyacente and mid_price is not None and not np.isnan(mid_price) and mid_price > 0:
                item['Premium_Ratio'] = (mid_price / precio_subyacente) * 100
            else:
                item['Premium_Ratio'] = np.nan
            
            # Time Value
            if precio_subyacente and strike > 0 and mid_price is not None and not np.isnan(mid_price) and mid_price > 0:
                tipo = item.get('Tipo_Opcion', item.get('Tipo', ''))
                if tipo == 'CALL':
                    intrinsic = max(precio_subyacente - strike, 0)
                else:
                    intrinsic = max(strike - precio_subyacente, 0)
                item['Time_Value'] = max(mid_price - intrinsic, 0)
                item['Time_Value_Pct'] = (item['Time_Value'] / mid_price * 100) if mid_price > 0 else 0
            else:
                item['Time_Value'] = np.nan
                item['Time_Value_Pct'] = np.nan
                
        except (ValueError, TypeError, KeyError) as e:
            continue
    
    return datos_lista if not isinstance(datos, pd.DataFrame) else pd.DataFrame(datos_lista)
