'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useTriggerRun } from '@/hooks/useApi';
import type { Flow } from '@/types/api';
import { SkeletonCards } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

export default function Dashboard() {
  const { data: workspace, isLoading: workspaceLoading, error: workspaceError, refetch: refetchWorkspace } = useQuery({ queryKey: ['workspace'], queryFn: api.getWorkspace });
  const { data: runs } = useQuery({ queryKey: ['runs'], queryFn: () => api.getRuns() });
  const { data: flows } = useQuery({ queryKey: ['flows'], queryFn: api.getFlows });
  const triggerRun = useTriggerRun();
  const [selectedFlow, setSelectedFlow] = useState('');

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      {workspaceLoading ? (
        <div className="mb-8"><SkeletonCards count={3} /></div>
      ) : workspaceError ? (
        <div className="mb-8">
          <QueryError error={workspaceError as Error} message="Failed to load workspace data" onRetry={refetchWorkspace} />
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
            <p className="text-sm text-gray-400">Agents</p>
            <p className="text-3xl font-bold">{workspace?.agent_count ?? '-'}</p>
          </div>
          <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
            <p className="text-sm text-gray-400">Flows</p>
            <p className="text-3xl font-bold">{workspace?.pipeline_count ?? '-'}</p>
          </div>
          <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
            <p className="text-sm text-gray-400">Runs</p>
            <p className="text-3xl font-bold">{runs?.total ?? '-'}</p>
          </div>
        </div>
      )}
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
        <h3 className="font-bold mb-3">Trigger Run</h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label htmlFor="flow-select" className="block text-sm text-gray-400 mb-1">Flow</label>
            <select
              id="flow-select"
              value={selectedFlow}
              onChange={(e) => setSelectedFlow(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select a flow...</option>
              {(flows ?? []).map((f: Flow) => (
                <option key={f.name} value={f.name}>{f.name}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            disabled={!selectedFlow || triggerRun.isPending}
            onClick={() => {
              if (selectedFlow) triggerRun.mutate({ flowName: selectedFlow });
            }}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {triggerRun.isPending ? 'Running...' : 'Run'}
          </button>
        </div>
        {triggerRun.isError && (
          <p className="text-red-400 text-sm mt-2">
            {triggerRun.error instanceof Error ? triggerRun.error.message : 'Failed to trigger run'}
          </p>
        )}
        {triggerRun.isSuccess && (
          <p className="text-green-400 text-sm mt-2">
            Run started: {triggerRun.data.run_id.slice(0, 8)}...
          </p>
        )}
      </div>
    </div>
  );
}
