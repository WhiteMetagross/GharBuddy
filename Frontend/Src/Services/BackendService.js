const baseUrl = ""; // Handled dynamically via Vite server proxy

export const BackendService = {
  async getDevices() {
    const res = await fetch(`${baseUrl}/api/devices`);
    if (!res.ok) throw new Error("Failed to fetch device data");
    return res.json();
  },

  async toggleDevice(deviceId, status) {
    const res = await fetch(`${baseUrl}/api/devices/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

  async updateSettings(settings) {
    const res = await fetch(`${baseUrl}/api/settings/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings)
    });
    if (!res.ok) throw new Error("Failed to sync settings");
    return res.json();
  },

  async triggerSensor(sensorId, value) {
    const res = await fetch(`${baseUrl}/api/sensors/trigger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sensorId, value })
    });
    if (!res.ok) throw new Error("Failed to dispatch sensor trigger");
    return res.json();
  },

  async approveAction(actionId, approve) {
    const res = await fetch(`${baseUrl}/api/actions/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actionId, approve })
    });
    if (!res.ok) throw new Error("Failed to send action override");
    return res.json();
  },

  async addVectorRule(content, category) {
    const res = await fetch(`${baseUrl}/api/vectors/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
};
