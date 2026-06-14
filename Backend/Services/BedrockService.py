import json
from Backend.Config.AppConfig import AppConfig

class BedrockService:
    def __init__(self):
        self.client = None
        self.initBedrockClient()

    def initBedrockClient(self):
        if not AppConfig.mockMode:
            try:
                import boto3
                self.client = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=AppConfig.awsRegion
                )
                print("AWS Bedrock client initialized successfully.")
            except Exception as e:
                print(f"Failed to initialize AWS Bedrock client: {e}. Falling back to mock Bedrock mode.")

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
            "You must respond with ONLY a valid JSON object. No extra text, no wrapper markdown."
        )

        prompt = f"""
        Situation Context:
        {json.dumps(contextData, indent=2)}

        Retrieved Grounding RAG Context:
        {ragContextText}

        Respond with a JSON object matching this structure:
        {{
          "shouldExecute": boolean,
          "shouldSuggest": boolean,
          "actionId": "string",
          "targetDevice": "string",
          "deviceCommand": "string",
          "explanationEnglish": "string",
          "explanationHindi": "string",
          "estimatedSavingsWh": number
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

            response = self.client.invoke_model(
                modelId=AppConfig.bedrockModelId,
                body=body
            )

            responseBody = json.loads(response.get("body").read())
            rawOutputText = responseBody["content"][0]["text"]
            
            parsedOutput = json.loads(rawOutputText.strip())
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
                "retrievedRagRules": ragContext
            }

        action = predicted.get("predictedAction")
        device = predicted.get("targetDevice")
        command = predicted.get("deviceCommand")
        confidence = predicted.get("confidence", 0.0)
        reason = predicted.get("reason", "")

        shouldExecute = confidence > 0.85
        shouldSuggest = 0.70 <= confidence <= 0.85

        explanationEnglish = f"Bedrock verified action: {reason}"
        explanationHindi = "कन्फर्म की गई गतिविधि: "
        savings = 0

        # RAG feedback logs matching
        ragSummaries = [r.get("content") for r in ragContext]

        # Check for matching overrides generically
        for r in ragContext:
            content = r.get("content", "")
            cat = r.get("category", "")
            if cat == "override":
                content_lower = content.lower()
                if ("geyser" in content_lower and action == "turnOnGeyser") or \
                   (("water pump motor" in content_lower or "water motor" in content_lower or "pump" in content_lower) and action == "startWaterMotor") or \
                   ("inverter" in content_lower and action == "prechargeInverter"):
                    return {
                        "shouldExecute": False,
                        "shouldSuggest": False,
                        "actionId": f"suppressed_{action}",
                        "targetDevice": device,
                        "deviceCommand": "OFF" if action != "prechargeInverter" else "STANDBY",
                        "explanationEnglish": f"Action suppressed due to RAG-retrieved user override rule: '{content}'.",
                        "explanationHindi": f"उपयोगकर्ता की प्राथमिकता नियम '{content}' के कारण कार्रवाई रोक दी गई है।",
                        "estimatedSavingsWh": 0,
                        "retrievedRagRules": ragContext
                    }

        # Specific safety guardrail mock check
        overrideDetected = False
        for rule in ragSummaries:
            if "Never turn on Geyser" in rule or "Never start a geyser" in rule:
                overrideDetected = True
                break

        if overrideDetected and action == "turnOnGeyser":
            return {
                "shouldExecute": False,
                "shouldSuggest": False,
                "actionId": "suppressedGeyserOverride",
                "targetDevice": "geyser",
                "deviceCommand": "OFF",
                "explanationEnglish": "Geyser activation suppressed due to RAG-retrieved user safety constraint rule: 'Never turn on Geyser when water level is critical'.",
                "explanationHindi": "सुरक्षा कारणों (पानी के कम स्तर) से गीज़र चालू नहीं किया गया है।",
                "estimatedSavingsWh": 0,
                "retrievedRagRules": ragContext
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
            "retrievedRagRules": ragContext
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
            response = self.client.invoke_model(
                modelId=AppConfig.bedrockModelId,
                body=body
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
            response = self.client.invoke_model(
                modelId=AppConfig.bedrockModelId,
                body=body
            )
            responseBody = json.loads(response.get("body").read())
            consolidatedText = responseBody["content"][0]["text"].strip()
            if consolidatedText.startswith('"') and consolidatedText.endswith('"'):
                consolidatedText = consolidatedText[1:-1]
            return consolidatedText
        except Exception as e:
            print(f"Error consolidating rules via Bedrock: {e}")
            return f"Consolidated: {rule1} and {rule2}"
