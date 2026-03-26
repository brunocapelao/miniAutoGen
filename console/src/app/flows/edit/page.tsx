'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useFlow } from '@/hooks/useApi';
import { FlowForm } from '@/components/FlowForm';
import { SkeletonCard } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

function EditFlowContent() {
  const searchParams = useSearchParams();
  const name = searchParams.get('name') ?? '';
  const { data: flow, isLoading, error, refetch } = useFlow(name);

  if (!name) return <p className="text-gray-400">No flow name specified.</p>;
  if (isLoading) return (
    <div className="space-y-4">
      <div className="h-6 bg-gray-800 rounded animate-pulse w-48 mb-4" />
      <SkeletonCard />
    </div>
  );
  if (error) return <QueryError error={error as Error} message="Flow not found or failed to load" onRetry={refetch} />;

  return (
    <div>
      <div className="mb-4">
        <Link href="/flows" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Flows
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <Link href={`/flows/detail?name=${encodeURIComponent(name)}`} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          {name}
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">Edit</span>
      </div>
      <h2 className="text-2xl font-bold mb-6">Edit Flow</h2>
      {flow && <FlowForm mode="edit" initialData={flow} />}
    </div>
  );
}

export default function EditFlowPage() {
  return (
    <Suspense fallback={<SkeletonCard />}>
      <EditFlowContent />
    </Suspense>
  );
}
