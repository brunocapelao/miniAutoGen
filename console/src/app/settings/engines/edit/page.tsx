'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useEngine } from '@/hooks/useApi';
import { EngineForm } from '@/components/EngineForm';
import { SkeletonCard } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';

function EditEngineContent() {
  const searchParams = useSearchParams();
  const name = searchParams.get('name') ?? '';
  const { data: engine, isLoading, error, refetch } = useEngine(name);

  if (!name) return <p className="text-gray-400">No engine name specified.</p>;
  if (isLoading) return (
    <div className="space-y-4">
      <div className="h-6 bg-gray-800 rounded animate-pulse w-48 mb-4" />
      <SkeletonCard />
    </div>
  );
  if (error) return <QueryError error={error as Error} message="Engine not found or failed to load" onRetry={refetch} />;

  return (
    <div>
      <div className="mb-4">
        <Link href="/settings" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Settings
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">Edit Engine</span>
      </div>
      <h2 className="text-2xl font-bold mb-6">Edit Engine</h2>
      {engine && <EngineForm mode="edit" initialData={engine} />}
    </div>
  );
}

export default function EditEnginePage() {
  return (
    <Suspense fallback={<SkeletonCard />}>
      <EditEngineContent />
    </Suspense>
  );
}
