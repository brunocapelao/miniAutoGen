'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import type { Flow } from '@/types/api';
import { SkeletonCards } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';
import { useDeleteFlow } from '@/hooks/useApi';

export default function FlowsPage() {
  const { data: flows, isLoading, error, refetch } = useQuery({ queryKey: ['flows'], queryFn: api.getFlows });
  const deleteFlow = useDeleteFlow();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (isLoading) return <SkeletonCards count={3} />;
  if (error) return <QueryError error={error as Error} message="Failed to load flows" onRetry={refetch} />;

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteFlow.mutateAsync(deleteTarget);
    setDeleteTarget(null);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Flows</h2>
        <Link
          href="/flows/new"
          className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
        >
          New Flow
        </Link>
      </div>
      <div className="grid gap-4">
        {(flows ?? []).map((flow: Flow) => (
          <div
            key={flow.name}
            className="border border-gray-800 rounded-lg p-4 bg-gray-900/50 hover:bg-gray-800/50 hover:border-gray-700 transition-all"
          >
            <div className="flex items-center justify-between mb-2">
              <Link href={`/flows/detail?name=${flow.name}`} className="font-mono font-bold hover:text-blue-400 transition-colors">
                {flow.name}
              </Link>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  flow.mode === 'workflow' ? 'bg-blue-500/10 text-blue-400' :
                  flow.mode === 'deliberation' ? 'bg-purple-500/10 text-purple-400' :
                  flow.mode === 'loop' ? 'bg-green-500/10 text-green-400' :
                  'bg-gray-500/10 text-gray-400'
                }`}>
                  {flow.mode}
                </span>
                <Link
                  href={`/flows/edit?name=${encodeURIComponent(flow.name)}`}
                  className="text-xs px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 rounded transition-colors"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  onClick={() => setDeleteTarget(flow.name)}
                  className="text-xs px-2 py-1 bg-red-600/10 hover:bg-red-600/20 text-red-400 rounded transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
            <Link href={`/flows/detail?name=${flow.name}`} className="block">
              <p className="text-sm text-gray-500">
                {flow.participants.length} agent{flow.participants.length !== 1 ? 's' : ''}: {flow.participants.join(', ')}
              </p>
              {flow.leader && (
                <p className="text-xs text-gray-600 mt-1">Leader: {flow.leader}</p>
              )}
            </Link>
          </div>
        ))}
      </div>

      {deleteTarget && (
        <DeleteConfirmModal
          resourceName={deleteTarget}
          resourceType="Flow"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={deleteFlow.isPending}
        />
      )}
    </div>
  );
}
