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
            className="border border-gray-800 rounded-lg p-4 bg-gray-900 hover:bg-gray-800 transition-colors block"
          >
            <h3 className="font-mono font-bold">{flow.name}</h3>
            <p className="text-sm text-gray-400">Mode: {flow.mode} | Target: {flow.target}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
