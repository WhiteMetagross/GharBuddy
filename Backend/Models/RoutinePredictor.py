"""
RoutinePredictor — enhanced sequence learning predictor for Indian household routines.

Architecture:
- Sliding window of last 20 sensor events (session memory)
- Long-term pattern store: maps (hourSlot, sensorSequence) → (action, hit_count, last_seen)
- Confidence scoring: base_confidence * frequency_multiplier * recency_multiplier
- Sequence matching: checks if recent N sensors match stored pattern prefixes
"""
import datetime
import math
from collections import defaultdict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hour slots (0-47 = 30-min buckets per day)
def _hourToSlot(h: float) -> int:
    return min(47, int(h * 2))

# Sensor sequence patterns for known Indian household routines
# Each entry: (trigger_sensors: tuple, action, base_confidence, description)
ROUTINE_PATTERNS = [
    # Morning bath routine
    (("toiletFlush",),             "turnOnGeyser",         0.90, "Toilet flush → geyser pre-heat"),
    (("bathroomMotion",),          "turnOnGeyser",         0.88, "Bathroom motion → geyser"),
    (("toiletFlush","bathroomMotion"),"turnOnGeyser",       0.97, "Flush+motion → geyser (strong signal)"),

    # Pooja routine
    (("poojaRoomMotion",),         "activatePoojaMode",    0.92, "Pooja room motion → dim lights"),

    # Water motor
    (("waterLevelLow",),           "startWaterMotor",      0.84, "Low water level → start motor"),
    (("waterMotorRunningLong",),   "stopWaterMotorLeakAlert", 0.97, "Motor overtime → leak alert"),

    # Power cut pre-charge
    (("powerCutRiskHigh",),        "prechargeInverter",    0.89, "Risk signal → pre-charge"),

    # Study mode
    (("childrenStudyMotion",),     "activateStudyMode",    0.87, "Study motion → focus mode"),

    # Bedtime
    (("lateNightQuiet",),          "activateBedtimeRoutine", 0.92, "Night quiet → bedtime"),
    (("bedroomMotion",),           "activateBedtimeRoutine", 0.88, "Bedroom motion → bedtime check"),
]

# Time window constraints for each action (hour_start, hour_end)
ACTION_TIME_WINDOWS = {
    "turnOnGeyser":         (5.5, 8.5),
    "activatePoojaMode":    (5.5, 8.0),
    "startWaterMotor":      (6.5, 8.0),   # morning slot
    "stopWaterMotorLeakAlert": (0, 24),   # any time
    "prechargeInverter":    (17.0, 19.5),
    "activateStudyMode":    (16.5, 20.0),
    "activateBedtimeRoutine": (21.0, 24.0),
    "cookerCompletionAlert": (0, 24),
}

DEVICE_MAP = {
    "turnOnGeyser":         ("geyser",         "ON",                  "turnOnGeyser"),
    "activatePoojaMode":    ("poojaLights",     "MEDITATION_DIMS",     "activatePoojaMode"),
    "startWaterMotor":      ("waterMotor",      "ON",                  "startWaterMotor"),
    "stopWaterMotorLeakAlert": ("waterMotor",   "OFF",                 "stopWaterMotorLeakAlert"),
    "prechargeInverter":    ("inverterBackup",  "FAST_CHARGE",         "prechargeInverter"),
    "activateStudyMode":    ("livingRoomLights","STUDY_FOCUS_BRIGHTNESS","activateStudyMode"),
    "activateBedtimeRoutine": ("allDevices",    "SLEEP_SHUTDOWN",      "activateBedtimeRoutine"),
    "cookerCompletionAlert":("speakerSystem",   "ANNOUNCE_WHISTLE",    "cookerCompletionAlert"),
}


class RoutinePredictor:
    def __init__(self):
        self.recentEventList = []
        self.whistleCount = 0
        self.targetWhistles = 3

        # Long-term frequency learning store
        # key: (hourSlot, frozenset_of_sensors) → {"action": str, "hits": int, "daysSeen": int}
        self._patternStore = defaultdict(lambda: {"hits": 0, "daysSeen": 0, "lastDayKey": ""})

        # Track which actions were already suggested this session (avoid duplicates)
        self._recentlyTriggered = set()
        self._lastResetDay = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recordEvent(self, sensorId: str, value, timestamp: str = None) -> dict:
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        event = {"sensorId": sensorId, "value": value, "timestamp": timestamp}
        self.recentEventList.append(event)

        if len(self.recentEventList) > 20:
            self.recentEventList.pop(0)

        if sensorId == "cookerWhistle" and value == "active":
            self.whistleCount += 1
            print(f"[RoutinePredictor] Whistle #{self.whistleCount}/{self.targetWhistles}")
        elif sensorId == "resetCooker":
            self.whistleCount = 0
            if isinstance(value, int):
                self.targetWhistles = value

        return event

    def clearCookingWhistles(self):
        self.whistleCount = 0

    def predictNextAction(
        self,
        currentTimeString: str,
        isFastingDay: bool = False,
        powerStatus: str = "GRID",
    ) -> dict | None:
        """
        Returns the best predicted action with confidence score, or None.
        Uses sequence matching + frequency learning + time-window constraints.
        """
        try:
            parts = currentTimeString.split(":")
            hourFloat = int(parts[0]) + int(parts[1]) / 60.0
        except Exception:
            hourFloat = 12.0

        # Reset daily trigger deduplication
        dayKey = currentTimeString[:2]  # hour as proxy for day reset
        if dayKey != self._lastResetDay and hourFloat < 6.0:
            self._recentlyTriggered.clear()
            self._lastResetDay = dayKey

        recentSensorIds = [e["sensorId"] for e in self.recentEventList]
        recentSet = set(recentSensorIds)

        # Cooker completion (highest priority)
        if self.whistleCount > 0 and not isFastingDay:
            if self.whistleCount >= self.targetWhistles:
                count = self.whistleCount
                self.whistleCount = 0
                return self._buildResult(
                    "cookerCompletionAlert",
                    0.98,
                    f"Pressure cooker reached {self.targetWhistles} whistles."
                )
            # Active cooking: give partial progress signal
            progress = self.whistleCount / max(self.targetWhistles, 1)
            return self._buildResult(
                "cookerCompletionAlert",
                0.5 + progress * 0.3,
                f"Cooker active: {self.whistleCount}/{self.targetWhistles} whistles."
            )
        elif self.whistleCount > 0 and isFastingDay:
            self.whistleCount = 0
            return None

        # Sequence pattern matching
        best = None
        bestScore = 0.0

        for (triggerSensors, action, baseConf, desc) in ROUTINE_PATTERNS:
            # Skip if outside time window
            window = ACTION_TIME_WINDOWS.get(action)
            if window and not (window[0] <= hourFloat < window[1]):
                continue

            # Skip fasting-day cooking actions
            if isFastingDay and action in ("startWaterMotor", "cookerCompletionAlert"):
                continue

            # Skip power-charge if already on inverter
            if action == "prechargeInverter" and powerStatus == "INVERTER":
                continue

            # Check if trigger sensors are in recent events
            triggerSet = set(triggerSensors)
            matchCount = len(triggerSet & recentSet)
            if matchCount == 0:
                continue

            # Sequence match score: fraction of trigger sensors matched
            matchRatio = matchCount / len(triggerSet)

            # Frequency multiplier from learning store
            slotKey = _hourToSlot(hourFloat)
            storeKey = (slotKey, frozenset(triggerSensors))
            stored = self._patternStore[storeKey]
            freqMultiplier = 1.0 + math.log1p(stored.get("hits", 0)) * 0.05

            # Recency multiplier: boost if last event matches trigger
            lastSensor = recentSensorIds[-1] if recentSensorIds else ""
            recencyBoost = 1.1 if lastSensor in triggerSet else 1.0

            score = baseConf * matchRatio * freqMultiplier * recencyBoost
            score = min(0.99, score)

            if score > bestScore:
                bestScore = score
                best = (action, score, desc, storeKey)

        if best is None:
            return None

        action, score, desc, storeKey = best

        # Avoid re-triggering same action in same session window
        sessionKey = f"{action}_{int(hourFloat)}"
        if sessionKey in self._recentlyTriggered:
            return None
        self._recentlyTriggered.add(sessionKey)

        # Update frequency store (learning)
        self._patternStore[storeKey]["hits"] += 1

        return self._buildResult(action, score, desc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _buildResult(self, action: str, confidence: float, reason: str) -> dict:
        mapping = DEVICE_MAP.get(action, (action, "ON", action))
        return {
            "predictedAction": action,
            "targetDevice": mapping[0],
            "deviceCommand": mapping[1],
            "confidence": round(confidence, 3),
            "reason": reason,
            "sequenceLearningHits": self._patternStore.get(
                next((k for k in self._patternStore if action in str(k)), None),
                {}
            ).get("hits", 0),
        }

    def getPatternStats(self) -> list:
        """Returns learned pattern frequencies — for analytics/debugging."""
        stats = []
        for (slot, sensors), data in self._patternStore.items():
            if data["hits"] > 0:
                stats.append({
                    "hourSlot": slot / 2,  # convert back to hours
                    "sensors": list(sensors),
                    "hits": data["hits"],
                })
        return sorted(stats, key=lambda x: x["hits"], reverse=True)
