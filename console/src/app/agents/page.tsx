'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import type { Agent } from '@/types/api';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';
import { useDeleteAgent } from '@/hooks/useApi';

export default function AgentsPage() {
  const { data: agents, isLoading, error, refetch } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });
  const deleteAgent = useDeleteAgent();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (isLoading) return <SkeletonTable rows={5} cols={3} />;
  if (error) return <QueryError error={error as Error} message="Failed to load agents" onRetry={refetch} />;

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteAgent.mutateAsync(deleteTarget);
    setDeleteTarget(null);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Agents</h2>
        <Link
          href="/agents/new"
          className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
        >
          New Agent
        </Link>
      </div>
      <div className="border border-gray-800 rounded-lg bg-gray-900">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Engine</th>
              <th className="text-right p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent: Agent) => (
              <tr key={agent.name} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/30 transition-colors">
                <td className="p-3">
                  <Link href={`/agents/detail?name=${encodeURIComponent(agent.name)}`} className="flex items-center gap-3 hover:text-blue-400 transition-colors">
                    <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 text-xs font-bold uppercase">
                      {agent.name.slice(0, 2)}
                    </div>
                    <span className="font-mono text-sm">{agent.name}</span>
                  </Link>
                </td>
                <td className="p-3 text-sm text-gray-300">{agent.role}</td>
                <td className="p-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">
                    {agent.engine_type || agent.engine_profile}
                  </span>
                </td>
                <td className="p-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      href={`/agents/edit?name=${encodeURIComponent(agent.name)}`}
                      className="text-xs px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 rounded transition-colors"
                    >
                      Edit
                    </Link>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(agent.name)}
                      className="text-xs px-2 py-1 bg-red-600/10 hover:bg-red-600/20 text-red-400 rounded transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {deleteTarget && (
        <DeleteConfirmModal
          resourceName={deleteTarget}
          resourceType="Agent"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={deleteAgent.isPending}
        />
      )}
    </div>
  );
}
