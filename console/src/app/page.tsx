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
        <div className="mb-6"><SkeletonCards count={3} /></div>
      ) : workspaceError ? (
        <div className="mb-6">
          <QueryError error={workspaceError as Error} message="Failed to load workspace data" onRetry={refetchWorkspace} />
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Agents</p>
                <p className="text-2xl font-bold mt-1">{workspace?.agent_count ?? '-'}</p>
                <p className="text-xs text-gray-600 mt-1">configured</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <circle cx="9" cy="7" r="4" /><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
                </svg>
              </div>
            </div>
          </div>
          <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Flows</p>
                <p className="text-2xl font-bold mt-1">{workspace?.pipeline_count ?? '-'}</p>
                <p className="text-xs text-gray-600 mt-1">available</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <circle cx="6" cy="18" r="3" /><circle cx="18" cy="6" r="3" /><path d="M6 15V6h12" />
                </svg>
              </div>
            </div>
          </div>
          <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Runs</p>
                <p className="text-2xl font-bold mt-1">{runs?.total ?? '-'}</p>
                <p className="text-xs text-gray-600 mt-1">total</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <polygon points="5,3 19,12 5,21" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/50">
        <div className="flex items-center gap-2 mb-3">
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <polygon points="5,3 19,12 5,21" />
          </svg>
          <h3 className="font-semibold text-sm">Trigger Run</h3>
        </div>
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <label htmlFor="flow-select" className="block text-xs text-gray-500 mb-1.5">Select Flow</label>
            <select
              id="flow-select"
              value={selectedFlow}
              onChange={(e) => setSelectedFlow(e.target.value)}
              className="w-full bg-gray-800/80 border border-gray-700 rounded-lg px-3 py-2 pr-8 text-sm text-white appearance-none cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Choose a flow...</option>
              {(flows ?? []).map((f: Flow) => (
                <option key={f.name} value={f.name}>{f.name} ({f.mode})</option>
              ))}
            </select>
            <svg className="absolute right-2.5 top-[calc(50%+4px)] w-4 h-4 text-gray-500 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>
          <button
            type="button"
            disabled={!selectedFlow || triggerRun.isPending}
            onClick={() => {
              if (selectedFlow) triggerRun.mutate({ flowName: selectedFlow });
            }}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
