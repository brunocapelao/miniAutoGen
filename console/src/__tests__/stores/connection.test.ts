import { describe, it, expect, beforeEach } from 'vitest';
import { useConnectionStore } from '@/stores/connection';

describe('useConnectionStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useConnectionStore.setState({ status: 'disconnected', runId: null });
  });

  it('initial state is { status: "disconnected", runId: null }', () => {
    const state = useConnectionStore.getState();
    expect(state.status).toBe('disconnected');
    expect(state.runId).toBeNull();
  });

  it('setStatus updates status', () => {
    useConnectionStore.getState().setStatus('connected');
    expect(useConnectionStore.getState().status).toBe('connected');
  });

  it('setRunId updates runId', () => {
    useConnectionStore.getState().setRunId('run-abc-123');
    expect(useConnectionStore.getState().runId).toBe('run-abc-123');
  });

  it('setRunId can set runId to null', () => {
    useConnectionStore.getState().setRunId('some-run');
    useConnectionStore.getState().setRunId(null);
    expect(useConnectionStore.getState().runId).toBeNull();
  });

  it('status can be set to "disconnected"', () => {
    useConnectionStore.getState().setStatus('disconnected');
    expect(useConnectionStore.getState().status).toBe('disconnected');
  });

  it('status can be set to "connecting"', () => {
    useConnectionStore.getState().setStatus('connecting');
    expect(useConnectionStore.getState().status).toBe('connecting');
  });

  it('status can be set to "connected"', () => {
    useConnectionStore.getState().setStatus('connected');
    expect(useConnectionStore.getState().status).toBe('connected');
  });

  it('status can be set to "polling"', () => {
    useConnectionStore.getState().setStatus('polling');
    expect(useConnectionStore.getState().status).toBe('polling');
  });
});
