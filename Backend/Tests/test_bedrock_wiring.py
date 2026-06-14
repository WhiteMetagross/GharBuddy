"""
Wiring tests for BedrockService generation methods.
Tasks 5.1 and 5.2 — Requirements: 4.1, 4.2, 4.3, 6.1, 6.2, 6.3
"""
import json
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock

import Backend.Config.AppConfig as cfg_mod
from Backend.Services.BedrockService import BedrockService


def _json_body(data: dict) -> dict:
    """Return a response dict whose 'body' is a readable BytesIO of JSON."""
    return {
        "body": BytesIO(json.dumps(data).encode()),
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


class TestGenerationMethodsUseInvokeWithRetry(unittest.TestCase):
    """Task 5.1: Each generation method must call _invokeWithRetry, not client.invoke_model directly."""

    def test_generate_reasoning_uses_invoke_with_retry(self):
        """generateReasoning calls _invokeWithRetry in non-mock mode (Requirement 4.1)."""
        reasoning_response = {
            "shouldExecute": True,
            "shouldSuggest": False,
            "actionId": "turnOnGeyser",
            "targetDevice": "geyser",
            "deviceCommand": "ON",
            "explanationEnglish": "Test",
            "explanationHindi": "Test",
            "estimatedSavingsWh": 100,
        }
        bedrock_response = _json_body({"content": [{"text": json.dumps(reasoning_response)}]})

        svc = BedrockService.__new__(BedrockService)
        svc.client = MagicMock()  # non-None client

        context = {
            "ragContext": [],
            "predictedActionDetails": {
                "predictedAction": "turnOnGeyser",
                "targetDevice": "geyser",
                "deviceCommand": "ON",
                "confidence": 0.9,
                "reason": "morning flush",
            },
        }

        with patch.object(cfg_mod.AppConfig, "mockMode", False), \
             patch.object(svc, "_invokeWithRetry", return_value=bedrock_response) as mock_retry:
            svc.generateReasoning(context)
            mock_retry.assert_called_once()
            svc.client.invoke_model.assert_not_called()

    def test_generate_preference_rule_uses_invoke_with_retry(self):
        """generatePreferenceRule calls _invokeWithRetry in non-mock mode (Requirement 4.2)."""
        rule_response = _json_body({"content": [{"text": "Never turn on Geyser."}]})

        svc = BedrockService.__new__(BedrockService)
        svc.client = MagicMock()

        with patch.object(cfg_mod.AppConfig, "mockMode", False), \
             patch.object(svc, "_invokeWithRetry", return_value=rule_response) as mock_retry:
            svc.generatePreferenceRule("turnOnGeyser", "06:15:00", "GRID")
            mock_retry.assert_called_once()
            svc.client.invoke_model.assert_not_called()

    def test_generate_consolidated_rule_uses_invoke_with_retry(self):
        """generateConsolidatedRule calls _invokeWithRetry in non-mock mode (Requirement 4.3)."""
        consolidated_response = _json_body({"content": [{"text": "Never run motor."}]})

        svc = BedrockService.__new__(BedrockService)
        svc.client = MagicMock()

        with patch.object(cfg_mod.AppConfig, "mockMode", False), \
             patch.object(svc, "_invokeWithRetry", return_value=consolidated_response) as mock_retry:
            svc.generateConsolidatedRule("Do not run motor at 07:00", "Do not run motor at 08:00")
            mock_retry.assert_called_once()
            svc.client.invoke_model.assert_not_called()

    def test_no_invoke_with_retry_when_client_is_none(self):
        """When self.client is None, _invokeWithRetry must never be called (Requirement 6.2)."""
        svc = BedrockService.__new__(BedrockService)
        svc.client = None

        with patch.object(BedrockService, "_invokeWithRetry",
                          side_effect=AssertionError("should not be called")) as mock_retry:
            svc.generateReasoning({})
            svc.generatePreferenceRule("turnOnGeyser", "06:00:00", "GRID")
            svc.generateConsolidatedRule("rule A", "rule B")

        mock_retry.assert_not_called()


class TestMockModeIsolation(unittest.TestCase):
    """Task 5.2: With mockMode=True, _invokeWithRetry must never be invoked (Requirement 6.1)."""

    def test_mock_mode_reasoning_returns_mock_without_invoke_with_retry(self):
        """generateReasoning returns mock output without calling _invokeWithRetry when mockMode=True."""
        svc = BedrockService.__new__(BedrockService)
        svc.client = None  # mockMode always leaves client=None

        with patch.object(cfg_mod.AppConfig, "mockMode", True), \
             patch.object(BedrockService, "_invokeWithRetry",
                          side_effect=AssertionError("_invokeWithRetry called in mock mode")) as mock_retry:
            result = svc.generateReasoning({})
            mock_retry.assert_not_called()

        self.assertIn("shouldExecute", result)

    def test_mock_mode_preference_rule_no_invoke_with_retry(self):
        """generatePreferenceRule works without _invokeWithRetry when mockMode=True."""
        svc = BedrockService.__new__(BedrockService)
        svc.client = None

        with patch.object(cfg_mod.AppConfig, "mockMode", True), \
             patch.object(BedrockService, "_invokeWithRetry",
                          side_effect=AssertionError("_invokeWithRetry called in mock mode")) as mock_retry:
            result = svc.generatePreferenceRule("turnOnGeyser", "06:00:00", "GRID")
            mock_retry.assert_not_called()

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_mock_mode_consolidated_rule_no_invoke_with_retry(self):
        """generateConsolidatedRule works without _invokeWithRetry when mockMode=True."""
        svc = BedrockService.__new__(BedrockService)
        svc.client = None

        with patch.object(cfg_mod.AppConfig, "mockMode", True), \
             patch.object(BedrockService, "_invokeWithRetry",
                          side_effect=AssertionError("_invokeWithRetry called in mock mode")) as mock_retry:
            result = svc.generateConsolidatedRule("rule A", "rule B")
            mock_retry.assert_not_called()

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
