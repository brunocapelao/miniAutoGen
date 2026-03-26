'use client';

import Link from 'next/link';
import { EngineForm } from '@/components/EngineForm';

export default function NewEnginePage() {
  return (
    <div>
      <div className="mb-4">
        <Link href="/settings" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Settings
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">New Engine</span>
      </div>
      <h2 className="text-2xl font-bold mb-6">New Engine</h2>
      <EngineForm mode="create" />
    </div>
  );
}
