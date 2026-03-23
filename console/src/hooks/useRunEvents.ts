'use client';

import { useEffect, useRef, useState } from 'react';
import { RunEventStream } from '@/lib/ws-client';
import { api } from '@/lib/api-client';

export function useRunEvents(runId: string) {
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [isLive, setIsLive] = useState(false);
  const streamRef = useRef<RunEventStream | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId) return;
    const stream = new RunEventStream(runId);
    streamRef.current = stream;

    const unsub = stream.onEvent((event) => {
      if (event.type === 'connected') { setIsLive(true); return; }
      if (event.type === 'finished') { setIsLive(false); return; }
      setEvents((prev) => [...prev, event]);
    });

    stream.connect();

    const timeout = setTimeout(() => {
      if (!stream.isConnected) {
        setIsLive(false);
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
    };
  }, [runId]);

  return { events, isLive };
}
