'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { FlowCanvas } from '@/components/flow-graph/FlowCanvas';
import type { Flow } from '@/types/api';
import { SkeletonCard } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

function FlowDetailContent() {
  const searchParams = useSearchParams();
  const name = searchParams.get('name') ?? '';
  const { data: flow, isLoading, error } = useQuery<Flow>({
    queryKey: ['flow', name],
    queryFn: () => api.getFlow(name),
    enabled: !!name,
  });

  if (!name) return <p className="text-gray-400">No flow name specified.</p>;
  if (isLoading) return (
    <div className="space-y-4">
      <div className="h-6 bg-gray-800 rounded animate-pulse w-48 mb-4" />
      <SkeletonCard />
    </div>
  );
  if (error) return <QueryError error={error as Error} message="Flow not found or failed to load" />;

  const participants = flow?.participants ?? [];
  const leader = flow?.leader ?? null;
  const mode = flow?.mode ?? '';

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
        {flow?.target != null && <span>Target: {flow.target}</span>}
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
    <Suspense fallback={<SkeletonCard />}>
      <FlowDetailContent />
    </Suspense>
  );
}
