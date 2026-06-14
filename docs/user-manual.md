# GharBuddy User Manual

*Smart Home Assistant for Indian Households — WhatsApp & Voice Guide*

---

## Getting Started

GharBuddy sends all alerts and suggestions to your WhatsApp. You'll also see them in the dashboard's notification panel.

### Dashboard Access
- Open browser: `http://localhost:5173`
- Login: `admin` / `gharbuddy123`
- Or from production: your deployed Vercel/Netlify URL

---

## WhatsApp Notifications

### Automatic Alerts You'll Receive

| Alert Type | When | Example Message |
|---|---|---|
| **Geyser Pre-heat** | Morning toilet flush detected | *"सुबह की हलचल देखकर गीज़र चालू कर दिया गया"* |
| **Pooja Mode** | Motion in prayer room (6–7 AM) | *"पूजा का समय — लाइटें धीमी"* |
| **Cooker Alert** | Target whistles reached | *"कुकर की सीटियाँ पूरी हो गई हैं"* |
| **Motor Leak Risk** | Motor running >20 min | *"⚠️ मोटर बंद की गई — रिसाव का खतरा"* |
| **Power Cut Warning** | 85%+ cut risk detected | *"⚡ बिजली कटौती की संभावना — इन्वर्टर चार्ज हो रहा है"* |
| **Caregiver Alert** | No motion by 9 AM | *"⚠️ सुबह 9 बजे तक कोई हलचल नहीं — जाँच करें"* |

### Approval Messages (Suggestions)

When GharBuddy is not sure, it asks for confirmation:

```
सजाव: गीज़र चालू करूँ? क्या मैं इसे चालू करूँ? (Approve?)
```

Reply by clicking **✅ Approve** or **❌ Decline** in the dashboard.

If you **decline**, GharBuddy remembers and won't suggest this again in similar conditions.

---

## Voice Commands (Hindi / Hinglish)

Press the 🎙️ button on the dashboard and speak:

### Device Control

| Say This | Action |
|---|---|
| *"Geyser on"* / *"Geyser chalu"* | Turn on bathroom geyser |
| *"Geyser off"* / *"Geyser band"* | Turn off geyser |
| *"Batti on"* / *"Lights on"* | Turn on living room lights |
| *"Batti off"* / *"Lights off"* | Turn off lights |
| *"TV on"* / *"TV off"* | Toggle television |
| *"AC on"* / *"AC off"* | Toggle air conditioner |
| *"Motor on"* / *"Motor chalu"* | Start water pump motor |
| *"Motor off"* / *"Motor band"* | Stop water pump motor |

### Modes

| Say This | Action |
|---|---|
| *"Pooja mode"* / *"Pooja"* | Activate prayer mode (dim lights, DND speaker) |
| *"Padhai mode"* / *"Study mode"* | Activate study focus mode |
| *"So jao"* / *"Bedtime"* | Activate bedtime routine (shut down all devices) |
| *"Inverter charge"* | Trigger inverter pre-charge |

> **Tip:** You don't need exact phrases — GharBuddy does partial matching. "please turn the geyser on" will work too.

---

## Sensor Simulator

In the dashboard, use **Sensor Simulator & Context Toggles** to test scenarios:

### Common Demos

| Button | Simulates | Expected AI Response |
|---|---|---|
| 🚽 Toilet Flush | Morning bathroom use | Geyser pre-heat suggestion |
| 🪔 Pooja Room Motion | Prayer time | Pooja mode activation |
| 💨 Cooker Whistle | Cooking in progress | Countdown + completion alert |
| ⚡ loadShedding Predicted | 85% power cut risk | Inverter pre-charge |
| ⚠️ Motor Leak Risk | Motor overflow hazard | Automatic motor shutoff |
| 📚 Study Room Motion | Tuition/study hours | Focus mode activation |
| 🌙 Wind Down Silent | Bedtime | All-device sleep shutdown |

### Time Warp Presets

Change simulated time to test time-specific routines:
- **06:05 AM** — Morning wake window (geyser, pooja triggers)
- **06:30 AM** — Peak pooja hour
- **07:15 AM** — Water motor scheduled window
- **06:15 PM** — Evening power cut risk window
- **10:30 PM** — Bedtime routine window

---

## Fasting & Festival Modes

### How to Enable
Select a date in the **Simulated Calendar Date** dropdown:
- **Navratri** (10th Oct) — Fasting day, cooker suppressed
- **Diwali** (8th Nov) — Festival day, pooja mode enhanced
- **Ekadashi** (14th Jun) — Fasting day

### What Changes on Fasting Days
- Cooker whistle alerts are suppressed
- Kitchen room glow is muted on the 2D map
- 🙏 badge appears near Kitchen on the floor plan
- Pooja mode activation text mentions the festival name

---

## Adding Custom Rules

Use the **"Add Custom Grounding / Override Rule"** panel in the Reasoning section:

### Examples

```
Category: override
Rule: Never turn on geyser before 6 AM

Category: safety  
Rule: Do not start water motor when inverter is on backup

Category: cultural
Rule: On Ekadashi fasting days, suppress all kitchen device automation

Category: routine
Rule: When children study motion is detected, mute the TV automatically
```

Rules are automatically embedded using Titan and stored in the vector database. They influence future AI decisions immediately.

---

## Understanding the AI Reasoning Panel

After any sensor trigger, the reasoning panel shows:

1. **Confidence Dial** — How sure Bedrock is (>85% = auto-execute, 70-85% = suggest)
2. **Action Classification** — What action was decided
3. **Hindi Explanation** — What GharBuddy did in Hindi
4. **RAG Rules Tab** — Which vector DB rules influenced the decision (with similarity %)
5. **Prompt Inspector** — The exact context sent to Claude
6. **⚠️ Conflict Resolved badge** — When a higher-priority rule overrode the prediction

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Page stuck at "Powering on..." | Check FastAPI is running on port 8000 |
| Voice widget says "not recognised" | Use shorter, clearer phrases; check mic permissions |
| No AI response after sensor | Check MOCK_MODE setting; verify Bedrock credentials |
| Load shedding badge not showing | Backend must be running; check `/api/inverter/load-shedding-risk` |
| Login fails | Use `admin` / `gharbuddy123` or check JWT_SECRET env var |
| Caregiver alert fires unexpectedly | Reset via `POST /api/safety/caregiver/reset` or trigger any motion sensor |
