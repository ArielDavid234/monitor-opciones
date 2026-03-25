import os
import unittest
from unittest.mock import patch

from infrastructure.platform.security import anonymize_user_id, sanitize_error_for_user, validate_startup_secrets


class TestPlatformSecurity(unittest.TestCase):
    def test_anonymize_user_id(self):
        out = anonymize_user_id("123e4567-e89b-12d3-a456-426614174000")
        self.assertTrue(out.startswith("anon:"))
        self.assertGreater(len(out), 8)

    def test_sanitize_error_for_user(self):
        self.assertIn("cuota", sanitize_error_for_user("HTTP 429 too many requests"))
        self.assertIn("servicio", sanitize_error_for_user("timeout from upstream"))

    def test_validate_startup_secrets(self):
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "",
                "SUPABASE_ANON_KEY": "",
            },
            clear=False,
        ):
            errors = validate_startup_secrets()

        self.assertTrue(any("SUPABASE_URL" in e for e in errors))
        self.assertTrue(any("SUPABASE_ANON_KEY" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
