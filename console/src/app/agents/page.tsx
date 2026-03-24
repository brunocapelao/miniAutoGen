'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { Agent } from '@/types/api';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

export default function AgentsPage() {
  const { data: agents, isLoading, error, refetch } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });

  if (isLoading) return <SkeletonTable rows={5} cols={3} />;
  if (error) return <QueryError error={error as Error} message="Failed to load agents" onRetry={refetch} />;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Agents</h2>
      <div className="border border-gray-800 rounded-lg bg-gray-900">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Engine</th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent: Agent) => (
              <tr key={agent.name} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/30 transition-colors">
                <td className="p-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 text-xs font-bold uppercase">
                      {agent.name.slice(0, 2)}
                    </div>
                    <span className="font-mono text-sm">{agent.name}</span>
                  </div>
                </td>
                <td className="p-3 text-sm text-gray-300">{agent.role}</td>
                <td className="p-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">
                    {agent.engine_type || agent.engine_profile}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
