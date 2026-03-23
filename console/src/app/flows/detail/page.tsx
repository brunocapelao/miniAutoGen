'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { FlowCanvas } from '@/components/flow-graph/FlowCanvas';

function FlowDetailContent() {
  const searchParams = useSearchParams();
  const name = searchParams.get('name') ?? '';
  const { data: flow, isLoading, error } = useQuery({
    queryKey: ['flow', name],
    queryFn: () => api.getFlow(name),
    enabled: !!name,
  });

  if (!name) return <p className="text-gray-400">No flow name specified.</p>;
  if (isLoading) return <p className="text-gray-400">Loading...</p>;
  if (error) return <p className="text-red-400">Flow not found.</p>;

  const participants = (flow?.participants as string[]) ?? [];
  const leader = flow?.leader as string | null;
  const mode = flow?.mode as string;

  return (
    <div>
      <div className="mb-6">
        <Link href="/flows" className="text-sm text-gray-400 hover:text-white">
          &larr; Back to Flows
        </Link>
      </div>
      <h2 className="text-2xl font-bold mb-2 font-mono">{name}</h2>
      <div className="flex gap-4 text-sm text-gray-400 mb-6">
        <span>Mode: {mode}</span>
        {flow?.target != null && <span>Target: {String(flow.target)}</span>}
        {leader && <span>Leader: {leader}</span>}
        {flow?.max_rounds != null && <span>Max rounds: {Number(flow.max_rounds)}</span>}
      </div>

      {participants.length > 0 ? (
        <div>
          <h3 className="font-bold mb-2">Flow Graph ({participants.length} agents)</h3>
          <FlowCanvas participants={participants} leader={leader} mode={mode} />
        </div>
      ) : (
        <p className="text-gray-400">No participants defined for this flow.</p>
      )}
    </div>
  );
}

export default function FlowDetailPage() {
  return (
    <Suspense fallback={<p className="text-gray-400">Loading...</p>}>
      <FlowDetailContent />
    </Suspense>
  );
}
