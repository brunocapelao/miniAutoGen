'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export default function Dashboard() {
  const { data: workspace } = useQuery({ queryKey: ['workspace'], queryFn: api.getWorkspace });
  const { data: runs } = useQuery({ queryKey: ['runs'], queryFn: () => api.getRuns() });

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
          <p className="text-sm text-gray-400">Agents</p>
          <p className="text-3xl font-bold">{(workspace as any)?.agent_count ?? '-'}</p>
        </div>
        <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
          <p className="text-sm text-gray-400">Flows</p>
          <p className="text-3xl font-bold">{(workspace as any)?.pipeline_count ?? '-'}</p>
        </div>
        <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
          <p className="text-sm text-gray-400">Runs</p>
          <p className="text-3xl font-bold">{runs?.total ?? '-'}</p>
        </div>
      </div>
    </div>
  );
}
