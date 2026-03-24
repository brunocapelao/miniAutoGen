import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

// Mock ws-client — must use a class so `new RunEventStream()` works
vi.mock('@/lib/ws-client', () => {
  class MockRunEventStream {
    connect = vi.fn();
    disconnect = vi.fn();
    isConnected = false;
    onEvent = vi.fn().mockReturnValue(() => {});
  }
  return { RunEventStream: MockRunEventStream };
});

// Mock api-client
vi.mock('@/lib/api-client', () => ({
  api: {
    getRunEvents: vi.fn().mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 }),
  },
}));

// Mock connection store
vi.mock('@/stores/connection', () => ({
  useConnectionStore: vi.fn().mockReturnValue({
    setStatus: vi.fn(),
    setRunId: vi.fn(),
  }),
}));

import { useRunEvents } from '@/hooks/useRunEvents';

describe('useRunEvents', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty events initially', () => {
    const { result } = renderHook(() => useRunEvents('run-test-123'));
    expect(result.current.events).toEqual([]);
  });

  it('returns isLive: false initially', () => {
    const { result } = renderHook(() => useRunEvents('run-test-123'));
    expect(result.current.isLive).toBe(false);
  });

  it('returns both events and isLive in result', () => {
    const { result } = renderHook(() => useRunEvents('run-test-456'));
    expect(result.current).toHaveProperty('events');
    expect(result.current).toHaveProperty('isLive');
  });
});
