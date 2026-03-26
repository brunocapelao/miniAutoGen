'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateFlow, useUpdateFlow } from '@/hooks/useApi';
import type { Flow } from '@/types/api';

const FLOW_MODES = ['workflow', 'deliberation', 'loop', 'composite'] as const;

type FlowFormProps = {
  mode: 'create' | 'edit';
  initialData?: Flow;
};

export function FlowForm({ mode, initialData }: FlowFormProps) {
  const router = useRouter();
  const createFlow = useCreateFlow();
  const updateFlow = useUpdateFlow();

  const [name, setName] = useState(initialData?.name ?? '');
  const [flowMode, setFlowMode] = useState(initialData?.mode ?? 'workflow');
  const [participants, setParticipants] = useState(initialData?.participants?.join(', ') ?? '');
  const [leader, setLeader] = useState(initialData?.leader ?? '');
  const [target, setTarget] = useState(initialData?.target ?? '');
  const [error, setError] = useState<string | null>(null);

  const isSubmitting = createFlow.isPending || updateFlow.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const participantList = participants
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean);

    try {
      if (mode === 'create') {
        await createFlow.mutateAsync({
          name,
          mode: flowMode,
          participants: participantList,
          leader: leader || undefined,
          target: target || undefined,
        });
      } else {
        await updateFlow.mutateAsync({
          name,
          data: {
            mode: flowMode,
            participants: participantList,
            leader: leader || undefined,
            target: target || undefined,
          },
        });
      }
      router.push('/flows');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-5">
      {error && (
        <div className="border border-red-500/30 bg-red-500/5 rounded-lg p-3">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      <div>
        <label htmlFor="name" className="block text-sm font-medium text-gray-400 mb-1">Name</label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          readOnly={mode === 'edit'}
          required
          className={`w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 ${
            mode === 'edit' ? 'opacity-60 cursor-not-allowed' : ''
          }`}
          placeholder="e.g. research-pipeline"
        />
      </div>

      <div>
        <label htmlFor="flowMode" className="block text-sm font-medium text-gray-400 mb-1">Mode</label>
        <select
          id="flowMode"
          value={flowMode}
          onChange={(e) => setFlowMode(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        >
          {FLOW_MODES.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="participants" className="block text-sm font-medium text-gray-400 mb-1">
          Participants <span className="text-gray-600">(comma-separated agent names)</span>
        </label>
        <input
          id="participants"
          type="text"
          value={participants}
          onChange={(e) => setParticipants(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. researcher, writer, reviewer"
        />
      </div>

      <div>
        <label htmlFor="leader" className="block text-sm font-medium text-gray-400 mb-1">
          Leader <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="leader"
          type="text"
          value={leader}
          onChange={(e) => setLeader(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. researcher"
        />
      </div>

      <div>
        <label htmlFor="target" className="block text-sm font-medium text-gray-400 mb-1">
          Target <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="target"
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. Produce a comprehensive research report"
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors disabled:opacity-50"
        >
          {isSubmitting ? 'Saving...' : mode === 'create' ? 'Create Flow' : 'Save Changes'}
        </button>
        <button
          type="button"
          onClick={() => router.push('/flows')}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
