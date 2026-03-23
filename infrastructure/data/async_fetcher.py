import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import get_settings

from infrastructure.data.provider_runtime import get_provider_metrics, request_channel
from infrastructure.data.yahoo_finance_client import fetch_single_chain

logger = logging.getLogger(__name__)


def _max_workers() -> int:
    try:
        settings_workers = int(get_settings().chain_fetch_max_workers)
    except Exception:
        settings_workers = 6

    env_value = os.getenv("CHAIN_FETCH_MAX_WORKERS")
    if env_value is not None:
        try:
            settings_workers = int(env_value)
        except ValueError:
            pass

    # Concurrencia moderada por defecto para evitar saturacion de proveedor.
    return max(4, min(settings_workers, 8))


def _fetch_one(ticker_sym: str, exp_date: str):
    try:
        with request_channel("live_scanning"):
            _, chain_data, error = fetch_single_chain(ticker_sym, exp_date)
        if error:
            get_provider_metrics().record_chain_failure()
        return exp_date, chain_data, error
    except Exception as exc:
        get_provider_metrics().record_chain_failure()
        return exp_date, None, str(exc)


def get_multiple_chains_fast(ticker_sym: str, exp_dates: list[str]) -> dict:
    """Descarga multiples cadenas en paralelo via fachada de proveedor."""
    if not exp_dates:
        return {}

    out = {}
    workers = min(_max_workers(), len(exp_dates))
    logger.info(
        "Bulk chain fetch | ticker=%s | expirations=%d | workers=%d",
        ticker_sym,
        len(exp_dates),
        workers,
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_one, ticker_sym, exp_date) for exp_date in exp_dates]
        for future in as_completed(futures):
            exp_date, chain_data, error = future.result()
            if chain_data:
                out[exp_date] = chain_data
            elif error:
                logger.warning("Error fetch_single_chain %s: %s", exp_date, error)

    return out
