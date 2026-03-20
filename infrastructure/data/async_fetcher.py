import logging
import time

from infrastructure.data.yahoo_finance_client import fetch_single_chain

logger = logging.getLogger(__name__)


def get_multiple_chains_fast(ticker_sym: str, exp_dates: list[str]) -> dict:
    """Respeta free tier de Polygon: max 5 requests/min con pausa de 12s."""
    if not exp_dates:
        return {}

    out = {}
    for idx, exp_date in enumerate(exp_dates):
        if idx > 0:
            time.sleep(12)
        try:
            _, chain_data, error = fetch_single_chain(ticker_sym, exp_date)
            if chain_data:
                out[exp_date] = chain_data
            elif error:
                logger.warning("Error fetch_single_chain %s: %s", exp_date, error)
        except Exception as exc:
            logger.error("Fallo fetching %s: %s", exp_date, exc)
    return out
