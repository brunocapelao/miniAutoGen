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
      <div className="mb-4">
        <Link href="/flows" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Flows
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">{name}</span>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-2xl font-bold font-mono">{name}</h2>
        <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
          mode === 'workflow' ? 'bg-blue-500/10 text-blue-400' :
          mode === 'deliberation' ? 'bg-purple-500/10 text-purple-400' :
          mode === 'loop' ? 'bg-green-500/10 text-green-400' :
          'bg-gray-500/10 text-gray-400'
        }`}>
          {mode}
        </span>
      </div>

      <div className="flex gap-4 text-sm text-gray-500 mb-6">
        {leader && (
          <div className="flex items-center gap-1.5">
            <span className="text-gray-600">Leader:</span>
            <span className="text-gray-300 font-mono">{leader}</span>
          </div>
        )}
        {flow?.max_rounds != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-gray-600">Max rounds:</span>
            <span className="text-gray-300">{Number(flow.max_rounds)}</span>
          </div>
        )}
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
