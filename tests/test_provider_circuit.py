import unittest

from infrastructure.data.provider_runtime import ProviderCircuitBreaker


class TestProviderCircuit(unittest.TestCase):
    def test_circuit_opens_after_threshold(self):
        c = ProviderCircuitBreaker()
        c._failure_threshold = 2
        c.record_failure()
        c.record_failure()
        snap = c.snapshot()
        self.assertEqual(snap["state"], "open")

    def test_circuit_closes_on_success(self):
        c = ProviderCircuitBreaker()
        c._failure_threshold = 1
        c.record_failure()
        self.assertEqual(c.snapshot()["state"], "open")
        c._opened_at_ts = 0
        c.allow_request()
        c.record_success()
        self.assertEqual(c.snapshot()["state"], "closed")


if __name__ == "__main__":
    unittest.main()
