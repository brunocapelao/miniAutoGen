import type { Workspace, Agent, Flow, Engine, RunSummary, RunEvent, Approval, Page } from '@/types/api';

// In production (static export served by FastAPI), use relative URL (same origin).
// In development (next dev), use NEXT_PUBLIC_API_URL env var.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(error.error || resp.statusText);
  }
  return resp.json();
}

function post<T>(path: string, data: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'POST', body: JSON.stringify(data) });
}

function put<T>(path: string, data: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'PUT', body: JSON.stringify(data) });
}

function del<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' });
}

export const api = {
  getWorkspace: () => apiFetch<Workspace>('/workspace'),
  getAgents: () => apiFetch<Agent[]>('/agents'),
  getAgent: (name: string) => apiFetch<Agent>(`/agents/${encodeURIComponent(name)}`),
  getFlows: () => apiFetch<Flow[]>('/flows'),
  getFlow: (name: string) => apiFetch<Flow>(`/flows/${encodeURIComponent(name)}`),
  getRuns: (offset = 0, limit = 20) =>
    apiFetch<Page<RunSummary>>(`/runs?offset=${offset}&limit=${limit}`),
  getRun: (id: string) => apiFetch<RunSummary>(`/runs/${encodeURIComponent(id)}`),
  getRunEvents: (id: string, offset = 0) =>
    apiFetch<Page<RunEvent>>(`/runs/${encodeURIComponent(id)}/events?offset=${offset}`),
  triggerRun: (flowName: string, input?: string) =>
    apiFetch<{ run_id: string }>('/runs', {
      method: 'POST',
      body: JSON.stringify({ flow_name: flowName, input }),
    }),
  getApprovals: (runId: string) =>
    apiFetch<Approval[]>(`/runs/${encodeURIComponent(runId)}/approvals`),
  resolveApproval: (runId: string, requestId: string, decision: 'approved' | 'denied', reason?: string) =>
    apiFetch<{ status: string; decision: string }>(`/runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(requestId)}`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    }),

  // Agent CRUD
  createAgent: (data: { name: string; role: string; goal: string; engine_profile: string; temperature?: number }) =>
    post<Agent>('/agents', data),
  updateAgent: (name: string, data: Record<string, unknown>) =>
    put<Agent>(`/agents/${encodeURIComponent(name)}`, data),
  deleteAgent: (name: string) =>
    del<{ status: string }>(`/agents/${encodeURIComponent(name)}`),

  // Engine CRUD
  getEngines: () => apiFetch<Engine[]>('/engines'),
  getEngine: (name: string) => apiFetch<Engine>(`/engines/${encodeURIComponent(name)}`),
  createEngine: (data: { name: string; provider: string; model: string; kind?: string; temperature?: number; api_key_env?: string; endpoint?: string }) =>
    post<Engine>('/engines', data),
  updateEngine: (name: string, data: Record<string, unknown>) =>
    put<Engine>(`/engines/${encodeURIComponent(name)}`, data),
  deleteEngine: (name: string) =>
    del<{ status: string }>(`/engines/${encodeURIComponent(name)}`),

  // Events
  fetchEvents: (params?: { limit?: number; type?: string }) => {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.type) query.set('type', params.type);
    const qs = query.toString();
    return apiFetch<RunEvent[]>(`/events${qs ? `?${qs}` : ''}`);
  },

  // Config
  getConfigDetail: () => apiFetch<Record<string, unknown>>('/config/detail'),

  // Flow CRUD
  createFlow: (data: { name: string; mode?: string; participants?: string[]; leader?: string; target?: string }) =>
    post<Flow>('/flows', data),
  updateFlow: (name: string, data: Record<string, unknown>) =>
    put<Flow>(`/flows/${encodeURIComponent(name)}`, data),
  deleteFlow: (name: string) =>
    del<{ status: string }>(`/flows/${encodeURIComponent(name)}`),
};
