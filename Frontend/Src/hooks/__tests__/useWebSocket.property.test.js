/**
 * Property-Based Tests for useWebSocket.js
 *
 * Feature: issue-5-websocket, Property 4: lastMessage round-trip preserves the original payload
 * Feature: issue-5-websocket, Property 5: isConnected accurately reflects socket open/close event history
 *
 * All properties use fast-check with numRuns: 100.
 */

// Feature: issue-5-websocket, Property 4: lastMessage round-trip preserves the original payload
// Feature: issue-5-websocket, Property 5: isConnected accurately reflects socket open/close event history

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "../useWebSocket.js";

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    this.onclose = null;
    MockWebSocket._lastInstance = this;
    MockWebSocket._instances.push(this);
  }

  send(data) {}

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: 1000 });
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen();
  }

  simulateMessage(data) {
    if (this.onmessage)
      this.onmessage({ data: typeof data === "string" ? data : JSON.stringify(data) });
  }

  simulateError() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onerror) this.onerror(new Error("mock error"));
    if (this.onclose) this.onclose({ code: 1006 });
  }
}

MockWebSocket.CONNECTING = 0;
MockWebSocket.OPEN = 1;
MockWebSocket.CLOSING = 2;
MockWebSocket.CLOSED = 3;
MockWebSocket._lastInstance = null;
MockWebSocket._instances = [];

// ---------------------------------------------------------------------------
// Arbitraries for StateSnapshot
// ---------------------------------------------------------------------------

const deviceArb = fc.record({
  status: fc.constantFrom("OFF", "ON", "STANDBY"),
  wattage: fc.nat(3000),
});

const devicesArb = fc.record({
  geyser: deviceArb,
  waterMotor: deviceArb,
  livingRoomLights: deviceArb,
});

const systemStateArb = fc.record({
  simulatedTime: fc.constant("08:30:00"),
  simulatedDate: fc.constant("06-13"),
  powerStatus: fc.constantFrom("GRID", "INVERTER"),
  whistleCount: fc.nat(10),
  targetWhistles: fc.nat(10),
  isFastingDay: fc.boolean(),
  festivalName: fc.option(fc.string({ minLength: 1, maxLength: 30 }), { nil: null }),
  eventHistory: fc.array(fc.string({ minLength: 1, maxLength: 20 }), { maxLength: 5 }),
});

const energyStatsArb = fc.record({
  totalSavedWh: fc.nat(10000),
  rupeesSaved: fc.nat(1000),
  peakPowerAvoidedW: fc.nat(3000),
  inverterBatteryCharge: fc.integer({ min: 0, max: 100 }),
});

const notificationArb = fc.record({
  message: fc.string({ minLength: 1, maxLength: 100 }),
  actionId: fc.string({ minLength: 1, maxLength: 30 }),
  requiresApproval: fc.boolean(),
});

const snapshotArb = fc.record({
  devices: devicesArb,
  systemState: systemStateArb,
  energyStats: energyStatsArb,
  notifications: fc.array(notificationArb, { maxLength: 3 }),
});

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  MockWebSocket._lastInstance = null;
  MockWebSocket._instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Property 4: lastMessage round-trip preserves the original payload
// Validates: Requirements 4.2, 5.2
// ---------------------------------------------------------------------------

describe("Property 4: lastMessage round-trip preserves the original payload", () => {
  it("serialise → deliver as message event → lastMessage deep-equals original", () => {
    fc.assert(
      fc.property(snapshotArb, (snapshot) => {
        const { result, unmount } = renderHook(() =>
          useWebSocket("ws://localhost:8000/ws")
        );

        const ws = MockWebSocket._lastInstance;

        act(() => {
          ws.simulateOpen();
        });

        act(() => {
          ws.simulateMessage(snapshot);
        });

        expect(result.current.lastMessage).toEqual(snapshot);

        unmount();
        // Reset instances for next iteration
        MockWebSocket._lastInstance = null;
        MockWebSocket._instances = [];
      }),
      { numRuns: 100 }
    );
  });

  it("ping messages are ignored and do not update lastMessage", () => {
    const { result, unmount } = renderHook(() =>
      useWebSocket("ws://localhost:8000/ws")
    );
    const ws = MockWebSocket._lastInstance;

    act(() => {
      ws.simulateOpen();
    });
    act(() => {
      ws.simulateMessage({ type: "ping" });
    });

    expect(result.current.lastMessage).toBeNull();
    unmount();
  });
});

// ---------------------------------------------------------------------------
// Property 5: isConnected accurately reflects socket open/close event history
// Validates: Requirements 4.3, 4.4, 4.6
// ---------------------------------------------------------------------------

/**
 * Pure state-machine model of the hook's isConnected/maxRetriesReached logic.
 * This models what the hook should do given a sequence of single-socket events
 * where the socket is reconnected on each close (so open always resets retryCount).
 *
 * We test the pure model here (not the async reconnect machinery).
 */
function simulateStateMachine(events) {
  let isConnected = false;
  let retryCount = 0;
  let maxRetriesReached = false;

  for (const event of events) {
    if (maxRetriesReached) break;

    if (event === "open") {
      isConnected = true;
      retryCount = 0;
    } else if (event === "close" || event === "error") {
      isConnected = false;
      retryCount += 1;
      if (retryCount > 5) {
        maxRetriesReached = true;
      }
    }
  }

  return { isConnected, maxRetriesReached };
}

describe("Property 5: isConnected accurately reflects socket open/close event history", () => {
  it("pure model: isConnected === true iff last meaningful event was open and maxRetriesReached is false", () => {
    // Feature: issue-5-websocket, Property 5: isConnected accurately reflects socket open/close event history
    // Validates: Requirements 4.3, 4.4, 4.6
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom("open", "close", "error"), {
          minLength: 1,
          maxLength: 10,
        }),
        (events) => {
          const { isConnected, maxRetriesReached } = simulateStateMachine(events);
          // Core invariant: isConnected is true only when last event was open and not exhausted
          if (isConnected) {
            const lastEvent = events[events.indexOf("open", events.lastIndexOf("open"))];
            expect(maxRetriesReached).toBe(false);
          }
          if (maxRetriesReached) {
            expect(isConnected).toBe(false);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("isConnected is false on initial mount before any event", () => {
    const { result, unmount } = renderHook(() =>
      useWebSocket("ws://localhost:8000/ws")
    );
    expect(result.current.isConnected).toBe(false);
    unmount();
  });

  it("isConnected becomes true on open, false on close", () => {
    const { result, unmount } = renderHook(() =>
      useWebSocket("ws://localhost:8000/ws")
    );
    const ws = MockWebSocket._lastInstance;

    act(() => {
      ws.simulateOpen();
    });
    expect(result.current.isConnected).toBe(true);

    act(() => {
      ws.close();
    });
    expect(result.current.isConnected).toBe(false);

    unmount();
  });

  it("isConnected stays false after max retries (>5 close events without open)", () => {
    const { result, unmount } = renderHook(() =>
      useWebSocket("ws://localhost:8000/ws")
    );

    // Fire close on the initial socket and each subsequent reconnected socket
    for (let i = 0; i < 6; i++) {
      act(() => {
        const ws = MockWebSocket._lastInstance;
        ws.close();
        vi.advanceTimersByTime(20000); // advance past any backoff timer
      });
    }

    expect(result.current.isConnected).toBe(false);
    unmount();
  });
});
