import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pandas as pd

from infrastructure.caching import get_cache
from infrastructure.data import yahoo_finance_client as facade


class TestSnapshotLoad(unittest.TestCase):
    def test_concurrent_multiuser_latency_improves_with_snapshot_cache(self):
        cache = get_cache()
        cache.clear_all()

        provider_calls = {"dates": 0, "chain": 0}

        def fake_dates(_ticker):
            provider_calls["dates"] += 1
            time.sleep(0.03)
            return ("2026-12-18", "2026-12-24")

        def fake_chain(_ticker, exp_date):
            provider_calls["chain"] += 1
            time.sleep(0.03)
            row = {
                "strike": 100.0,
                "lastPrice": 1.0,
                "bid": 0.9,
                "ask": 1.1,
                "volume": 10,
                "openInterest": 20,
                "impliedVolatility": 0.2,
            }
            df = pd.DataFrame([row])
            return exp_date, {"calls": df, "puts": df.copy()}, None

        provider = {
            "fetch_options_dates": fake_dates,
            "fetch_single_chain": fake_chain,
            "obtener_precio_actual": lambda _ticker: (123.45, None),
            "get_price_history": lambda *_args, **_kwargs: pd.DataFrame(),
            "get_contract_history": lambda *_args, **_kwargs: pd.DataFrame(),
            "get_ticker_details": lambda *_args, **_kwargs: None,
        }

        def user_flow(ticker):
            start = time.perf_counter()
            dates = facade.fetch_options_dates(ticker)
            facade.fetch_single_chain(ticker, dates[0])
            return (time.perf_counter() - start) * 1000.0

        tickers = ["SPY", "QQQ", "AAPL"]

        with patch("infrastructure.data.yahoo_finance_client._provider_impls", return_value=provider):
            with patch("infrastructure.data.yahoo_finance_client._request_snapshot_revalidate"):
                with ThreadPoolExecutor(max_workers=9) as pool:
                    first_wave = list(pool.map(user_flow, tickers * 3))
                calls_after_first = dict(provider_calls)
                with ThreadPoolExecutor(max_workers=9) as pool:
                    second_wave = list(pool.map(user_flow, tickers * 3))

        first_p50 = sorted(first_wave)[len(first_wave) // 2]
        second_p50 = sorted(second_wave)[len(second_wave) // 2]

        self.assertLess(second_p50, first_p50)
        self.assertLessEqual(provider_calls["dates"], calls_after_first["dates"] + 1)
        self.assertLessEqual(provider_calls["chain"], calls_after_first["chain"] + 1)


if __name__ == "__main__":
    unittest.main()
