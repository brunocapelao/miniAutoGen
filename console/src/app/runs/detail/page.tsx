'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useRunEvents } from '@/hooks/useRunEvents';
import { RunStatus } from '@/components/run/RunStatus';
import { EventFeed } from '@/components/run/EventFeed';

function RunDetailContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id') ?? '';
  const { data: run } = useQuery({
    queryKey: ['run', id],
    queryFn: () => api.getRun(id),
    enabled: !!id,
  });
  const { events, isLive } = useRunEvents(id);

  if (!id) {
    return <p className="text-gray-400">No run ID specified.</p>;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-2xl font-bold">
          Run <span className="font-mono text-gray-400">{id.slice(0, 8)}</span>
        </h2>
        {run && <RunStatus status={run.status as string} />}
        {isLive && (
          <span className="text-xs text-green-400 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            LIVE
          </span>
        )}
      </div>
      <div>
        <h3 className="font-bold mb-2">Events ({events.length})</h3>
        <EventFeed events={events} />
      </div>
    </div>
  );
}

export default function RunDetailPage() {
  return (
    <Suspense fallback={<p className="text-gray-400">Loading...</p>}>
      <RunDetailContent />
    </Suspense>
  );
}
