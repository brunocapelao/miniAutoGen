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

export const api = {
  getWorkspace: () => apiFetch<Record<string, unknown>>('/workspace'),
  getAgents: () => apiFetch<Record<string, unknown>[]>('/agents'),
  getAgent: (name: string) => apiFetch<Record<string, unknown>>(`/agents/${encodeURIComponent(name)}`),
  getFlows: () => apiFetch<Record<string, unknown>[]>('/flows'),
  getFlow: (name: string) => apiFetch<Record<string, unknown>>(`/flows/${encodeURIComponent(name)}`),
  getRuns: (offset = 0, limit = 20) =>
    apiFetch<{ items: Record<string, unknown>[]; total: number }>(`/runs?offset=${offset}&limit=${limit}`),
  getRun: (id: string) => apiFetch<Record<string, unknown>>(`/runs/${encodeURIComponent(id)}`),
  getRunEvents: (id: string, offset = 0) =>
    apiFetch<{ items: Record<string, unknown>[]; total: number }>(`/runs/${encodeURIComponent(id)}/events?offset=${offset}`),
  triggerRun: (flowName: string, input?: string) =>
    apiFetch<{ run_id: string }>('/runs', {
      method: 'POST',
      body: JSON.stringify({ flow_name: flowName, input }),
    }),
  getApprovals: (runId: string) =>
    apiFetch<Record<string, unknown>[]>(`/runs/${encodeURIComponent(runId)}/approvals`),
  resolveApproval: (runId: string, requestId: string, decision: 'approved' | 'denied', reason?: string) =>
    apiFetch<Record<string, unknown>>(`/runs/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(requestId)}`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    }),
};
