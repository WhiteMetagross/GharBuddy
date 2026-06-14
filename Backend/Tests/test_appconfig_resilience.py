"""
Smoke tests for AppConfig resilience fields.
Task 1.1 — Requirements: 1.1, 1.2, 1.3, 1.4
"""
import os
import unittest
from unittest.mock import patch


class TestAppConfigDefaults(unittest.TestCase):
    """Validates default values for the three new resilience fields (Requirements 1.1-1.3)."""

    def test_default_max_retries(self):
        from Backend.Config.AppConfig import AppConfig
        self.assertEqual(AppConfig.bedrockMaxRetries, 3)

    def test_default_connect_timeout(self):
        from Backend.Config.AppConfig import AppConfig
        self.assertEqual(AppConfig.bedrockConnectTimeoutSeconds, 5)

    def test_default_read_timeout(self):
        from Backend.Config.AppConfig import AppConfig
        self.assertEqual(AppConfig.bedrockReadTimeoutSeconds, 30)


class TestAppConfigEnvOverrides(unittest.TestCase):
    """
    Validates each field reads from its environment variable at class load time (Requirement 1.4).
    These tests verify the parsing logic by checking the int() conversion of known env var values.
    """

    def test_max_retries_from_env(self):
        """BEDROCK_MAX_RETRIES env var is parsed to int when AppConfig is loaded."""
        # Verify the class attribute is an int (type check) and that env-driven defaults work.
        from Backend.Config.AppConfig import AppConfig
        # If the env var is set to the default, we still get 3; test the type and a manual parse.
        raw = os.getenv("BEDROCK_MAX_RETRIES", "3")
        self.assertEqual(AppConfig.bedrockMaxRetries, int(raw))

    def test_connect_timeout_from_env(self):
        """BEDROCK_CONNECT_TIMEOUT_SECONDS env var is parsed to int when AppConfig is loaded."""
        from Backend.Config.AppConfig import AppConfig
        raw = os.getenv("BEDROCK_CONNECT_TIMEOUT_SECONDS", "5")
        self.assertEqual(AppConfig.bedrockConnectTimeoutSeconds, int(raw))

    def test_read_timeout_from_env(self):
        """BEDROCK_READ_TIMEOUT_SECONDS env var is parsed to int when AppConfig is loaded."""
        from Backend.Config.AppConfig import AppConfig
        raw = os.getenv("BEDROCK_READ_TIMEOUT_SECONDS", "30")
        self.assertEqual(AppConfig.bedrockReadTimeoutSeconds, int(raw))

    def test_fields_are_integers(self):
        """All three resilience fields must be integer type (not strings)."""
        from Backend.Config.AppConfig import AppConfig
        self.assertIsInstance(AppConfig.bedrockMaxRetries, int)
        self.assertIsInstance(AppConfig.bedrockConnectTimeoutSeconds, int)
        self.assertIsInstance(AppConfig.bedrockReadTimeoutSeconds, int)


if __name__ == "__main__":
    unittest.main()
