import json
import time
import logging
import botocore.exceptions
from botocore.config import Config
from Backend.Config.AppConfig import AppConfig

_RETRYABLE_CODES = frozenset({"ThrottlingException", "ServiceUnavailableException", "TooManyRequestsException"})
_BACKOFF_SEQUENCE = [1, 2, 4]
_logger = logging.getLogger(__name__)


class BedrockService:
    def __init__(self):
        self.client = None
        self.initBedrockClient()

    def initBedrockClient(self):
        if not AppConfig.mockMode:
            try:
                import boto3
                config = Config(
                    connect_timeout=AppConfig.bedrockConnectTimeoutSeconds,
                    read_timeout=AppConfig.bedrockReadTimeoutSeconds,
                    retries={"max_attempts": 0},
                )
                self.client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=AppConfig.awsRegion,
                    config=config,
                )
                print("AWS Bedrock client initialized successfully.")
            except Exception as e:
                print(f"Failed to initialize AWS Bedrock client: {e}. Falling back to mock Bedrock mode.")

    def _logTokenUsage(self, response, modelId):
        """Log input/output token counts from a successful Bedrock response."""
        input_tokens = None
        output_tokens = None

        # Try parsed response body usage dict (Claude Bedrock API shape)
        usage = None
        if isinstance(response, dict):
            usage = response.get("usage")
        if usage and isinstance(usage, dict):
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")

        # Fallback: ResponseMetadata headers
        if input_tokens is None or output_tokens is None:
            metadata = response.get("ResponseMetadata", {}) if isinstance(response, dict) else {}
            headers = metadata.get("HTTPHeaders", {})
            if input_tokens is None:
                input_tokens = headers.get("x-amzn-bedrock-input-token-count")
            if output_tokens is None:
                output_tokens = headers.get("x-amzn-bedrock-output-token-count")

        if input_tokens is None or output_tokens is None:
            _logger.warning("Bedrock response missing token usage fields for model %s", modelId)
            return

        _logger.info(
            "Bedrock token usage | model=%s inputTokens=%s outputTokens=%s",
            modelId,
            input_tokens,
            output_tokens,
        )

    def _invokeWithRetry(self, modelId, body, maxRetries=None):
        """Invoke Bedrock model with exponential back-off retry for transient errors."""
        if maxRetries is None:
            maxRetries = AppConfig.bedrockMaxRetries

        lastException = None
        for attempt in range(maxRetries):
            try:
                response = self.client.invoke_model(modelId=modelId, body=body)
                self._logTokenUsage(response, modelId)
                return response
            except botocore.exceptions.ClientError as e:
                code = e.response["Error"]["Code"]
                if code in _RETRYABLE_CODES:
                    lastException = e
                    if attempt < maxRetries - 1:
                        backoff_idx = min(attempt, len(_BACKOFF_SEQUENCE) - 1)
                        time.sleep(_BACKOFF_SEQUENCE[backoff_idx])
                    # loop continues; after exhausting all attempts we re-raise below
                else:
                    raise  # non-retryable ClientError: immediate re-raise
            except Exception:
                raise  # non-ClientError: immediate re-raise
        raise lastException

    def _deviceKeywordsMatch(self, rule_content, target_device):
        """
        Returns True if any keyword token for target_device appears as a substring
        in the lowercased rule_content. Case-insensitive. Handles None content gracefully.
        """
        content_lower = (rule_content or "").lower()
        device_lower = (target_device or "").lower()

        # Build keyword token set from known synonym map
        SYNONYM_MAP = {
            "geyser":           ["geyser", "heater"],
            "watermotor":       ["water", "motor", "pump", "watermotor"],
            "inverterbackup":   ["inverter", "backup", "precharge"],
            "airconditioner":   ["ac", "air", "conditioner"],
            "television":       ["television", "tv"],
        }

        tokens = set()
        if device_lower in SYNONYM_MAP:
            tokens.update(SYNONYM_MAP[device_lower])
        else:
            # General fallback: split camelCase into lowercase tokens
            import re
            parts = re.sub(r'([A-Z])', r' \1', target_device or "").split()
            tokens.update(p.lower() for p in parts if p)
            tokens.add(device_lower)

        return any(token in content_lower for token in tokens)

    def generateReasoning(self, contextData):
        """
        Receives context data (dictionary) and queries Bedrock Claude or returns a mock reasoning packet.
        """
        if AppConfig.mockMode or not self.client:
            return self.generateMockReasoning(contextData)

        # Extract semantic rules retrieved via RAG Vector search
        ragList = contextData.get("ragContext", [])
        ragContextText = "\n".join([
            f"- [{r.get('category').upper()}] {r.get('content')} (Similarity: {r.get('similarity'):.2f})"
            for r in ragList
        ])

        systemPrompt = (
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

        prompt = f"""
        Situation Context:
        {json.dumps(contextData, indent=2)}

        Retrieved Grounding RAG Context:
        {ragContextText}

        You must respond with ONLY a valid JSON object matching this exact schema:
        {{
          "shouldExecute": boolean,
          "shouldSuggest": boolean,
          "actionId": "string",
          "targetDevice": "string",
          "deviceCommand": "string",
          "explanationEnglish": "string",
          "explanationHindi": "string",
          "estimatedSavingsWh": number,
          "conflictDetected": boolean,
          "conflictDescription": "string | null"
        }}
        """

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "system": systemPrompt,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2
            })

            response = self._invokeWithRetry(
                modelId=AppConfig.bedrockModelId,
                body=body,
            )

            responseBody = json.loads(response.get("body").read())
            rawOutputText = responseBody["content"][0]["text"]
            
            parsedOutput = json.loads(rawOutputText.strip())
            parsedOutput.setdefault("conflictDetected", False)
            parsedOutput.setdefault("conflictDescription", None)
            return parsedOutput
            
        except Exception as e:
            print(f"Error calling AWS Bedrock: {e}. Falling back to mock reasoning.")
            return self.generateMockReasoning(contextData)

    def generateMockReasoning(self, context):
        """
        Generates realistic Bedrock output augmented by the retrieved RAG context.
        """
        predicted = context.get("predictedActionDetails")
        calendar = context.get("calendarContext", {})
        isFasting = calendar.get("isFastingDay", False)
        festivalName = calendar.get("festivalName", "")
        ragContext = context.get("ragContext", [])

        if not predicted:
            return {
                "shouldExecute": False,
                "shouldSuggest": False,
                "actionId": "none",
                "targetDevice": "",
                "deviceCommand": "",
                "explanationEnglish": "No proactive actions predicted for the current context.",
                "explanationHindi": "वर्तमान संदर्भ के लिए कोई पूर्व-सक्रिय कार्रवाई नहीं मिली।",
                "estimatedSavingsWh": 0,
                "retrievedRagRules": ragContext,
                "conflictDetected": False,
                "conflictDescription": None,
            }

        action = predicted.get("predictedAction")
        device = predicted.get("targetDevice", "")
        command = predicted.get("deviceCommand")
        confidence = predicted.get("confidence", 0.0)
        reason = predicted.get("reason", "")

        shouldExecute = confidence > 0.85
        shouldSuggest = 0.70 <= confidence <= 0.85

        explanationEnglish = f"Bedrock verified action: {reason}"
        explanationHindi = "कन्फर्म की गई गतिविधि: "
        savings = 0


        # Safety guardrail: geyser requires recent motion confirmation (Issue #17)
        recentEvents = context.get("recentSensorEvents", [])
        recentSensorIdList = [e.get("sensorId", "") for e in recentEvents]
        MOTION_SENSOR_IDS = {"bathroomMotion", "bedroomMotion", "toiletFlush", "poojaRoomMotion", "childrenStudyMotion"}
        hasRecentMotion = any(sid in MOTION_SENSOR_IDS for sid in recentSensorIdList)

        if action in ("turnOnGeyser",) and not hasRecentMotion and len(recentEvents) >= 3:
            return {
                "shouldExecute": False,
                "shouldSuggest": True,
                "actionId": "geyserMotionGuardrail",
                "targetDevice": "geyser",
                "deviceCommand": "ON",
                "explanationEnglish": "Geyser activation requires recent motion confirmation for safety. No motion detected in recent sensor history. Awaiting user confirmation.",
                "explanationHindi": "सुरक्षा जाँच: गीज़र चालू करने से पहले हाल की हलचल की पुष्टि आवश्यक है। कोई हलचल नहीं मिली — कृपया पुष्टि करें।",
                "estimatedSavingsWh": 0,
                "retrievedRagRules": ragContext,
                "conflictDetected": True,
                "conflictDescription": "Safety guardrail: geyser requires recent motion confirmation."
            }

        # Unified suppression pass — Priority 1 (override) and Priority 2 (safety)
        for rule in ragContext:
            cat = rule.get("category", "")
            if cat in ("override", "safety"):
                if self._deviceKeywordsMatch(rule.get("content"), device):
                    content = rule.get("content", "")
                    return {
                        "shouldExecute": False,
                        "shouldSuggest": False,
                        "actionId": f"suppressed_{action}",
                        "targetDevice": device,
                        "deviceCommand": "OFF",
                        "explanationEnglish": f"Action suppressed due to RAG-retrieved rule: '{content}'.",
                        "explanationHindi": f"नियम '{content}' के कारण कार्रवाई रोक दी गई है।",
                        "estimatedSavingsWh": 0,
                        "retrievedRagRules": ragContext,
                        "conflictDetected": True,
                        "conflictDescription": content,
                    }

        if action == "turnOnGeyser":
            explanationHindi = "सुबह की हलचल देखकर स्नान के लिए गीज़र चालू कर दिया गया है।"
            savings = 300
        elif action == "activatePoojaMode":
            if isFasting:
                explanationEnglish = f"Pooja mode activated on {festivalName}. Setting dim prayer lights, speaker DND, and suppressing cooker updates as matching RAG cultural fasting rules."
                explanationHindi = f"{festivalName} पूजा का समय शुरू हो गया है। व्रत के नियमों के अनुसार रसोई की सूचनाएं बंद कर दी गई हैं।"
            else:
                explanationEnglish = "Pooja mode activated. Setting dim lights and enabling do-not-disturb on speakers."
                explanationHindi = "पूजा का समय। लाइटें धीमी कर दी गई हैं और स्पीकर पर डिस्टर्ब न करने का मोड सक्रिय है।"
            savings = 50
        elif action == "cookerCompletionAlert":
            explanationEnglish = f"Cooker count reached target whistles. Alerting user."
            explanationHindi = "कुकर की सीटियाँ पूरी हो गई हैं। आपको सूचित कर दिया गया है।"
            savings = 120
        elif action == "startWaterMotor":
            explanationEnglish = "Scheduled cycle + low water level proxy: starting motor pumps."
            explanationHindi = "समय सारणी और कम पानी के स्तर के अनुसार पानी की मोटर चालू की गई है।"
            savings = 150
        elif action == "stopWaterMotorLeakAlert":
            explanationEnglish = "Safety hazard: stopping water pump motor to prevent overhead tank leakage."
            explanationHindi = "सुरक्षा चेतावनी: पानी बहने से रोकने के लिए मोटर को बंद किया गया है।"
            savings = 500
        elif action == "prechargeInverter":
            explanationEnglish = f"Predicting 85%+ chance of power cut in 15 minutes during local load shedding. Pre-charging backup inverter."
            explanationHindi = "अगले 15 मिनट में बिजली कटौती की संभावना 85% है। इन्वर्टर को पहले से चार्ज किया जा रहा है।"
            savings = 600
        elif action == "activateStudyMode":
            explanationEnglish = "Evening tuition/study window. Reducing television volume and optimizing brightness."
            explanationHindi = "पढ़ाई का समय शुरू। टीवी की आवाज़ कम की गई और लाइटें अनुकूलित की गई हैं।"
            savings = 80
        elif action == "activateBedtimeRoutine":
            explanationEnglish = "Bedtime schedule detected. Turning off smart displays and shifting to standby power mode."
            explanationHindi = "सोने का समय। सभी गैर-जरूरी उपकरण बंद कर दिए गए हैं।"
            savings = 400

        return {
            "shouldExecute": shouldExecute,
            "shouldSuggest": shouldSuggest,
            "actionId": action,
            "targetDevice": device,
            "deviceCommand": command,
            "explanationEnglish": explanationEnglish,
            "explanationHindi": explanationHindi,
            "estimatedSavingsWh": savings,
            "retrievedRagRules": ragContext,
            "conflictDetected": False,
            "conflictDescription": None,
        }

    def generatePreferenceRule(self, actionId, currentTime, powerStatus):
        """
        Synthesizes a natural-language rule from a user override (decline action).
        """
        if AppConfig.mockMode or not self.client:
            # Deterministic offline rule synthesis
            if actionId == "turnOnGeyser":
                return f"Never turn on Geyser at {currentTime} when water level is critical."
            elif actionId == "startWaterMotor":
                return f"Do not automatically start the water pump motor at {currentTime} under {powerStatus} conditions."
            elif actionId == "prechargeInverter":
                return f"Suppress inverter precharge triggers at {currentTime} during stable {powerStatus} supply."
            return f"Do not automatically trigger {actionId} at {currentTime} under {powerStatus} grid mode."

        prompt = (
            f"You are GharBuddy's cognitive rules compiler. Generate a single natural-language user preference rule "
            f"expressing that the user does not want action '{actionId}' executed at simulated time '{currentTime}' "
            f"under power status '{powerStatus}'. "
            f"Keep it short, direct, and focused. Return ONLY the rule text (e.g. 'Never turn on Geyser when water level is critical.') and nothing else."
        )
        
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            })
            response = self._invokeWithRetry(
                modelId=AppConfig.bedrockModelId,
                body=body,
            )
            responseBody = json.loads(response.get("body").read())
            ruleText = responseBody["content"][0]["text"].strip()
            if ruleText.startswith('"') and ruleText.endswith('"'):
                ruleText = ruleText[1:-1]
            return ruleText
        except Exception as e:
            print(f"Error generating preference rule via Bedrock: {e}")
            return f"Never automatically trigger {actionId} at {currentTime} under {powerStatus}."

    def generateConsolidatedRule(self, rule1, rule2):
        if AppConfig.mockMode or not self.client:
            # Deterministic consolidation logic for offline/mock runs
            if "water pump motor" in rule1.lower() and "water pump motor" in rule2.lower():
                return "Do not automatically start the water pump motor under GRID or INVERTER conditions."
            if "geyser" in rule1.lower() and "geyser" in rule2.lower():
                return "Do not automatically preheat the bath geyser at critical time windows."
            return f"Consolidated Preference: {rule1} / {rule2}"

        prompt = (
            f"You are GharBuddy's cognitive rules optimizer. Consolidate the following two redundant or "
            f"highly overlapping smart home preference rules into a single clear, cohesive preference rule:\n"
            f"1) '{rule1}'\n"
            f"2) '{rule2}'\n"
            f"Respond with ONLY the single consolidated rule text and nothing else. No explanation, no quotes."
        )
        
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 150,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            })
            response = self._invokeWithRetry(
                modelId=AppConfig.bedrockModelId,
                body=body,
            )
            responseBody = json.loads(response.get("body").read())
            consolidatedText = responseBody["content"][0]["text"].strip()
            if consolidatedText.startswith('"') and consolidatedText.endswith('"'):
                consolidatedText = consolidatedText[1:-1]
            return consolidatedText
        except Exception as e:
            print(f"Error consolidating rules via Bedrock: {e}")
            return f"Consolidated: {rule1} and {rule2}"
