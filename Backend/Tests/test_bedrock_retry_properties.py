"""
Property-based tests for BedrockService._invokeWithRetry.
Tasks 3.1–3.5 and edge-case 3.6.

Feature: issue-9-bedrock-resilience
"""
import unittest
import logging
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError

from hypothesis import given, settings
import hypothesis.strategies as st

from Backend.Services.BedrockService import BedrockService, _BACKOFF_SEQUENCE, _RETRYABLE_CODES
from Backend.Config.AppConfig import AppConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_error(code: str) -> ClientError:
    """Create a botocore ClientError with the given error code."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "test"}},
        operation_name="InvokeModel",
    )


def _make_service_with_mock_client() -> BedrockService:
    """Create a BedrockService instance with a MagicMock client (bypasses real boto3 init)."""
    svc = BedrockService.__new__(BedrockService)
    svc.client = MagicMock()
    return svc


# ---------------------------------------------------------------------------
# Property 1 — Retry back-off sequence is respected
# Validates: Requirements 3.2, 3.5
# Feature: issue-9-bedrock-resilience, Property 1: retry backoff sequence is respected
# ---------------------------------------------------------------------------

class TestRetryBackoffSequence(unittest.TestCase):
    """Property 1: Retry back-off sequence is respected"""

    @given(st.integers(min_value=1, max_value=AppConfig.bedrockMaxRetries - 1))
    @settings(max_examples=50)
    def test_backoff_sequence_respected(self, k):
        """
        When invoke_model fails k times with ThrottlingException then succeeds,
        time.sleep must be called with BACKOFF_SEQUENCE[0:k] in order.
        **Validates: Requirements 3.2, 3.5**
        """
        # Feature: issue-9-bedrock-resilience, Property 1: retry backoff sequence is respected
        svc = _make_service_with_mock_client()
        success_response = {"body": MagicMock(), "usage": {"input_tokens": 10, "output_tokens": 5}}

        throttle = _make_client_error("ThrottlingException")
        side_effects = [throttle] * k + [success_response]
        svc.client.invoke_model.side_effect = side_effects

        with patch("Backend.Services.BedrockService.time.sleep") as mock_sleep:
            result = svc._invokeWithRetry(modelId="test-model", body="{}")

        self.assertIs(result, success_response)
        expected_sleep_calls = [call(_BACKOFF_SEQUENCE[i]) for i in range(k)]
        self.assertEqual(mock_sleep.call_args_list, expected_sleep_calls)


# ---------------------------------------------------------------------------
# Property 2 — Retries exhausted causes re-raise
# Validates: Requirements 3.3
# Feature: issue-9-bedrock-resilience, Property 2: retries exhausted causes re-raise
# ---------------------------------------------------------------------------

class TestRetriesExhausted(unittest.TestCase):
    """Property 2: Retries exhausted causes re-raise"""

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_reraises_after_exhausting_retries(self, max_retries):
        """
        When invoke_model always raises ThrottlingException, _invokeWithRetry must
        re-raise ClientError after exactly maxRetries calls.
        **Validates: Requirements 3.3**
        """
        # Feature: issue-9-bedrock-resilience, Property 2: retries exhausted causes re-raise
        svc = _make_service_with_mock_client()
        throttle = _make_client_error("ThrottlingException")
        svc.client.invoke_model.side_effect = throttle

        with patch("Backend.Services.BedrockService.time.sleep"):
            with self.assertRaises(ClientError):
                svc._invokeWithRetry(modelId="test-model", body="{}", maxRetries=max_retries)

        self.assertEqual(svc.client.invoke_model.call_count, max_retries)


# ---------------------------------------------------------------------------
# Property 3 — Non-retryable errors propagate immediately
# Validates: Requirements 3.4
# Feature: issue-9-bedrock-resilience, Property 3: non-retryable errors propagate immediately
# ---------------------------------------------------------------------------

_NON_RETRYABLE_CODES = [
    "AccessDeniedException",
    "ValidationException",
    "ResourceNotFoundException",
    "InternalServerError",
    "ModelNotReadyException",
    "SomeOtherError",
]


class TestNonRetryableImmediateReraise(unittest.TestCase):
    """Property 3: Non-retryable errors propagate immediately"""

    @given(st.sampled_from(_NON_RETRYABLE_CODES))
    @settings(max_examples=50)
    def test_non_retryable_client_error_immediate_reraise(self, error_code):
        """
        A ClientError with a non-retryable code must be re-raised immediately
        after exactly 1 invoke_model call with zero sleeps.
        **Validates: Requirements 3.4**
        """
        # Feature: issue-9-bedrock-resilience, Property 3: non-retryable errors propagate immediately
        assert error_code not in _RETRYABLE_CODES, f"{error_code} must not be retryable for this test"

        svc = _make_service_with_mock_client()
        error = _make_client_error(error_code)
        svc.client.invoke_model.side_effect = error

        with patch("Backend.Services.BedrockService.time.sleep") as mock_sleep:
            with self.assertRaises(ClientError):
                svc._invokeWithRetry(modelId="test-model", body="{}")

        self.assertEqual(svc.client.invoke_model.call_count, 1)
        mock_sleep.assert_not_called()

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=30)
    def test_non_client_error_immediate_reraise(self, message):
        """
        Any non-ClientError exception (e.g. ValueError) must propagate immediately
        after exactly 1 invoke_model call with zero sleeps.
        **Validates: Requirements 3.4**
        """
        # Feature: issue-9-bedrock-resilience, Property 3: non-retryable errors propagate immediately
        svc = _make_service_with_mock_client()
        svc.client.invoke_model.side_effect = ValueError(message)

        with patch("Backend.Services.BedrockService.time.sleep") as mock_sleep:
            with self.assertRaises(ValueError):
                svc._invokeWithRetry(modelId="test-model", body="{}")

        self.assertEqual(svc.client.invoke_model.call_count, 1)
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Property 4 — Successful response is returned unchanged
# Validates: Requirements 3.5
# Feature: issue-9-bedrock-resilience, Property 4: successful response is returned unchanged
# ---------------------------------------------------------------------------

class TestResponsePassThrough(unittest.TestCase):
    """Property 4: Successful response is returned unchanged"""

    @given(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=20), max_size=10))
    @settings(max_examples=100)
    def test_response_returned_unchanged(self, response_dict):
        """
        _invokeWithRetry must return the identical response object from invoke_model.
        **Validates: Requirements 3.5**
        """
        # Feature: issue-9-bedrock-resilience, Property 4: successful response is returned unchanged
        svc = _make_service_with_mock_client()
        svc.client.invoke_model.return_value = response_dict

        with patch.object(svc, "_logTokenUsage"):  # isolate; tested separately
            result = svc._invokeWithRetry(modelId="test-model", body="{}")

        self.assertIs(result, response_dict)


# ---------------------------------------------------------------------------
# Property 5 — Token usage log contains model ID and token counts
# Validates: Requirements 5.1, 5.2
# Feature: issue-9-bedrock-resilience, Property 5: token usage log contains model ID and token counts
# ---------------------------------------------------------------------------

class TestTokenUsageLogContent(unittest.TestCase):
    """Property 5: Token usage log contains model ID and token counts"""

    @given(
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_.")),
        st.integers(min_value=0, max_value=100_000),
        st.integers(min_value=0, max_value=100_000),
    )
    @settings(max_examples=100)
    def test_log_contains_model_id_and_token_counts(self, model_id, input_tokens, output_tokens):
        """
        The INFO log emitted by _logTokenUsage must contain modelId, inputTokens, and outputTokens.
        **Validates: Requirements 5.1, 5.2**
        """
        # Feature: issue-9-bedrock-resilience, Property 5: token usage log contains model ID and token counts
        from Backend.Services import BedrockService as bedrock_module

        svc = _make_service_with_mock_client()
        response = {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        }

        with patch.object(bedrock_module._logger, "info") as mock_info:
            svc._logTokenUsage(response, model_id)

        mock_info.assert_called_once()
        log_args = mock_info.call_args
        # Reconstruct the formatted log message
        fmt = log_args[0][0]
        params = log_args[0][1:]
        formatted = fmt % params

        self.assertIn(model_id, formatted)
        self.assertIn(str(input_tokens), formatted)
        self.assertIn(str(output_tokens), formatted)


# ---------------------------------------------------------------------------
# Edge-case test 3.6 — Missing token usage fields triggers WARNING, no exception
# Requirements: 5.3
# ---------------------------------------------------------------------------

class TestMissingTokenUsageFields(unittest.TestCase):
    """Edge-case 3.6: Missing token usage fields in response."""

    def test_missing_usage_logs_warning_no_exception(self):
        """
        When the response has no 'usage' key and no ResponseMetadata usage headers,
        _logTokenUsage must log a WARNING and return without raising.
        Requirements: 5.3
        """
        from Backend.Services import BedrockService as bedrock_module

        svc = _make_service_with_mock_client()
        response = {}  # no usage fields at all

        with patch.object(bedrock_module._logger, "warning") as mock_warning, \
             patch.object(bedrock_module._logger, "info") as mock_info:
            # Must not raise
            svc._logTokenUsage(response, "some-model")

        mock_warning.assert_called_once()
        mock_info.assert_not_called()
        # Warning message should reference the model id
        warning_args = mock_warning.call_args[0]
        self.assertIn("some-model", warning_args[1])

    def test_partial_usage_logs_warning(self):
        """
        When only one of input_tokens / output_tokens is present, a WARNING is emitted.
        Requirements: 5.3
        """
        from Backend.Services import BedrockService as bedrock_module

        svc = _make_service_with_mock_client()
        response = {"usage": {"input_tokens": 42}}  # output_tokens missing

        with patch.object(bedrock_module._logger, "warning") as mock_warning, \
             patch.object(bedrock_module._logger, "info") as mock_info:
            svc._logTokenUsage(response, "partial-model")

        mock_warning.assert_called_once()
        mock_info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
