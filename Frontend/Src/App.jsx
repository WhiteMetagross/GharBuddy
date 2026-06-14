import React, { useState, useEffect, useRef } from "react";
import { BackendService } from "./Services/BackendService";
import { useWebSocket } from "./hooks/useWebSocket.js";
import SensorSimulator from "./Components/SensorSimulator";
import DeviceGrid from "./Components/DeviceGrid";
import ReasoningPanel from "./Components/ReasoningPanel";
import WhatsAppMock from "./Components/WhatsAppMock";
import EnergyTracker from "./Components/EnergyTracker";
import HouseholdMap from "./Components/HouseholdMap";
import VoiceWidget from "./Components/VoiceWidget";
import LoginModal from "./Components/LoginModal";

export default function App() {
  const [devices, setDevices] = useState({});
  const [energyStats, setEnergyStats] = useState({
    totalSavedWh: 4200,
    rupeesSaved: 34,
    peakPowerAvoidedW: 750,
    inverterBatteryCharge: 85
  });
  const [notifications, setNotifications] = useState([]);
  const [systemState, setSystemState] = useState({
    simulatedTime: "06:00:00",
    simulatedDate: "06-13",
    powerStatus: "GRID",
    whistleCount: 0,
    targetWhistles: 3,
    isFastingDay: false,
    festivalName: null,
    eventHistory: []
  });
  const [lastTriggerResult, setLastTriggerResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showLogin, setShowLogin] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  // Session-backed auth token (Issue #6 — full login gate)
  const [authToken, setAuthToken] = useState(() => sessionStorage.getItem("gb_token") || "");
  const [loginError, setLoginError] = useState("");
  const [loginForm, setLoginForm] = useState({ username: "admin", password: "gharbuddy123" });

  const { isConnected, lastMessage } = useWebSocket("ws://localhost:8000/ws");
  const pollingIntervalRef = useRef(null);

  // Core data synchronization
  const syncData = async () => {
    // Preserve scroll position across polling re-renders
    const scrollY = window.scrollY;
    try {
      const [devicesRes, energyRes, notificationsRes, systemRes] = await Promise.all([
        BackendService.getDevices(),
        BackendService.getEnergyStats(),
        BackendService.getNotifications(),
        BackendService.getSystemState()
      ]);

      // Batch all state updates in one React flush to avoid multiple re-renders
      setDevices(devicesRes);
      setEnergyStats(energyRes);
      setNotifications(notificationsRes);
      setSystemState(systemRes);
      setLoading(false);
    } catch (e) {
      console.error("Sync error:", e);
      setError("Unable to connect to GharBuddy API. Please verify the FastAPI server is running.");
      setLoading(false);
    } finally {
      // Restore scroll position after React re-render
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, behavior: "instant" }));
    }
  };

  // Initial data fetch — runs once on mount regardless of WebSocket state
  useEffect(() => {
    syncData();
  }, []);

  // Restore session from localStorage on mount (legacy token support)
  useEffect(() => {
    const token = localStorage.getItem("gharbuddy_token");
    const userJson = localStorage.getItem("gharbuddy_user");
    if (token && userJson) {
      try {
        const user = JSON.parse(userJson);
        setCurrentUser(user);
        // Also populate sessionStorage token if not already set
        if (!sessionStorage.getItem("gb_token")) {
          sessionStorage.setItem("gb_token", token);
          setAuthToken(token);
        }
      } catch (_) {
        // Ignore malformed stored user
      }
    }
  }, []);

  // Issue #6 — Handle login form submission (full-page gate)
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginForm)
      });
      if (!res.ok) { setLoginError("Invalid credentials"); return; }
      const data = await res.json();
      sessionStorage.setItem("gb_token", data.access_token);
      setAuthToken(data.access_token);
      setCurrentUser({ username: data.username, role: data.role });
      setLoginError("");
    } catch (_e) {
      setLoginError("Cannot connect to backend");
    }
  };

  // Effect A — handle WebSocket messages
  useEffect(() => {
    if (!lastMessage || lastMessage.type === "ping") return;
    if (lastMessage.devices) setDevices(lastMessage.devices);
    if (lastMessage.energyStats) setEnergyStats(lastMessage.energyStats);
    if (lastMessage.notifications) setNotifications(lastMessage.notifications);
    if (lastMessage.systemState) setSystemState(lastMessage.systemState);
    setLoading(false);
  }, [lastMessage]);

  // Effect B — manage polling as fallback when WebSocket is disconnected
  useEffect(() => {
    if (isConnected) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    } else {
      if (!pollingIntervalRef.current) {
        syncData(); // immediate sync when falling back to polling
        pollingIntervalRef.current = setInterval(syncData, 3000);
      }
    }
    return () => clearInterval(pollingIntervalRef.current);
  }, [isConnected]);

  const handleStateChange = async (type, payload) => {
    try {
      if (type === "settings") {
        await BackendService.updateSettings(payload, authToken);
      } else if (type === "sensor") {
        const response = await BackendService.triggerSensor(payload.sensorId, payload.value, authToken);
        setLastTriggerResult(response);
      }
      await syncData();
    } catch (e) {
      console.error("Error setting state:", e);
    }
  };

  const handleToggleDevice = async (deviceId, status) => {
    try {
      await BackendService.toggleDevice(deviceId, status, authToken);
      await syncData();
    } catch (e) {
      console.error("Error toggling device:", e);
    }
  };

  const handleApproveAction = async (actionId, approve) => {
    try {
      await BackendService.approveAction(actionId, approve, authToken);
      // Remove or resolve active suggestion locally
      await syncData();
    } catch (e) {
      console.error("Error approving action:", e);
    }
  };

  // Issue #6 — Full-page login gate: show login screen until authenticated
  if (!authToken) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh", alignItems: "center", justifyContent: "center", gap: "20px", background: "var(--bgPrimary)" }}>
        <div style={{ fontSize: "48px" }}>🪔</div>
        <h1 className="gradientText" style={{ fontSize: "28px" }}>GharBuddy</h1>
        <p style={{ color: "var(--textSecondary)", fontSize: "13px" }}>Context-Aware Smart Home for Indian Households</p>
        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "12px", width: "300px" }}>
          <input
            value={loginForm.username}
            onChange={e => setLoginForm(f => ({ ...f, username: e.target.value }))}
            placeholder="Username"
            aria-label="Username"
            style={{ padding: "10px 14px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", color: "white", fontSize: "14px", fontFamily: "var(--fontFamily)" }}
          />
          <input
            type="password"
            value={loginForm.password}
            onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))}
            placeholder="Password"
            aria-label="Password"
            style={{ padding: "10px 14px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", color: "white", fontSize: "14px", fontFamily: "var(--fontFamily)" }}
          />
          {loginError && <span role="alert" style={{ color: "var(--colorDanger)", fontSize: "12px" }}>{loginError}</span>}
          <button type="submit" className="btn btnPrimary" style={{ padding: "12px" }}>Sign In →</button>
          <p style={{ fontSize: "11px", color: "var(--textMuted)", textAlign: "center" }}>Demo: admin / gharbuddy123</p>
        </form>
      </div>
    );
  }

  if (loading && Object.keys(devices).length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh", alignItems: "center", justifyContent: "center", gap: "16px" }}>
        <div className="glowingDot" style={{ width: "24px", height: "24px", background: "var(--colorOrange)" }}></div>
        <span style={{ fontSize: "16px", color: "var(--textSecondary)" }}>Powering on GharBuddy Systems...</span>
      </div>
    );
  }

  return (
    <div className="appContainer">
      {/* Premium Dashboard Header */}
      <header className="appHeader">
        <div className="appLogo">
          <span style={{ fontSize: "32px" }}>🪔</span>
          <div>
            <h1 className="gradientText">GharBuddy (घर बड्डी)</h1>
            <p style={{ fontSize: "12px", color: "var(--textSecondary)", marginTop: "2px" }}>
              Context-Aware Proactive Smart Home for Indian Households
            </p>
          </div>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {/* Live system state summary badges */}
          <div className="statusBadge" style={{ background: "rgba(255,126,64,0.1)", color: "var(--colorOrange)", border: "1px solid rgba(255,126,64,0.15)" }}>
            🕒 {systemState.simulatedTime}
          </div>
          <div className="statusBadge" style={{ background: "rgba(52,152,219,0.12)", color: "var(--colorActive)", border: "1px solid rgba(52,152,219,0.18)" }}>
            ⚡ Grid: {systemState.powerStatus}
          </div>
          {systemState.festivalName && (
            <div className="statusBadge" style={{ background: "rgba(142,45,226,0.15)", color: "#a855f7", border: "1px solid rgba(142,45,226,0.2)" }}>
              🎉 Fasting & Festival: {systemState.festivalName}
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "10px" }}>
            {(() => {
              const status = isConnected ? "ws" : error ? "offline" : "polling";
              return (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "10px" }}>
                  {status === "ws" && <span className="glowingDot"></span>}
                  {status === "polling" && <span className="glowingDot" style={{ background: "var(--colorOrange)", boxShadow: "0 0 10px var(--colorOrange)" }}></span>}
                  {status === "offline" && <span className="glowingDotRed"></span>}
                  <span style={{ fontSize: "12px", color: status === "ws" ? "var(--colorSuccess)" : status === "polling" ? "var(--colorOrange)" : "var(--colorDanger)" }}>
                    {status === "ws" ? "WebSocket Live" : status === "polling" ? "Polling" : "Backend Offline"}
                  </span>
                </div>
              );
            })()}
          </div>
          {/* Auth user badge (Issue #6) */}
          {currentUser ? (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div className="statusBadge" style={{ background: "rgba(46,213,115,0.1)", color: "var(--colorSuccess)", border: "1px solid rgba(46,213,115,0.2)", cursor: "default" }}>
                &#x1F464; {currentUser.username} <span style={{ opacity: 0.7, fontSize: "10px" }}>({currentUser.role})</span>
              </div>
              <button
                onClick={() => {
                  sessionStorage.removeItem("gb_token");
                  localStorage.removeItem("gharbuddy_token");
                  localStorage.removeItem("gharbuddy_user");
                  setAuthToken("");
                  setCurrentUser(null);
                }}
                className="btn"
                style={{ fontSize: "11px", padding: "4px 10px" }}
                aria-label="Sign out"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              className="btn btnPrimary"
              style={{ fontSize: "12px", padding: "6px 14px" }}
            >
              &#x1F511; Sign In
            </button>
          )}
        </div>
      </header>

      {error && (
        <div style={{ background: "rgba(236,112,99,0.1)", border: "1px solid rgba(236,112,99,0.2)", borderRadius: "12px", padding: "16px", marginBottom: "24px", color: "var(--colorDanger)", fontSize: "14px" }}>
          ⚠️ <strong>Connection Error:</strong> {error}
          <div style={{ fontSize: "12px", color: "var(--textSecondary)", marginTop: "6px" }}>
            Make sure to start the FastAPI server using: <code>uvicorn Backend.MainFastApi:app --reload --port 8000</code>
          </div>
        </div>
      )}

      {/* Main Grid Section */}
      <main className="dashboardGrid">
        {/* Left Column: Appliances, energy stats, and simulator triggers */}
        <div className="columnLeft">
          <HouseholdMap devices={devices} systemState={systemState} lastTriggerResult={lastTriggerResult} onToggleDevice={handleToggleDevice} />
          <DeviceGrid devices={devices} onToggleDevice={handleToggleDevice} />
          <VoiceWidget />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
            <EnergyTracker energyStats={energyStats} />
            <SensorSimulator systemState={systemState} onStateChange={handleStateChange} />
          </div>
        </div>

        {/* Right Column: Bedrock AI Reasoning Log & WhatsApp mockup */}
        <div className="columnRight">
          <ReasoningPanel lastTriggerResult={lastTriggerResult} />
          <WhatsAppMock notifications={notifications} onApproveAction={handleApproveAction} />
        </div>
      </main>

      <footer style={{ marginTop: "48px", textAlign: "center", padding: "20px 0", borderTop: "1px solid rgba(255,255,255,0.05)", fontSize: "11px", color: "var(--textMuted)" }}>
        GharBuddy Smart Systems &bull; HackOn with Amazon Season 6.0 Submission &bull; Powered by AWS Bedrock Claude &amp; AWS IoT Core
      </footer>
      {showLogin && (
        <LoginModal
          onLogin={(u) => {
            const token = u.access_token || u.token || "";
            if (token) {
              sessionStorage.setItem("gb_token", token);
              setAuthToken(token);
            }
            setCurrentUser({ username: u.username, role: u.role });
            setShowLogin(false);
          }}
          onClose={() => setShowLogin(false)}
        />
      )}
    </div>
  );
}
