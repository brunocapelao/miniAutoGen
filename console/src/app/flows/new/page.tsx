'use client';

import Link from 'next/link';
import { FlowForm } from '@/components/FlowForm';

export default function NewFlowPage() {
  return (
    <div>
      <div className="mb-4">
        <Link href="/flows" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Flows
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">New</span>
      </div>
      <h2 className="text-2xl font-bold mb-6">New Flow</h2>
      <FlowForm mode="create" />
    </div>
  );
}
