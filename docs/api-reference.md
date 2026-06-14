# GharBuddy API Reference

Base URL: `http://localhost:8000` (development) | `https://gharbuddy-api.onrender.com` (production)

> **Authentication**: Protected endpoints require `Authorization: Bearer <token>` header.
> In `MOCK_MODE=True`, auth is bypassed for all endpoints.

---

## Authentication

### POST /api/auth/login
Authenticate and receive a JWT token.

**Request:**
```json
{ "username": "admin", "password": "gharbuddy123" }
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "username": "admin",
  "role": "admin",
  "expires_in_minutes": 1440
}
```

**Demo credentials:**
| Username | Password | Role |
|---|---|---|
| `admin` | `gharbuddy123` | admin |
| `child` | `child123` | child |

---

### GET /api/auth/me 🔒
Returns the authenticated user's info.

---

## Devices

### GET /api/devices
Returns current state of all smart devices.

**Response:**
```json
{
  "geyser": {"name": "Bathroom Geyser", "status": "OFF", "wattage": 2000},
  "livingRoomLights": {"name": "Living Room Lights", "status": "ON", "wattage": 80}
}
```

### POST /api/devices/toggle 🔒
Toggle a device on or off.

**Request:** `{"deviceId": "geyser", "status": "ON"}`

---

## System State

### GET /api/system/state
Returns current simulated context.

**Response:**
```json
{
  "simulatedTime": "06:30:00",
  "powerStatus": "GRID",
  "whistleCount": 2,
  "targetWhistles": 3,
  "isFastingDay": false,
  "festivalName": null,
  "eventHistory": [...]
}
```

### POST /api/settings/update 🔒
Update simulation context (time, date, power status, cooker target).

---

## Sensors

### POST /api/sensors/trigger 🔒
Fire a sensor event and get AI reasoning response.

**Request:** `{"sensorId": "bathroomMotion", "value": "active"}`

**Response:**
```json
{
  "status": "processed",
  "prediction": {"predictedAction": "turnOnGeyser", "confidence": 0.94},
  "decision": {
    "shouldExecute": true,
    "actionId": "turnOnGeyser",
    "explanationHindi": "गीज़र चालू कर दिया गया।",
    "conflictDetected": false
  },
  "ragContext": [{"content": "...", "category": "routine", "similarity": 0.85}]
}
```

**Available sensor IDs:**
`toiletFlush`, `bathroomMotion`, `poojaRoomMotion`, `cookerWhistle`, `waterLevelLow`, `waterMotorRunningLong`, `powerCutRiskHigh`, `childrenStudyMotion`, `bedroomMotion`, `lateNightQuiet`

---

## Actions

### POST /api/actions/override 🔒
Approve or decline a suggested AI action.

**Request:** `{"actionId": "turnOnGeyser", "approve": false}`

When declined, a preference rule is auto-generated and stored in the vector DB.

---

## Energy

### GET /api/energy/stats
Returns cumulative energy savings.

---

## Vector Rules (RAG)

### GET /api/vectors
List all stored grounding rules.

### POST /api/vectors/add 🔒
Add a custom rule to the vector store (auto-embedded via Titan).

**Request:** `{"content": "Never turn on geyser after 9 PM", "category": "override"}`

### POST /api/vectors/consolidate
Merge redundant similar rules via Bedrock.

### GET /api/vectors/stats
Returns total rule count and category breakdown.

### POST /api/vectors/auto-consolidate
Run auto-consolidation (only runs if > 20 rules exist).

---

## Cache

### GET /api/cache/diagnostics
Returns Titan embedding cache hit rate and occupancy.

---

## Safety

### GET /api/safety/caregiver
Returns morning motion detection status and alert state.

### POST /api/safety/caregiver/reset
Reset caregiver monitor for a new test day.

---

## Voice

### POST /api/voice/transcribe
Submit audio for Hindi/Hinglish transcription and device control.

**Request:** `multipart/form-data` with `audio` field (webm/wav/mp3)

**Response:**
```json
{
  "status": "executed",
  "transcript": "geyser on",
  "action": "Toggled geyser → ON",
  "executed": true
}
```

**Supported phrases:** `geyser on/off`, `batti on/off`, `pooja mode`, `motor on/off`, `padhai mode`, `so jao`, etc.

---

## Inverter / Load Shedding

### GET /api/inverter/load-shedding-risk
Returns predicted power cut risk for current date/time.

**Response:**
```json
{
  "riskScore": 0.85,
  "shouldPrecharge": true,
  "nextCutStart": 18.5,
  "recommendation": "precharge_inverter"
}
```

---

## WebSocket

### WS /ws
Real-time state push. Connect with `ws://localhost:8000/ws`.

Receives `StateSnapshot` on every device/sensor mutation.
Receives `{"type": "ping"}` heartbeat every 30 seconds.

---

## Notifications

### GET /api/notifications
Returns WhatsApp notification log (last 30 messages).
