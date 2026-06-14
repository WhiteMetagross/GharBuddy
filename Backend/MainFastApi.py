from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import json as _json
import tempfile
import os as _os

from Backend.Models.IndianCalendar import IndianCalendar
from Backend.Models.RoutinePredictor import RoutinePredictor
from Backend.Services.DatabaseService import DatabaseService
from Backend.Services.TwilioService import TwilioService
from Backend.Services.BedrockService import BedrockService
from Backend.Services.VectorStoreService import VectorStoreService
from Backend.Services.CaregiverMonitor import CaregiverMonitor
from Backend.Services.LoadSheddingCalendar import LoadSheddingCalendar

HEARTBEAT_INTERVAL = 30


class ConnectionManager:
    def __init__(self):
        self.activeConnections: list = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.activeConnections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.activeConnections:
            self.activeConnections.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        disconnected = []
        for ws in list(self.activeConnections):
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()

app = FastAPI(title="GharBuddy API", description="Context-Aware Smart Home for Indian Households")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singleton services
calendarInstance = IndianCalendar()
predictorInstance = RoutinePredictor()
databaseInstance = DatabaseService()
vectorStoreInstance = VectorStoreService(databaseInstance.pgService)
twilioInstance = TwilioService()
caregiverMonitor = CaregiverMonitor(twilioInstance, databaseInstance)
bedrockInstance = BedrockService()
loadSheddingCalendar = LoadSheddingCalendar()

# Global state trackers for simulated environments
simulatedTime = "06:00:00"
powerStatus = "GRID"


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------

def buildSystemState():
    festival = calendarInstance.getFestivalStatus()
    return {
        "simulatedTime": simulatedTime,
        "simulatedDate": calendarInstance.getCurrentDateString(),
        "powerStatus": powerStatus,
        "whistleCount": predictorInstance.whistleCount,
        "targetWhistles": predictorInstance.targetWhistles,
        "isFastingDay": calendarInstance.isFastingToday(),
        "festivalName": festival.get("festivalName") if festival else None,
        "eventHistory": databaseInstance.getEventHistory()
    }


async def broadcastSnapshot():
    snapshot = {
        "devices": databaseInstance.getDeviceStates(),
        "systemState": buildSystemState(),
        "energyStats": databaseInstance.getEnergyStats(),
        "notifications": twilioInstance.getNotificationLogs(),
    }
    await manager.broadcast(snapshot)


@app.websocket("/ws")
async def websocketEndpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)

# API schemas
class SensorTriggerRequest(BaseModel):
    sensorId: str
    value: str

class ActionOverrideRequest(BaseModel):
    actionId: str
    approve: bool

class DeviceToggleRequest(BaseModel):
    deviceId: str
    status: str

class SettingsUpdateRequest(BaseModel):
    simulatedTime: Optional[str] = None
    simulatedDate: Optional[str] = None
    powerStatus: Optional[str] = None
    targetWhistles: Optional[int] = None

@app.get("/api/devices")
def getDevices():
    return databaseInstance.getDeviceStates()

@app.post("/api/devices/toggle")
def toggleDevice(req: DeviceToggleRequest, background_tasks: BackgroundTasks):
    success = databaseInstance.updateDeviceState(req.deviceId, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    background_tasks.add_task(broadcastSnapshot)
    return {"status": "success", "deviceId": req.deviceId, "newStatus": req.status}

@app.get("/api/energy/stats")
def getEnergyStats():
    return databaseInstance.getEnergyStats()

@app.get("/api/notifications")
def getNotifications():
    return twilioInstance.getNotificationLogs()

@app.get("/api/system/state")
def getSystemState():
    return buildSystemState()

@app.post("/api/settings/update")
def updateSettings(req: SettingsUpdateRequest, background_tasks: BackgroundTasks):
    global simulatedTime, powerStatus
    if req.simulatedTime is not None:
        simulatedTime = req.simulatedTime
    if req.simulatedDate is not None:
        calendarInstance.setSimulatedDate(req.simulatedDate)
    if req.powerStatus is not None:
        powerStatus = req.powerStatus
        if powerStatus == "INVERTER":
            databaseInstance.setInverterCharge(65)
        else:
            databaseInstance.setInverterCharge(95)
    if req.targetWhistles is not None:
        predictorInstance.recordEvent("resetCooker", req.targetWhistles)

    # Check morning anomaly whenever time is updated
    caregiverMonitor.checkMorningAnomalyAlert(simulatedTime, calendarInstance.getCurrentDateString())

    background_tasks.add_task(broadcastSnapshot)
    return {"status": "success", "message": "Simulation settings synced."}

def executeAction(decision):
    target = decision.get("targetDevice")
    command = decision.get("deviceCommand")
    actionId = decision.get("actionId")
    savings = decision.get("estimatedSavingsWh", 0)
    explanation = decision.get("explanationHindi") or decision.get("explanationEnglish", "")

    # Execute and update database
    if target == "allDevices":
        databaseInstance.updateDeviceState("geyser", "OFF")
        databaseInstance.updateDeviceState("waterMotor", "OFF")
        databaseInstance.updateDeviceState("livingRoomLights", "OFF")
        databaseInstance.updateDeviceState("television", "OFF")
        databaseInstance.updateDeviceState("airConditioner", "STANDBY")
    elif target:
        databaseInstance.updateDeviceState(target, command)

    # Secondary action implications
    if actionId == "activatePoojaMode":
        databaseInstance.updateDeviceState("television", "OFF")
        databaseInstance.updateDeviceState("speakerSystem", "DO_NOT_DISTURB")
    elif actionId == "prechargeInverter":
        databaseInstance.updateDeviceState("geyser", "OFF")
        databaseInstance.updateDeviceState("airConditioner", "OFF")
        databaseInstance.setInverterCharge(100)

    # Accumulate energy stats
    rupees = max(1, int(savings * 0.008))  # estimated tariff proxy
    databaseInstance.addEnergySavings(savings, rupees)

    # Dispatch WhatsApp logger
    msgText = f"सक्रिय (Active): {explanation}"
    twilioInstance.sendWhatsApp(msgText, actionId=actionId, suggestActions=False)

@app.post("/api/sensors/trigger")
def triggerSensor(req: SensorTriggerRequest, background_tasks: BackgroundTasks):
    # Log sensor hit
    event = predictorInstance.recordEvent(req.sensorId, req.value, simulatedTime)
    databaseInstance.logEvent(event)

    # Proactive inverter pre-charge check via load shedding calendar
    loadRisk = loadSheddingCalendar.getPredictedRisk(
        calendarInstance.getCurrentDateString(), simulatedTime
    )
    if loadRisk["shouldPrecharge"] and powerStatus == "GRID":
        currentDevices = databaseInstance.getDeviceStates()
        inverterStatus = currentDevices.get("inverterBackup", {}).get("status", "")
        if inverterStatus not in ("FAST_CHARGE",):
            loadMsg = (
                f"⚡ लोड शेडिंग चेतावनी (Load Shedding Alert): "
                f"अगले 30 मिनट में बिजली कटौती की संभावना {int(loadRisk['riskScore']*100)}% है। "
                f"(Power cut risk: {int(loadRisk['riskScore']*100)}% — Pre-charging inverter.)"
            )
            twilioInstance.sendWhatsApp(loadMsg, actionId="loadSheddingAutoPrecharge", suggestActions=False)

    # Caregiver anomaly check
    caregiverMonitor.recordMotionEvent(req.sensorId, simulatedTime)
    caregiverMonitor.checkMorningAnomalyAlert(simulatedTime, calendarInstance.getCurrentDateString())

    isFasting = calendarInstance.isFastingToday()
    festivalInfo = calendarInstance.getFestivalStatus()

    # Query sequence learning models
    prediction = predictorInstance.predictNextAction(simulatedTime, isFasting, powerStatus)

    if not prediction:
        background_tasks.add_task(broadcastSnapshot)
        return {
            "status": "logged",
            "message": f"Sensor event '{req.sensorId}' logged. No proactive actions suggested.",
            "decision": None
        }

    # Retrieve similar rules from Vector DB
    queryText = f"Sensor {req.sensorId} with value {req.value}. Prediction: {prediction.get('predictedAction')}."
    similarRules = vectorStoreInstance.querySimilarRules(queryText, topK=3)

    # Construct complete reasoning context
    contextData = {
        "currentTime": simulatedTime,
        "currentDate": calendarInstance.getCurrentDateString(),
        "calendarContext": {
            "isFastingDay": isFasting,
            "festivalName": festivalInfo.get("festivalName") if festivalInfo else "Normal Day",
            "poojaDuration": calendarInstance.getPoojaDurationMinutes()
        },
        "powerGridStatus": powerStatus,
        "recentSensorEvents": databaseInstance.getEventHistory()[-5:],
        "predictedActionDetails": prediction,
        "ragContext": similarRules
    }

    # Reason context via Bedrock
    decision = bedrockInstance.generateReasoning(contextData)

    if decision.get("shouldExecute"):
        executeAction(decision)
    elif decision.get("shouldSuggest"):
        msgText = f"सजाव (Suggest): {decision.get('explanationHindi')} क्या मैं इसे चालू करूँ? (Approve?)"
        twilioInstance.sendWhatsApp(msgText, actionId=decision.get("actionId"), suggestActions=True)

    background_tasks.add_task(broadcastSnapshot)
    return {
        "status": "processed",
        "event": event,
        "prediction": prediction,
        "decision": decision,
        "ragContext": similarRules
    }

@app.post("/api/actions/override")
def handleActionOverride(req: ActionOverrideRequest, background_tasks: BackgroundTasks):
    if not req.approve:
        rule = bedrockInstance.generatePreferenceRule(req.actionId, simulatedTime, powerStatus)
        vectorStoreInstance.addRule(rule, "override")
        msg = f"प्राथमिकता सहेज ली गई है (Preference saved): '{rule}'. भविष्य में इसे ब्लॉक किया जाएगा।"
        twilioInstance.sendWhatsApp(msg)
        background_tasks.add_task(broadcastSnapshot)
        return {"status": "declined", "ruleGenerated": rule}

    actionId = req.actionId
    decision = {
        "actionId": actionId,
        "targetDevice": "",
        "deviceCommand": "ON",
        "estimatedSavingsWh": 100,
        "explanationHindi": "आपके निर्देशानुसार डिवाइस चालू कर दिया गया है।"
    }

    if actionId == "turnOnGeyser":
        decision["targetDevice"] = "geyser"
    elif actionId == "activatePoojaMode":
        decision["targetDevice"] = "poojaLights"
        decision["deviceCommand"] = "MEDITATION_DIMS"
    elif actionId == "startWaterMotor":
        decision["targetDevice"] = "waterMotor"
    elif actionId == "stopWaterMotorLeakAlert":
        decision["targetDevice"] = "waterMotor"
        decision["deviceCommand"] = "OFF"
    elif actionId == "prechargeInverter":
        decision["targetDevice"] = "inverterBackup"
        decision["deviceCommand"] = "FAST_CHARGE"
    elif actionId == "activateStudyMode":
        decision["targetDevice"] = "livingRoomLights"
        decision["deviceCommand"] = "STUDY_FOCUS_BRIGHTNESS"
    elif actionId == "activateBedtimeRoutine":
        decision["targetDevice"] = "allDevices"
        decision["deviceCommand"] = "SLEEP_SHUTDOWN"

    executeAction(decision)
    background_tasks.add_task(broadcastSnapshot)
    return {"status": "executed", "decision": decision}

class VectorRuleRequest(BaseModel):
    content: str
    category: str

@app.post("/api/vectors/add")
def addVectorRule(req: VectorRuleRequest):
    try:
        vectorStoreInstance.addRule(req.content, req.category)
        return {"status": "success", "message": "Rule successfully embedded and stored."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vectors")
def getVectorRules():
    try:
        records = databaseInstance.pgService.getVectors()
        return [{"content": r["content"], "category": r["category"]} for r in records]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vectors/consolidate")
def consolidateVectorRules():
    try:
        count = vectorStoreInstance.consolidateRules(bedrockInstance)
        return {"status": "success", "consolidatedCount": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/safety/caregiver")
def getCaregiverStatus():
    return caregiverMonitor.getStatus()

@app.post("/api/safety/caregiver/reset")
def resetCaregiverMonitor():
    caregiverMonitor.resetForTesting()
    return {"status": "success", "message": "Caregiver monitor reset."}

# Voice intent → device action mapping
VOICE_INTENT_MAP = {
    "geyser on": ("toggleDevice", "geyser", "ON"),
    "geyser band karo": ("toggleDevice", "geyser", "ON"),
    "geyser chalu": ("toggleDevice", "geyser", "ON"),
    "geyser off": ("toggleDevice", "geyser", "OFF"),
    "geyser band": ("toggleDevice", "geyser", "OFF"),
    "batti on": ("toggleDevice", "livingRoomLights", "ON"),
    "lights on": ("toggleDevice", "livingRoomLights", "ON"),
    "batti off": ("toggleDevice", "livingRoomLights", "OFF"),
    "lights off": ("toggleDevice", "livingRoomLights", "OFF"),
    "pooja mode": ("sensor", "poojaRoomMotion", "active"),
    "pooja": ("sensor", "poojaRoomMotion", "active"),
    "motor on": ("toggleDevice", "waterMotor", "ON"),
    "motor chalu": ("toggleDevice", "waterMotor", "ON"),
    "motor off": ("toggleDevice", "waterMotor", "OFF"),
    "motor band": ("toggleDevice", "waterMotor", "OFF"),
    "inverter charge": ("sensor", "powerCutRiskHigh", "active"),
    "so jao": ("sensor", "lateNightQuiet", "active"),
    "bedtime": ("sensor", "lateNightQuiet", "active"),
    "padhai mode": ("sensor", "childrenStudyMotion", "active"),
    "study mode": ("sensor", "childrenStudyMotion", "active"),
    "tv on": ("toggleDevice", "television", "ON"),
    "tv off": ("toggleDevice", "television", "OFF"),
    "ac on": ("toggleDevice", "airConditioner", "ON"),
    "ac off": ("toggleDevice", "airConditioner", "OFF"),
}

def matchVoiceIntent(transcript: str):
    lower = transcript.lower().strip()
    for phrase, action in VOICE_INTENT_MAP.items():
        if phrase in lower:
            return action, phrase
    return None, None

@app.post("/api/voice/transcribe")
async def transcribeVoice(audio: UploadFile = File(...)):
    transcript = ""
    whisperAvailable = False
    try:
        import whisper
        whisperAvailable = True
    except ImportError:
        pass

    audio_bytes = await audio.read()

    if whisperAvailable and len(audio_bytes) > 1000:
        try:
            model = whisper.load_model("tiny")
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            result = model.transcribe(tmp_path, language="hi", task="transcribe")
            transcript = result.get("text", "").strip()
            _os.unlink(tmp_path)
        except Exception as e:
            transcript = ""
            print(f"Whisper transcription error: {e}")

    if not transcript:
        transcript = audio.filename or ""
        for ext in [".webm", ".wav", ".mp3", ".ogg", ".m4a"]:
            transcript = transcript.replace(ext, "")
        transcript = transcript.replace("_", " ").replace("-", " ").strip()

    action, matchedPhrase = matchVoiceIntent(transcript)
    if not action:
        return {"status": "no_match", "transcript": transcript,
                "message": "No device command matched.", "executed": False}

    actionType, param1, param2 = action
    if actionType == "toggleDevice":
        databaseInstance.updateDeviceState(param1, param2)
        return {"status": "executed", "transcript": transcript,
                "matchedPhrase": matchedPhrase, "action": f"Toggled {param1} → {param2}", "executed": True}
    elif actionType == "sensor":
        event = predictorInstance.recordEvent(param1, param2, simulatedTime)
        databaseInstance.logEvent(event)
        return {"status": "executed", "transcript": transcript,
                "matchedPhrase": matchedPhrase, "action": f"Triggered sensor {param1}", "executed": True}

    return {"status": "error", "transcript": transcript, "executed": False}

@app.get("/api/inverter/load-shedding-risk")
def getLoadSheddingRisk():
    return loadSheddingCalendar.getPredictedRisk(
        calendarInstance.getCurrentDateString(), simulatedTime
    )

@app.get("/api/inverter/schedule")
def getLoadSheddingSchedule():
    return loadSheddingCalendar.getSchedule()

class LoadSheddingScheduleRequest(BaseModel):
    date: str
    slots: list

@app.post("/api/inverter/schedule")
def addLoadSheddingSchedule(req: LoadSheddingScheduleRequest):
    loadSheddingCalendar.addCustomSchedule(req.date, [tuple(s) for s in req.slots])
    return {"status": "success", "date": req.date}
