from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from Backend.Models.IndianCalendar import IndianCalendar
from Backend.Models.RoutinePredictor import RoutinePredictor
from Backend.Services.DatabaseService import DatabaseService
from Backend.Services.TwilioService import TwilioService
from Backend.Services.BedrockService import BedrockService
from Backend.Services.VectorStoreService import VectorStoreService

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
bedrockInstance = BedrockService()

# Global state trackers for simulated environments
simulatedTime = "06:00:00"
powerStatus = "GRID"

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
def toggleDevice(req: DeviceToggleRequest):
    success = databaseInstance.updateDeviceState(req.deviceId, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "success", "deviceId": req.deviceId, "newStatus": req.status}

@app.get("/api/energy/stats")
def getEnergyStats():
    return databaseInstance.getEnergyStats()

@app.get("/api/notifications")
def getNotifications():
    return twilioInstance.getNotificationLogs()

@app.get("/api/system/state")
def getSystemState():
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

@app.post("/api/settings/update")
def updateSettings(req: SettingsUpdateRequest):
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
def triggerSensor(req: SensorTriggerRequest):
    # Log sensor hit
    event = predictorInstance.recordEvent(req.sensorId, req.value, simulatedTime)
    databaseInstance.logEvent(event)

    isFasting = calendarInstance.isFastingToday()
    festivalInfo = calendarInstance.getFestivalStatus()

    # Query sequence learning models
    prediction = predictorInstance.predictNextAction(simulatedTime, isFasting, powerStatus)

    if not prediction:
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

    return {
        "status": "processed",
        "event": event,
        "prediction": prediction,
        "decision": decision,
        "ragContext": similarRules
    }

@app.post("/api/actions/override")
def handleActionOverride(req: ActionOverrideRequest):
    if not req.approve:
        rule = bedrockInstance.generatePreferenceRule(req.actionId, simulatedTime, powerStatus)
        vectorStoreInstance.addRule(rule, "override")
        msg = f"प्राथमिकता सहेज ली गई है (Preference saved): '{rule}'. भविष्य में इसे ब्लॉक किया जाएगा।"
        twilioInstance.sendWhatsApp(msg)
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
