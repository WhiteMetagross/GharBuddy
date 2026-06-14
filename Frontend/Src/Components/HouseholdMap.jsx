import React, { useState, useRef, useEffect } from "react";
import {
  computeTotalLoad,
  deriveRoomGlows,
  deriveAmbientTheme,
  derivePresence,
  deriveCookerState,
  getNodeStyle,
  computeNextStatus,
  SENSOR_TO_ROOM,
} from "../lib/digitalTwinHelpers.js";

// ---------------------------------------------------------------------------
// Layout constants — SVG viewBox: "0 0 720 430"
// ---------------------------------------------------------------------------

const ROOMS = {
  living:   { x: 12,  y: 12,  w: 268, h: 182, label: "LIVING ROOM",   color: "#3498db", devices: ["television", "livingRoomLights", "speakerSystem"] },
  bedroom:  { x: 292, y: 12,  w: 262, h: 162, label: "BEDROOM",        color: "#26c281", devices: ["airConditioner"] },
  kitchen:  { x: 566, y: 12,  w: 142, h: 162, label: "KITCHEN",        color: "#ffc837", devices: ["cooker"] },
  bathroom: { x: 12,  y: 206, w: 152, h: 210, label: "BATHROOM",       color: "#ff7e40", devices: ["geyser"] },
  pooja:    { x: 176, y: 206, w: 158, h: 210, label: "POOJA ROOM",     color: "#ffc837", devices: ["poojaLights"] },
  utility:  { x: 346, y: 186, w: 362, h: 232, label: "UTILITY AREA",  color: "#9b59b6", devices: ["waterMotor", "inverterBackup"] },
};

const DOORWAYS = [
  { x1: 278, y1: 72,  x2: 292, y2: 72  },  // Living ↔ Bedroom
  { x1: 554, y1: 72,  x2: 566, y2: 72  },  // Bedroom ↔ Kitchen
  { x1: 72,  y1: 192, x2: 72,  y2: 206 },  // Living ↔ Bathroom
  { x1: 256, y1: 252, x2: 256, y2: 272 },  // Bathroom ↔ Pooja
  { x1: 426, y1: 198, x2: 426, y2: 186 },  // Pooja/Bathroom ↔ Utility
];

const DEVICE_POSITIONS = {
  television:       { roomKey: "living",   relX: 14,  relY: 42  },
  livingRoomLights: { roomKey: "living",   relX: 140, relY: 42  },
  speakerSystem:    { roomKey: "living",   relX: 78,  relY: 112 },
  airConditioner:   { roomKey: "bedroom",  relX: 72,  relY: 52  },
  cooker:           { roomKey: "kitchen",  relX: 16,  relY: 48  },
  geyser:           { roomKey: "bathroom", relX: 18,  relY: 52  },
  poojaLights:      { roomKey: "pooja",    relX: 22,  relY: 52  },
  waterMotor:       { roomKey: "utility",  relX: 18,  relY: 52  },
  inverterBackup:   { roomKey: "utility",  relX: 18,  relY: 126 },
};

const PRESENCE_POSITIONS = {
  living:   { x: 272, y: 88  },
  bedroom:  { x: 296, y: 88  },
  bathroom: { x: 72,  y: 202 },
  kitchen:  { x: 570, y: 28  },
  pooja:    { x: 256, y: 256 },
};

// ---------------------------------------------------------------------------
// DeviceNode — internal SVG sub-component
// ---------------------------------------------------------------------------

function DeviceNode({ deviceKey, device, x, y, isPulsing, roomColor, onToggle, readOnly }) {
  const safeDevice = device || { name: deviceKey, status: "OFF", wattage: 0 };
  const { fill, stroke } = getNodeStyle(safeDevice.status, roomColor);

  const ICON_MAP = {
    geyser: "🚿", poojaLights: "🪔", waterMotor: "⛲",
    inverterBackup: "🔋", livingRoomLights: "💡", television: "📺",
    airConditioner: "❄️", speakerSystem: "🔊", cooker: "🫕"
  };
  const icon = ICON_MAP[deviceKey] || "🔌";

  const isActive = safeDevice.status !== "OFF" && safeDevice.status !== "STANDBY";

  // Compact status labels for the small SVG node — long enum names overflow the box otherwise
  const statusLabelMap = {
    DO_NOT_DISTURB: "Do Not Disturb",
    NORMAL_CHARGE:  "Charging",
    FAST_CHARGE:    "Fast Charge",
    MEDITATION_DIMS: "Pooja Dim",
    STUDY_FOCUS_BRIGHTNESS: "Focus",
  };
  const statusDisplay = statusLabelMap[safeDevice.status] || safeDevice.status.replace(/_/g, " ");
  const wattDisplay = safeDevice.wattage > 0 ? `${safeDevice.wattage}W` : "";

  // Truncate device name + combined status to fit within ~73px text region of the 105px rect
  const truncate = (s, max) => (s && s.length > max ? `${s.slice(0, max - 1)}…` : s || "");
  const nameText = truncate(safeDevice.name, 13);
  const statusLine = `${wattDisplay ? `${wattDisplay} · ` : ""}${statusDisplay}`;
  const statusText = truncate(statusLine, 16);

  const handleClick = () => {
    if (readOnly) return;
    const next = computeNextStatus(deviceKey, safeDevice.status, readOnly ? "kitchen" : "other");
    if (next !== null && onToggle) onToggle(deviceKey, next);
  };

  return (
    <g
      transform={`translate(${x}, ${y})`}
      cursor={readOnly ? "default" : "pointer"}
      onClick={handleClick}
    >
      {/* Outer glow when active */}
      {isActive && (
        <rect
          x="-3" y="-3" width="111" height="50" rx="9"
          fill="none"
          stroke={stroke}
          strokeWidth="1"
          opacity="0.3"
        />
      )}

      {/* Main background */}
      <rect
        x="0" y="0" width="105" height="44" rx="6"
        fill={fill}
        stroke={stroke}
        strokeWidth={isActive ? "1.5" : "1"}
        className="deviceNodeTransition"
      />

      {/* Top accent bar when active */}
      {isActive && (
        <rect x="0" y="0" width="105" height="3" rx="3"
          fill={stroke} opacity="0.8"
        />
      )}

      {/* DO_NOT_DISTURB overlay */}
      {safeDevice.status === "DO_NOT_DISTURB" && (
        <text x="90" y="14" fontSize="10" style={{ userSelect: "none" }}>🔇</text>
      )}

      {/* FAST_CHARGE bar */}
      {safeDevice.status === "FAST_CHARGE" && (
        <rect x="2" y="2" width="5" height="40" rx="2"
          fill="#26c281" opacity="0.7" className="chargeBarAnim"
        />
      )}

      {/* Icon */}
      <text x="8" y="27" fontSize="16" style={{ userSelect: "none" }}>{icon}</text>

      {/* Device name */}
      <text x="30" y="18" fill="rgba(245,246,250,0.95)" fontSize="9" fontWeight="700">{nameText}</text>

      {/* Status + wattage */}
      <text x="30" y="31" fill={isActive ? stroke : "rgba(160,165,181,0.7)"} fontSize="7.5" fontWeight={isActive ? "600" : "400"}>
        {statusText}
      </text>

      {/* AI pulse ring */}
      {isPulsing && (
        <circle cx="52" cy="22" r="10" fill="none"
          stroke={roomColor} strokeWidth="2" opacity="0"
          className="pulseRingAnim"
        />
      )}

      <title>{`${safeDevice.name} | ${safeDevice.status} | ${safeDevice.wattage}W`}</title>
    </g>
  );
}

// ---------------------------------------------------------------------------
// HouseholdMap — main export
// ---------------------------------------------------------------------------

export default function HouseholdMap({ devices, systemState, lastTriggerResult, onToggleDevice }) {
  const safeSystemState = systemState || {
    simulatedTime: "12:00:00",
    powerStatus: "GRID",
    whistleCount: 0,
    targetWhistles: 0,
    isFastingDay: false,
    festivalName: null,
    eventHistory: []
  };

  const [pulseTarget, setPulseTarget] = useState(null);
  const prevTriggerRef = useRef(null);
  const [poojaHighlight, setPoojaHighlight] = useState(false);

  const totalLoad = computeTotalLoad(devices);
  const roomGlows = deriveRoomGlows(devices, safeSystemState);
  const cookerState = deriveCookerState(safeSystemState);
  const presenceMap = derivePresence(safeSystemState.eventHistory);
  const ambientTheme = deriveAmbientTheme(safeSystemState);

  const kitchenRoom = ROOMS.kitchen;
  const cookerPos = DEVICE_POSITIONS.cooker;
  const cookerAbsX = kitchenRoom.x + cookerPos.relX;
  const cookerAbsY = kitchenRoom.y + cookerPos.relY;

  useEffect(() => {
    if (!lastTriggerResult || lastTriggerResult === prevTriggerRef.current) return;
    const decision = lastTriggerResult.decision;
    if (!decision) return;
    prevTriggerRef.current = lastTriggerResult;
    const target = decision.targetDevice === "allDevices" ? "all" : decision.targetDevice;
    setPulseTarget(target);
    if (decision.actionId === "activatePoojaMode") {
      setPoojaHighlight(true);
      setTimeout(() => setPoojaHighlight(false), 3000);
    }
    const timer = setTimeout(() => setPulseTarget(null), 1200);
    return () => clearTimeout(timer);
  }, [lastTriggerResult]);

  const loadColor = totalLoad > 1500 ? "#ec7063" : totalLoad > 1000 ? "#ffc837" : "#26c281";

  return (
    <div className="glassCard digitalTwinCard" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "var(--textPrimary)" }}>
              🏠 Live 2D Digital Twin
            </h2>
            {/* Live pulse indicator */}
            <span style={{
              display: "inline-flex", alignItems: "center", gap: "4px",
              fontSize: "10px", fontWeight: "700", color: "#26c281",
              background: "rgba(38,194,129,0.1)", border: "1px solid rgba(38,194,129,0.2)",
              borderRadius: "10px", padding: "2px 7px"
            }}>
              <span className="glowingDot" style={{ width: "5px", height: "5px" }}></span>
              LIVE
            </span>
            {safeSystemState.powerStatus === "INVERTER" && (
              <span data-testid="inverter-badge" style={{
                display: "inline-flex", alignItems: "center", gap: "4px",
                fontSize: "10px", fontWeight: "700", color: "#ffc837",
                background: "rgba(255,200,55,0.1)", border: "1px solid rgba(255,200,55,0.3)",
                borderRadius: "10px", padding: "2px 7px"
              }}>⚡ INVERTER</span>
            )}
          </div>
          <p style={{ fontSize: "10px", color: "var(--textMuted)", marginTop: "3px" }}>
            Click any appliance to toggle it · Real-time sensor sync
          </p>
        </div>

        {/* Power load widget */}
        <div style={{
          textAlign: "right",
          background: "rgba(0,0,0,0.3)",
          border: `1px solid ${loadColor}33`,
          borderRadius: "10px",
          padding: "8px 14px"
        }}>
          <div style={{ fontSize: "9px", color: "var(--textMuted)", textTransform: "uppercase", fontWeight: "700", letterSpacing: "1px" }}>
            Home Load
          </div>
          <div style={{ fontSize: "22px", fontWeight: "800", color: loadColor, lineHeight: 1.2 }}>
            {totalLoad}<span style={{ fontSize: "11px", fontWeight: "500", marginLeft: "3px", opacity: 0.7 }}>W</span>
          </div>
        </div>
      </div>

      {/* SVG Map */}
      <div style={{
        background: "linear-gradient(145deg, #090a0f 0%, #0c0d14 100%)",
        borderRadius: "12px",
        border: "1px solid rgba(255,255,255,0.07)",
        overflow: "hidden",
        position: "relative",
        boxShadow: "inset 0 0 40px rgba(0,0,0,0.5)"
      }}>
        <svg viewBox="0 0 720 430" width="100%" style={{ display: "block" }}>
          <defs>
            {/* Room glow gradients */}
            {Object.entries(ROOMS).map(([roomKey, room]) => (
              <radialGradient key={roomKey} id={`${roomKey}Glow`} cx="50%" cy="50%" r="65%">
                <stop offset="0%" stopColor={room.color} stopOpacity="0.22" />
                <stop offset="100%" stopColor={room.color} stopOpacity="0" />
              </radialGradient>
            ))}

            {/* Floor grid pattern */}
            <pattern id="floorGrid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="0.5"/>
            </pattern>

            {/* Wall inner shadow filter */}
            <filter id="wallGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur"/>
              <feComposite in="SourceGraphic" in2="blur" operator="over"/>
            </filter>

            {/* Device node shadow */}
            <filter id="nodeShadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.4"/>
            </filter>
          </defs>

          {/* Global floor grid */}
          <rect x="0" y="0" width="720" height="430" fill="url(#floorGrid)" />

          {/* Ambient tint */}
          {ambientTheme.bgTint && (
            <rect x="0" y="0" width="720" height="430"
              fill={ambientTheme.bgTint} pointerEvents="none"
              style={{ transition: "fill 800ms ease" }}
            />
          )}

          {/* Room floor fills — subtle colored floor per room */}
          {Object.entries(ROOMS).map(([roomKey, room]) => {
            const glowOpacity = roomKey === "pooja" && poojaHighlight
              ? 1
              : (roomGlows[roomKey] ?? 0);
            return (
              <g key={`floor-${roomKey}`}>
                {/* Base floor */}
                <rect
                  x={room.x + 1} y={room.y + 1}
                  width={room.w - 2} height={room.h - 2}
                  fill={`${room.color}08`}
                  rx="5"
                />
                {/* Glow overlay */}
                <rect
                  x={room.x + 1} y={room.y + 1}
                  width={room.w - 2} height={room.h - 2}
                  fill={`url(#${roomKey}Glow)`}
                  style={{ opacity: glowOpacity, transition: "opacity 600ms ease" }}
                  rx="5"
                />
              </g>
            );
          })}

          {/* Room walls — double-line effect */}
          {Object.entries(ROOMS).map(([roomKey, room]) => {
            const isGlowing = (roomGlows[roomKey] ?? 0) > 0 || (roomKey === "pooja" && poojaHighlight);
            const wallColor = isGlowing ? room.color : "rgba(255,255,255,0.1)";
            const wallOpacity = isGlowing ? 0.6 : 1;
            return (
              <g key={`wall-${roomKey}`}>
                {/* Outer wall (thicker, darker) */}
                <rect
                  x={room.x} y={room.y} width={room.w} height={room.h}
                  fill="none"
                  stroke="rgba(0,0,0,0.6)"
                  strokeWidth="4"
                  rx="6"
                />
                {/* Inner wall (colored) */}
                <rect
                  x={room.x} y={room.y} width={room.w} height={room.h}
                  fill="none"
                  stroke={wallColor}
                  strokeWidth="1.5"
                  opacity={wallOpacity}
                  rx="6"
                  style={{ transition: "stroke 600ms ease, opacity 600ms ease" }}
                />
              </g>
            );
          })}

          {/* Doorways */}
          {DOORWAYS.map((d, i) => (
            <line key={`door-${i}`}
              x1={d.x1} y1={d.y1} x2={d.x2} y2={d.y2}
              stroke="#090a0f" strokeWidth="7"
            />
          ))}

          {/* Room labels with background pill */}
          {Object.entries(ROOMS).map(([roomKey, room]) => {
            const isGlowing = (roomGlows[roomKey] ?? 0) > 0;
            return (
              <g key={`label-${roomKey}`}>
                <rect
                  x={room.x + 8} y={room.y + 7}
                  width={room.label.length * 6.2 + 10} height="14"
                  rx="3"
                  fill={isGlowing ? `${room.color}20` : "rgba(0,0,0,0.3)"}
                  style={{ transition: "fill 600ms ease" }}
                />
                <text
                  x={room.x + 13} y={room.y + 18}
                  fill={isGlowing ? room.color : "rgba(160,165,181,0.7)"}
                  fontSize="8.5" fontWeight="800" letterSpacing="0.8"
                  style={{ transition: "fill 600ms ease" }}
                >
                  {room.label}
                </text>
              </g>
            );
          })}

          {/* Pooja icon */}
          <text x={ROOMS.pooja.x + 8} y={ROOMS.pooja.y + 34} fontSize="12" style={{ userSelect: "none" }}>🪔</text>

          {/* Festival watermark */}
          {safeSystemState.festivalName && (
            <text x="360" y="222" textAnchor="middle" fontSize="52" fontWeight="800"
              fill="rgba(255,200,55,0.06)" className="festivalShimmerAnim"
              style={{ userSelect: "none", pointerEvents: "none" }}>
              {safeSystemState.festivalName}
            </text>
          )}

          {/* Fasting badge */}
          {safeSystemState.isFastingDay && (
            <text data-testid="fasting-badge"
              x={ROOMS.kitchen.x + 10} y={ROOMS.kitchen.y + 38}
              fill="rgba(255,200,55,0.9)" fontSize="14" style={{ userSelect: "none" }}>
              🙏
            </text>
          )}

          {/* Device Nodes */}
          {Object.entries(DEVICE_POSITIONS)
            .filter(([key]) => key !== "cooker")
            .map(([deviceKey, pos]) => {
              const room = ROOMS[pos.roomKey];
              const absX = room.x + pos.relX;
              const absY = room.y + pos.relY;
              const isPulsing = pulseTarget === deviceKey || pulseTarget === "all";
              return (
                <DeviceNode
                  key={deviceKey}
                  deviceKey={deviceKey}
                  device={devices[deviceKey]}
                  x={absX} y={absY}
                  isPulsing={isPulsing}
                  roomColor={room.color}
                  onToggle={onToggleDevice}
                  readOnly={pos.roomKey === "kitchen"}
                />
              );
            })
          }

          {/* Cooker Node */}
          {(() => {
            const { state, progress } = cookerState;
            const radius = 18;
            const circumference = 2 * Math.PI * radius;
            const dashOffset = circumference * (1 - progress);
            const isActive = state !== "dormant";
            return (
              <g transform={`translate(${cookerAbsX}, ${cookerAbsY})`} cursor="default">
                {isActive && (
                  <rect x="-3" y="-3" width="111" height="50" rx="9"
                    fill="none"
                    stroke={state === "done" ? "#26c281" : "#ffc837"}
                    strokeWidth="1" opacity="0.3"
                  />
                )}
                <rect x="0" y="0" width="105" height="44" rx="6"
                  fill={state === "dormant" ? "rgba(255,255,255,0.02)" : state === "done" ? "rgba(38,194,129,0.12)" : "rgba(255,200,55,0.12)"}
                  stroke={state === "dormant" ? "rgba(255,255,255,0.1)" : state === "done" ? "#26c281" : "#ffc837"}
                  strokeWidth="1.5"
                />
                {isActive && (
                  <rect x="0" y="0" width="105" height="3" rx="3"
                    fill={state === "done" ? "#26c281" : "#ffc837"} opacity="0.8"
                  />
                )}
                {state === "active" && (
                  <circle cx="52" cy="22" r={radius}
                    fill="none" stroke="#ffc837" strokeWidth="3"
                    strokeDasharray={circumference}
                    strokeDashoffset={dashOffset}
                    strokeLinecap="round"
                    transform="rotate(-90 52 22)"
                    style={{ transition: "stroke-dashoffset 400ms ease" }}
                    className="cookerArcAnim"
                  />
                )}
                <text x="8" y="27" fontSize="16" style={{ userSelect: "none" }}>🫕</text>
                <text x="30" y="18" fill="rgba(245,246,250,0.95)" fontSize="9" fontWeight="700">Cooker</text>
                <text x="30" y="31" fill={state === "done" ? "#26c281" : state === "active" ? "#ffc837" : "rgba(160,165,181,0.6)"} fontSize="7.5" fontWeight="600">
                  {state === "done" ? "✅ Done!" : state === "active" ? `${safeSystemState.whistleCount}/${safeSystemState.targetWhistles} whistles` : "Idle"}
                </text>
                <title>{`Cooker | ${safeSystemState.whistleCount}/${safeSystemState.targetWhistles} whistles | ${state}`}</title>
              </g>
            );
          })()}

          {/* Presence Indicators */}
          {Object.entries(PRESENCE_POSITIONS).map(([roomKey, pos]) => {
            const isPresent = presenceMap.has(roomKey);
            return (
              <g key={`presence-${roomKey}`}>
                {isPresent && (
                  <circle cx={pos.x} cy={pos.y} r="9"
                    fill={ROOMS[roomKey]?.color ?? "#fff"}
                    opacity="0.08"
                    className="presencePulseAnim"
                  />
                )}
                <circle
                  cx={pos.x} cy={pos.y} r="4"
                  fill={ROOMS[roomKey]?.color ?? "#fff"}
                  opacity={isPresent ? 0.9 : 0}
                  style={{ transition: "opacity 400ms ease" }}
                  className={isPresent ? "presencePulseAnim" : ""}
                />
              </g>
            );
          })}

          {/* HUD corner brackets */}
          <g stroke="rgba(52,152,219,0.3)" strokeWidth="1.5" fill="none">
            <path d="M 4 16 L 4 4 L 16 4" />
            <path d="M 704 16 L 704 4 L 692 4" />
            <path d="M 4 414 L 4 426 L 16 426" />
            <path d="M 704 414 L 704 426 L 692 426" />
          </g>

          {/* Scan line effect — subtle horizontal line that drifts */}
          <rect x="0" y="0" width="720" height="1"
            fill="rgba(255,255,255,0.04)" pointerEvents="none"
            className="scanlineAnim"
          />

        </svg>
      </div>

      {/* Legend row */}
      <div style={{
        display: "flex", gap: "10px", flexWrap: "wrap",
        justifyContent: "center", fontSize: "10px", color: "var(--textMuted)"
      }}>
        {Object.entries(ROOMS).map(([key, room]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{
              width: "7px", height: "7px", borderRadius: "50%",
              background: room.color,
              boxShadow: (roomGlows[key] ?? 0) > 0 ? `0 0 6px ${room.color}` : "none",
              transition: "box-shadow 600ms ease"
            }}></span>
            <span>{room.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
