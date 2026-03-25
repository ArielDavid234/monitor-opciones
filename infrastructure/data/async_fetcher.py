import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from infrastructure.data.provider_runtime import get_provider_metrics, request_channel
from infrastructure.data.yahoo_finance_client import fetch_single_chain

logger = logging.getLogger(__name__)

# Yahoo Finance no tiene límite estricto formal, pero para evitar bloqueos
# por abuso se procesan las fechas en lotes pequeños con pausa entre lotes.
_BATCH_SIZE = 2          # fechas descargadas simultáneamente por lote
_BATCH_PAUSE_SEC = 1.2   # pausa entre lotes (segundos)


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
    """Descarga múltiples cadenas en lotes de 2 con pausa entre lotes.

    Evita errores 429 (Too Many Requests) al nunca superar 2 solicitudes
    concurrentes en el mismo segundo.
    """
    if not exp_dates:
        return {}

    out = {}
    total = len(exp_dates)
    logger.info(
        "Bulk chain fetch | ticker=%s | expirations=%d | batch_size=%d",
        ticker_sym,
        total,
        _BATCH_SIZE,
    )

    for i in range(0, total, _BATCH_SIZE):
        batch = exp_dates[i: i + _BATCH_SIZE]

        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = [executor.submit(_fetch_one, ticker_sym, exp_date) for exp_date in batch]
            for future in as_completed(futures):
                exp_date, chain_data, error = future.result()
                if chain_data:
                    out[exp_date] = chain_data
                elif error:
                    logger.warning("Error fetch_single_chain %s: %s", exp_date, error)

        # Pausa entre lotes para respetar el rate-limit del proveedor,
        # excepto tras el último lote (no hay siguiente solicitud).
        if i + _BATCH_SIZE < total:
            time.sleep(_BATCH_PAUSE_SEC)

    return out
