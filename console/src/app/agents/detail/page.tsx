'use client';

import { Suspense, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAgent, useDeleteAgent } from '@/hooks/useApi';
import { SkeletonCard } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

function AgentDetailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const name = searchParams.get('name') ?? '';
  const { data: agent, isLoading, error, refetch } = useAgent(name);
  const deleteAgent = useDeleteAgent();
  const [showDelete, setShowDelete] = useState(false);

  if (!name) return <p className="text-gray-400">No agent name specified.</p>;
  if (isLoading) return (
    <div className="space-y-4">
      <div className="h-6 bg-gray-800 rounded animate-pulse w-48 mb-4" />
      <SkeletonCard />
    </div>
  );
  if (error) return <QueryError error={error as Error} message="Agent not found or failed to load" onRetry={refetch} />;

  async function handleDelete() {
    await deleteAgent.mutateAsync(name);
    router.push('/agents');
  }

  return (
    <div>
      <div className="mb-4">
        <Link href="/agents" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Agents
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">{name}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 text-sm font-bold uppercase">
            {name.slice(0, 2)}
          </div>
          <h2 className="text-2xl font-bold font-mono">{name}</h2>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/agents/edit?name=${encodeURIComponent(name)}`}
            className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md transition-colors"
          >
            Edit
          </Link>
          <button
            type="button"
            onClick={() => setShowDelete(true)}
            className="px-3 py-1.5 text-sm bg-red-600/10 hover:bg-red-600/20 text-red-400 rounded-md transition-colors"
          >
            Delete
          </button>
        </div>
      </div>

      <div className="border border-gray-800 rounded-lg bg-gray-900 divide-y divide-gray-800">
        <div className="p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Role</p>
          <p className="text-sm text-gray-200">{agent?.role}</p>
        </div>
        {agent?.goal && (
          <div className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Goal</p>
            <p className="text-sm text-gray-200">{agent.goal}</p>
          </div>
        )}
        <div className="p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Engine</p>
          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">
            {agent?.engine_type || agent?.engine_profile}
          </span>
        </div>
        {agent?.temperature != null && (
          <div className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Temperature</p>
            <p className="text-sm text-gray-200">{agent.temperature}</p>
          </div>
        )}
      </div>

      {showDelete && (
        <DeleteConfirmModal
          resourceName={name}
          resourceType="Agent"
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
          isDeleting={deleteAgent.isPending}
        />
      )}
    </div>
  );
}

export default function AgentDetailPage() {
  return (
    <Suspense fallback={<SkeletonCard />}>
      <AgentDetailContent />
    </Suspense>
  );
}
