"""Databento data engine.

Proveedor de mercado/opciones para mantener compatibilidad con el contrato
esperado por el escaner.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    import databento as db
except Exception:  # pragma: no cover - import guard
    db = None

from infrastructure.data.env_resolver import get_env_value
from infrastructure.data.provider_runtime import (
    get_budget_manager,
    get_provider_metrics,
    get_request_channel,
)

logger = logging.getLogger(__name__)


CHAIN_COLUMNS = [
    "strike",
    "lastPrice",
    "bid",
    "ask",
    "volume",
    "openInterest",
    "impliedVolatility",
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_chain_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=CHAIN_COLUMNS)

    out = df.copy()
    for col in CHAIN_COLUMNS:
        if col not in out.columns:
            out[col] = 0

    out["strike"] = pd.to_numeric(out["strike"], errors="coerce").fillna(0.0).astype(float)
    out["lastPrice"] = pd.to_numeric(out["lastPrice"], errors="coerce").fillna(0.0).astype(float)
    out["bid"] = pd.to_numeric(out["bid"], errors="coerce").fillna(0.0).astype(float)
    out["ask"] = pd.to_numeric(out["ask"], errors="coerce").fillna(0.0).astype(float)
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype(int)
    out["openInterest"] = pd.to_numeric(out["openInterest"], errors="coerce").fillna(0).astype(int)
    out["impliedVolatility"] = pd.to_numeric(out["impliedVolatility"], errors="coerce").fillna(0.0).astype(float)
    return out[CHAIN_COLUMNS]


def _client():
    if db is None:
        raise RuntimeError("Dependencia 'databento' no instalada")

    api_key = get_env_value("DATABENTO_API_KEY", "")
    if not api_key:
        raise RuntimeError("DATABENTO_API_KEY no configurada")
    return db.Historical(api_key)


def _options_dataset() -> str:
    return get_env_value("DATABENTO_OPTIONS_DATASET", "OPRA.PILLAR") or "OPRA.PILLAR"


def _equity_datasets() -> list[str]:
    raw = get_env_value("DATABENTO_EQUITY_DATASETS", "EQUS.MINI,DBEQ.BASIC,XNAS.BASIC")
    datasets = [x.strip() for x in raw.split(",") if x.strip()]
    return datasets or ["EQUS.MINI", "DBEQ.BASIC", "XNAS.BASIC"]


def _period_days(period: str) -> int:
    mapping = {
        "1d": 3,
        "5d": 10,
        "1mo": 40,
        "3mo": 110,
        "6mo": 220,
        "1y": 370,
        "2y": 740,
    }
    return mapping.get(period, 370)


def _to_df(store) -> pd.DataFrame:
    try:
        return store.to_df(price_type="float", pretty_ts=True, map_symbols=True)
    except TypeError:
        return store.to_df()


def _is_temporary_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    transient_tokens = (
        "429",
        "rate",
        "timeout",
        "timed out",
        "tempor",
        "503",
        "504",
        "connection",
        "unavailable",
    )
    return any(tok in msg for tok in transient_tokens)


def _with_retry(fn, op_name: str, retries: int = 2, base_sleep: float = 0.35):
    op_ticker = op_name.split(":")[-1] if ":" in op_name else "N/A"
    budget = get_budget_manager()
    metrics = get_provider_metrics()
    decision = budget.acquire(
        endpoint=op_name,
        ticker=op_ticker,
        critical=(get_request_channel() == "live_scanning"),
    )
    if not decision.allowed:
        metrics.record_request("denied")
        raise RuntimeError(
            f"Cuota temporal alta para datos de mercado. Reintenta en {decision.retry_in_seconds} segundos"
        )

    last_exc = None
    for attempt in range(retries + 1):
        try:
            result = fn()
            metrics.record_request("ok")
            return result
        except Exception as exc:  # pragma: no cover - network-dependent
            last_exc = exc
            if "429" in str(exc):
                metrics.record_request("429")
            else:
                metrics.record_request("error")
            if attempt >= retries or not _is_temporary_error(exc):
                break
            wait_s = base_sleep * (2**attempt)
            logger.warning("Databento %s transient error (attempt %d/%d): %s", op_name, attempt + 1, retries + 1, exc)
            time.sleep(wait_s)
    raise RuntimeError("Servicio de datos de mercado temporalmente no disponible")


def _parse_occ_symbol(raw_symbol: str) -> tuple[float, str | None]:
    """Parsea OCC (e.g. SPY   240814P00561000) -> (strike, side)."""
    if not raw_symbol:
        return 0.0, None

    text = str(raw_symbol)
    m = re.search(r"([CP])(\d{8})$", text)
    if not m:
        return 0.0, None

    side = "call" if m.group(1) == "C" else "put"
    strike = _safe_float(m.group(2), 0.0) / 1000.0
    return strike, side


def _normalize_expiration(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce", utc=True)
    return values.dt.strftime("%Y-%m-%d")


def _fetch_definition_df(ticker_sym: str, lookback_days: int = 7) -> pd.DataFrame:
    client = _client()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=max(lookback_days, 1))).strftime("%Y-%m-%d")

    data = _with_retry(
        lambda: client.timeseries.get_range(
            dataset=_options_dataset(),
            schema="definition",
            stype_in="parent",
            symbols=[f"{ticker_sym}.OPT"],
            start=start,
            end=now.isoformat(),
            limit=500_000,
        ),
        op_name=f"definition:{ticker_sym}",
    )
    df = _to_df(data)
    if df.empty:
        return df

    df = df.reset_index(drop=False)
    if "raw_symbol" not in df.columns and "symbol" in df.columns:
        df["raw_symbol"] = df["symbol"].astype(str)
    if "expiration" in df.columns:
        df["expiration_date"] = _normalize_expiration(df["expiration"])
    elif "expiration_date" in df.columns:
        df["expiration_date"] = _normalize_expiration(df["expiration_date"])
    else:
        df["expiration_date"] = ""

    return df


def _fetch_tcbbo_df(ticker_sym: str) -> pd.DataFrame:
    client = _client()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=2)).strftime("%Y-%m-%d")

    data = _with_retry(
        lambda: client.timeseries.get_range(
            dataset=_options_dataset(),
            schema="tcbbo",
            stype_in="parent",
            symbols=[f"{ticker_sym}.OPT"],
            start=start,
            end=now.isoformat(),
            limit=1_000_000,
        ),
        op_name=f"tcbbo:{ticker_sym}",
    )
    df = _to_df(data)
    if df.empty:
        return df
    return df.reset_index(drop=False)


def _fetch_statistics_df(ticker_sym: str) -> pd.DataFrame:
    client = _client()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    data = _with_retry(
        lambda: client.timeseries.get_range(
            dataset=_options_dataset(),
            schema="statistics",
            stype_in="parent",
            symbols=[f"{ticker_sym}.OPT"],
            start=start,
            end=now.isoformat(),
            limit=1_000_000,
        ),
        op_name=f"statistics:{ticker_sym}",
    )
    df = _to_df(data)
    if df.empty:
        return df
    return df.reset_index(drop=False)


def obtener_precio_actual(ticker_sym: str):
    """Obtiene precio spot (close reciente) desde datasets de equity Databento."""
    try:
        hist = get_price_history(ticker_sym, period="5d")
        if hist.empty:
            return None, "Sin datos de precio"
        close = _safe_float(hist["Close"].iloc[-1], 0.0)
        if close <= 0:
            return None, "Precio inválido"
        return close, None
    except Exception as exc:
        logger.warning("Databento precio actual fallo (%s): %s", ticker_sym, exc)
        return None, str(exc)


def fetch_options_dates(ticker_sym: str):
    """Retorna expiraciones disponibles (YYYY-MM-DD) para el underlying."""
    try:
        defs = _fetch_definition_df(ticker_sym, lookback_days=14)
        if defs.empty or "expiration_date" not in defs.columns:
            return tuple()

        today = datetime.now(timezone.utc).date()
        expirations = sorted(
            {
                str(x)
                for x in defs["expiration_date"].dropna().astype(str)
                if x and x != "NaT" and datetime.strptime(str(x), "%Y-%m-%d").date() >= today
            }
        )
        return tuple(expirations)
    except Exception as exc:
        logger.warning("Databento expiraciones fallo (%s): %s", ticker_sym, exc)
        return tuple()


def fetch_single_chain(ticker_sym: str, exp_date: str):
    """Retorna cadena normalizada para escaner.

    Debe retornar:
        (exp_date, {"calls": calls_df, "puts": puts_df}, error)
    """
    empty = {
        "calls": pd.DataFrame(columns=CHAIN_COLUMNS),
        "puts": pd.DataFrame(columns=CHAIN_COLUMNS),
    }

    try:
        definitions = _fetch_definition_df(ticker_sym, lookback_days=14)
        if definitions.empty:
            return exp_date, empty, "Sin definiciones de opciones"

        df_exp = definitions[definitions.get("expiration_date", "") == exp_date].copy()
        if df_exp.empty:
            return exp_date, empty, None

        if "raw_symbol" not in df_exp.columns and "symbol" in df_exp.columns:
            df_exp["raw_symbol"] = df_exp["symbol"].astype(str)

        strike_series = pd.to_numeric(df_exp.get("strike_price"), errors="coerce")
        if strike_series.isna().all():
            parsed = df_exp["raw_symbol"].astype(str).map(_parse_occ_symbol)
            df_exp["strike_price"] = [x[0] for x in parsed]
            inferred_side = [x[1] for x in parsed]
            if "instrument_class" not in df_exp.columns:
                df_exp["instrument_class"] = inferred_side

        if "instrument_class" in df_exp.columns:
            side_raw = df_exp["instrument_class"].astype(str).str.upper()
            df_exp["opt_side"] = side_raw.map({"C": "call", "P": "put", "CALL": "call", "PUT": "put"})
        else:
            df_exp["opt_side"] = df_exp["raw_symbol"].astype(str).map(lambda x: _parse_occ_symbol(x)[1])

        tcbbo = _fetch_tcbbo_df(ticker_sym)
        tcbbo_map = {}
        if not tcbbo.empty and "symbol" in tcbbo.columns:
            t = tcbbo.copy()
            t["symbol"] = t["symbol"].astype(str)

            bid_col = "bid_px_00" if "bid_px_00" in t.columns else "bid_px"
            ask_col = "ask_px_00" if "ask_px_00" in t.columns else "ask_px"

            if bid_col not in t.columns:
                t[bid_col] = 0.0
            if ask_col not in t.columns:
                t[ask_col] = 0.0
            if "price" not in t.columns:
                t["price"] = 0.0
            if "size" not in t.columns:
                t["size"] = 0

            t["_ts"] = pd.to_datetime(t.get("ts_recv", t.get("ts_event")), errors="coerce", utc=True)
            t = t.sort_values("_ts")
            vol_by_symbol = t.groupby("symbol")["size"].sum().to_dict()
            latest = t.groupby("symbol", as_index=False).tail(1)

            for _, row in latest.iterrows():
                sym = str(row.get("symbol", ""))
                tcbbo_map[sym] = {
                    "lastPrice": _safe_float(row.get("price"), 0.0),
                    "bid": _safe_float(row.get(bid_col), 0.0),
                    "ask": _safe_float(row.get(ask_col), 0.0),
                    "volume": _safe_int(vol_by_symbol.get(sym, 0), 0),
                }

        stats = _fetch_statistics_df(ticker_sym)
        oi_map = {}
        if not stats.empty and "symbol" in stats.columns:
            s = stats.copy()
            s["symbol"] = s["symbol"].astype(str)
            oi_col = None
            for candidate in ["open_interest", "openInterest", "oi"]:
                if candidate in s.columns:
                    oi_col = candidate
                    break

            if oi_col is not None:
                s["_ts"] = pd.to_datetime(s.get("ts_recv", s.get("ts_event")), errors="coerce", utc=True)
                s = s.sort_values("_ts")
                latest_stats = s.groupby("symbol", as_index=False).tail(1)
                oi_map = {
                    str(row.get("symbol", "")): _safe_int(row.get(oi_col), 0)
                    for _, row in latest_stats.iterrows()
                }

        rows_calls = []
        rows_puts = []
        for _, row in df_exp.iterrows():
            symbol = str(row.get("raw_symbol", "")).strip()
            side = str(row.get("opt_side", "")).lower()
            strike = _safe_float(row.get("strike_price"), 0.0)

            market = tcbbo_map.get(symbol, {})
            out = {
                "strike": strike,
                "lastPrice": _safe_float(market.get("lastPrice"), 0.0),
                "bid": _safe_float(market.get("bid"), 0.0),
                "ask": _safe_float(market.get("ask"), 0.0),
                "volume": _safe_int(market.get("volume"), 0),
                "openInterest": _safe_int(oi_map.get(symbol), 0),
                "impliedVolatility": 0.0,
            }

            if side == "call":
                rows_calls.append(out)
            elif side == "put":
                rows_puts.append(out)

        calls_df = _normalize_chain_df(pd.DataFrame(rows_calls))
        puts_df = _normalize_chain_df(pd.DataFrame(rows_puts))
        return exp_date, {"calls": calls_df, "puts": puts_df}, None
    except Exception as exc:
        get_provider_metrics().record_chain_failure()
        logger.warning("Databento chain fallo (%s, %s): %s", ticker_sym, exp_date, exc)
        return exp_date, empty, "Datos parciales no disponibles temporalmente"


def get_price_history(ticker_sym: str, period: str = "1y") -> pd.DataFrame:
    """Devuelve OHLCV diario en formato estilo yfinance para un ticker de equity."""
    days = _period_days(period)
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    for dataset in _equity_datasets():
        try:
            client = _client()
            data = _with_retry(
                lambda: client.timeseries.get_range(
                    dataset=dataset,
                    schema="ohlcv-1d",
                    stype_in="raw_symbol",
                    symbols=[ticker_sym],
                    start=start,
                    end=now.isoformat(),
                    limit=10_000,
                ),
                op_name=f"ohlcv:{dataset}:{ticker_sym}",
            )
            df = _to_df(data)
            if df.empty:
                continue
            df = df.reset_index(drop=False)

            ts_col = "ts_event" if "ts_event" in df.columns else "ts_recv"
            if ts_col not in df.columns:
                continue

            out = pd.DataFrame(
                {
                    "Date": pd.to_datetime(df[ts_col], errors="coerce", utc=True),
                    "Open": pd.to_numeric(df.get("open", 0), errors="coerce").fillna(0.0),
                    "High": pd.to_numeric(df.get("high", 0), errors="coerce").fillna(0.0),
                    "Low": pd.to_numeric(df.get("low", 0), errors="coerce").fillna(0.0),
                    "Close": pd.to_numeric(df.get("close", 0), errors="coerce").fillna(0.0),
                    "Volume": pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0).astype(int),
                }
            )
            out = out.dropna(subset=["Date"]).set_index("Date").sort_index()
            if not out.empty:
                return out
        except Exception as exc:
            logger.debug("Databento history fallo dataset=%s ticker=%s: %s", dataset, ticker_sym, exc)

    return pd.DataFrame()


def get_contract_history(contract_symbol: str, period: str = "1mo") -> pd.DataFrame:
    """Historial de contrato de opcion via OPRA en ohlcv-1d."""
    days = _period_days(period)
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        client = _client()
        data = _with_retry(
            lambda: client.timeseries.get_range(
                dataset=_options_dataset(),
                schema="ohlcv-1d",
                stype_in="raw_symbol",
                symbols=[contract_symbol],
                start=start,
                end=now.isoformat(),
                limit=20_000,
            ),
            op_name=f"contract_ohlcv:{contract_symbol}",
        )
        df = _to_df(data)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index(drop=False)

        ts_col = "ts_event" if "ts_event" in df.columns else "ts_recv"
        out = pd.DataFrame(
            {
                "Date": pd.to_datetime(df.get(ts_col), errors="coerce", utc=True),
                "Open": pd.to_numeric(df.get("open", 0), errors="coerce").fillna(0.0),
                "High": pd.to_numeric(df.get("high", 0), errors="coerce").fillna(0.0),
                "Low": pd.to_numeric(df.get("low", 0), errors="coerce").fillna(0.0),
                "Close": pd.to_numeric(df.get("close", 0), errors="coerce").fillna(0.0),
                "Volume": pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0).astype(int),
            }
        )
        out = out.dropna(subset=["Date"]).set_index("Date").sort_index()
        return out
    except Exception as exc:
        logger.warning("Databento contract history fallo (%s): %s", contract_symbol, exc)
        return pd.DataFrame()


def get_ticker_details(ticker_sym: str):
    """Compat helper para fachada: Databento no expone ticker_details equivalente."""
    return None
