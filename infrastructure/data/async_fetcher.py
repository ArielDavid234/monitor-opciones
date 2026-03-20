import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Hacemos import condicionado local para evitar imports circulares pesados
from infrastructure.data.yahoo_finance_client import fetch_single_chain

logger = logging.getLogger(__name__)


def get_multiple_chains_fast(ticker_sym: str, exp_dates: list[str]) -> dict:
    """Usa Threading nativo validado por yfinance crumbs"""
    if not exp_dates:
        return {}

    out = {}
    # Burst control: 10 workers para acelerar descarga de expiraciones.
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_single_chain, ticker_sym, exp_date): exp_date
            for exp_date in exp_dates
        }

        for future in as_completed(futures):
            try:
                exp_date, chain_data, error = future.result()
                if chain_data:
                    out[exp_date] = chain_data
                elif error:
                    logger.warning(f"Error paralelo fetch_single_chain {exp_date}: {error}")
            except Exception as exc:
                logger.error(f"Fallo en hilo fetching dates {futures[future]}: {exc}")
    return out
