"""
LoadSheddingCalendar — regional power cut schedule database for Indian cities.
Provides algorithm to cross-reference simulated date/time against schedule.
"""

# Default load shedding schedule for demo (Indian city patterns)
# Format: { "MM-DD": [(start_hour, end_hour, probability), ...] }
DEFAULT_SCHEDULE = {
    # Standard weekday patterns (applies when no date-specific override)
    "default_weekday": [
        (6.0, 7.0, 0.4),    # Early morning
        (13.0, 14.0, 0.5),  # Afternoon peak
        (18.0, 20.0, 0.85), # Evening peak (highest risk)
        (22.0, 23.0, 0.3),  # Late night
    ],
    "default_weekend": [
        (7.0, 8.0, 0.3),
        (14.0, 15.0, 0.6),
        (19.0, 21.0, 0.75),
    ],
    # Date-specific overrides (MM-DD format)
    "10-12": [(6.0, 10.0, 0.9), (16.0, 20.0, 0.95)],  # Navratri - high demand
    "11-08": [(17.0, 23.0, 0.95)],                      # Diwali - very high demand
    "06-14": [(13.0, 15.0, 0.7), (18.0, 20.0, 0.8)],   # Summer peak
}

PRECHARGE_LEAD_TIME_HOURS = 0.5   # Start charging 30 min before predicted cut
RISK_THRESHOLD = 0.75             # Trigger pre-charge at 75% probability


class LoadSheddingCalendar:
    def __init__(self):
        self.schedule = dict(DEFAULT_SCHEDULE)
        # In-memory city-specific overrides
        self.customSchedule = {}

    def getPredictedRisk(self, simulatedDate: str, simulatedTime: str) -> dict:
        """
        Cross-reference simulated date/time against the load shedding schedule.
        Returns { riskScore: float, nextCutStart: float|None, recommendation: str }
        """
        try:
            parts = simulatedTime.split(":")
            hourFloat = int(parts[0]) + int(parts[1]) / 60.0
        except Exception:
            hourFloat = 12.0

        # Determine weekday (simulate based on date hash for demo)
        try:
            month, day = simulatedDate.split("-")
            dayNum = (int(month) * 3 + int(day)) % 7
            isWeekend = dayNum in (5, 6)
        except Exception:
            isWeekend = False

        # Get applicable schedule
        slots = (
            self.customSchedule.get(simulatedDate)
            or self.schedule.get(simulatedDate)
            or (self.schedule["default_weekend"] if isWeekend else self.schedule["default_weekday"])
        )

        currentRisk = 0.0
        nextCutStart = None
        upcomingRisk = 0.0

        for (start, end, prob) in slots:
            # Current risk: are we in a shedding window?
            if start <= hourFloat < end:
                currentRisk = max(currentRisk, prob)
            # Upcoming risk: is a high-risk window starting within lead time?
            timeUntilStart = start - hourFloat
            if 0 < timeUntilStart <= PRECHARGE_LEAD_TIME_HOURS and prob >= RISK_THRESHOLD:
                if upcomingRisk < prob:
                    upcomingRisk = prob
                    nextCutStart = start

        effectiveRisk = max(currentRisk, upcomingRisk)

        recommendation = "no_action"
        if effectiveRisk >= RISK_THRESHOLD:
            recommendation = "precharge_inverter"
        elif effectiveRisk >= 0.5:
            recommendation = "monitor"

        return {
            "riskScore": round(effectiveRisk, 2),
            "currentRisk": round(currentRisk, 2),
            "upcomingRisk": round(upcomingRisk, 2),
            "nextCutStart": nextCutStart,
            "recommendation": recommendation,
            "shouldPrecharge": effectiveRisk >= RISK_THRESHOLD,
        }

    def addCustomSchedule(self, date: str, slots: list):
        """Add or override schedule for a specific date. slots = [(start, end, prob), ...]"""
        self.customSchedule[date] = slots

    def getSchedule(self) -> dict:
        """Return all schedule data for the API endpoint."""
        return {
            "defaultWeekday": DEFAULT_SCHEDULE["default_weekday"],
            "defaultWeekend": DEFAULT_SCHEDULE["default_weekend"],
            "customOverrides": {
                k: v for k, v in {**DEFAULT_SCHEDULE, **self.customSchedule}.items()
                if k not in ("default_weekday", "default_weekend")
            },
            "riskThreshold": RISK_THRESHOLD,
            "prechargeLeadTimeMinutes": int(PRECHARGE_LEAD_TIME_HOURS * 60),
        }
