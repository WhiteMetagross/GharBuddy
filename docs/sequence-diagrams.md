# GharBuddy Sequence Diagrams

## 1. Morning Routine Automation

```
User        Bathroom Sensor    FastAPI          RoutinePredictor    Bedrock        Geyser
  |               |               |                    |               |              |
  |  Toilet flush |               |                    |               |              |
  |──────────────►|               |                    |               |              |
  |               | POST /trigger |                    |               |              |
  |               |──────────────►|                    |               |              |
  |               |               | recordEvent()      |               |              |
  |               |               |───────────────────►|               |              |
  |               |               | predictNextAction()|               |              |
  |               |               |◄───────────────────| turnOnGeyser  |              |
  |               |               | querySimilarRules()|               |              |
  |               |               | generateReasoning()|──────────────►|              |
  |               |               |◄───────────────────|  shouldExecute|              |
  |               |               | updateDeviceState()|               |   ON         |
  |               |               |────────────────────────────────────────────────►  |
  |               |               | broadcastSnapshot()|               |              |
  |    WebSocket push             |◄───────────────────────────────────────────────── |
  |◄──────────────────────────────|                    |               |              |
```

## 2. Override Rule Learning

```
User         ReasoningPanel      FastAPI          VectorStore        Bedrock
  |               |               |                    |               |
  | Click Decline |               |                    |               |
  |──────────────►|               |                    |               |
  |               | POST /override|                    |               |
  |               | approve:false |                    |               |
  |               |──────────────►|                    |               |
  |               |               | generatePreferenceRule()           |
  |               |               |────────────────────────────────────►
  |               |               |◄────────────────────────────────── "Never turn on Geyser at 06:30"
  |               |               | addRule(override)  |               |
  |               |               |───────────────────►|               |
  |               |               |                    | Titan embed + store
  |               |◄──────────────|                    |               |
  | Rule saved ✓  |               |                    |               |
```

## 3. WebSocket State Sync

```
Browser          useWebSocket       FastAPI /ws      Mutation Endpoint
  |                  |                  |                  |
  | mount            |                  |                  |
  |─────────────────►|                  |                  |
  |                  | new WebSocket()  |                  |
  |                  |─────────────────►|                  |
  |                  |◄─────────────────| open             |
  | isConnected=true |                  |                  |
  |◄─────────────────|                  |                  |
  |                  |                  |                  |
  | toggleDevice     |                  |                  |
  |──────────────────────────────────────────────────────►|
  |                  |                  |         broadcastSnapshot()
  |                  |◄─────────────────|────────────────── StateSnapshot
  | setDevices()     |                  |                  |
  |◄─────────────────|                  |                  |
  |  (< 100ms)       |                  |                  |
```
