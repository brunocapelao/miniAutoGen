'use client';

import { useEffect, useRef, useState } from 'react';
import { RunEventStream } from '@/lib/ws-client';
import { api } from '@/lib/api-client';
import { useConnectionStore } from '@/stores/connection';
import type { RunEvent } from '@/types/api';

export function useRunEvents(runId: string) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [isLive, setIsLive] = useState(false);
  const streamRef = useRef<RunEventStream | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { setStatus, setRunId } = useConnectionStore();

  useEffect(() => {
    if (!runId) return;
    setRunId(runId);
    setStatus('connecting');

    const stream = new RunEventStream(runId);
    streamRef.current = stream;

    const unsub = stream.onEvent((event) => {
      if (event.type === 'connected') {
        setIsLive(true);
        setStatus('connected');
        return;
      }
      if (event.type === 'finished') {
        setIsLive(false);
        setStatus('disconnected');
        return;
      }
      setEvents((prev) => [...prev, event]);
    });

    stream.connect();

    const timeout = setTimeout(() => {
      if (!stream.isConnected) {
        setIsLive(false);
        setStatus('polling');
        let offset = 0;
        pollingRef.current = setInterval(async () => {
          try {
            const data = await api.getRunEvents(runId, offset);
            if (data.items.length > 0) {
              setEvents((prev) => [...prev, ...data.items]);
              offset += data.items.length;
            }
          } catch { /* ignore polling errors */ }
        }, 1000);
      }
    }, 2000);

    return () => {
      clearTimeout(timeout);
      unsub();
      stream.disconnect();
      if (pollingRef.current) clearInterval(pollingRef.current);
      setStatus('disconnected');
      setRunId(null);
    };
  }, [runId, setStatus, setRunId]);

  return { events, isLive };
}
