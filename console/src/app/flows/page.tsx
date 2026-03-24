'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import type { Flow } from '@/types/api';
import { SkeletonCards } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

export default function FlowsPage() {
  const { data: flows, isLoading, error, refetch } = useQuery({ queryKey: ['flows'], queryFn: api.getFlows });

  if (isLoading) return <SkeletonCards count={3} />;
  if (error) return <QueryError error={error as Error} message="Failed to load flows" onRetry={refetch} />;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Flows</h2>
      <div className="grid gap-4">
        {(flows ?? []).map((flow: Flow) => (
          <Link
            key={flow.name}
            href={`/flows/detail?name=${flow.name}`}
            className="border border-gray-800 rounded-lg p-4 bg-gray-900/50 hover:bg-gray-800/50 hover:border-gray-700 transition-all block"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-mono font-bold">{flow.name}</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                flow.mode === 'workflow' ? 'bg-blue-500/10 text-blue-400' :
                flow.mode === 'deliberation' ? 'bg-purple-500/10 text-purple-400' :
                flow.mode === 'loop' ? 'bg-green-500/10 text-green-400' :
                'bg-gray-500/10 text-gray-400'
              }`}>
                {flow.mode}
              </span>
            </div>
            <p className="text-sm text-gray-500">
              {flow.participants.length} agent{flow.participants.length !== 1 ? 's' : ''}: {flow.participants.join(', ')}
            </p>
            {flow.leader && (
              <p className="text-xs text-gray-600 mt-1">Leader: {flow.leader}</p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
