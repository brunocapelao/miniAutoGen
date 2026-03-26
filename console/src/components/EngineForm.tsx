'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateEngine, useUpdateEngine } from '@/hooks/useApi';
import type { Engine } from '@/types/api';

type EngineFormProps = {
  mode: 'create' | 'edit';
  initialData?: Engine;
};

const PROVIDERS = ['openai', 'anthropic', 'gemini', 'vllm', 'litellm'];
const KINDS = ['api', 'cli'];

export function EngineForm({ mode, initialData }: EngineFormProps) {
  const router = useRouter();
  const createEngine = useCreateEngine();
  const updateEngine = useUpdateEngine();

  const [name, setName] = useState(initialData?.name ?? '');
  const [provider, setProvider] = useState(initialData?.provider ?? 'openai');
  const [model, setModel] = useState(initialData?.model ?? '');
  const [kind, setKind] = useState(initialData?.kind ?? 'api');
  const [temperature, setTemperature] = useState<string>(
    initialData?.temperature != null ? String(initialData.temperature) : ''
  );
  const [apiKeyEnv, setApiKeyEnv] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [error, setError] = useState<string | null>(null);

  const isSubmitting = createEngine.isPending || updateEngine.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    try {
      if (mode === 'create') {
        await createEngine.mutateAsync({
          name,
          provider,
          model,
          kind: kind || undefined,
          temperature: temperature ? parseFloat(temperature) : undefined,
          api_key_env: apiKeyEnv || undefined,
          endpoint: endpoint || undefined,
        });
      } else {
        await updateEngine.mutateAsync({
          name,
          data: {
            provider,
            model,
            kind: kind || undefined,
            temperature: temperature ? parseFloat(temperature) : undefined,
            api_key_env: apiKeyEnv || undefined,
            endpoint: endpoint || undefined,
          },
        });
      }
      router.push('/settings');
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
          placeholder="e.g. gpt-4o"
        />
      </div>

      <div>
        <label htmlFor="provider" className="block text-sm font-medium text-gray-400 mb-1">Provider</label>
        <select
          id="provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        >
          {PROVIDERS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="model" className="block text-sm font-medium text-gray-400 mb-1">Model</label>
        <input
          id="model"
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. gpt-4o-2024-05-13"
        />
      </div>

      <div>
        <label htmlFor="kind" className="block text-sm font-medium text-gray-400 mb-1">
          Kind <span className="text-gray-600">(optional)</span>
        </label>
        <select
          id="kind"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
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

      <div>
        <label htmlFor="api_key_env" className="block text-sm font-medium text-gray-400 mb-1">
          API Key Env Var <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="api_key_env"
          type="text"
          value={apiKeyEnv}
          onChange={(e) => setApiKeyEnv(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. OPENAI_API_KEY"
        />
      </div>

      <div>
        <label htmlFor="endpoint" className="block text-sm font-medium text-gray-400 mb-1">
          Endpoint <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="endpoint"
          type="text"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g. https://api.openai.com/v1"
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors disabled:opacity-50"
        >
          {isSubmitting ? 'Saving...' : mode === 'create' ? 'Create Engine' : 'Save Changes'}
        </button>
        <button
          type="button"
          onClick={() => router.push('/settings')}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-md transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
