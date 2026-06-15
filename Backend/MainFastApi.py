from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from Backend.Services.AuthService import (
    authenticate,
    createAccessToken,
    verifyToken,
    verifyTokenFull,
    loginUser,
    registerUser,
    loadRegisteredUsers,
    RegistrationError,
    REGISTERED_USERS,
    DEMO_USERS,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
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
# Auth security scheme and dependency
# ---------------------------------------------------------------------------

_security = HTTPBearer(auto_error=False)

def requireAuth(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    """Dependency that validates Bearer token. In mockMode always passes."""
    from Backend.Config.AppConfig import AppConfig
    if AppConfig.mockMode:
        return "admin"  # bypass in demo mode
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    username = verifyToken(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


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
def toggleDevice(req: DeviceToggleRequest, background_tasks: BackgroundTasks, user: str = Depends(requireAuth)):
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
def updateSettings(req: SettingsUpdateRequest, background_tasks: BackgroundTasks, user: str = Depends(requireAuth)):
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

@app.get("/api/auth/me")
def getMe(user: str = Depends(requireAuth)):
    """Issue #6 — Return the authenticated user's info."""
    role = None
    # Registered users (real signup) take precedence
    reg = REGISTERED_USERS.get(user)
    if reg:
        role = reg.get("role")
    else:
        user_entry = DEMO_USERS.get(user)
        if user_entry:
            role = user_entry.get("role")
    return {"username": user, "role": role or "member"}

@app.post("/api/sensors/trigger")
def triggerSensor(req: SensorTriggerRequest, background_tasks: BackgroundTasks, user: str = Depends(requireAuth)):
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
def handleActionOverride(req: ActionOverrideRequest, background_tasks: BackgroundTasks, user: str = Depends(requireAuth)):
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

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "family"


@app.on_event("startup")
def _hydrateUsersOnStartup():
    """Pull any persisted users into the in-memory store on boot."""
    try:
        loaded = loadRegisteredUsers(databaseInstance.pgService)
        if loaded:
            print(f"[Auth] Loaded {loaded} registered user(s) from database.")
    except Exception as e:
        print(f"[Auth] Skipped user hydration: {e}")

    # Start weekly LSTM training scheduler thread
    import threading
    import datetime
    import time
    
    def run_weekly_lstm_training():
        while True:
            now = datetime.datetime.now()
            # Run weekly on Sunday at 02:00:00 AM
            if now.weekday() == 6 and now.hour == 2:
                print("[Weekly Scheduler] Starting weekly LSTM training routine...")
                try:
                    from Backend.Data.train_lstm import main as train_main
                    train_main()
                    print("[Weekly Scheduler] LSTM training routine completed successfully.")
                except Exception as e:
                    print(f"[Weekly Scheduler] LSTM training routine failed: {e}")
                time.sleep(3600)  # Avoid double triggers
            time.sleep(60)

    thread = threading.Thread(target=run_weekly_lstm_training, daemon=True)
    thread.start()
    print("[Weekly Scheduler] Weekly LSTM training routine scheduler started.")


@app.post("/api/auth/register", status_code=201)
def register(req: RegisterRequest):
    """
    Create a new account with PBKDF2-hashed password and return a session token.
    Roles: parent, child, family.
    """
    try:
        result = registerUser(
            req.username,
            req.password,
            req.role,
            pgService=databaseInstance.pgService,
        )
    except RegistrationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "access_token": result["token"],
        "token": result["token"],
        "token_type": "bearer",
        "username": result["username"],
        "role": result["role"],
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "expiresIn": result["expiresIn"],
        "message": "Account created successfully.",
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    # Try multi-user demo store first (Issue #6)
    result = loginUser(req.username, req.password)
    if result:
        # Also expose as access_token for backward compat with existing frontend
        return {
            "access_token": result["token"],
            "token": result["token"],
            "token_type": "bearer",
            "username": result["username"],
            "role": result["role"],
            "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
            "expiresIn": result["expiresIn"],
            "message": "GharBuddy authentication successful"
        }
    # Legacy single-user env-var fallback
    if not authenticate(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = createAccessToken(req.username)
    return {
        "access_token": token,
        "token": token,
        "token_type": "bearer",
        "username": req.username,
        "role": "parent",
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "expiresIn": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "message": "GharBuddy authentication successful"
    }

class GoogleLoginRequest(BaseModel):
    token: str

@app.post("/api/auth/google")
def googleLogin(req: GoogleLoginRequest):
    """Authenticate a user using a Google ID token and return a JWT access token."""
    from Backend.Config.AppConfig import AppConfig
    token = req.token
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                AppConfig.googleClientId
            )
            email = idinfo["email"]
            username = email.split("@")[0]
        except ValueError as ve:
            if AppConfig.mockMode:
                username = "google_user"
                email = "google_user@example.com"
            else:
                raise HTTPException(status_code=401, detail=f"Invalid Google ID token: {ve}")
    except Exception as e:
        if AppConfig.mockMode:
            username = "google_user"
            email = "google_user@example.com"
        else:
            raise HTTPException(status_code=401, detail=f"Google Authentication failed: {e}")

    role = "family"
    if username not in REGISTERED_USERS:
        try:
            import secrets
            dummy_pass = secrets.token_hex(16)
            registerUser(
                username=username,
                password=dummy_pass,
                role=role,
                pgService=databaseInstance.pgService
            )
        except Exception:
            pass
    local_token = createAccessToken(username)
    return {
        "access_token": local_token,
        "token": local_token,
        "token_type": "bearer",
        "username": username,
        "role": role,
        "expires_in_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "expiresIn": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "message": "Google authentication successful"
    }

@app.get("/api/auth/verify")
def verifyAuth(authorization: str = Header(default="")):
    """Issue #6 - Verify a Bearer token and return user info."""
    token = authorization.replace("Bearer ", "").strip()
    payload = verifyTokenFull(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True, "username": payload.get("sub"), "role": payload.get("role", "parent")}

@app.get("/api/auth/status")
def authStatus():
    from Backend.Config.AppConfig import AppConfig
    return {
        "mockMode": AppConfig.mockMode,
        "authRequired": not AppConfig.mockMode,
        "message": "In mock mode, all endpoints are accessible without authentication."
    }

class VectorRuleRequest(BaseModel):
    content: str
    category: str

@app.post("/api/vectors/add")
def addVectorRule(req: VectorRuleRequest, user: str = Depends(requireAuth)):
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

@app.get("/api/vectors/cache-stats")
def getVectorCacheStats():
    return vectorStoreInstance.getCacheStats()

@app.get("/api/cache/diagnostics")
def getCacheDiagnostics():
    return databaseInstance.pgService.getCacheDiagnostics()

@app.post("/api/vectors/cache-evict")
def evictVectorCache():
    vectorStoreInstance.evictOldestEmbeddings(keepCount=500)
    return {"status": "success", "message": "Old embeddings evicted. Kept 500 most recent."}

@app.get("/api/vectors/consolidation-stats")
def getConsolidationStats():
    return vectorStoreInstance.getConsolidationStats()

@app.get("/api/vectors/stats")
def getVectorStats():
    try:
        return vectorStoreInstance.getConsolidationStats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vectors/auto-consolidate")
def autoConsolidate():
    result = vectorStoreInstance.scheduleAutoConsolidation(bedrockInstance)
    return result

@app.get("/api/safety/caregiver")
def getCaregiverStatus():
    return caregiverMonitor.getStatus()

@app.post("/api/safety/caregiver/reset")
def resetCaregiverMonitor():
    caregiverMonitor.resetForTesting()
    return {"status": "success", "message": "Caregiver monitor reset."}

@app.post("/api/admin/train-lstm")
def triggerLstmTraining(background_tasks: BackgroundTasks, user: str = Depends(requireAuth)):
    """Manually trigger the weekly LSTM training routine in the background."""
    def run_train():
        try:
            print("[API Trigger] Starting LSTM training routine in background...")
            from Backend.Data.train_lstm import main as train_main
            train_main()
            print("[API Trigger] LSTM training routine completed successfully.")
        except Exception as e:
            print(f"[API Trigger] LSTM training routine failed: {e}")

    background_tasks.add_task(run_train)
    return {"message": "LSTM training routine started in the background."}

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
            
            # Use an initial prompt to give the model context about expected words
            expected_commands = "geyser on, batti off, pooja mode, motor band, padhai mode, so jao, tv on, ac off"
            result = model.transcribe(tmp_path, initial_prompt=expected_commands)
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

import random as _random

# Simulated community homes (demo data, deterministic based on time)
COMMUNITY_HOMES = [
    {"id": "home_A", "name": "Sharma House",   "solarKw": 2.5},
    {"id": "home_B", "name": "Patel House",    "solarKw": 3.0},
    {"id": "home_C", "name": "Gupta Residence","solarKw": 0.0},
    {"id": "home_D", "name": "Iyer Villa",     "solarKw": 4.0},
    {"id": "home_E", "name": "Singh Bhawan",   "solarKw": 1.5},
]

@app.get("/api/community/energy")
def getCommunityEnergy():
    """
    Issue #7 — Returns simulated community energy stats:
    peak demand per home, solar generation, peer-to-peer trading recs,
    and cooperative load-shedding schedule.
    """
    import math as _math

    # Use simulatedTime to make the data time-aware
    try:
        parts = simulatedTime.split(":")
        hourFloat = int(parts[0]) + int(parts[1]) / 60.0
    except Exception:
        hourFloat = 12.0

    # Simulate solar generation curve (peaks at noon)
    solarFactor = max(0.0, _math.sin(_math.pi * (hourFloat - 6) / 12)) if 6 <= hourFloat <= 18 else 0.0

    homes = []
    totalDemandW = 0
    totalSolarW = 0
    totalExcessW = 0

    for home in COMMUNITY_HOMES:
        # Simulate load (higher in morning and evening, lower at noon)
        baseLoad = 800 + 400 * abs(_math.sin(_math.pi * hourFloat / 12))
        currentLoadW = round(baseLoad + (hash(home["id"]) % 300))

        # Solar generation
        solarGenerationW = round(home["solarKw"] * 1000 * solarFactor)
        excessW = max(0, solarGenerationW - currentLoadW)
        netDemandW = max(0, currentLoadW - solarGenerationW)

        totalDemandW += currentLoadW
        totalSolarW += solarGenerationW
        totalExcessW += excessW

        # Load shedding priority (higher load = higher priority to shed)
        sheddingPriority = "HIGH" if currentLoadW > 1200 else "MEDIUM" if currentLoadW > 900 else "LOW"

        homes.append({
            "id": home["id"],
            "name": home["name"],
            "currentLoadW": currentLoadW,
            "solarCapacityKw": home["solarKw"],
            "solarGenerationW": solarGenerationW,
            "excessSolarW": excessW,
            "netDemandW": netDemandW,
            "sheddingPriority": sheddingPriority,
            "canShareSolar": excessW > 100,
        })

    # Peer-to-peer trading recommendations
    sellers = [h for h in homes if h["canShareSolar"]]
    buyers = [h for h in homes if h["netDemandW"] > 200 and not h["canShareSolar"]]
    tradingRecs = []
    for seller in sellers[:2]:
        for buyer in buyers[:2]:
            shareW = min(seller["excessSolarW"], buyer["netDemandW"], 500)
            if shareW > 50:
                tradingRecs.append({
                    "fromHome": seller["name"],
                    "toHome": buyer["name"],
                    "shareWatts": shareW,
                    "savingsRupees": round(shareW * 0.008),
                    "message": f"{seller['name']} → {buyer['name']}: Share {shareW}W solar surplus"
                })

    # Cooperative load shedding schedule — shed HIGH priority homes first
    sheddingSchedule = [
        {"home": h["name"], "priority": h["sheddingPriority"], "recommendShed": h["sheddingPriority"] == "HIGH"}
        for h in sorted(homes, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["sheddingPriority"]])
    ]

    # Transformer load status
    transformerLoadPct = round((totalDemandW / (len(homes) * 2000)) * 100)
    transformerStatus = "CRITICAL" if transformerLoadPct > 85 else "HIGH" if transformerLoadPct > 70 else "NORMAL"

    return {
        "simulatedTime": simulatedTime,
        "homes": homes,
        "totals": {
            "totalDemandW": totalDemandW,
            "totalSolarW": totalSolarW,
            "totalExcessSolarW": totalExcessW,
            "netGridDemandW": max(0, totalDemandW - totalSolarW),
        },
        "transformerLoad": {
            "percentageUsed": transformerLoadPct,
            "status": transformerStatus,
        },
        "tradingRecommendations": tradingRecs,
        "cooperativeSheddingSchedule": sheddingSchedule,
    }

class LoadSheddingScheduleRequest(BaseModel):
    date: str
    slots: list

@app.post("/api/inverter/schedule")
def addLoadSheddingSchedule(req: LoadSheddingScheduleRequest):
    loadSheddingCalendar.addCustomSchedule(req.date, [tuple(s) for s in req.slots])
    return {"status": "success", "date": req.date}
