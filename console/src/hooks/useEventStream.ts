'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

interface StreamEvent {
  type: string;
  timestamp: string;
  run_id?: string;
  scope?: string;
  payload?: Record<string, unknown>;
}

export function useEventStream(maxEvents = 500) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const clear = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/events`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (evt) => {
      try {
        const event: StreamEvent = JSON.parse(evt.data);
        setEvents((prev) => {
          const next = [...prev, event];
          return next.length > maxEvents ? next.slice(-maxEvents) : next;
        });
      } catch {
        /* ignore parse errors */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [maxEvents]);

  return { events, connected, clear };
}
