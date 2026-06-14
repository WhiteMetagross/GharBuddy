/**
 * Integration test: App renders the correct connection-status badge
 * based on the value returned by useWebSocket.
 *
 * Validates: Requirements 6.1, 6.2, 6.3, 6.4
 *
 * Strategy: mock useWebSocket, BackendService, and all child components
 * so we can isolate just the badge rendering logic in App.jsx.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock useWebSocket — must come before import of App
// ---------------------------------------------------------------------------

vi.mock("../hooks/useWebSocket.js", () => ({
  useWebSocket: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Mock BackendService — no top-level variable references (hoisting issue)
// ---------------------------------------------------------------------------

vi.mock("../Services/BackendService", () => ({
  BackendService: {
    getDevices: vi.fn().mockResolvedValue({ geyser: { status: "OFF", wattage: 2000 } }),
    getEnergyStats: vi.fn().mockResolvedValue({
      totalSavedWh: 0,
      rupeesSaved: 0,
      peakPowerAvoidedW: 0,
      inverterBatteryCharge: 0,
    }),
    getNotifications: vi.fn().mockResolvedValue([]),
    getSystemState: vi.fn().mockResolvedValue({
      simulatedTime: "06:00:00",
      simulatedDate: "06-13",
      powerStatus: "GRID",
      whistleCount: 0,
      targetWhistles: 3,
      isFastingDay: false,
      festivalName: null,
      eventHistory: [],
    }),
    getVectorRules: vi.fn().mockResolvedValue([]),
  },
}));

// ---------------------------------------------------------------------------
// Mock all child components to avoid deep render tree issues
// ---------------------------------------------------------------------------

vi.mock("../Components/HouseholdMap", () => ({
  default: () => <div data-testid="mock-household-map" />,
}));
vi.mock("../Components/DeviceGrid", () => ({
  default: () => <div data-testid="mock-device-grid" />,
}));
vi.mock("../Components/EnergyTracker", () => ({
  default: () => <div data-testid="mock-energy-tracker" />,
}));
vi.mock("../Components/SensorSimulator", () => ({
  default: () => <div data-testid="mock-sensor-simulator" />,
}));
vi.mock("../Components/ReasoningPanel", () => ({
  default: () => <div data-testid="mock-reasoning-panel" />,
}));
vi.mock("../Components/WhatsAppMock", () => ({
  default: () => <div data-testid="mock-whatsapp-mock" />,
}));

import App from "../App.jsx";
import { useWebSocket } from "../hooks/useWebSocket.js";

/** Flush all pending promises (microtasks) */
const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
  vi.clearAllMocks();
});

describe("App connection-status badge", () => {
  it('displays "WebSocket Live" badge when isConnected is true', async () => {
    useWebSocket.mockReturnValue({ isConnected: true, lastMessage: null });

    await act(async () => {
      render(<App />);
      // Flush all pending promises (syncData, etc.)
      await flushPromises();
    });

    expect(await screen.findByText("WebSocket Live")).toBeInTheDocument();
  });

  it('displays "Polling" badge when isConnected is false and no error', async () => {
    useWebSocket.mockReturnValue({ isConnected: false, lastMessage: null });

    await act(async () => {
      render(<App />);
      await flushPromises();
    });

    expect(await screen.findByText("Polling")).toBeInTheDocument();
  });
});
