# GharBuddy: Context-Aware Smart Home for Indian Households

[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/WhiteMetagross/GharBuddy)
[![Live Site](https://img.shields.io/badge/Live-Site-green)](http://gharbuddy123.in)

GharBuddy is a proactive, context-aware smart home assistant designed for Indian households. It understands daily routines like morning pooja, pressure cooker whistles, load-shedding windows, and caregiver anomalies, acting autonomously to preheat water, dim lights, schedule inverter charging, and alert family members.

## Overview of GharBuddy:

GharBuddy bridges smart home devices with state-of-the-art Generative AI reasoning. Instead of relying solely on hard-coded schedules or manually triggered scenes, it uses an LSTM machine learning routine combined with LLM orchestrations (AWS Bedrock Claude 3.5 Sonnet and Google Gemini 3.5 Flash) to infer intent and take preemptive action. The front-end React interface is built with premium aesthetics, offering a live 2D digital twin of the home alongside real-time telemetry, AI decision consoles, and neighborhood micro-grid statistics.

## System Architecture:

![GharBuddy System Architecture](visuals/GharBuddy_System_Architecture.png)

*The complete 5-layer architecture of GharBuddy: Presentation → API Gateway → Context Engine → AI/Semantic Layer → Infrastructure. Detailed documentation on the architecture and diagrams can be found in the [architecture.md](docs/architecture.md) file.*

## Live Visual Demos:

Below are the visual screenshots captured from the live running system:

### 1. User Authentication Portal:
![User Authentication Portal](visuals/login_page.png)
The secure login screen handles JWT credentials and integrates Google OAuth login options.

### 2. Google Sign-In Portal:
![Google Sign-In Portal](visuals/google_signin_page.png)
The custom Google OAuth sign-in option prompts users for authorization.

### 3. Google OAuth Active Sign-In Dialog:
![Google OAuth Active Sign-In Dialog](visuals/GoogleOAuthScreen.png)
The standard Google identity service overlay requesting email and password authorizations.

### 4. Home Overview Dashboard (Midnight Saffron Theme):
![Home Overview Dashboard](visuals/overview.png)
The default midnight theme rendering the interactive SVG floor plan, room occupancies, and device indicators.

### 5. Home Overview Dashboard (Dawn Light Theme):
![Home Overview Dashboard (Dawn Light Theme)](visuals/theme_dawn_light.png)
The high-contrast dawn light theme designed for daytime accessibility.

### 6. Home Overview Dashboard (Royal Indigo Theme):
![Home Overview Dashboard (Royal Indigo Theme)](visuals/theme_royal_indigo.png)
The glassmorphic royal indigo theme matching specialized evening settings.

### 7. Smart Appliances Console:
![Smart Appliances Console](visuals/devices.png)
A dedicated device manager displaying real-time power consumption, toggle switches, and quick-preset activities.

### 8. Energy Analytics Control:
![Energy Analytics Control](visuals/energy.png)
Detailed consumption histories, load-shedding lookaheads, and battery status visualizations.

### 9. AI Reasoning Insights:
![AI Reasoning Insights](visuals/ai_insights.png)
The cognitive brain of the system displaying live explainable decisions, RAG lookup indicators, and simulation triggers.

### 10. AI Agent and WhatsApp Integration:
![AI Agent and WhatsApp Integration](visuals/whatsapp_alert_cooker.png)
The live WhatsApp simulator sending automated alerts and request confirmations when the cooker whistle threshold is reached.

### 11. Community Micro-Grid:
![Community Micro-Grid](visuals/community.png)
A localized dashboard simulating neighborhood solar shares, energy transfers, and active grid demand.

## Major Features and Capabilities:

The system is equipped with the following features:
- Live 2D Digital Twin: The reactive SVG floor plan shows room occupancies and device status dynamically.
- Hybrid LLM Reasoner: System switches dynamically between AWS Bedrock and Google Gemini to calculate explainable choices.
- Caregiver Safety Monitor: Tracks morning motions between 6:00 AM and 9:00 AM, automatically executing safety notifications.
- Predictive Inverter Charger: Syncs with regional power cut timetables to charge batteries prior to outages.
- Twilio WhatsApp Alerts: Dispatches immediate push notifications to family members regarding anomalies.
- Vector RAG Optimizer: Evaluates custom user overrides and stores rules inside an indexed database repository.

## Documentation Index:

Refer to these dedicated guides to learn more about the codebase structure, installations, and architecture:
- [CodeBaseIndex.md](docs/CodeBaseIndex.md): Directory structures, packages, and file organization.
- [Frontend.md](docs/Frontend.md): Client-side components, state providers, and page layouts.
- [Backend.md](docs/Backend.md): Server endpoints, background tasks, and database managers.
- [AIAgent.md](docs/AIAgent.md): Model parameters, RAG lookup rules, and training routines.
- [Architecture.md](docs/architecture.md): Data flows, message sequences, and hardware simulation loops.
- [InstallationAndSetup.md](docs/InstallationAndSetup.md): Prerequisites, local builds, and database setup instructions.
- [Deploy.md](docs/Deploy.md): Render blueprint steps, Vercel deployments, and environment syncs.
