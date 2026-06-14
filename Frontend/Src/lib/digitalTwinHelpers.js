/**
 * digitalTwinHelpers.js
 *
 * Pure helper functions for the Live 2D Digital Twin (HouseholdMap).
 * All functions are stateless and side-effect-free, making them
 * independently testable without React or DOM.
 *
 * Requirements: 3.1–3.9, 4.1–4.8, 5.1–5.5, 6.1, 6.5, 8.1–8.8,
 *               9.1, 9.3, 10.1–10.4
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Maps motion sensor IDs to their corresponding room keys.
 * Requirements: 6.5
 */
export const SENSOR_TO_ROOM = {
  motion_living: "living",
  motion_bedroom: "bedroom",
  motion_bathroom: "bathroom",
  motion_kitchen: "kitchen",
  motion_pooja: "pooja",
};

// Internal sets used across helpers — defined once for performance.
const OFF_STANDBY = new Set(["OFF", "STANDBY"]);

// ---------------------------------------------------------------------------
// Helper 1: computeTotalLoad
// ---------------------------------------------------------------------------

/**
 * Computes the total household load in Watts, applying cultural status
 * overrides and excluding zero-watt active devices.
 *
 * Override rules (requirements 10.4):
 *   MEDITATION_DIMS        → 15 W
 *   STUDY_FOCUS_BRIGHTNESS → 45 W
 *   DO_NOT_DISTURB         → 5 W
 *   OFF / STANDBY          → 0 W
 *   all others             → device.wattage if > 0, else 0
 *
 * @param {Object} devices — { [deviceKey]: { status: string, wattage: number } }
 * @returns {number} non-negative total watts
 *
 * Requirements: 10.1, 10.4
 */
export function computeTotalLoad(devices) {
  if (!devices || typeof devices !== "object") return 0;

  let total = 0;

  for (const device of Object.values(devices)) {
    if (!device) continue;
    const status = device.status ?? "OFF";

    if (OFF_STANDBY.has(status)) {
      // OFF / STANDBY → contributes nothing
      continue;
    }

    if (status === "MEDITATION_DIMS") {
      total += 15;
    } else if (status === "STUDY_FOCUS_BRIGHTNESS") {
      total += 45;
    } else if (status === "DO_NOT_DISTURB") {
      total += 5;
    } else {
      // Any other active status → use rated wattage, floor at 0
      const w = typeof device.wattage === "number" ? device.wattage : 0;
      total += w > 0 ? w : 0;
    }
  }

  return total;
}

// ---------------------------------------------------------------------------
// Helper 2: getNodeStyle
// ---------------------------------------------------------------------------

/**
 * Returns the SVG fill and stroke colors for a device node based on its
 * current status and the host room's accent color.
 *
 * The function is total: every possible string input has a defined output
 * and it never throws.
 *
 * @param {string} status    — device status string
 * @param {string} roomColor — hex color of the host room, e.g. "#3498db"
 * @returns {{ fill: string, stroke: string }}
 *
 * Requirements: 3.1–3.8
 */
export function getNodeStyle(status, roomColor) {
  switch (status) {
    case "OFF":
    case "STANDBY":
      return {
        fill: "rgba(255,255,255,0.02)",
        stroke: "rgba(255,255,255,0.1)",
      };

    case "ON":
    case "NORMAL":
      // 10% alpha hex suffix "26" appended to the room color
      return {
        fill: `${roomColor}26`,
        stroke: `${roomColor}`,
      };

    case "MEDITATION_DIMS":
      return {
        fill: "rgba(255,200,55,0.15)",
        stroke: "#ffc837",
      };

    case "STUDY_FOCUS_BRIGHTNESS":
      return {
        fill: "rgba(52,152,219,0.2)",
        stroke: "#3498db",
      };

    case "DO_NOT_DISTURB":
      return {
        fill: "rgba(155,89,182,0.15)",
        stroke: "#9b59b6",
      };

    case "FAST_CHARGE":
      return {
        fill: "rgba(38,194,129,0.15)",
        stroke: "#26c281",
      };

    case "NORMAL_CHARGE":
      return {
        fill: "rgba(38,194,129,0.1)",
        stroke: "#26c281",
      };

    default:
      // Unknown status → same dimmed appearance as OFF/STANDBY; never throw
      return {
        fill: "rgba(255,255,255,0.02)",
        stroke: "rgba(255,255,255,0.1)",
      };
  }
}

// ---------------------------------------------------------------------------
// Helper 3: deriveRoomGlows
// ---------------------------------------------------------------------------

/**
 * Room-to-device mapping used internally by deriveRoomGlows.
 * Kitchen devices are omitted here because Kitchen glow is driven by
 * whistleCount, not device status.
 */
const ROOM_DEVICES = {
  living: ["television", "livingRoomLights", "speakerSystem"],
  bedroom: ["airConditioner"],
  bathroom: ["geyser"],
  pooja: ["poojaLights"],
  utility: ["waterMotor", "inverterBackup"],
};

/**
 * Returns an opacity map `{ [roomKey]: number }` for all rooms.
 *
 * Rules (requirements 4.1–4.7):
 *   - All devices OFF/STANDBY → 0
 *   - Any device active        → 1
 *   - Kitchen special:
 *       isFastingDay            → 0 (overrides whistle count)
 *       targetWhistles > 0      → Math.min(1, whistleCount / targetWhistles)
 *       otherwise               → 0
 *
 * @param {Object} devices     — device map
 * @param {Object} systemState — { whistleCount, targetWhistles, isFastingDay }
 * @returns {{ [roomKey]: number }}
 *
 * Requirements: 4.1–4.7
 */
export function deriveRoomGlows(devices, systemState) {
  const glows = {};
  const devs = devices && typeof devices === "object" ? devices : {};
  const sys = systemState && typeof systemState === "object" ? systemState : {};

  // Non-kitchen rooms
  for (const [roomKey, deviceKeys] of Object.entries(ROOM_DEVICES)) {
    const hasActive = deviceKeys.some((key) => {
      const device = devs[key];
      if (!device) return false;
      return !OFF_STANDBY.has(device.status ?? "OFF");
    });
    glows[roomKey] = hasActive ? 1 : 0;
  }

  // Kitchen — driven by whistle count, not device status
  const isFastingDay = Boolean(sys.isFastingDay);
  if (isFastingDay) {
    glows["kitchen"] = 0;
  } else {
    const targetWhistles =
      typeof sys.targetWhistles === "number" ? sys.targetWhistles : 0;
    const whistleCount =
      typeof sys.whistleCount === "number" ? sys.whistleCount : 0;

    if (targetWhistles > 0) {
      glows["kitchen"] = Math.min(1, whistleCount / targetWhistles);
    } else {
      glows["kitchen"] = 0;
    }
  }

  return glows;
}

// ---------------------------------------------------------------------------
// Helper 4: deriveCookerState
// ---------------------------------------------------------------------------

/**
 * Derives the pressure cooker's display state from whistle progress.
 *
 * @param {{ whistleCount?: number, targetWhistles?: number }} param
 * @returns {{ state: "dormant"|"active"|"done", progress: number }}
 *
 * Requirements: 5.1–5.5
 */
export function deriveCookerState({ whistleCount, targetWhistles } = {}) {
  const target =
    typeof targetWhistles === "number" ? targetWhistles : 0;
  const count =
    typeof whistleCount === "number" ? whistleCount : 0;

  if (target <= 0) {
    return { state: "dormant", progress: 0 };
  }

  if (count >= target) {
    return { state: "done", progress: 1 };
  }

  // target > 0 and count < target — division is safe
  return { state: "active", progress: count / target };
}

// ---------------------------------------------------------------------------
// Helper 5: derivePresence
// ---------------------------------------------------------------------------

/**
 * Scans eventHistory for motion sensor events and returns the Set of
 * room keys where occupancy is inferred.
 *
 * @param {Array|null|undefined} eventHistory
 * @returns {Set<string>}
 *
 * Requirements: 6.1, 6.5
 */
export function derivePresence(eventHistory) {
  const presence = new Set();

  if (!Array.isArray(eventHistory)) return presence;

  const motionPattern = /^motion_(.+)$/;

  for (const event of eventHistory) {
    if (!event || typeof event.sensorId !== "string") continue;

    const match = event.sensorId.match(motionPattern);
    if (!match) continue;

    // match[1] is the captured suffix, e.g. "living" from "motion_living"
    const roomKey = SENSOR_TO_ROOM[event.sensorId];
    if (roomKey) {
      presence.add(roomKey);
    }
    // Unrecognized sensor IDs are silently ignored
  }

  return presence;
}

// ---------------------------------------------------------------------------
// Helper 6: deriveAmbientTheme
// ---------------------------------------------------------------------------

/**
 * Derives the ambient background tint, border tint, and glow modifier
 * based on power status and simulated time.
 *
 * Priority order (highest wins):
 *   1. powerStatus === "INVERTER" → amber tint
 *   2. (GRID only) simulatedTime night  23:00–05:59 → dark tint, modifier 0.6
 *   3. (GRID only) simulatedTime evening 18:00–22:59 → amber tint
 *   4. (GRID only) simulatedTime morning 06:00–11:59 → warm-orange tint
 *   5. Afternoon (default) → no tint
 *
 * Malformed or missing simulatedTime falls back to afternoon without throwing.
 *
 * @param {Object} systemState — { powerStatus?: string, simulatedTime?: string }
 * @returns {{ bgTint: string|null, borderTint: string|null, glowModifier: number }}
 *
 * Requirements: 8.1, 8.2, 8.5–8.8
 */
export function deriveAmbientTheme(systemState) {
  const sys =
    systemState && typeof systemState === "object" ? systemState : {};

  // Priority 1: INVERTER overrides all time-based tints
  if (sys.powerStatus === "INVERTER") {
    return {
      bgTint: "rgba(255,200,55,0.06)",
      borderTint: "#ffc837",
      glowModifier: 1,
    };
  }

  // Priority 2+: time-based theming (GRID or unset)
  const timeStr =
    typeof sys.simulatedTime === "string" ? sys.simulatedTime : "";

  let hour = -1; // sentinel for "unparseable"
  try {
    const parts = timeStr.split(":");
    if (parts.length >= 2) {
      const parsed = parseInt(parts[0], 10);
      if (!isNaN(parsed) && parsed >= 0 && parsed <= 23) {
        hour = parsed;
      }
    }
  } catch (_) {
    // fall through to afternoon default
  }

  if (hour === -1) {
    // Malformed time → afternoon default
    return { bgTint: null, borderTint: null, glowModifier: 1 };
  }

  // Night: 23:00–05:59
  if (hour >= 23 || hour <= 5) {
    return {
      bgTint: "rgba(0,0,0,0.3)",
      borderTint: null,
      glowModifier: 0.6,
    };
  }

  // Evening: 18:00–22:59
  if (hour >= 18 && hour <= 22) {
    return {
      bgTint: "rgba(255,126,64,0.05)",
      borderTint: null,
      glowModifier: 1,
    };
  }

  // Morning: 06:00–11:59
  if (hour >= 6 && hour <= 11) {
    return {
      bgTint: "rgba(255,150,80,0.04)",
      borderTint: null,
      glowModifier: 1,
    };
  }

  // Afternoon: 12:00–17:59 (default)
  return { bgTint: null, borderTint: null, glowModifier: 1 };
}

// ---------------------------------------------------------------------------
// Helper 7: computeNextStatus
// ---------------------------------------------------------------------------

/**
 * Returns the next device status after a user toggle click.
 *
 * Rules (requirements 9.1, 9.3):
 *   - Kitchen room → null (read-only; never call onToggleDevice)
 *   - currentStatus === "OFF" → "ON"
 *   - any other status        → "OFF"
 *
 * @param {string} deviceKey     — device key (unused in logic, kept for API clarity)
 * @param {string} currentStatus — current device status
 * @param {string} roomKey       — room the device belongs to
 * @returns {string|null}
 *
 * Requirements: 9.1, 9.3
 */
export function computeNextStatus(deviceKey, currentStatus, roomKey) {
  if (roomKey === "kitchen") return null;

  return currentStatus === "OFF" ? "ON" : "OFF";
}
