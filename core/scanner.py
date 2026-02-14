"""
Scanner de opciones: sesiones anti-ban, escaneo de cadenas,
construcción de símbolos y persistencia CSV.
"""
import os
import csv
import glob
import time
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime
from random import uniform, choice
from curl_cffi.requests import Session as CurlSession

from config.constants import SCAN_SLEEP_RANGE

logger = logging.getLogger(__name__)


def _safe_num(value, default=0):
    """Retorna el valor si no es NaN/None, o el default."""
    return value if pd.notna(value) else default


def _clasificar_lado(last_price, bid, ask):
    """Clasifica si la transacción se ejecutó al Bid, Ask o Mid.
    
    - Ask  → compra agresiva (el comprador paga el precio del vendedor)
    - Bid  → venta agresiva  (el vendedor acepta el precio del comprador)
    - Mid  → ejecutado entre bid y ask
    - N/A  → sin datos suficientes
    """
    if ask <= 0 and bid <= 0:
        return "N/A"
    if last_price <= 0:
        return "N/A"
    if ask > 0 and last_price >= ask:
        return "Ask"
    if bid > 0 and last_price <= bid:
        return "Bid"
    if bid > 0 and ask > 0 and bid < last_price < ask:
        return "Mid"
    return "N/A"


# ============================================================================
#                    SISTEMA ANTI-BANEO
# ============================================================================
BROWSER_PROFILES = [
    "chrome110", "chrome116", "chrome119", "chrome120",
    "chrome123", "chrome124",
    "edge99", "edge101",
    "safari15_3", "safari15_5", "safari17_0",
]


def crear_sesion_nueva():
    """Crea sesión curl_cffi con perfil TLS aleatorio."""
    perfil = choice(BROWSER_PROFILES)
    session = CurlSession(impersonate=perfil)
    return session, perfil


def construir_simbolo_contrato(ticker_sym, exp_date, opt_type, strike):
    """Construye el símbolo del contrato de opción en formato Yahoo Finance.
    Ej: SPY260220C00600000 = SPY, 2026-02-20, CALL, strike 600"""
    parts = exp_date.split("-")
    fecha_fmt = parts[0][2:] + parts[1] + parts[2]  # YYMMDD
    tipo_letra = "C" if opt_type == "CALL" else "P"
    strike_fmt = f"{int(strike * 1000):08d}"
    return f"{ticker_sym}{fecha_fmt}{tipo_letra}{strike_fmt}"


def obtener_historial_contrato(contract_symbol):
    """Obtiene el historial de precios de un contrato de opción."""
    try:
        session, _ = crear_sesion_nueva()
        contract = yf.Ticker(contract_symbol, session=session)
        hist = contract.history(period="1mo")
        if hist.empty:
            hist = contract.history(period="5d")
        return hist, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def ejecutar_escaneo(
    ticker_sym, u_vol, u_oi, u_prima, u_filtro, carpeta_csv, guardar
):
    """Ejecuta un ciclo completo de escaneo y retorna alertas + datos."""
    alertas = []
    datos = []

    session, perfil = crear_sesion_nueva()
    ticker = yf.Ticker(ticker_sym, session=session)

    try:
        options_dates = ticker.options
    except Exception as e:
        return [], [], str(e), perfil, []

    if not options_dates:
        return [], [], "No se encontraron fechas de vencimiento", perfil, []

    dates_to_scan = list(options_dates)

    for idx, exp_date in enumerate(dates_to_scan):
        if idx > 0:
            time.sleep(uniform(*SCAN_SLEEP_RANGE))

        try:
            chain = ticker.option_chain(exp_date)

            for opt_type, df in [("CALL", chain.calls), ("PUT", chain.puts)]:
                for _, row in df.iterrows():
                    vol = int(_safe_num(row["volume"])) if _safe_num(row["volume"]) > 0 else 0
                    oi = int(_safe_num(row["openInterest"]))

                    iv = _safe_num(row.get("impliedVolatility", 0))
                    ask_val = _safe_num(row.get("ask", 0))
                    bid_val = _safe_num(row.get("bid", 0))
                    last_val = _safe_num(row.get("lastPrice", 0))
                    price_volume = (
                        ask_val if ask_val > 0 else (last_val if last_val > 0 else 0)
                    )

                    volume_premium = vol * price_volume * 100

                    lado = _clasificar_lado(last_val, bid_val, ask_val)

                    datos.append(
                        {
                            "Vencimiento": exp_date,
                            "Tipo": opt_type,
                            "Strike": row["strike"],
                            "Volumen": vol,
                            "OI": oi,
                            "Ask": round(ask_val, 2),
                            "Bid": round(bid_val, 2),
                            "Ultimo": round(last_val, 2),
                            "IV": round(iv * 100, 2) if iv else 0,
                            "Prima_Volumen": round(volume_premium, 0),
                            "Lado": lado,
                        }
                    )

                    if vol < u_vol or oi < u_oi:
                        continue

                    tipo_alerta = None
                    if volume_premium >= u_prima:
                        tipo_alerta = "PRINCIPAL"
                    else:
                        tipo_alerta = "PRIMA_ALTA"

                    if tipo_alerta:
                        contract_sym = construir_simbolo_contrato(
                            ticker_sym, exp_date, opt_type, row["strike"]
                        )
                        alerta = {
                            "Fecha_Hora": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "Ticker": ticker_sym,
                            "Tipo_Alerta": tipo_alerta,
                            "Tipo_Opcion": opt_type,
                            "Vencimiento": exp_date,
                            "Strike": row["strike"],
                            "Volumen": vol,
                            "OI": oi,
                            "Prima_Volumen": round(volume_premium, 0),
                            "Ask": round(ask_val, 2),
                            "Bid": round(bid_val, 2),
                            "Ultimo": round(last_val, 2),
                            "Contrato": contract_sym,
                            "Lado": lado,
                        }
                        alertas.append(alerta)

                        if guardar:
                            guardar_alerta_csv(carpeta_csv, ticker_sym, alerta)

        except Exception:
            continue

    return alertas, datos, None, perfil, dates_to_scan


def guardar_alerta_csv(carpeta, ticker_sym, alerta):
    """Guarda una alerta individual en el archivo CSV diario."""
    try:
        os.makedirs(carpeta, exist_ok=True)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        csv_path = os.path.join(carpeta, f"alertas_{ticker_sym}_{fecha_hoy}.csv")
        escribir_header = not os.path.exists(csv_path)

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Fecha_Hora", "Ticker", "Tipo_Alerta", "Tipo_Opcion",
                    "Vencimiento", "Strike", "Volumen", "OI",
                    "Prima_Total", "Ask", "Bid", "Ultimo", "Lado",
                ],
            )
            if escribir_header:
                writer.writeheader()
            # Renombrar Prima_Volumen a Prima_Total para el CSV (claridad para el usuario)
            alerta_csv = alerta.copy()
            if "Prima_Volumen" in alerta_csv:
                alerta_csv["Prima_Total"] = alerta_csv.pop("Prima_Volumen")
            writer.writerow(alerta_csv)
    except Exception as e:
        logger.error("Error guardando alerta CSV: %s", e)


def cargar_historial_csv(carpeta):
    """Carga todos los archivos CSV de alertas históricas."""
    if not os.path.exists(carpeta):
        return pd.DataFrame()

    archivos = glob.glob(os.path.join(carpeta, "alertas_*.csv"))
    if not archivos:
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            df = pd.read_csv(archivo, encoding="utf-8")
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            logger.warning("Error leyendo CSV %s: %s", archivo, e)
            continue

    if not dfs:
        return pd.DataFrame()
    
    result_df = pd.concat(dfs, ignore_index=True)
    
    # Compatibilidad: renombrar Prima_Volumen a Prima_Total si existe (CSVs antiguos)
    if "Prima_Volumen" in result_df.columns:
        result_df = result_df.rename(columns={"Prima_Volumen": "Prima_Total"})
    
    return result_df
