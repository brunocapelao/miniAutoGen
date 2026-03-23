'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { RunStatus } from '@/components/run/RunStatus';

export default function RunsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.getRuns(),
    refetchInterval: 3000,
  });

  if (isLoading) return <p className="text-gray-400">Loading...</p>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Runs</h2>
      {(data?.items ?? []).length === 0 ? (
        <p className="text-gray-400">No runs yet. Trigger a run from the Dashboard.</p>
      ) : (
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
              {data?.items.map((run: any) => (
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
      )}
    </div>
  );
}
