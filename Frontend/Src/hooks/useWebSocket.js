/**
 * useWebSocket — manages a native WebSocket connection with exponential-backoff reconnection.
 *
 * @param {string} url - WebSocket URL to connect to (e.g. "ws://localhost:8000/ws").
 * @returns {{ isConnected: boolean, lastMessage: object | null }}
 */
import { useState, useRef, useEffect } from "react";
import { computeBackoffDelay } from "./computeBackoffDelay.js";

export function useWebSocket(url) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);

  const wsRef = useRef(null);
  const retryCountRef = useRef(0);
  const maxRetriesReachedRef = useRef(false);
  const timeoutIdRef = useRef(null);
  const lastMessageTimeRef = useRef(Date.now());
  const deadCheckRef = useRef(null);

  const connect = () => {
    if (maxRetriesReachedRef.current) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      retryCountRef.current = 0;
      lastMessageTimeRef.current = Date.now();
    };

    ws.onmessage = (event) => {
      lastMessageTimeRef.current = Date.now();
      try {
        const data = JSON.parse(event.data);
        if (data.type === "ping") return;
        setLastMessage(data);
      } catch (e) {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      retryCountRef.current += 1;
      const delay = computeBackoffDelay(retryCountRef.current);
      if (delay === "exhausted") {
        maxRetriesReachedRef.current = true;
        return;
      }
      timeoutIdRef.current = setTimeout(connect, delay);
    };
  };

  useEffect(() => {
    connect();

    // Dead-connection guard: check every 15 s
    deadCheckRef.current = setInterval(() => {
      if (
        wsRef.current &&
        wsRef.current.readyState === WebSocket.OPEN &&
        Date.now() - lastMessageTimeRef.current > 60000
      ) {
        wsRef.current.close();
      }
    }, 15000);

    return () => {
      wsRef.current?.close();
      clearTimeout(timeoutIdRef.current);
      clearInterval(deadCheckRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { isConnected, lastMessage };
}
