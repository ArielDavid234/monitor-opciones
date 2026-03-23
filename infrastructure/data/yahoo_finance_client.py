"""Facade de compatibilidad para proveedores de datos.

Este módulo conserva la API pública usada por el resto del sistema
y enruta al proveedor activo via DATA_PROVIDER.
"""

from __future__ import annotations

import logging
import os
import time

import pandas as pd
import streamlit as st

from infrastructure.caching import get_cache as _get_cache
from infrastructure.data.env_resolver import get_env_value
from infrastructure.data.provider_runtime import (
    CircuitOpenError,
    get_cross_user_dedupe,
    get_provider_circuit,
    get_provider_metrics,
    get_refresh_priority_registry,
    get_single_flight_group,
    request_channel,
)
from infrastructure.data.snapshot_pipeline import get_snapshot_scheduler

logger = logging.getLogger(__name__)
_cache = _get_cache()
_CHAIN_REQUIRED_COLUMNS = [
    "strike",
    "lastPrice",
    "bid",
    "ask",
    "volume",
    "openInterest",
    "impliedVolatility",
]


def _estimate_dynamic_chain_ttl_seconds(chain_payload) -> int:
    base = int(get_env_value("SNAPSHOT_CHAIN_FRESH_SEC", "240"))
    min_ttl = int(get_env_value("SNAPSHOT_CHAIN_MIN_TTL_SEC", "60"))
    max_ttl = int(get_env_value("SNAPSHOT_CHAIN_MAX_TTL_SEC", "900"))

    if not isinstance(chain_payload, dict):
        return max(min(base, max_ttl), min_ttl)

    calls = chain_payload.get("calls")
    puts = chain_payload.get("puts")
    if calls is None or puts is None:
        return max(min(base, max_ttl), min_ttl)

    try:
        total_volume = float(calls["volume"].fillna(0).sum() + puts["volume"].fillna(0).sum())
    except Exception:
        total_volume = 0.0

    try:
        iv_values = pd.concat([calls["impliedVolatility"], puts["impliedVolatility"]], axis=0)
        iv_mean = float(iv_values.fillna(0).mean())
    except Exception:
        iv_mean = 0.0

    ttl = base
    if total_volume >= 60000:
        ttl -= 90
    elif total_volume <= 6000:
        ttl += 150

    if iv_mean >= 0.55:
        ttl -= 80
    elif iv_mean <= 0.25:
        ttl += 80

    return max(min(ttl, max_ttl), min_ttl)


def _cache_version() -> str:
    return get_env_value("MARKET_CACHE_VERSION", "v1") or "v1"


def _cache_base_prefix() -> str:
    return f"market:{_cache_version()}:{_provider_name()}"


def _snapshot_hard_ttl() -> int:
    return int(get_env_value("SNAPSHOT_HARD_TTL_SEC", "1800"))


def _snapshot_fresh_seconds(kind: str) -> int:
    if kind == "price":
        return int(get_env_value("SNAPSHOT_PRICE_FRESH_SEC", "60"))
    if kind == "exp":
        return int(get_env_value("SNAPSHOT_EXP_FRESH_SEC", "300"))
    if kind == "chain":
        return int(get_env_value("SNAPSHOT_CHAIN_FRESH_SEC", "240"))
    return int(get_env_value("SNAPSHOT_FRESH_SEC", "180"))


def _meta_key(kind: str, ticker: str, expiration: str | None = None) -> str:
    if kind == "chain" and expiration:
        return f"{_cache_base_prefix()}:meta:chain:{ticker}:{expiration}"
    return f"{_cache_base_prefix()}:meta:{kind}:{ticker}"


def _set_meta(kind: str, ticker: str, expiration: str | None = None) -> None:
    _cache.set(_meta_key(kind, ticker, expiration), {"ts": time.time()}, ttl=_snapshot_hard_ttl())


def _get_age_seconds(kind: str, ticker: str, expiration: str | None = None) -> float | None:
    meta = _cache.get(_meta_key(kind, ticker, expiration))
    if not isinstance(meta, dict):
        return None
    ts = meta.get("ts")
    if ts is None:
        return None
    try:
        return max(0.0, time.time() - float(ts))
    except (TypeError, ValueError):
        return None


def _is_fresh(kind: str, ticker: str, expiration: str | None = None) -> bool:
    age = _get_age_seconds(kind, ticker, expiration)
    if age is None:
        return False
    return age <= float(_snapshot_fresh_seconds(kind))


def _normalize_chain_df(df) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=_CHAIN_REQUIRED_COLUMNS)

    out = df.copy()
    for col in _CHAIN_REQUIRED_COLUMNS:
        if col not in out.columns:
            out[col] = 0

    out["strike"] = pd.to_numeric(out["strike"], errors="coerce").fillna(0.0).astype(float)
    out["lastPrice"] = pd.to_numeric(out["lastPrice"], errors="coerce").fillna(0.0).astype(float)
    out["bid"] = pd.to_numeric(out["bid"], errors="coerce").fillna(0.0).astype(float)
    out["ask"] = pd.to_numeric(out["ask"], errors="coerce").fillna(0.0).astype(float)
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype(int)
    out["openInterest"] = pd.to_numeric(out["openInterest"], errors="coerce").fillna(0).astype(int)
    out["impliedVolatility"] = pd.to_numeric(out["impliedVolatility"], errors="coerce").fillna(0.0).astype(float)
    return out[_CHAIN_REQUIRED_COLUMNS]


def _normalize_chain_payload(ticker: str, expiration: str, payload):
    if not isinstance(payload, dict):
        logger.warning(
            "snapshot guardrail | ticker=%s | exp=%s | issue=payload_not_dict",
            ticker,
            expiration,
        )
        return {
            "calls": pd.DataFrame(columns=_CHAIN_REQUIRED_COLUMNS),
            "puts": pd.DataFrame(columns=_CHAIN_REQUIRED_COLUMNS),
        }

    calls = _normalize_chain_df(payload.get("calls"))
    puts = _normalize_chain_df(payload.get("puts"))
    return {"calls": calls, "puts": puts}


def _request_snapshot_revalidate(ticker: str, reason: str, priority: str = "normal", immediate: bool = False) -> None:
    scheduler = get_snapshot_scheduler()
    scheduler.request_revalidate(ticker, reason=reason, priority=priority, immediate=immediate)


def _register_snapshot_access(ticker: str, priority: str = "normal") -> None:
    scheduler = get_snapshot_scheduler()
    scheduler.mark_access(ticker, priority=priority)


def _provider_name() -> str:
    provider = get_env_value("DATA_PROVIDER", "databento").lower()
    if provider != "databento":
        provider = "databento"
    return provider


def _provider_impls():
    from infrastructure.data.databento_client import (
        fetch_options_dates as _databento_fetch_options_dates,
        fetch_single_chain as _databento_fetch_single_chain,
        get_contract_history as _databento_get_contract_history,
        get_ticker_details as _databento_get_ticker_details,
        get_price_history as _databento_get_price_history,
        obtener_precio_actual as _databento_obtener_precio_actual,
    )

    return {
        "name": "databento",
        "fetch_options_dates": _databento_fetch_options_dates,
        "fetch_single_chain": _databento_fetch_single_chain,
        "get_price_history": _databento_get_price_history,
        "get_contract_history": _databento_get_contract_history,
        "get_ticker_details": _databento_get_ticker_details,
        "obtener_precio_actual": _databento_obtener_precio_actual,
    }


def _provider_call(op_name: str, ticker: str, fn, *args, **kwargs):
    circuit = get_provider_circuit()
    if not circuit.allow_request():
        snap = circuit.snapshot()
        raise CircuitOpenError(
            "CircuitOpen provider protection active; retry in "
            f"{int(snap.get('retry_after_sec', 30))} seconds"
        )

    try:
        result = fn(*args, **kwargs)
        circuit.record_success()
        return result
    except CircuitOpenError:
        raise
    except Exception:
        circuit.record_failure()
        raise


def get_active_provider() -> str:
    return _provider_name()


def _cache_key_dates(ticker: str) -> str:
    return f"{_cache_base_prefix()}:exp:{ticker}"


def _legacy_cache_key_dates(ticker: str) -> str:
    return f"market:{_provider_name()}:exp:{ticker}"


def _older_legacy_cache_key_dates(ticker: str) -> str:
    return f"dates:{_provider_name()}:{ticker}"


def _cache_key_chain(ticker: str, expiration: str) -> str:
    return f"{_cache_base_prefix()}:chain:{ticker}:{expiration}"


def _legacy_cache_key_chain(ticker: str, expiration: str) -> str:
    return f"market:{_provider_name()}:chain:{ticker}:{expiration}"


def _older_legacy_cache_key_chain(ticker: str, expiration: str) -> str:
    return f"chain:{_provider_name()}:{ticker}:{expiration}"


def _cache_key_history(ticker: str, period: str) -> str:
    return f"{_cache_base_prefix()}:history:{ticker}:{period}"


def _legacy_cache_key_history(ticker: str, period: str) -> str:
    return f"market:{_provider_name()}:history:{ticker}:{period}"


def _older_legacy_cache_key_history(ticker: str, period: str) -> str:
    return f"history:{_provider_name()}:{ticker}:{period}"


def _cache_key_spot(ticker: str) -> str:
    return f"{_cache_base_prefix()}:price:{ticker}"


def _legacy_cache_key_spot(ticker: str) -> str:
    return f"market:{_provider_name()}:price:{ticker}"


def _older_legacy_cache_key_spot(ticker: str) -> str:
    return f"spot:{_provider_name()}:{ticker}"


def _get_cache_with_legacy(new_key: str, legacy_key: str, older_legacy_key: str | None = None):
    cached = _cache.get(new_key)
    if cached is not None:
        return cached
    legacy = _cache.get(legacy_key)
    if legacy is not None:
        _cache.set(new_key, legacy, ttl=240)
        return legacy
    if older_legacy_key:
        older = _cache.get(older_legacy_key)
        if older is not None:
            _cache.set(new_key, older, ttl=240)
            return older
    return None


def get_cached_chain(ticker: str, expiration: str):
    cached = _get_cache_with_legacy(
        _cache_key_chain(ticker, expiration),
        _legacy_cache_key_chain(ticker, expiration),
        _older_legacy_cache_key_chain(ticker, expiration),
    )
    if cached is None:
        get_provider_metrics().record_snapshot_access(hit=False)
        return None

    normalized = _normalize_chain_payload(ticker, expiration, cached)
    get_provider_metrics().record_snapshot_access(hit=True)
    _register_snapshot_access(ticker, priority="hot")
    if not _is_fresh("chain", ticker, expiration):
        _request_snapshot_revalidate(
            ticker,
            reason=f"stale_chain:{expiration}",
            priority="hot",
            immediate=False,
        )
    return normalized


def cache_chain(ticker: str, expiration: str, chain_df, ttl_seconds: int = 240):
    normalized = _normalize_chain_payload(ticker, expiration, chain_df)
    dynamic_ttl = _estimate_dynamic_chain_ttl_seconds(normalized)
    effective_ttl = max(ttl_seconds, dynamic_ttl, _snapshot_hard_ttl())
    _cache.set(_cache_key_chain(ticker, expiration), normalized, ttl=effective_ttl)
    _set_meta("chain", ticker, expiration)


def _chain_is_cacheable(result):
    if not isinstance(result, dict):
        return False
    puts = result.get("puts")
    calls = result.get("calls")
    if puts is None or calls is None:
        return False
    return not (puts.empty and calls.empty)


def _history_is_cacheable(result):
    if result is None:
        return False
    return not result.empty


def _cached_options_dates(ticker_sym):
    key = _cache_key_dates(ticker_sym)
    cached = _get_cache_with_legacy(
        key,
        _legacy_cache_key_dates(ticker_sym),
        _older_legacy_cache_key_dates(ticker_sym),
    )
    if cached is not None:
        get_provider_metrics().record_snapshot_access(hit=True)
        _register_snapshot_access(ticker_sym, priority="hot")
        if not _is_fresh("exp", ticker_sym):
            _request_snapshot_revalidate(
                ticker_sym,
                reason="stale_expirations",
                priority="hot",
                immediate=False,
            )
        return tuple(cached)

    get_provider_metrics().record_snapshot_access(hit=False)

    provider = _provider_impls()
    with request_channel("live_scanning"):
        dates = tuple(
            _provider_call(
                "fetch_options_dates",
                ticker_sym,
                provider["fetch_options_dates"],
                ticker_sym,
            )
        )
    if dates:
        _cache.set(key, dates, ttl=max(900, _snapshot_hard_ttl()))
        _set_meta("exp", ticker_sym)
    return dates


def _cached_option_chain(ticker_sym, exp_date):
    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return cached

    provider = _provider_impls()
    _, chain_data, err = _provider_call(
        "fetch_single_chain",
        ticker_sym,
        provider["fetch_single_chain"],
        ticker_sym,
        exp_date,
    )
    if err:
        raise RuntimeError(err)
    if _chain_is_cacheable(chain_data):
        cache_chain(ticker_sym, exp_date, chain_data, ttl_seconds=240)
    return chain_data


def _cached_history(ticker_sym, period="1d"):
    key = _cache_key_history(ticker_sym, period)
    cached = _get_cache_with_legacy(
        key,
        _legacy_cache_key_history(ticker_sym, period),
        _older_legacy_cache_key_history(ticker_sym, period),
    )
    if cached is not None:
        return cached

    provider = _provider_impls()
    hist = _provider_call(
        "get_price_history",
        ticker_sym,
        provider["get_price_history"],
        ticker_sym,
        period,
    )
    if _history_is_cacheable(hist):
        _cache.set(key, hist, ttl=300)
    return hist


def _cached_options_dates_cache_clear():
    _cache.clear_prefix(f"{_cache_base_prefix()}:exp:")
    _cache.clear_prefix(f"{_cache_base_prefix()}:meta:exp:")
    _cache.clear_prefix(f"market:{_provider_name()}:exp:")
    _cache.clear_prefix(f"dates:{_provider_name()}:")


def _cached_options_dates_cache_invalidate(ticker_sym):
    _cache.delete(_cache_key_dates(ticker_sym))
    _cache.delete(_legacy_cache_key_dates(ticker_sym))
    _cache.delete(_older_legacy_cache_key_dates(ticker_sym))
    _cache.delete(_meta_key("exp", ticker_sym))


def _cached_option_chain_cache_clear():
    _cache.clear_prefix(f"{_cache_base_prefix()}:chain:")
    _cache.clear_prefix(f"{_cache_base_prefix()}:meta:chain:")
    _cache.clear_prefix(f"market:{_provider_name()}:chain:")
    _cache.clear_prefix(f"chain:{_provider_name()}:")


def _cached_option_chain_cache_invalidate(ticker_sym, exp_date):
    _cache.delete(_cache_key_chain(ticker_sym, exp_date))
    _cache.delete(_legacy_cache_key_chain(ticker_sym, exp_date))
    _cache.delete(_older_legacy_cache_key_chain(ticker_sym, exp_date))
    _cache.delete(_meta_key("chain", ticker_sym, exp_date))


def _cached_history_cache_clear():
    _cache.clear_prefix(f"{_cache_base_prefix()}:history:")
    _cache.clear_prefix(f"market:{_provider_name()}:history:")
    _cache.clear_prefix(f"history:{_provider_name()}:")


def _cached_history_cache_invalidate(ticker_sym, period="1d"):
    _cache.delete(_cache_key_history(ticker_sym, period))
    _cache.delete(_legacy_cache_key_history(ticker_sym, period))
    _cache.delete(_older_legacy_cache_key_history(ticker_sym, period))


_cached_options_dates.cache_clear = _cached_options_dates_cache_clear
_cached_options_dates.cache_invalidate = _cached_options_dates_cache_invalidate
_cached_option_chain.cache_clear = _cached_option_chain_cache_clear
_cached_option_chain.cache_invalidate = _cached_option_chain_cache_invalidate
_cached_history.cache_clear = _cached_history_cache_clear
_cached_history.cache_invalidate = _cached_history_cache_invalidate


def limpiar_cache_ticker(ticker_sym=None):
    if ticker_sym is None:
        _cached_options_dates.cache_clear()
        _cached_option_chain.cache_clear()
        _cached_history.cache_clear()
        _cache.clear_prefix(f"{_cache_base_prefix()}:price:")
        _cache.clear_prefix(f"{_cache_base_prefix()}:meta:price:")
        _cache.clear_prefix(f"market:{_provider_name()}:price:")
        _cache.clear_prefix(f"spot:{_provider_name()}:")
        logger.info("Cache completo limpiado")
    else:
        _cached_options_dates.cache_invalidate(ticker_sym)
        _cache.clear_prefix(f"{_cache_base_prefix()}:chain:{ticker_sym}:")
        _cache.clear_prefix(f"{_cache_base_prefix()}:meta:chain:{ticker_sym}:")
        _cache.clear_prefix(f"market:{_provider_name()}:chain:{ticker_sym}:")
        _cache.clear_prefix(f"chain:{_provider_name()}:{ticker_sym}:")
        _cached_history.cache_invalidate(ticker_sym, "1d")
        _cached_history.cache_invalidate(ticker_sym, "1mo")
        _cached_history.cache_invalidate(ticker_sym, "3mo")
        _cached_history.cache_invalidate(ticker_sym, "5d")
        _cache.delete(_cache_key_spot(ticker_sym))
        _cache.delete(_legacy_cache_key_spot(ticker_sym))
        _cache.delete(_older_legacy_cache_key_spot(ticker_sym))
        _cache.delete(_meta_key("price", ticker_sym))
        logger.info("Cache limpiado para ticker: %s", ticker_sym)


def limpiar_cache_version(version: str | None = None, ticker_sym: str | None = None):
    target_version = (version or _cache_version()).strip() or _cache_version()
    provider = _provider_name()
    base = f"market:{target_version}:{provider}:"
    if ticker_sym is None:
        _cache.clear_prefix(base)
        logger.info("Cache version limpiado | version=%s | provider=%s", target_version, provider)
        return

    ticker = ticker_sym.strip().upper()
    _cache.delete(f"{base}price:{ticker}")
    _cache.delete(f"{base}exp:{ticker}")
    _cache.delete(f"{base}meta:price:{ticker}")
    _cache.delete(f"{base}meta:exp:{ticker}")
    _cache.clear_prefix(f"{base}chain:{ticker}:")
    _cache.clear_prefix(f"{base}meta:chain:{ticker}:")
    logger.info("Cache version ticker limpiado | version=%s | provider=%s | ticker=%s", target_version, provider, ticker)


def obtener_precio_actual(ticker_sym):
    key = _cache_key_spot(ticker_sym)
    cached = _get_cache_with_legacy(
        key,
        _legacy_cache_key_spot(ticker_sym),
        _older_legacy_cache_key_spot(ticker_sym),
    )
    if cached is not None:
        get_provider_metrics().record_snapshot_access(hit=True)
        _register_snapshot_access(ticker_sym, priority="hot")
        if not _is_fresh("price", ticker_sym):
            _request_snapshot_revalidate(
                ticker_sym,
                reason="stale_price",
                priority="hot",
                immediate=False,
            )
        return cached

    get_provider_metrics().record_snapshot_access(hit=False)

    provider = _provider_impls()
    with request_channel("live_scanning"):
        result = _provider_call(
            "obtener_precio_actual",
            ticker_sym,
            provider["obtener_precio_actual"],
            ticker_sym,
        )
    if isinstance(result, tuple) and result[0] is not None:
        _cache.set(key, result, ttl=max(60, _snapshot_hard_ttl()))
        _set_meta("price", ticker_sym)
    return result


def crear_sesion_nueva():
    """Compat: ya no existe sesion HTTP Yahoo; se usa proveedor configurado."""
    return None, _provider_name()


def get_price_history(ticker_sym: str, period: str = "1y"):
    return _cached_history(ticker_sym, period)


def get_ticker_details(ticker_sym: str):
    provider = _provider_impls()
    getter = provider.get("get_ticker_details")
    if getter is None:
        return None
    return _provider_call("get_ticker_details", ticker_sym, getter, ticker_sym)


@st.cache_data(ttl=300, show_spinner=False)
def obtener_historial_contrato(contract_symbol):
    try:
        provider = _provider_impls()
        hist = _provider_call(
            "get_contract_history",
            contract_symbol,
            provider["get_contract_history"],
            contract_symbol,
            period="1mo",
        )
        if hist.empty:
            hist = _provider_call(
                "get_contract_history",
                contract_symbol,
                provider["get_contract_history"],
                contract_symbol,
                period="5d",
            )
        return hist, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def fetch_single_chain(ticker_sym, exp_date, max_retries=3):
    _ = max_retries
    _register_snapshot_access(ticker_sym, priority="hot")
    dedupe = get_cross_user_dedupe().register_request(ticker_sym)

    if dedupe.get("dedupe_candidate"):
        cached_again = get_cached_chain(ticker_sym, exp_date)
        if cached_again is not None:
            return exp_date, cached_again, None

    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return exp_date, cached, None

    provider = _provider_impls()
    sf = get_single_flight_group()

    def _leader_call():
        with request_channel("live_scanning"):
            return _provider_call(
                "fetch_single_chain",
                ticker_sym,
                provider["fetch_single_chain"],
                ticker_sym,
                exp_date,
            )

    exp, chain_data, err = sf.do(f"chain:{ticker_sym}:{exp_date}", _leader_call)
    if chain_data is not None and err is None:
        cache_chain(ticker_sym, exp, chain_data, ttl_seconds=_estimate_dynamic_chain_ttl_seconds(chain_data))
        return exp, get_cached_chain(ticker_sym, exp) or chain_data, None
    return exp, chain_data, err


def fetch_options_dates(ticker_sym):
    _register_snapshot_access(ticker_sym, priority="hot")
    return _cached_options_dates(ticker_sym)


def fetch_with_cache(ticker_sym: str, exp_date: str):
    cached = get_cached_chain(ticker_sym, exp_date)
    if cached is not None:
        return exp_date, cached, None

    result = fetch_single_chain(ticker_sym, exp_date)
    exp_date, chain_data, error = result
    if chain_data is not None:
        cache_chain(ticker_sym, exp_date, chain_data)
    return result


def _refresh_ticker_snapshot(ticker_sym: str, reason: str) -> bool:
    provider = _provider_impls()
    ticker = str(ticker_sym or "").strip().upper()
    if not ticker:
        return False

    logger.info("snapshot refresh start | ticker=%s | provider=%s | reason=%s", ticker, provider["name"], reason)
    get_refresh_priority_registry().register_demand(ticker, user_plan=os.getenv("SNAPSHOT_DEFAULT_PLAN", "pro"))
    ok_any = False
    with request_channel("background"):
        price = _provider_call(
            "obtener_precio_actual",
            ticker,
            provider["obtener_precio_actual"],
            ticker,
        )
        if isinstance(price, tuple) and price[0] is not None:
            _cache.set(_cache_key_spot(ticker), price, ttl=max(60, _snapshot_hard_ttl()))
            _set_meta("price", ticker)
            ok_any = True

        dates = tuple(
            _provider_call(
                "fetch_options_dates",
                ticker,
                provider["fetch_options_dates"],
                ticker,
            )
        )
        if dates:
            _cache.set(_cache_key_dates(ticker), dates, ttl=max(900, _snapshot_hard_ttl()))
            _set_meta("exp", ticker)
            ok_any = True

        max_exp = max(1, int(os.getenv("SNAPSHOT_MAX_EXP_PER_TICKER", "4")))
        for exp_date in list(dates)[:max_exp]:
            _, payload, err = _provider_call(
                "fetch_single_chain",
                ticker,
                provider["fetch_single_chain"],
                ticker,
                exp_date,
            )
            if err:
                continue
            cache_chain(ticker, exp_date, payload, ttl_seconds=240)
            ok_any = True

    return ok_any


def start_snapshot_services(hot_tickers: list[str] | None = None) -> None:
    scheduler = get_snapshot_scheduler()
    scheduler.set_refresh_handler(_refresh_ticker_snapshot)
    scheduler.start()

    warm_enabled = os.getenv("SNAPSHOT_WARM_START_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    warm_raw = os.getenv("SNAPSHOT_WARM_START_TICKERS", "SPY,QQQ,AAPL")
    warm_tickers = [x.strip().upper() for x in warm_raw.split(",") if x.strip()]
    if warm_enabled and warm_tickers:
        scheduler.register_tickers(warm_tickers, priority="hot", immediate=False)

    if hot_tickers:
        scheduler.register_tickers([x for x in hot_tickers if x], priority="hot", immediate=True)
