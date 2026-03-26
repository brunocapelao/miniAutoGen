'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateAgent, useUpdateAgent } from '@/hooks/useApi';
import type { Agent } from '@/types/api';

type AgentFormProps = {
  mode: 'create' | 'edit';
  initialData?: Agent;
};

export function AgentForm({ mode, initialData }: AgentFormProps) {
  const router = useRouter();
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent();

  const [name, setName] = useState(initialData?.name ?? '');
  const [role, setRole] = useState(initialData?.role ?? '');
  const [goal, setGoal] = useState(initialData?.goal ?? '');
  const [engineProfile, setEngineProfile] = useState(initialData?.engine_profile ?? '');
  const [temperature, setTemperature] = useState<string>(
    initialData?.temperature != null ? String(initialData.temperature) : ''
  );
  const [error, setError] = useState<string | null>(null);

  const isSubmitting = createAgent.isPending || updateAgent.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    try {
      if (mode === 'create') {
        await createAgent.mutateAsync({
          name,
          role,
          goal,
          engine_profile: engineProfile,
          temperature: temperature ? parseFloat(temperature) : undefined,
        });
      } else {
        await updateAgent.mutateAsync({
          name,
          data: {
            role,
            goal,
            engine_profile: engineProfile,
            temperature: temperature ? parseFloat(temperature) : undefined,
          },
        });
      }
      router.push('/agents');
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
          placeholder="e.g. researcher"
        />
      </div>

      <div>
        <label htmlFor="role" className="block text-sm font-medium text-gray-400 mb-1">Role</label>
        <input
          id="role"
          type="text"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. Senior Researcher"
        />
      </div>

      <div>
        <label htmlFor="goal" className="block text-sm font-medium text-gray-400 mb-1">Goal</label>
        <textarea
          id="goal"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          required
          rows={3}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 resize-none"
          placeholder="e.g. Research and synthesize information on the given topic"
        />
      </div>

      <div>
        <label htmlFor="engine_profile" className="block text-sm font-medium text-gray-400 mb-1">Engine Profile</label>
        <input
          id="engine_profile"
          type="text"
          value={engineProfile}
          onChange={(e) => setEngineProfile(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. gpt-4o"
        />
      </div>

      <div>
        <label htmlFor="temperature" className="block text-sm font-medium text-gray-400 mb-1">
          Temperature <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="temperature"
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={temperature}
          onChange={(e) => setTemperature(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. 0.7"
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors disabled:opacity-50"
        >
          {isSubmitting ? 'Saving...' : mode === 'create' ? 'Create Agent' : 'Save Changes'}
        </button>
        <button
          type="button"
          onClick={() => router.push('/agents')}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
