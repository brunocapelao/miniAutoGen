'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import type { Engine } from '@/types/api';
import { useDeleteEngine, useConfigDetail } from '@/hooks/useApi';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

type Tab = 'engines' | 'workspace';

function EnginesTab() {
  const { data: engines, isLoading, error, refetch } = useQuery({ queryKey: ['engines'], queryFn: api.getEngines });
  const deleteEngine = useDeleteEngine();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (isLoading) return <SkeletonTable rows={5} cols={4} />;
  if (error) return <QueryError error={error as Error} message="Failed to load engines" onRetry={refetch} />;

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteEngine.mutateAsync(deleteTarget);
    setDeleteTarget(null);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-400">{(engines ?? []).length} engine(s) configured</p>
        <Link
          href="/settings/engines/new"
          className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
        >
          New Engine
        </Link>
      </div>
      <div className="border border-gray-800 rounded-lg bg-gray-900">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Provider</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Kind</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Source</th>
              <th className="text-right p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(engines ?? []).map((engine: Engine) => (
              <tr key={engine.name} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/30 transition-colors">
                <td className="p-3">
                  <span className="font-mono text-sm">{engine.name}</span>
                </td>
                <td className="p-3 text-sm text-gray-300">{engine.provider}</td>
                <td className="p-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">
                    {engine.model}
                  </span>
                </td>
                <td className="p-3 text-sm text-gray-400">{engine.kind ?? '-'}</td>
                <td className="p-3 text-sm text-gray-500">{engine.source ?? '-'}</td>
                <td className="p-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      href={`/settings/engines/edit?name=${encodeURIComponent(engine.name)}`}
                      className="text-xs px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 rounded transition-colors"
                    >
                      Edit
                    </Link>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(engine.name)}
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
          resourceType="Engine"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={deleteEngine.isPending}
        />
      )}
    </div>
  );
}

function WorkspaceTab() {
  const { data: config, isLoading, error, refetch } = useConfigDetail();

  if (isLoading) return <SkeletonTable rows={3} cols={2} />;
  if (error) return <QueryError error={error as Error} message="Failed to load config" onRetry={refetch} />;

  const entries = config ? Object.entries(config) : [];

  return (
    <div className="border border-gray-800 rounded-lg bg-gray-900">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Key</th>
            <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/30 transition-colors">
              <td className="p-3">
                <span className="font-mono text-sm text-gray-300">{key}</span>
              </td>
              <td className="p-3 text-sm text-gray-400">
                <pre className="whitespace-pre-wrap font-mono text-xs">
                  {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                </pre>
              </td>
            </tr>
          ))}
          {entries.length === 0 && (
            <tr>
              <td colSpan={2} className="p-6 text-center text-sm text-gray-500">No configuration data available.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('engines');

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Settings</h2>

      <div className="flex gap-1 mb-6 border-b border-gray-800">
        {(['engines', 'workspace'] as Tab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === 'engines' && <EnginesTab />}
      {activeTab === 'workspace' && <WorkspaceTab />}
    </div>
  );
}
