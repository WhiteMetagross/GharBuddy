"""
CaregiverMonitor — background safety monitor for elderly residents.
Checks for morning motion activity and fires WhatsApp alerts when absent.
"""
import datetime
import threading

class CaregiverMonitor:
    def __init__(self, twilioService, databaseService):
        self.twilioService = twilioService
        self.databaseService = databaseService
        # Track whether morning motion has been detected today
        self._morningMotionDetected = False
        self._lastCheckedDate = None
        self._alertFired = False
        self._lock = threading.Lock()

    def recordMotionEvent(self, sensorId: str, simulatedTime: str):
        """
        Called whenever any motion sensor fires. Records that the household
        is active. Relevant sensors: bathroomMotion, bedroomMotion,
        poojaRoomMotion, childrenStudyMotion.
        """
        MOTION_SENSORS = {
            "bathroomMotion", "bedroomMotion", "poojaRoomMotion",
            "childrenStudyMotion", "toiletFlush"
        }
        if sensorId not in MOTION_SENSORS:
            return

        try:
            parts = simulatedTime.split(":")
            hourFloat = int(parts[0]) + int(parts[1]) / 60.0
        except Exception:
            hourFloat = 12.0

        # Morning window: 5:00 AM – 10:00 AM
        if 5.0 <= hourFloat <= 10.0:
            with self._lock:
                self._morningMotionDetected = True
                self._alertFired = False  # reset if motion detected

    def checkMorningAnomalyAlert(self, simulatedTime: str, simulatedDate: str) -> dict | None:
        """
        Check if it's past 9:00 AM and no morning motion has been recorded.
        Returns an alert dict if an alert was fired, else None.
        Should be called after any sensor trigger or settings update.
        """
        try:
            parts = simulatedTime.split(":")
            hourFloat = int(parts[0]) + int(parts[1]) / 60.0
        except Exception:
            return None

        # Only trigger after 9:00 AM
        if hourFloat < 9.0:
            return None

        with self._lock:
            # Reset state when date changes
            if self._lastCheckedDate != simulatedDate:
                self._lastCheckedDate = simulatedDate
                self._morningMotionDetected = False
                self._alertFired = False

            # Don't double-fire per day
            if self._alertFired:
                return None

            # If no motion detected by 9 AM, fire alert
            if not self._morningMotionDetected:
                self._alertFired = True
                alert = {
                    "alertType": "caregiverMorningAnomaly",
                    "simulatedTime": simulatedTime,
                    "simulatedDate": simulatedDate,
                    "message": (
                        "⚠️ सुरक्षा चेतावनी (Safety Alert): सुबह 9 बजे तक कोई हलचल नहीं पकड़ी गई। "
                        "कृपया घर के सदस्यों की जाँच करें। "
                        "(No morning motion detected by 9 AM. Please check on household members.)"
                    ),
                    "severity": "HIGH"
                }
                # Send WhatsApp notification
                self.twilioService.sendWhatsApp(
                    alert["message"],
                    actionId="caregiverMorningAnomaly",
                    suggestActions=False
                )
                # Log to database event history
                self.databaseService.logEvent({
                    "sensorId": "caregiverAlert",
                    "value": "morningAnomalyDetected",
                    "timestamp": simulatedTime
                })
                print(f"[CaregiverMonitor] ALERT FIRED: No morning motion by {simulatedTime}")
                return alert

        return None

    def getStatus(self) -> dict:
        """Returns current monitor state for the /api/safety/caregiver endpoint."""
        with self._lock:
            return {
                "morningMotionDetected": self._morningMotionDetected,
                "alertFired": self._alertFired,
                "lastCheckedDate": self._lastCheckedDate,
            }

    def resetForTesting(self):
        """Reset state — for use in tests and simulator resets."""
        with self._lock:
            self._morningMotionDetected = False
            self._alertFired = False
            self._lastCheckedDate = None
