"""Polygon.io data engine.

Centraliza acceso de mercado y opciones usando polygon-api-client.
"""

from __future__ import annotations

import logging
import os
import time
import urllib.request
import json
from datetime import date, datetime, timedelta

import pandas as pd
from polygon import RESTClient

logger = logging.getLogger(__name__)


def _client() -> RESTClient:
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY no configurada")
    return RESTClient(api_key)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def obtener_precio_actual(ticker_sym: str):
    """Obtiene precio de cierre previo desde Polygon."""
    try:
        client = _client()
        prev = client.get_previous_close_agg(ticker_sym, adjusted=True)
        results = getattr(prev, "results", None) or []
        if not results:
            return None, "Sin datos de precio"

        row = results[0]
        close = _safe_float(getattr(row, "c", None), default=0.0)
        if close <= 0:
            return None, "Precio inválido"
        return close, None
    except Exception as exc:
        logger.warning("Polygon precio actual fallo (%s): %s", ticker_sym, exc)
        return None, str(exc)


def fetch_options_dates(ticker_sym: str):
    """Lista fechas de exp usando URL raw para evitar la auto-paginación de la SDK."""
    import requests

    try:
        api_key = os.getenv("POLYGON_API_KEY")
        if not api_key:
            logger.warning("POLYGON_API_KEY no configurada")
            return tuple()

        url = (
            "https://api.polygon.io/v3/reference/options/contracts"
            f"?underlying_ticker={ticker_sym}&expired=false&limit=1000&apiKey={api_key}"
        )

        # Solo un request para no quemar cuota free-tier por auto-paginacion
        response = requests.get(url, timeout=10)
        if response.status_code == 429:
            logger.warning("Polygon Rate Limit en dates, esperando 13 segs...")
            time.sleep(13)
            response = requests.get(url, timeout=10)

        data = response.json()
        results = data.get("results", [])

        expirations = set()
        for contract in results:
            exp = contract.get("expiration_date", None)
            if exp:
                expirations.add(str(exp))

        fechas_ordenadas = sorted(expirations)
        return tuple(fechas_ordenadas[:10])
    except Exception as exc:
        logger.warning("Polygon expiraciones fallo (%s): %s", ticker_sym, exc)
        return tuple()


def fetch_single_chain(ticker_sym: str, exp_date: str):
    """Obtiene la cadena de opciones y normaliza columnas para la UI.

    Retorna:
        (exp_date, {"calls": DataFrame, "puts": DataFrame}, error)
    """
    cols = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]
    calls_rows = []
    puts_rows = []

    try:
        client = _client()
        snapshots = client.list_snapshot_options_chain(
            ticker_sym,
            params={"expiration_date": exp_date, "limit": 250},
        )

        for snap in snapshots:
            details = getattr(snap, "details", None)
            side = (getattr(details, "contract_type", "") or "").lower()
            if side not in {"call", "put"}:
                continue

            quote = getattr(snap, "last_quote", None)
            trade = getattr(snap, "last_trade", None)
            day = getattr(snap, "day", None)

            row = {
                "strike": _safe_float(getattr(details, "strike_price", None), 0.0),
                "lastPrice": _safe_float(getattr(trade, "price", None), 0.0),
                "bid": _safe_float(getattr(quote, "bid", None), 0.0),
                "ask": _safe_float(getattr(quote, "ask", None), 0.0),
                "volume": _safe_int(getattr(day, "volume", None), 0),
                "openInterest": _safe_int(getattr(snap, "open_interest", None), 0),
                "impliedVolatility": _safe_float(getattr(snap, "implied_volatility", None), 0.0),
            }

            if side == "call":
                calls_rows.append(row)
            else:
                puts_rows.append(row)

        calls_df = pd.DataFrame(calls_rows, columns=cols)
        puts_df = pd.DataFrame(puts_rows, columns=cols)
        return exp_date, {"calls": calls_df, "puts": puts_df}, None
    except Exception as exc:
        err_msg = str(exc)
        if "429" in err_msg or "rate limit" in err_msg.lower():
            logger.warning("Polygon chain 429 (%s %s), esperando 13s y reintentando...", ticker_sym, exp_date)
            time.sleep(13)
            try:
                client = _client()
                snapshots = client.list_snapshot_options_chain(
                    ticker_sym,
                    params={"expiration_date": exp_date, "limit": 250},
                )

                for snap in snapshots:
                    details = getattr(snap, "details", None)
                    side = (getattr(details, "contract_type", "") or "").lower()
                    if side not in {"call", "put"}:
                        continue

                    quote = getattr(snap, "last_quote", None)
                    trade = getattr(snap, "last_trade", None)
                    day = getattr(snap, "day", None)

                    row = {
                        "strike": _safe_float(getattr(details, "strike_price", None), 0.0),
                        "lastPrice": _safe_float(getattr(trade, "price", None), 0.0),
                        "bid": _safe_float(getattr(quote, "bid", None), 0.0),
                        "ask": _safe_float(getattr(quote, "ask", None), 0.0),
                        "volume": _safe_int(getattr(day, "volume", None), 0),
                        "openInterest": _safe_int(getattr(snap, "open_interest", None), 0),
                        "impliedVolatility": _safe_float(getattr(snap, "implied_volatility", None), 0.0),
                    }

                    if side == "call":
                        calls_rows.append(row)
                    else:
                        puts_rows.append(row)

                calls_df = pd.DataFrame(calls_rows, columns=cols)
                puts_df = pd.DataFrame(puts_rows, columns=cols)
                return exp_date, {"calls": calls_df, "puts": puts_df}, None
            except Exception as retry_exc:
                logger.warning("Retry SDK chain fallo (%s %s): %s", ticker_sym, exp_date, retry_exc)

        # Fallback manual (raw request) tolerante
        try:
            api_key = os.getenv("POLYGON_API_KEY")
            if api_key:
                url = (
                    "https://api.polygon.io/v3/snapshot/options/"
                    f"{ticker_sym}?expiration_date={exp_date}&limit=250&apiKey={api_key}"
                )
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))

                results = payload.get("results", []) or []
                for snap in results:
                    details = snap.get("details", {}) or {}
                    side = (details.get("contract_type") or "").lower()
                    if side not in {"call", "put"}:
                        continue

                    quote = snap.get("last_quote", {}) or {}
                    trade = snap.get("last_trade", {}) or {}
                    day = snap.get("day", {}) or {}

                    row = {
                        "strike": _safe_float(details.get("strike_price"), 0.0),
                        "lastPrice": _safe_float(trade.get("price"), 0.0),
                        "bid": _safe_float(quote.get("bid"), 0.0),
                        "ask": _safe_float(quote.get("ask"), 0.0),
                        "volume": _safe_int(day.get("volume"), 0),
                        "openInterest": _safe_int(snap.get("open_interest"), 0),
                        "impliedVolatility": _safe_float(snap.get("implied_volatility"), 0.0),
                    }

                    if side == "call":
                        calls_rows.append(row)
                    else:
                        puts_rows.append(row)

                calls_df = pd.DataFrame(calls_rows, columns=cols)
                puts_df = pd.DataFrame(puts_rows, columns=cols)
                return exp_date, {"calls": calls_df, "puts": puts_df}, None
        except Exception as raw_exc:
            logger.warning("Fallback raw chain fallo (%s %s): %s", ticker_sym, exp_date, raw_exc)

        logger.warning("Polygon chain fallo (%s %s): %s", ticker_sym, exp_date, exc)
        return exp_date, {"calls": pd.DataFrame(columns=cols), "puts": pd.DataFrame(columns=cols)}, str(exc)


def get_price_history(ticker_sym: str, period: str = "1y") -> pd.DataFrame:
    """Devuelve OHLCV diario en formato estilo yfinance (Open/High/Low/Close/Volume)."""
    days_map = {
        "5d": 10,
        "1mo": 40,
        "3mo": 120,
        "6mo": 220,
        "1y": 370,
        "2y": 740,
    }
    lookback_days = days_map.get(period, 370)

    try:
        client = _client()
        to_dt = date.today()
        from_dt = to_dt - timedelta(days=lookback_days)
        aggs = client.get_aggs(
            ticker=ticker_sym,
            multiplier=1,
            timespan="day",
            from_=from_dt,
            to=to_dt,
            adjusted=True,
            limit=50000,
        )

        rows = []
        for a in aggs:
            ts = getattr(a, "timestamp", None)
            dt = datetime.utcfromtimestamp(ts / 1000.0) if ts else None
            rows.append(
                {
                    "Date": dt,
                    "Open": _safe_float(getattr(a, "open", None)),
                    "High": _safe_float(getattr(a, "high", None)),
                    "Low": _safe_float(getattr(a, "low", None)),
                    "Close": _safe_float(getattr(a, "close", None)),
                    "Volume": _safe_int(getattr(a, "volume", None)),
                }
            )

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["Date"]).set_index("Date").sort_index()
        return df
    except Exception as exc:
        logger.warning("Polygon history fallo (%s, %s): %s", ticker_sym, period, exc)
        return pd.DataFrame()


def get_ticker_details(ticker_sym: str):
    """Retorna detalle del ticker desde Polygon (objeto o None)."""
    try:
        client = _client()
        return client.get_ticker_details(ticker_sym)
    except Exception as exc:
        logger.debug("Polygon ticker details fallo (%s): %s", ticker_sym, exc)
        return None


def get_contract_history(contract_symbol: str, period: str = "1mo") -> pd.DataFrame:
    """Histórico OHLCV para contrato (si Polygon reconoce el símbolo)."""
    return get_price_history(contract_symbol, period=period)
