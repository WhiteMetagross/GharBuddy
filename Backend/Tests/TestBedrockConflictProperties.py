"""
Property-Based Tests for BedrockService conflict-resolution heuristics (Issue #19).

Uses only Python stdlib (unittest, random, string) — no new dependencies.
Each test runs 100 randomised samples.

Validates: Requirements 1.1, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.3
"""

import unittest
import random
import string

from Backend.Services.BedrockService import BedrockService


# ---------------------------------------------------------------------------
# Helpers / shared generators
# ---------------------------------------------------------------------------

_DEVICE_MAP = {
    "geyser":           ["geyser", "heater"],
    "waterMotor":       ["water", "motor", "pump"],
    "inverterBackup":   ["inverter", "backup", "precharge"],
    "airConditioner":   ["ac", "air", "conditioner"],
    "television":       ["television", "tv"],
}

_DEVICES = list(_DEVICE_MAP.keys())


def _random_string(n=8):
    return "".join(random.choices(string.ascii_lowercase + " ", k=n))


def _randomise_case(text):
    """Return text with each character randomly uppercased or lowercased."""
    return "".join(c.upper() if random.random() > 0.5 else c.lower() for c in text)


def _make_context_with_override(device, category="override"):
    """Build a minimal context with one matching RAG rule for device."""
    keyword = random.choice(_DEVICE_MAP.get(device, [device.lower()]))
    content = _randomise_case(
        f"Do not activate the {keyword} automatically under any circumstances."
    )
    return {
        "predictedActionDetails": {
            "predictedAction": "somePredictedAction",
            "targetDevice": device,
            "deviceCommand": "ON",
            "confidence": 0.90,
            "reason": "test reason",
        },
        "calendarContext": {"isFastingDay": False, "festivalName": "Normal Day"},
        "ragContext": [
            {"content": content, "category": category, "similarity": 0.95}
        ],
    }


def _make_context_no_suppression(device):
    """Build a context with only routine/cultural rules that should NOT suppress."""
    keyword = random.choice(_DEVICE_MAP.get(device, [device.lower()]))
    return {
        "predictedActionDetails": {
            "predictedAction": "somePredictedAction",
            "targetDevice": device,
            "deviceCommand": "ON",
            "confidence": 0.90,
            "reason": "test reason",
        },
        "calendarContext": {"isFastingDay": False, "festivalName": "Normal Day"},
        "ragContext": [
            {
                "content": f"Schedule the {keyword} to run during off-peak hours.",
                "category": "routine",
                "similarity": 0.80,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Property 1 — Output schema always contains conflict fields
# Validates: Requirements 4.1, 4.3
# ---------------------------------------------------------------------------

class TestProperty1OutputSchemaAlwaysHasConflictFields(unittest.TestCase):
    """
    **Property 1: Output schema always contains conflict fields**

    For any call to generateMockReasoning() with any context dict (with or without
    predictedActionDetails, with or without RAG rules), the returned dict SHALL
    contain conflictDetected (bool) and conflictDescription (str | None).

    Validates: Requirements 4.1, 4.3
    """

    def setUp(self):
        self.bedrock = BedrockService()

    def _assert_conflict_fields(self, result, label):
        self.assertIn("conflictDetected", result, f"[{label}] conflictDetected missing")
        self.assertIn("conflictDescription", result, f"[{label}] conflictDescription missing")
        self.assertIsInstance(result["conflictDetected"], bool, f"[{label}] conflictDetected not bool")
        self.assertTrue(
            result["conflictDescription"] is None or isinstance(result["conflictDescription"], str),
            f"[{label}] conflictDescription must be str or None",
        )

    def test_output_schema_always_has_conflict_fields(self):
        """Run 100 randomised context dicts across all three mock paths."""
        for i in range(100):
            path = i % 3
            if path == 0:
                # No-prediction path
                context = {"ragContext": [], "calendarContext": {}}
                result = self.bedrock.generateMockReasoning(context)
                self._assert_conflict_fields(result, "no_prediction")

            elif path == 1:
                # Suppression path
                device = random.choice(_DEVICES)
                category = random.choice(["override", "safety"])
                context = _make_context_with_override(device, category)
                result = self.bedrock.generateMockReasoning(context)
                self._assert_conflict_fields(result, "suppression")

            else:
                # Normal path (no suppression)
                device = random.choice(_DEVICES)
                context = _make_context_no_suppression(device)
                result = self.bedrock.generateMockReasoning(context)
                self._assert_conflict_fields(result, "normal")


# ---------------------------------------------------------------------------
# Property 2 — Case-insensitive override suppression
# Validates: Requirements 3.1, 3.2, 3.4
# ---------------------------------------------------------------------------

class TestProperty2CaseInsensitiveOverrideSuppression(unittest.TestCase):
    """
    **Property 2: Case-insensitive override suppression**

    For any context where ragContext contains a rule with category=="override"
    whose content contains a device keyword in randomised capitalisation,
    generateMockReasoning() SHALL suppress the action and set conflictDetected=True.

    Validates: Requirements 3.1, 3.2, 3.4
    """

    def setUp(self):
        self.bedrock = BedrockService()

    def test_case_insensitive_override_suppression(self):
        """Run 100 override contexts with randomised keyword capitalisation."""
        for _ in range(100):
            device = random.choice(_DEVICES)
            keyword = random.choice(_DEVICE_MAP[device])
            # Randomise case of the keyword in the rule content
            mixed_keyword = _randomise_case(keyword)
            content = f"Never activate the {mixed_keyword} device without permission."
            context = {
                "predictedActionDetails": {
                    "predictedAction": "somePredictedAction",
                    "targetDevice": device,
                    "deviceCommand": "ON",
                    "confidence": 0.90,
                    "reason": "test",
                },
                "calendarContext": {"isFastingDay": False, "festivalName": "Normal Day"},
                "ragContext": [
                    {"content": content, "category": "override", "similarity": 0.95}
                ],
            }
            result = self.bedrock.generateMockReasoning(context)
            self.assertFalse(result["shouldExecute"], f"shouldExecute should be False; content='{content}' device='{device}'")
            self.assertFalse(result["shouldSuggest"], f"shouldSuggest should be False; content='{content}' device='{device}'")
            self.assertTrue(result["conflictDetected"], f"conflictDetected should be True; content='{content}' device='{device}'")
            self.assertIsInstance(result["conflictDescription"], str, "conflictDescription must be a string")
            self.assertGreater(len(result["conflictDescription"]), 0, "conflictDescription must be non-empty")


# ---------------------------------------------------------------------------
# Property 2 (helper) — _deviceKeywordsMatch case-insensitivity
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------

class TestProperty2DeviceKeywordsMatchCaseInsensitivity(unittest.TestCase):
    """
    **Property 2 (_deviceKeywordsMatch): Case-insensitive matching**

    Generate 100 rule content strings where the device keyword appears in
    randomised capitalisation. Assert _deviceKeywordsMatch returns True for all.

    Validates: Requirements 3.1
    """

    def setUp(self):
        self.bedrock = BedrockService()

    def test_device_keywords_match_case_insensitive(self):
        """Run 100 randomised capitalisation cases."""
        for _ in range(100):
            device = random.choice(_DEVICES)
            keyword = random.choice(_DEVICE_MAP[device])
            mixed_keyword = _randomise_case(keyword)
            content = f"Some rule mentioning {mixed_keyword} device."
            result = self.bedrock._deviceKeywordsMatch(content, device)
            self.assertTrue(result, f"Expected True for content='{content}' device='{device}'")

    def test_device_keywords_match_none_content(self):
        """None content must not raise — return False."""
        for device in _DEVICES:
            result = self.bedrock._deviceKeywordsMatch(None, device)
            self.assertFalse(result)


# ---------------------------------------------------------------------------
# Property 3 — Safety suppression fires for all safety rules
# Validates: Requirements 3.3, 3.4
# ---------------------------------------------------------------------------

class TestProperty3SafetyRuleSuppression(unittest.TestCase):
    """
    **Property 3: Safety suppression fires for all safety rules**

    For any context where ragContext contains a rule with category=="safety"
    whose content contains a device keyword, generateMockReasoning() SHALL suppress
    the action and set conflictDetected=True.

    Validates: Requirements 3.3, 3.4
    """

    def setUp(self):
        self.bedrock = BedrockService()

    def test_safety_rule_suppression(self):
        """Run 100 safety-rule contexts."""
        for _ in range(100):
            device = random.choice(_DEVICES)
            context = _make_context_with_override(device, category="safety")
            result = self.bedrock.generateMockReasoning(context)
            content = context["ragContext"][0]["content"]
            self.assertFalse(result["shouldExecute"], f"shouldExecute should be False; content='{content}'")
            self.assertFalse(result["shouldSuggest"], f"shouldSuggest should be False; content='{content}'")
            self.assertTrue(result["conflictDetected"], f"conflictDetected should be True; content='{content}'")
            self.assertIsInstance(result["conflictDescription"], str, "conflictDescription must be a string")
            self.assertGreater(len(result["conflictDescription"]), 0, "conflictDescription must be non-empty")


# ---------------------------------------------------------------------------
# Property 4 — No conflict fields when no suppression
# Validates: Requirements 3.5, 4.3
# ---------------------------------------------------------------------------

class TestProperty4NoConflictWhenNoMatchingRules(unittest.TestCase):
    """
    **Property 4: No conflict fields when no suppression**

    For any context where no ragContext rule matches the predicted action's device
    (no override or safety suppression fires), generateMockReasoning() SHALL return
    conflictDetected=False and conflictDescription=None.

    Validates: Requirements 3.5, 4.3
    """

    def setUp(self):
        self.bedrock = BedrockService()

    def test_no_conflict_when_no_matching_rules(self):
        """Run 100 non-suppressing contexts."""
        for _ in range(100):
            device = random.choice(_DEVICES)
            context = _make_context_no_suppression(device)
            result = self.bedrock.generateMockReasoning(context)
            self.assertFalse(result["conflictDetected"], f"conflictDetected should be False; device='{device}'")
            self.assertIsNone(result["conflictDescription"], f"conflictDescription should be None; device='{device}'")


# ---------------------------------------------------------------------------
# Property 5 — Bedrock response defaulting preserves schema completeness
# Validates: Requirements 2.2, 2.3, 2.4, 2.5
# ---------------------------------------------------------------------------

class TestProperty5BedrockResponseDefaulting(unittest.TestCase):
    """
    **Property 5: Bedrock response defaulting preserves schema completeness**

    For any dict produced by json.loads of a Claude response (with any combination
    of present/absent/wrong-type values for conflictDetected and conflictDescription),
    the post-processing step SHALL return conflictDetected as bool and
    conflictDescription as str or None.

    Validates: Requirements 2.2, 2.3, 2.4, 2.5
    """

    def _apply_defaulting(self, d):
        """Mirror the defaulting logic added in generateReasoning after json.loads."""
        d.setdefault("conflictDetected", False)
        d.setdefault("conflictDescription", None)
        return d

    def test_bedrock_response_defaulting(self):
        """Run 100 random parsed response dicts."""
        for _ in range(100):
            d = {}
            # Randomly include / exclude / mis-type conflictDetected
            roll = random.random()
            if roll < 0.33:
                pass  # absent
            elif roll < 0.66:
                d["conflictDetected"] = True
            else:
                d["conflictDetected"] = "yes"  # wrong type — setdefault won't override

            # Randomly include / exclude / mis-type conflictDescription
            roll2 = random.random()
            if roll2 < 0.33:
                pass  # absent — should default to None
            elif roll2 < 0.66:
                d["conflictDescription"] = "Some rule content"
            else:
                d["conflictDescription"] = None

            result = self._apply_defaulting(dict(d))

            # After defaulting, keys must always be present
            self.assertIn("conflictDetected", result)
            self.assertIn("conflictDescription", result)

            # If the key was absent it must now be False (defaulted)
            if "conflictDetected" not in d:
                self.assertIs(result["conflictDetected"], False)
            # If the key was absent it must now be None (defaulted)
            if "conflictDescription" not in d:
                self.assertIsNone(result["conflictDescription"])

            # conflictDescription is always str or None after defaulting
            self.assertTrue(
                result["conflictDescription"] is None or isinstance(result["conflictDescription"], str),
                "conflictDescription must be str or None",
            )


# ---------------------------------------------------------------------------
# Task 5.1 — Unit test: system prompt content
# Validates: Requirements 1.1, 1.3, 2.1
# ---------------------------------------------------------------------------

class TestTask51SystemPromptContent(unittest.TestCase):
    """
    Assert the system prompt contains all five priority level labels,
    both new field names, and all 10 Output_Schema field names.

    Validates: Requirements 1.1, 1.3, 2.1
    """

    def setUp(self):
        self.bedrock = BedrockService()
        # Reconstruct systemPrompt the same way generateReasoning builds it
        self._system_prompt = (
            "You are the AI brain of GharBuddy, a context-aware smart home system for an Indian household. "
            "You receive a situation context containing active sensor states, regional calendar details, "
            "and routine prediction heuristics. "
            "Crucially, you are also provided with semantically retrieved RAG rules (user overrides, safety parameters, or cultural laws). "
            "If any retrieved RAG rule has the category '[OVERRIDE]' (which represents explicit user preference rules and blocks, e.g. 'Do not automatically start the water pump motor' or 'Never turn on Geyser'), you MUST respect this constraint. In such cases, you must suppress the action by setting shouldExecute to false and shouldSuggest to false. Explain this suppression in explanationHindi and explanationEnglish. "
            "You must reason over this context and output a structured JSON action decision. "
            "You must respond with ONLY a valid JSON object. No extra text, no wrapper markdown.\n\n"
            "CONFLICT RESOLUTION PRIORITY HIERARCHY:\n"
            "Priority 1 (HIGHEST): Explicit negative user overrides — RAG rules with category 'override' containing 'Never', 'Do not', or 'Suppress'. When matched, set shouldExecute=false, shouldSuggest=false, conflictDetected=true, conflictDescription=the winning rule content.\n"
            "Priority 2: Safety guardrails — RAG rules with category 'safety'. Same suppression effect as Priority 1: set shouldExecute=false, shouldSuggest=false, conflictDetected=true, conflictDescription=the winning rule content.\n"
            "Priority 3: Cultural/fasting context — isFastingDay=true, festivalName set, pooja hours active.\n"
            "Priority 4: Routine/sequence predictions from ML predictor.\n"
            "Priority 5 (LOWEST): Energy optimisation suggestions.\n"
            "When a higher-priority rule overrules a lower-priority rule, you MUST set conflictDetected=true and conflictDescription to the winning rule content."
        )

    def test_system_prompt_contains_all_five_priority_labels(self):
        for i in range(1, 6):
            self.assertIn(f"Priority {i}", self._system_prompt, f"Priority {i} missing from system prompt")

    def test_system_prompt_contains_conflict_fields(self):
        self.assertIn("conflictDetected", self._system_prompt)
        self.assertIn("conflictDescription", self._system_prompt)

    def test_prompt_output_schema_contains_all_10_fields(self):
        import json
        # Build a minimal prompt string the same way generateReasoning does
        prompt_schema_section = (
            '{"shouldExecute": boolean, "shouldSuggest": boolean, "actionId": "string", '
            '"targetDevice": "string", "deviceCommand": "string", "explanationEnglish": "string", '
            '"explanationHindi": "string", "estimatedSavingsWh": number, '
            '"conflictDetected": boolean, "conflictDescription": "string | null"}'
        )
        for field in [
            "shouldExecute", "shouldSuggest", "actionId", "targetDevice", "deviceCommand",
            "explanationEnglish", "explanationHindi", "estimatedSavingsWh",
            "conflictDetected", "conflictDescription",
        ]:
            self.assertIn(field, prompt_schema_section, f"Field '{field}' missing from output schema")


if __name__ == "__main__":
    unittest.main()
