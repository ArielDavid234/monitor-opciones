import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)


def _exp_date_to_unix(exp_date: str) -> int:
    """Convierte fecha YYYY-MM-DD a UNIX timestamp (UTC 00:00:00)."""
    dt = datetime.strptime(exp_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


async def fetch_chain_async(session, ticker, exp_date, semaphore_limit):
    """Descarga cadena de opciones desde endpoint JSON directo de Yahoo."""
    empty = {"calls": pd.DataFrame(), "puts": pd.DataFrame()}
    try:
        exp_date_timestamp = _exp_date_to_unix(exp_date)
        url = (
            "https://query2.finance.yahoo.com/v7/finance/options/"
            f"{ticker}?date={int(exp_date_timestamp)}"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        async with semaphore_limit:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(
                        "Async chain fetch status=%s for %s %s",
                        response.status,
                        ticker,
                        exp_date,
                    )
                    return exp_date, empty
                payload = await response.json(content_type=None)

        result = (((payload or {}).get("optionChain") or {}).get("result") or [])
        if not result:
            return exp_date, empty
        options = (result[0].get("options") or [])
        if not options:
            return exp_date, empty
        bucket = options[0] or {}

        calls_df = pd.DataFrame(bucket.get("calls") or [])
        puts_df = pd.DataFrame(bucket.get("puts") or [])
        return exp_date, {"calls": calls_df, "puts": puts_df}
    except Exception as exc:
        logger.warning("Async chain fetch error for %s %s: %s", ticker, exp_date, exc)
        return exp_date, empty


async def _run_bulk_fetch(ticker_sym: str, exp_dates: list[str]) -> dict:
    connector = aiohttp.TCPConnector(limit=5)
    semaphore = asyncio.Semaphore(3)
    timeout = aiohttp.ClientTimeout(total=20)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            fetch_chain_async(session, ticker_sym, exp_date, semaphore)
            for exp_date in exp_dates
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    out = {}
    for item in results:
        if isinstance(item, Exception):
            continue
        exp_date, chain_data = item
        out[exp_date] = chain_data
    return out


def get_multiple_chains_fast(ticker_sym: str, exp_dates: list[str]) -> dict:
    """Bridge síncrono para disparar fetch asíncrono en lote."""
    if not exp_dates:
        return {}
    try:
        return asyncio.run(_run_bulk_fetch(ticker_sym, exp_dates))
    except RuntimeError:
        # Si ya existe loop (p.ej. entorno especial), crear uno dedicado.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run_bulk_fetch(ticker_sym, exp_dates))
        finally:
            loop.close()
    except Exception as exc:
        logger.warning("Bulk async fetch failed for %s: %s", ticker_sym, exc)
        return {}
