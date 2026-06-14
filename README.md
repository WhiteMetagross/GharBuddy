# 🪔 GharBuddy — Context-Aware Smart Home for Indian Households

> **HackOn with Amazon Season 6.0 Submission** · Powered by AWS Bedrock Claude & AWS IoT Core

GharBuddy is a proactive AI-powered smart home assistant that understands Indian household routines — morning pooja, pressure cooker timing, power cuts, and fasting days — and acts before you need to ask.

## 🌟 Features

- **Live 2D Digital Twin** — Interactive SVG floor plan with 6 rooms, real-time device state, presence indicators, AI pulse animations
- **Bedrock AI Reasoning** — Claude 3.5 Sonnet makes context-aware decisions with full explainability (Hindi + English)
- **RAG Similarity Visualizer** — See exactly which vector DB rules influenced each AI decision
- **Voice Control (Hindi/Hinglish)** — "geyser on", "batti off", "pooja mode" — Whisper ASR
- **WebSocket Real-time** — Sub-100ms state updates, no polling lag
- **Caregiver Safety Monitor** — Morning motion check, elderly resident anomaly alerts
- **Load Shedding Prediction** — Calendar-aware inverter pre-charge engine
- **JWT Authentication** — Role-based access, sign-in gate

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/yenode/GharBuddy
cd GharBuddy

# 2. Configure
cp .env.example .env
# Edit .env with your AWS/DB credentials

# 3. Backend
pip install -r Backend/requirements.txt
python -m uvicorn Backend.MainFastApi:app --reload --port 8000

# 4. Frontend (new terminal)
cd Frontend && npm install && npm run dev

# 5. Open http://localhost:5173
# Login: admin / gharbuddy123
```

## 🏗️ Architecture

```
React Dashboard (Vite)  ←→  FastAPI Backend  ←→  AWS Bedrock (Claude + Titan)
      │                          │                         │
   WebSocket                PostgreSQL                 Twilio
   Live Twin                + pgvector               WhatsApp
```

See [docs/architecture.md](docs/architecture.md) for full system design.

## 📡 API

Full API reference: [docs/api-reference.md](docs/api-reference.md)

Interactive Swagger UI: `http://localhost:8000/docs`

## 🚢 Deployment

- **Backend**: [Deploy to Render](deploy/backend/README.md)
- **Frontend**: [Deploy to Vercel/Netlify](deploy/frontend/README.md)
- **Database**: [Setup Neon/RDS](deploy/database/neon-setup.md)

## 📖 Documentation

- [System Architecture](docs/architecture.md)
- [API Reference](docs/api-reference.md)
- [User Manual (WhatsApp & Voice)](docs/user-manual.md)
- [Sequence Diagrams](docs/sequence-diagrams.md)

## 🧪 Tests

```bash
# Backend property-based tests
python -m pytest Backend/Tests/ -v

# Frontend tests
cd Frontend && npm test
```

## 🌍 Use Cases

| Routine | Trigger | Action |
|---|---|---|
| Morning Geyser | Toilet flush at 6-8 AM | Auto pre-heat geyser |
| Pooja Mode | Motion in prayer room | Dim lights, DND speaker |
| Cooker Alert | N whistle pulses | Completion notification |
| Power Cut Pre-charge | 85% cut risk window | Fast-charge inverter |
| Study Mode | Children motion 5-7 PM | Focus brightness |
| Bedtime | Motion + late hour | All-device sleep shutdown |
| Caregiver Alert | No motion by 9 AM | WhatsApp emergency alert |
