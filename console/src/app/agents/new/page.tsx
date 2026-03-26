'use client';

import Link from 'next/link';
import { AgentForm } from '@/components/AgentForm';

export default function NewAgentPage() {
  return (
    <div>
      <div className="mb-4">
        <Link href="/agents" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Agents
        </Link>
        <span className="text-xs text-gray-700 mx-1.5">/</span>
        <span className="text-xs text-gray-400">New</span>
      </div>
      <h2 className="text-2xl font-bold mb-6">New Agent</h2>
      <AgentForm mode="create" />
    </div>
  );
}
