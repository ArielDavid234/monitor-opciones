import unittest

from infrastructure.data.provider_runtime import BudgetManager


class TestProviderRuntime(unittest.TestCase):
    def test_background_quota_blocks_non_critical(self):
        budget = BudgetManager(
            total_per_minute=5,
            reserved_live_scanning=4,
            background_quota=1,
            high_watermark=0.95,
        )

        d1 = budget.acquire(endpoint="tcbbo:SPY", ticker="SPY", critical=False, channel="background")
        d2 = budget.acquire(endpoint="tcbbo:SPY", ticker="SPY", critical=False, channel="background")

        self.assertTrue(d1.allowed)
        self.assertFalse(d2.allowed)
        self.assertEqual(d2.reason, "background_quota")

    def test_live_scanning_is_not_blocked_by_background_quota(self):
        budget = BudgetManager(
            total_per_minute=4,
            reserved_live_scanning=3,
            background_quota=1,
            high_watermark=0.95,
        )
        budget.acquire(endpoint="definition:SPY", ticker="SPY", critical=False, channel="background")

        live = budget.acquire(endpoint="definition:SPY", ticker="SPY", critical=True, channel="live_scanning")
        self.assertTrue(live.allowed)


if __name__ == "__main__":
    unittest.main()
