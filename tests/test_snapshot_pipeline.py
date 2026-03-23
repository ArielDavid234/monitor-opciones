import time
import unittest

from infrastructure.data.snapshot_pipeline import SnapshotScheduler


class TestSnapshotPipeline(unittest.TestCase):
    def test_register_tickers_with_priority(self):
        scheduler = SnapshotScheduler()
        scheduler.register_tickers(["SPY", "QQQ"], priority="hot", immediate=True)

        self.assertIn("SPY", scheduler._tasks)
        self.assertEqual(scheduler._tasks["SPY"].priority, "hot")
        self.assertIn("QQQ", scheduler._tasks)

    def test_request_revalidate_immediate(self):
        scheduler = SnapshotScheduler()
        scheduler.register_tickers(["AAPL"], priority="normal", immediate=False)
        scheduler.request_revalidate("AAPL", reason="stale", priority="hot", immediate=True)

        task = scheduler._tasks["AAPL"]
        self.assertEqual(task.priority, "hot")
        self.assertLessEqual(task.next_run_ts, time.time() + 1.0)


if __name__ == "__main__":
    unittest.main()
