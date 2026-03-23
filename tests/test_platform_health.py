import unittest

from infrastructure.platform.health import cache_healthcheck, global_health_status


class TestPlatformHealth(unittest.TestCase):
    def test_cache_healthcheck(self):
        out = cache_healthcheck()
        self.assertIn(out["status"], {"ok", "degraded", "down"})
        self.assertEqual(out["name"], "cache")

    def test_global_health(self):
        out = global_health_status()
        self.assertIn(out["overall"], {"ok", "degraded", "down"})
        self.assertIn("checks", out)
        self.assertEqual(len(out["checks"]), 3)


if __name__ == "__main__":
    unittest.main()
