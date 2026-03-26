'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAgent } from '@/hooks/useApi';
import { AgentForm } from '@/components/AgentForm';
import { SkeletonCard } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

function EditAgentContent() {
  const searchParams = useSearchParams();
  const name = searchParams.get('name') ?? '';
  const { data: agent, isLoading, error, refetch } = useAgent(name);

  if (!name) return <p className="text-gray-400">No agent name specified.</p>;
  if (isLoading) return (
    <div className="space-y-4">
      <div className="h-6 bg-gray-800 rounded animate-pulse w-48 mb-4" />
      <SkeletonCard />
    </div>
  );
  if (error) return <QueryError error={error as Error} message="Agent not found or failed to load" onRetry={refetch} />;

  return (
    <div>
      <div className="mb-4">
        <Link href="/agents" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Agents
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <Link href={`/agents/detail?name=${encodeURIComponent(name)}`} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          {name}
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">Edit</span>
      </div>
      <h2 className="text-2xl font-bold mb-6">Edit Agent</h2>
      {agent && <AgentForm mode="edit" initialData={agent} />}
    </div>
  );
}

export default function EditAgentPage() {
  return (
    <Suspense fallback={<SkeletonCard />}>
      <EditAgentContent />
    </Suspense>
  );
}
