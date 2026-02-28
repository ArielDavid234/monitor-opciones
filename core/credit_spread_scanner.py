# -*- coding: utf-8 -*-
"""
Credit Spread Scanner — Escanea cadenas de opciones para encontrar
oportunidades de venta de prima (Bull Put Spreads y Bear Call Spreads).

Reutiliza las sesiones anti-ban y el caché TTL del scanner principal.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.constants import RISK_FREE_RATE, DAYS_PER_YEAR
from core.scanner import (
    _cached_options_dates,
    _cached_option_chain,
    obtener_precio_actual,
    _safe_num,
)

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
#  Helpers internos
# ────────────────────────────────────────────────────────────────────────────

def _dte_from_expiry(exp_str: str) -> int:
    """Calcula días hasta el vencimiento desde una fecha YYYY-MM-DD."""
    try:
        exp = datetime.strptime(exp_str, "%Y-%m-%d")
        return max((exp - datetime.now()).days, 0)
    except Exception:
        return 0


def _pop_from_delta(delta: float) -> float:
    """Probabilidad de ganancia estimada = 1 - |delta| del strike vendido."""
    return round(1.0 - abs(delta), 4)


def _bid_ask_spread(bid: float, ask: float) -> float:
    """Spread bid-ask en dólares."""
    if ask > 0 and bid >= 0:
        return round(ask - bid, 2)
    return 0.0


# ────────────────────────────────────────────────────────────────────────────
#  Construcción de spreads para una fecha de expiración
# ────────────────────────────────────────────────────────────────────────────

def _build_spreads_for_expiry(
    ticker: str,
    spot: float,
    exp_date: str,
    min_pop: float,
    min_credit: float,
) -> list[dict]:
    """Genera Bull Put Spreads y Bear Call Spreads para una expiración.

    Bull Put Spread (alcista):
        Vender Put alto + Comprar Put bajo → crédito neto.

    Bear Call Spread (bajista):
        Vender Call bajo + Comprar Call alto → crédito neto.
    """
    dte = _dte_from_expiry(exp_date)
    if dte <= 0:
        return []

    try:
        chain = _cached_option_chain(ticker, exp_date)
    except Exception as exc:
        logger.warning("Error obteniendo cadena %s %s: %s", ticker, exp_date, exc)
        return []

    puts: pd.DataFrame = chain.get("puts", pd.DataFrame())
    calls: pd.DataFrame = chain.get("calls", pd.DataFrame())

    results: list[dict] = []

    # ── Bull Put Spreads ─────────────────────────────────────────────────
    if not puts.empty and len(puts) >= 2:
        # Filtrar puts OTM (strike < spot) con bid > 0
        otm_puts = puts[
            (puts["strike"] < spot) &
            (puts["bid"].fillna(0) > 0)
        ].sort_values("strike", ascending=False).reset_index(drop=True)

        for i in range(len(otm_puts)):
            sold = otm_puts.iloc[i]
            sold_strike = float(sold["strike"])
            sold_bid = float(_safe_num(sold.get("bid", 0)))
            sold_ask = float(_safe_num(sold.get("ask", 0)))
            sold_delta = float(_safe_num(sold.get("delta", 0), 0))

            # Si no hay delta de la cadena, estimar con moneyness
            if sold_delta == 0:
                # Estimación simple basada en distancia al spot
                moneyness = (spot - sold_strike) / spot
                sold_delta = max(-0.50, min(-0.01, -0.50 + moneyness * 3))

            pop = _pop_from_delta(sold_delta)
            if pop < min_pop:
                continue

            # Buscar strikes comprados más bajos (protección)
            for j in range(i + 1, min(i + 6, len(otm_puts))):
                bought = otm_puts.iloc[j]
                bought_strike = float(bought["strike"])
                bought_ask = float(_safe_num(bought.get("ask", 0)))

                if bought_ask <= 0:
                    continue

                credit = round(sold_bid - bought_ask, 2)
                if credit < min_credit:
                    continue

                width = round(sold_strike - bought_strike, 2)
                if width <= 0:
                    continue

                max_risk = round(width - credit, 2)
                if max_risk <= 0:
                    continue

                retorno_pct = round((credit / max_risk) * 100, 2)

                results.append({
                    "Ticker": ticker,
                    "Tipo": "Bull Put",
                    "Spot": round(spot, 2),
                    "Strike Vendido": sold_strike,
                    "Strike Comprado": bought_strike,
                    "DTE": dte,
                    "Expiración": exp_date,
                    "Delta Vendido": round(sold_delta, 4),
                    "POP %": round(pop * 100, 1),
                    "Crédito": credit,
                    "Riesgo Máx": max_risk,
                    "Retorno %": retorno_pct,
                    "Volumen": int(_safe_num(sold.get("volume", 0))),
                    "OI": int(_safe_num(sold.get("openInterest", 0))),
                    "Bid-Ask": _bid_ask_spread(sold_bid, sold_ask),
                })

    # ── Bear Call Spreads ────────────────────────────────────────────────
    if not calls.empty and len(calls) >= 2:
        # Filtrar calls OTM (strike > spot) con bid > 0
        otm_calls = calls[
            (calls["strike"] > spot) &
            (calls["bid"].fillna(0) > 0)
        ].sort_values("strike", ascending=True).reset_index(drop=True)

        for i in range(len(otm_calls)):
            sold = otm_calls.iloc[i]
            sold_strike = float(sold["strike"])
            sold_bid = float(_safe_num(sold.get("bid", 0)))
            sold_ask = float(_safe_num(sold.get("ask", 0)))
            sold_delta = float(_safe_num(sold.get("delta", 0), 0))

            # Si no hay delta, estimar
            if sold_delta == 0:
                moneyness = (sold_strike - spot) / spot
                sold_delta = max(0.01, min(0.50, 0.50 - moneyness * 3))

            pop = _pop_from_delta(sold_delta)
            if pop < min_pop:
                continue

            # Buscar strikes comprados más altos (protección)
            for j in range(i + 1, min(i + 6, len(otm_calls))):
                bought = otm_calls.iloc[j]
                bought_strike = float(bought["strike"])
                bought_ask = float(_safe_num(bought.get("ask", 0)))

                if bought_ask <= 0:
                    continue

                credit = round(sold_bid - bought_ask, 2)
                if credit < min_credit:
                    continue

                width = round(bought_strike - sold_strike, 2)
                if width <= 0:
                    continue

                max_risk = round(width - credit, 2)
                if max_risk <= 0:
                    continue

                retorno_pct = round((credit / max_risk) * 100, 2)

                results.append({
                    "Ticker": ticker,
                    "Tipo": "Bear Call",
                    "Spot": round(spot, 2),
                    "Strike Vendido": sold_strike,
                    "Strike Comprado": bought_strike,
                    "DTE": dte,
                    "Expiración": exp_date,
                    "Delta Vendido": round(sold_delta, 4),
                    "POP %": round(pop * 100, 1),
                    "Crédito": credit,
                    "Riesgo Máx": max_risk,
                    "Retorno %": retorno_pct,
                    "Volumen": int(_safe_num(sold.get("volume", 0))),
                    "OI": int(_safe_num(sold.get("openInterest", 0))),
                    "Bid-Ask": _bid_ask_spread(sold_bid, sold_ask),
                })

    return results


# ────────────────────────────────────────────────────────────────────────────
#  Escaneo de un ticker completo (todas las expiraciones válidas)
# ────────────────────────────────────────────────────────────────────────────

def _scan_single_ticker(
    ticker: str,
    min_pop: float,
    max_dte: int,
    min_credit: float,
) -> list[dict]:
    """Escanea todas las expiraciones válidas de un ticker."""
    spot, err = obtener_precio_actual(ticker)
    if not spot:
        logger.warning("Sin precio para %s: %s", ticker, err)
        return []

    try:
        exp_dates = _cached_options_dates(ticker)
    except Exception as exc:
        logger.warning("Sin fechas de expiración para %s: %s", ticker, exc)
        return []

    all_spreads: list[dict] = []

    for exp_date in exp_dates:
        dte = _dte_from_expiry(exp_date)
        if dte <= 0 or dte > max_dte:
            continue
        spreads = _build_spreads_for_expiry(ticker, spot, exp_date, min_pop, min_credit)
        all_spreads.extend(spreads)

    return all_spreads


# ────────────────────────────────────────────────────────────────────────────
#  Función pública principal
# ────────────────────────────────────────────────────────────────────────────

def scan_credit_spreads(
    tickers: list[str],
    min_pop: float = 0.70,
    max_dte: int = 45,
    min_credit: float = 0.30,
    progress_callback=None,
) -> pd.DataFrame:
    """Escanea múltiples tickers buscando Credit Spreads óptimos.

    Parameters
    ----------
    tickers : list[str]
        Lista de símbolos a escanear.
    min_pop : float
        Probabilidad mínima de ganancia (0-1). Default 0.70.
    max_dte : int
        Máximo de días hasta vencimiento. Default 45.
    min_credit : float
        Crédito mínimo por spread en USD. Default 0.30.
    progress_callback : callable, optional
        Función(ticker, idx, total) para reportar progreso.

    Returns
    -------
    pd.DataFrame
        DataFrame con todas las oportunidades encontradas, ordenado por
        Retorno % descendente, luego por POP % descendente.
    """
    all_results: list[dict] = []

    for idx, ticker in enumerate(tickers):
        ticker = ticker.strip().upper()
        if not ticker:
            continue
        if progress_callback:
            progress_callback(ticker, idx, len(tickers))

        try:
            spreads = _scan_single_ticker(ticker, min_pop, max_dte, min_credit)
            all_results.extend(spreads)
        except Exception as exc:
            logger.error("Error escaneando %s: %s", ticker, exc)

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    # Ordenar por retorno y POP
    df = df.sort_values(
        ["Retorno %", "POP %"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return df
