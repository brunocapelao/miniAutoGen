import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '@/lib/api-client';

describe('api-client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('getWorkspace calls correct endpoint', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ project_name: 'test' }), { status: 200 }));
    const result = await api.getWorkspace();
    expect(result.project_name).toBe('test');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/workspace', expect.objectContaining({ headers: expect.any(Object) }));
  });

  it('getRuns passes offset and limit', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ items: [], total: 0, offset: 10, limit: 5 }), { status: 200 }));
    await api.getRuns(10, 5);
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/runs?offset=10&limit=5', expect.any(Object));
  });

  it('triggerRun sends POST with flow name', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ run_id: 'abc' }), { status: 200 }));
    const result = await api.triggerRun('my-flow', 'input data');
    expect(result.run_id).toBe('abc');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/runs', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ flow_name: 'my-flow', input: 'input data' }),
    }));
  });

  it('throws on non-ok response', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ error: 'Not found' }), { status: 404 }));
    await expect(api.getAgent('missing')).rejects.toThrow('Not found');
  });
});
