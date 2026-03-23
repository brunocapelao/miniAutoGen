'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export default function AgentsPage() {
  const { data: agents, isLoading } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });

  if (isLoading) return <p className="text-gray-400">Loading...</p>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Agents</h2>
      <div className="border border-gray-800 rounded-lg bg-gray-900">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left p-3 text-sm font-medium text-gray-400">Name</th>
              <th className="text-left p-3 text-sm font-medium text-gray-400">Role</th>
              <th className="text-left p-3 text-sm font-medium text-gray-400">Engine</th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent: any) => (
              <tr key={agent.name} className="border-b border-gray-800 last:border-0">
                <td className="p-3 font-mono text-sm">{agent.name}</td>
                <td className="p-3 text-sm">{agent.role}</td>
                <td className="p-3 text-sm text-gray-400">{agent.engine_type || agent.engine_profile}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
