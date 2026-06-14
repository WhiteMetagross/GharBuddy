# GharBuddy — System Architecture Guide

## Overview

GharBuddy is a context-aware proactive smart home assistant built for Indian households. It combines real-time IoT sensor fusion, AWS Bedrock Claude AI reasoning, vector RAG (Retrieval-Augmented Generation), and a live 2D digital twin dashboard.

## High-Level Architecture

```
IoT Sensors / App / Voice Commands
          │
          ▼
    FastAPI Backend (Python)
          │
    ┌─────┴──────────────────┐
    │                        │
    ▼                        ▼
RoutinePredictor         BedrockService
(Sequence Learning)      (Claude Reasoning)
    │                        │
    ▼                        ▼
Event History ──────► VectorStoreService
                       (RAG + Titan Embeddings)
                             │
                        PostgreSQL
                        + pgvector
                             │
                             ▼
                    WebSocket Broadcast
                             │
                             ▼
              React Dashboard (Live 2D Twin)
```

## Components

### Backend Services

| Service | File | Purpose |
|---|---|---|
| **MainFastApi** | `Backend/MainFastApi.py` | FastAPI app, REST + WebSocket endpoints, auth |
| **BedrockService** | `Backend/Services/BedrockService.py` | Claude AI reasoning, Titan embeddings, retry logic |
| **VectorStoreService** | `Backend/Services/VectorStoreService.py` | RAG rule retrieval, cosine similarity, consolidation |
| **PostgreSqlService** | `Backend/Services/PostgreSqlService.py` | DB pool, resilience, embedding cache |
| **DatabaseService** | `Backend/Services/DatabaseService.py` | Thin wrapper over PostgreSqlService |
| **AuthService** | `Backend/Services/AuthService.py` | JWT auth (HS256, stdlib) |
| **CaregiverMonitor** | `Backend/Services/CaregiverMonitor.py` | Morning anomaly detection, safety alerts |
| **LoadSheddingCalendar** | `Backend/Services/LoadSheddingCalendar.py` | Regional power cut prediction |
| **TwilioService** | `Backend/Services/TwilioService.py` | WhatsApp notification delivery |

### Models

| Model | File | Purpose |
|---|---|---|
| **RoutinePredictor** | `Backend/Models/RoutinePredictor.py` | Probabilistic sequence learning, action prediction |
| **IndianCalendar** | `Backend/Models/IndianCalendar.py` | Fasting days, festivals, pooja hours |

### Frontend Components

| Component | Purpose |
|---|---|
| `HouseholdMap.jsx` | Live 2D digital twin SVG floor plan |
| `ReasoningPanel.jsx` | Bedrock AI decisions + RAG similarity visualizer |
| `VoiceWidget.jsx` | Whisper ASR Hindi/Hinglish voice control |
| `EnergyTracker.jsx` | Energy savings + load shedding risk badge |
| `WhatsAppMock.jsx` | WhatsApp notification mock panel |
| `SensorSimulator.jsx` | IoT sensor event simulator |

### Hooks

| Hook | Purpose |
|---|---|
| `useWebSocket.js` | WebSocket connection with exponential backoff |
| `computeBackoffDelay.js` | Pure backoff delay calculator |

---

## Data Flow — Sensor Trigger

```
1. Sensor event fired (POST /api/sensors/trigger)
2. RoutinePredictor.recordEvent() + predictNextAction()
3. VectorStoreService.querySimilarRules() — RAG context retrieval
4. BedrockService.generateReasoning() — Claude AI decision
5. executeAction() — device state change + WhatsApp notification
6. broadcastSnapshot() — WebSocket push to all connected clients
7. React Dashboard updates live (0ms lag via WebSocket)
```

## Database Schema

```sql
-- Device states
CREATE TABLE Devices (
    deviceId VARCHAR(50) PRIMARY KEY,
    deviceName VARCHAR(100),
    status VARCHAR(50),
    wattage INT
);

-- IoT event history
CREATE TABLE EventLogs (
    eventId SERIAL PRIMARY KEY,
    sensorId VARCHAR(50),
    value VARCHAR(200),
    timestamp VARCHAR(50)
);

-- Energy savings tracking
CREATE TABLE EnergyStats (
    id INT PRIMARY KEY DEFAULT 1,
    totalSavedWh INT,
    rupeesSaved INT,
    peakPowerAvoidedW INT,
    inverterCharge INT
);

-- RAG rule embeddings (pgvector)
CREATE TABLE VectorIndex (
    ruleId SERIAL PRIMARY KEY,
    content TEXT,
    vector vector(1536),  -- Titan embedding
    category VARCHAR(50)  -- routine | cultural | safety | override
);

-- Titan embedding cache
CREATE TABLE EmbeddingCache (
    textHash VARCHAR(64) PRIMARY KEY,
    inputText TEXT,
    embedding TEXT  -- JSON array
);
```

## AI Reasoning Pipeline

```
Sensor Event
    │
    ▼
RoutinePredictor (probabilistic sequence matching)
    ├── Time window gate (ACTION_TIME_WINDOWS)
    ├── Sensor pattern match (ROUTINE_PATTERNS)  
    ├── Frequency multiplier (learned hit counts)
    └── Recency boost (last sensor match)
    │
    ▼
VectorStoreService.querySimilarRules()
    ├── pgvector native (<=> cosine) [live mode]
    └── Chunked Python fallback [mock mode, Issue #18]
    │
    ▼
BedrockService.generateReasoning(contextData)
    ├── CONFLICT RESOLUTION PRIORITY HIERARCHY (5 levels)
    ├── Priority 1: User overrides (category=override)
    ├── Priority 2: Safety guardrails (category=safety)
    ├── Priority 3: Cultural/fasting context
    ├── Priority 4: Routine predictions
    └── Priority 5: Energy optimisation
    │
    ▼
Decision: shouldExecute | shouldSuggest | conflictDetected
```

## Security

- **JWT Authentication**: HS256 HMAC, 24h expiry, stdlib-only (no external dep)
- **Protected endpoints**: All mutation endpoints (toggle, trigger, override, add rule, settings)
- **Public endpoints**: All GET endpoints, /ws, /api/auth/login
- **Mock mode bypass**: `MOCK_MODE=True` skips auth for local development
- **Demo credentials**: `admin/gharbuddy123`, `child/child123`

## WebSocket Events

| Direction | Event | Payload |
|---|---|---|
| Server → Client | State snapshot | `{devices, systemState, energyStats, notifications}` |
| Server → Client | Heartbeat | `{"type": "ping"}` |

Snapshot is broadcast after every mutation (sensor trigger, device toggle, settings update, action override).

## Deployment Architecture

```
Internet
    │
    ▼
Vercel/Netlify (React SPA)
    │ /api/* proxy
    ▼
Render / AWS App Runner (FastAPI)
    │
    ├── AWS Bedrock (Claude + Titan) — us-east-1
    ├── Twilio (WhatsApp alerts)
    └── Neon / AWS RDS (PostgreSQL + pgvector)
```
