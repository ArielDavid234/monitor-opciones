"""
Cálculo de rango esperado de movimiento (1σ) usando
Black-Scholes para delta y datos de Yahoo Finance.
"""
import math
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime
from scipy.stats import norm

from config.constants import RISK_FREE_RATE, DEFAULT_TARGET_DELTA, DAYS_PER_YEAR
from core.scanner import crear_sesion_nueva

logger = logging.getLogger(__name__)


def calcular_delta_bs(S, K, T, r_rate, sigma, tipo="call"):
    """
    Calcula el delta de una opción usando el modelo Black-Scholes.

    Args:
        S: Precio del subyacente
        K: Strike price
        T: Tiempo hasta expiración (en años)
        r_rate: Tasa libre de riesgo (decimal, ej: 0.05)
        sigma: Volatilidad implícita (decimal, ej: 0.25)
        tipo: 'call' o 'put'

    Returns:
        float: Delta de la opción
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (math.log(S / K) + (r_rate + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

    if tipo == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1


def calcular_rango_esperado(symbol, expiration_date, target_delta=DEFAULT_TARGET_DELTA):
    """
    Calcula el rango esperado de movimiento (1 desviación estándar) usando
    yfinance + Black-Scholes para calcular delta de cada opción.

    100% GRATUITO — usa datos de Yahoo Finance + cálculo matemático.

    Busca la CALL con delta más cercano a +target_delta y la PUT con delta
    más cercano a -target_delta. Esos strikes definen los extremos del
    rango esperado del mercado hasta la expiración.

    Args:
        symbol: Símbolo del ticker (ej: 'SPY', 'META')
        expiration_date: Fecha de expiración formato YYYY-MM-DD
        target_delta: Delta objetivo (default 0.16 ≈ 1σ)

    Returns:
        (dict, None) con resultado exitoso, o (None, str_error)
    """
    try:
        session, perfil = crear_sesion_nueva()
        ticker = yf.Ticker(symbol, session=session)

        # Obtener precio actual
        try:
            hist = ticker.history(period="2d")
            if hist.empty:
                return None, f"No se pudo obtener el precio de {symbol}."
            underlying_price = float(hist["Close"].iloc[-1])
        except Exception as e:
            return None, f"Error obteniendo precio de {symbol}: {str(e)}"

        if underlying_price <= 0:
            return None, "Precio del subyacente inválido."

        # Verificar que la fecha de expiración existe
        try:
            options_dates = ticker.options
        except Exception as e:
            return None, f"Error obteniendo fechas de expiración: {str(e)}"

        if not options_dates:
            return None, f"No se encontraron fechas de expiración para {symbol}."

        if expiration_date not in options_dates:
            fechas_disp = ", ".join(options_dates[:10])
            return None, (
                f"La fecha {expiration_date} no está disponible. "
                f"Fechas disponibles: {fechas_disp}{'...' if len(options_dates) > 10 else ''}"
            )

        # Obtener cadena de opciones para esa fecha
        try:
            chain = ticker.option_chain(expiration_date)
        except Exception as e:
            return None, f"Error obteniendo cadena de opciones: {str(e)}"

        # Calcular tiempo hasta expiración (en años)
        exp_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
        dias_restantes = (exp_dt - datetime.now()).days
        T = max(dias_restantes, 1) / DAYS_PER_YEAR

        r_rate = RISK_FREE_RATE

        # Procesar CALLs
        calls = []
        for _, row in chain.calls.iterrows():
            strike = row["strike"]
            iv = row.get("impliedVolatility", 0)
            iv = iv if pd.notna(iv) and iv > 0 else 0
            last = row.get("lastPrice", 0)
            last = last if pd.notna(last) else 0

            if iv <= 0 or strike <= 0:
                continue

            delta = calcular_delta_bs(underlying_price, strike, T, r_rate, iv, "call")
            calls.append({
                "strike": strike,
                "delta": round(delta, 4),
                "iv": round(iv * 100, 2),
                "last_price": round(last, 2),
            })

        # Procesar PUTs
        puts = []
        for _, row in chain.puts.iterrows():
            strike = row["strike"]
            iv = row.get("impliedVolatility", 0)
            iv = iv if pd.notna(iv) and iv > 0 else 0
            last = row.get("lastPrice", 0)
            last = last if pd.notna(last) else 0

            if iv <= 0 or strike <= 0:
                continue

            delta = calcular_delta_bs(underlying_price, strike, T, r_rate, iv, "put")
            puts.append({
                "strike": strike,
                "delta": round(delta, 4),
                "iv": round(iv * 100, 2),
                "last_price": round(last, 2),
            })

        if not calls:
            return None, f"No se encontraron CALLs con IV válida para {expiration_date}."
        if not puts:
            return None, f"No se encontraron PUTs con IV válida para {expiration_date}."

        # Encontrar call con delta más cercano a +target_delta
        closest_call = min(calls, key=lambda x: abs(x["delta"] - target_delta))
        upside_points = max(closest_call["strike"] - underlying_price, 0)
        upside_pct = (upside_points / underlying_price) * 100

        # Encontrar put con delta más cercano a -target_delta
        closest_put = min(puts, key=lambda x: abs(x["delta"] + target_delta))
        downside_points = max(underlying_price - closest_put["strike"], 0)
        downside_pct = (downside_points / underlying_price) * 100

        resultado = {
            "symbol": symbol,
            "underlying_price": round(underlying_price, 2),
            "expiration": expiration_date,
            "dias_restantes": dias_restantes,
            "target_delta": target_delta,
            "upside_points": round(upside_points, 2),
            "upside_percent": round(upside_pct, 2),
            "downside_points": round(downside_points, 2),
            "downside_percent": round(downside_pct, 2),
            "expected_range_low": round(underlying_price - downside_points, 2),
            "expected_range_high": round(underlying_price + upside_points, 2),
            "total_range_points": round(upside_points + downside_points, 2),
            "total_range_pct": round(upside_pct + downside_pct, 2),
            "call_strike": closest_call["strike"],
            "call_delta": closest_call["delta"],
            "call_iv": closest_call["iv"],
            "put_strike": closest_put["strike"],
            "put_delta": closest_put["delta"],
            "put_iv": closest_put["iv"],
            "n_calls": len(calls),
            "n_puts": len(puts),
            "perfil_tls": perfil,
        }
        return resultado, None

    except Exception as e:
        return None, f"Error inesperado: {str(e)}"
