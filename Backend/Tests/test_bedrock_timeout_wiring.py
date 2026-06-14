"""
Unit tests for boto3 client timeout wiring in BedrockService.initBedrockClient().
Task 2.1 — Requirements: 2.1, 2.2
"""
import unittest
from unittest.mock import patch, MagicMock
from botocore.config import Config

import Backend.Config.AppConfig as cfg_mod


class TestInitBedrockClientTimeout(unittest.TestCase):
    """Verifies that initBedrockClient passes correct Config timeouts to boto3 (Requirement 2.1)."""

    def test_boto3_called_with_config_timeouts(self):
        """boto3.client must receive a Config with the correct connect/read timeouts."""
        mock_client_instance = MagicMock()

        # initBedrockClient does `import boto3` locally; patch boto3.client at module level.
        with patch.object(cfg_mod.AppConfig, "mockMode", False), \
             patch.object(cfg_mod.AppConfig, "bedrockConnectTimeoutSeconds", 5), \
             patch.object(cfg_mod.AppConfig, "bedrockReadTimeoutSeconds", 30), \
             patch("boto3.client", return_value=mock_client_instance) as mock_boto3_client:

            from Backend.Services.BedrockService import BedrockService
            svc = BedrockService.__new__(BedrockService)
            svc.client = None
            svc.initBedrockClient()

        self.assertTrue(mock_boto3_client.called, "boto3.client should have been called")
        _, kwargs = mock_boto3_client.call_args
        config_arg = kwargs.get("config")
        self.assertIsNotNone(config_arg, "boto3.client must receive a 'config' keyword argument")
        self.assertIsInstance(config_arg, Config)
        self.assertEqual(config_arg.connect_timeout, 5)
        self.assertEqual(config_arg.read_timeout, 30)

    def test_retries_disabled_in_config(self):
        """Config must set retries max_attempts=0 to disable SDK retries."""
        mock_client_instance = MagicMock()

        with patch.object(cfg_mod.AppConfig, "mockMode", False), \
             patch("boto3.client", return_value=mock_client_instance) as mock_boto3_client:

            from Backend.Services.BedrockService import BedrockService
            svc = BedrockService.__new__(BedrockService)
            svc.client = None
            svc.initBedrockClient()

        self.assertTrue(mock_boto3_client.called)
        _, kwargs = mock_boto3_client.call_args
        config_arg = kwargs.get("config")
        self.assertIsNotNone(config_arg)
        retries_cfg = config_arg._user_provided_options.get("retries", {})
        self.assertEqual(retries_cfg.get("max_attempts"), 0)

    def test_mock_mode_no_client_created(self):
        """When mockMode=True, self.client should remain None (Requirement 2.2)."""
        with patch.object(cfg_mod.AppConfig, "mockMode", True):
            from Backend.Services.BedrockService import BedrockService
            svc = BedrockService.__new__(BedrockService)
            svc.client = None
            svc.initBedrockClient()
            self.assertIsNone(svc.client)


if __name__ == "__main__":
    unittest.main()
