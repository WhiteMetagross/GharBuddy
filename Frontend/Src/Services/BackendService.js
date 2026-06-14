const baseUrl = ""; // Handled dynamically via Vite server proxy

// Helper: build auth headers for mutation calls
const _authHeaders = (token) =>
  token
    ? { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }
    : { "Content-Type": "application/json" };

export const BackendService = {
  // Auth token storage (in-memory for demo)
  _token: null,

  async login(username, password) {
    const res = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) throw new Error("Login failed");
    const data = await res.json();
    this._token = data.access_token;
    return data;
  },

  async verifyToken() {
    const token = sessionStorage.getItem("gb_token") || localStorage.getItem("gharbuddy_token") || this._token;
    if (!token) return null;
    const res = await fetch(`${baseUrl}/api/auth/verify`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!res.ok) return null;
    return res.json();
  },

  getAuthHeaders() {
    const token = sessionStorage.getItem("gb_token") || localStorage.getItem("gharbuddy_token") || this._token;
    if (token) {
      return { "Content-Type": "application/json", "Authorization": `Bearer ${token}` };
    }
    return { "Content-Type": "application/json" };
  },

  async getAuthStatus() {
    const res = await fetch(`${baseUrl}/api/auth/status`);
    if (!res.ok) throw new Error("Failed to get auth status");
    return res.json();
  },

  async getDevices() {
    const res = await fetch(`${baseUrl}/api/devices`);
    if (!res.ok) throw new Error("Failed to fetch device data");
    return res.json();
  },

  async toggleDevice(deviceId, status, token = "") {
    const res = await fetch(`${baseUrl}/api/devices/toggle`, {
      method: "POST",
      headers: _authHeaders(token || this.getAuthHeaders()["Authorization"]?.replace("Bearer ", "") || ""),
      body: JSON.stringify({ deviceId, status })
    });
    if (!res.ok) throw new Error("Failed to toggle device");
    return res.json();
  },

  async getEnergyStats() {
    const res = await fetch(`${baseUrl}/api/energy/stats`);
    if (!res.ok) throw new Error("Failed to fetch energy stats");
    return res.json();
  },

  async getNotifications() {
    const res = await fetch(`${baseUrl}/api/notifications`);
    if (!res.ok) throw new Error("Failed to fetch notifications");
    return res.json();
  },

  async getSystemState() {
    const res = await fetch(`${baseUrl}/api/system/state`);
    if (!res.ok) throw new Error("Failed to fetch system state");
    return res.json();
  },

  async updateSettings(settings, token = "") {
    const res = await fetch(`${baseUrl}/api/settings/update`, {
      method: "POST",
      headers: _authHeaders(token || this.getAuthHeaders()["Authorization"]?.replace("Bearer ", "") || ""),
      body: JSON.stringify(settings)
    });
    if (!res.ok) throw new Error("Failed to sync settings");
    return res.json();
  },

  async triggerSensor(sensorId, value, token = "") {
    const res = await fetch(`${baseUrl}/api/sensors/trigger`, {
      method: "POST",
      headers: _authHeaders(token || this.getAuthHeaders()["Authorization"]?.replace("Bearer ", "") || ""),
      body: JSON.stringify({ sensorId, value })
    });
    if (!res.ok) throw new Error("Failed to dispatch sensor trigger");
    return res.json();
  },

  async approveAction(actionId, approve, token = "") {
    const res = await fetch(`${baseUrl}/api/actions/override`, {
      method: "POST",
      headers: _authHeaders(token || this.getAuthHeaders()["Authorization"]?.replace("Bearer ", "") || ""),
      body: JSON.stringify({ actionId, approve })
    });
    if (!res.ok) throw new Error("Failed to send action override");
    return res.json();
  },

  async addVectorRule(content, category, token = "") {
    const res = await fetch(`${baseUrl}/api/vectors/add`, {
      method: "POST",
      headers: _authHeaders(token || this.getAuthHeaders()["Authorization"]?.replace("Bearer ", "") || ""),
      body: JSON.stringify({ content, category })
    });
    if (!res.ok) throw new Error("Failed to add vector rule");
    return res.json();
  },

  async getVectorRules() {
    const res = await fetch(`${baseUrl}/api/vectors`);
    if (!res.ok) throw new Error("Failed to fetch vector rules");
    return res.json();
  },

  async getCaregiverStatus() {
    const res = await fetch(`${baseUrl}/api/safety/caregiver`);
    if (!res.ok) throw new Error("Failed to fetch caregiver status");
    return res.json();
  },

  async resetCaregiverMonitor() {
    const res = await fetch(`${baseUrl}/api/safety/caregiver/reset`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to reset caregiver monitor");
    return res.json();
  },

  async transcribeVoice(audioBlob) {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    const res = await fetch(`${baseUrl}/api/voice/transcribe`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to transcribe voice");
    return res.json();
  },

  async getLoadSheddingRisk() {
    const res = await fetch(`${baseUrl}/api/inverter/load-shedding-risk`);
    if (!res.ok) throw new Error("Failed to fetch load shedding risk");
    return res.json();
  },

  async getLoadSheddingSchedule() {
    const res = await fetch(`${baseUrl}/api/inverter/schedule`);
    if (!res.ok) throw new Error("Failed to fetch schedule");
    return res.json();
  },

  async getCacheDiagnostics() {
    const res = await fetch(`${baseUrl}/api/cache/diagnostics`);
    if (!res.ok) throw new Error("Failed to fetch cache diagnostics");
    return res.json();
  },

  async getVectorStats() {
    const res = await fetch(`${baseUrl}/api/vectors/stats`);
    if (!res.ok) throw new Error("Failed to fetch vector stats");
    return res.json();
  },
};
