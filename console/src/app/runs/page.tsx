'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { RunStatus } from '@/components/run/RunStatus';
import type { RunSummary } from '@/types/api';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

const PAGE_SIZE = 20;

export default function RunsPage() {
  const [page, setPage] = useState(0);
  const offset = page * PAGE_SIZE;
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['runs', offset, PAGE_SIZE],
    queryFn: () => api.getRuns(offset, PAGE_SIZE),
    refetchInterval: 3000,
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  if (isLoading) return <SkeletonTable rows={5} cols={4} />;
  if (error) return <QueryError error={error as Error} message="Failed to load runs" onRetry={refetch} />;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Runs</h2>
      {(data?.items ?? []).length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <polygon points="5,3 19,12 5,21" />
            </svg>
          </div>
          <p className="text-gray-400 mb-1">No runs yet</p>
          <p className="text-sm text-gray-600 mb-4">Execute a flow to see run history here</p>
          <Link href="/" className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            Go to Dashboard
          </Link>
        </div>
      ) : (
        <>
          <div className="border border-gray-800 rounded-lg bg-gray-900">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left p-3 text-sm text-gray-400">Run ID</th>
                  <th className="text-left p-3 text-sm text-gray-400">Flow</th>
                  <th className="text-left p-3 text-sm text-gray-400">Status</th>
                  <th className="text-left p-3 text-sm text-gray-400">Events</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((run: RunSummary) => (
                  <tr key={run.run_id} className="border-b border-gray-800 last:border-0">
                    <td className="p-3">
                      <Link href={`/runs/detail?id=${run.run_id}`} className="font-mono text-sm text-blue-400 hover:underline">
                        {run.run_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="p-3 text-sm">{run.pipeline}</td>
                    <td className="p-3"><RunStatus status={run.status} /></td>
                    <td className="p-3 text-sm">{run.events}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-sm text-gray-400">
                Page {page + 1} of {totalPages} ({data?.total} runs)
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1 text-sm rounded border border-gray-700 text-gray-400 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1 text-sm rounded border border-gray-700 text-gray-400 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
