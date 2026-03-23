import unittest
from concurrent.futures import ThreadPoolExecutor
import time

from infrastructure.data.provider_runtime import (
    CrossUserTickerDedupe,
    SingleFlightGroup,
)


class TestProviderRuntimeStep7(unittest.TestCase):
    def test_cross_user_dedupe_detects_repeated_demand(self):
        dedupe = CrossUserTickerDedupe()
        first = dedupe.register_request("SPY")
        second = dedupe.register_request("SPY")

        self.assertFalse(first["dedupe_candidate"])
        self.assertTrue(second["dedupe_candidate"])
        self.assertTrue(dedupe.should_defer_live_fetch("SPY"))

    def test_single_flight_coalesces_calls(self):
        sf = SingleFlightGroup()
        counter = {"calls": 0}

        def run_once():
            def leader_fn():
                counter["calls"] += 1
                time.sleep(0.02)
                return "ok"

            return sf.do("chain:SPY:2026-01-16", leader_fn)

        with ThreadPoolExecutor(max_workers=8) as ex:
            out = list(ex.map(lambda _: run_once(), range(8)))

        self.assertEqual(set(out), {"ok"})
        self.assertEqual(counter["calls"], 1)


if __name__ == "__main__":
    unittest.main()
