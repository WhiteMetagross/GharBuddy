/**
 * Smoke tests for useWebSocket hook.
 * Validates basic mount, open, and message event behaviour with a mock WebSocket.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "../useWebSocket.js";

// ---------------------------------------------------------------------------
// Minimal MockWebSocket
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
  }

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
}

MockWebSocket.CONNECTING = 0;
MockWebSocket.OPEN = 1;
MockWebSocket.CLOSING = 2;
MockWebSocket.CLOSED = 3;
MockWebSocket._lastInstance = null;

beforeEach(() => {
  MockWebSocket._lastInstance = null;
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Smoke tests
// ---------------------------------------------------------------------------

describe("useWebSocket smoke tests", () => {
  it("isConnected becomes true on open event", () => {
    const { result, unmount } = renderHook(() =>
      useWebSocket("ws://localhost:8000/ws")
    );

    expect(result.current.isConnected).toBe(false);

    act(() => {
      MockWebSocket._lastInstance.simulateOpen();
    });

    expect(result.current.isConnected).toBe(true);
    unmount();
  });

  it("lastMessage is set when a non-ping message is received", () => {
    const { result, unmount } = renderHook(() =>
      useWebSocket("ws://localhost:8000/ws")
    );
    const ws = MockWebSocket._lastInstance;

    act(() => {
      ws.simulateOpen();
    });

    const payload = {
      devices: { geyser: { status: "OFF", wattage: 2000 } },
      systemState: { simulatedTime: "08:30:00" },
      energyStats: { totalSavedWh: 100 },
      notifications: [],
    };

    act(() => {
      ws.simulateMessage(payload);
    });

    expect(result.current.lastMessage).toEqual(payload);
    unmount();
  });

  it("isConnected becomes false when WebSocket closes", () => {
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
});
