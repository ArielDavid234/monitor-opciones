import os
import unittest
from unittest.mock import patch

import pandas as pd

from infrastructure.data import yahoo_finance_client as facade


class TestDataProviderContract(unittest.TestCase):
    def test_chain_columns_normalized_exact(self):
        raw_df = pd.DataFrame(
            [
                {
                    "strike": "450",
                    "bid": 1.2,
                    "volume": None,
                }
            ]
        )

        out = facade._normalize_chain_df(raw_df)
        expected = [
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "volume",
            "openInterest",
            "impliedVolatility",
        ]
        self.assertEqual(list(out.columns), expected)

    def test_chain_field_fallback_defaults(self):
        out = facade._normalize_chain_df(pd.DataFrame([{"strike": None}]))
        row = out.iloc[0]
        self.assertEqual(float(row["lastPrice"]), 0.0)
        self.assertEqual(float(row["impliedVolatility"]), 0.0)
        self.assertEqual(int(row["openInterest"]), 0)
        self.assertEqual(int(row["volume"]), 0)

    def test_provider_selection_by_env_default_only_yfinance(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATA_PROVIDER", None)
            self.assertEqual(facade.get_active_provider(), "yfinance")

        with patch.dict(os.environ, {"DATA_PROVIDER": "legacy_provider"}, clear=False):
            self.assertEqual(facade.get_active_provider(), "yfinance")

        with patch.dict(os.environ, {"DATA_PROVIDER": "unknown"}, clear=False):
            self.assertEqual(facade.get_active_provider(), "yfinance")

    def test_second_request_hits_cache(self):
        ticker = "TSTCACHE"
        exp = "2099-01-01"
        facade.limpiar_cache_ticker(ticker)

        calls = pd.DataFrame(
            [{"strike": 100.0, "lastPrice": 1.0, "bid": 0.9, "ask": 1.1, "volume": 10, "openInterest": 20, "impliedVolatility": 0.0}]
        )
        puts = pd.DataFrame(
            [{"strike": 100.0, "lastPrice": 1.0, "bid": 0.9, "ask": 1.1, "volume": 10, "openInterest": 20, "impliedVolatility": 0.0}]
        )

        call_counter = {"n": 0}

        def fake_fetch(_ticker, _exp, max_retries=3):
            call_counter["n"] += 1
            return _exp, {"calls": calls, "puts": puts}, None

        with patch("infrastructure.data.yahoo_finance_client.fetch_single_chain", side_effect=fake_fetch):
            r1 = facade.fetch_with_cache(ticker, exp)
            r2 = facade.fetch_with_cache(ticker, exp)

        self.assertIsNone(r1[2])
        self.assertIsNone(r2[2])
        self.assertEqual(call_counter["n"], 1)

    def test_dates_cache_hit_second_request(self):
        ticker = "TSTDATES"
        facade.limpiar_cache_ticker(ticker)

        calls = {"n": 0}

        def fake_dates(_ticker):
            calls["n"] += 1
            return ("2099-01-01", "2099-01-08")

        with patch("infrastructure.data.yahoo_finance_client._provider_impls", return_value={"fetch_options_dates": fake_dates}):
            d1 = facade.fetch_options_dates(ticker)
            d2 = facade.fetch_options_dates(ticker)

        self.assertEqual(d1, d2)
        self.assertEqual(calls["n"], 1)

    def test_spot_cache_hit_second_request(self):
        ticker = "TSTSPOT"
        facade.limpiar_cache_ticker(ticker)

        calls = {"n": 0}

        def fake_spot(_ticker):
            calls["n"] += 1
            return 123.45, None

        with patch(
            "infrastructure.data.yahoo_finance_client._provider_impls",
            return_value={"obtener_precio_actual": fake_spot},
        ):
            p1, e1 = facade.obtener_precio_actual(ticker)
            p2, e2 = facade.obtener_precio_actual(ticker)

        self.assertIsNone(e1)
        self.assertIsNone(e2)
        self.assertEqual(p1, p2)
        self.assertEqual(calls["n"], 1)

    def test_cache_key_prefixes_are_standardized(self):
        provider = facade.get_active_provider()
        version = facade._cache_version()
        self.assertEqual(
            facade._cache_key_spot("SPY"),
            f"market:{version}:{provider}:price:SPY",
        )
        self.assertEqual(
            facade._cache_key_dates("SPY"),
            f"market:{version}:{provider}:exp:SPY",
        )
        self.assertEqual(
            facade._cache_key_chain("SPY", "2026-12-18"),
            f"market:{version}:{provider}:chain:SPY:2026-12-18",
        )

    def test_stale_chain_returns_cached_and_requests_revalidate(self):
        ticker = "TSTSTALE"
        exp = "2099-12-18"
        facade.limpiar_cache_ticker(ticker)

        calls_df = pd.DataFrame(
            [{"strike": 100.0, "lastPrice": 1.0, "bid": 0.9, "ask": 1.1, "volume": 10, "openInterest": 20, "impliedVolatility": 0.2}]
        )
        payload = {"calls": calls_df, "puts": calls_df.copy()}
        facade.cache_chain(ticker, exp, payload, ttl_seconds=240)

        # Fuerza stale manipulando metadata
        key = facade._meta_key("chain", ticker, exp)
        facade._cache.set(key, {"ts": 0}, ttl=3600)

        with patch("infrastructure.data.yahoo_finance_client._request_snapshot_revalidate") as reval:
            out = facade.get_cached_chain(ticker, exp)

        self.assertIsNotNone(out)
        self.assertIn("calls", out)
        self.assertIn("puts", out)
        reval.assert_called_once()


if __name__ == "__main__":
    unittest.main()
