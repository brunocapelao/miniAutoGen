import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mock api-client
vi.mock('@/lib/api-client', () => ({
  api: {
    getWorkspace: vi.fn(),
    getRuns: vi.fn(),
    getFlows: vi.fn(),
    triggerRun: vi.fn(),
  },
}));

import { api } from '@/lib/api-client';
import Dashboard from '@/app/page';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getWorkspace).mockResolvedValue({
      project_name: 'test-project',
      project_root: '/tmp/test',
      agent_count: 3,
      pipeline_count: 2,
      engine_count: 1,
    });
    vi.mocked(api.getRuns).mockResolvedValue({
      items: [],
      total: 7,
      offset: 0,
      limit: 20,
    });
    vi.mocked(api.getFlows).mockResolvedValue([
      { name: 'flow-alpha', mode: 'workflow', target: 'agent1', participants: ['agent1'], leader: null },
      { name: 'flow-beta', mode: 'group_chat', target: 'agent2', participants: ['agent2'], leader: null },
    ]);
  });

  it('shows stat cards (Agents, Flows, Runs counts)', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument();
      expect(screen.getByText('Flows')).toBeInTheDocument();
      expect(screen.getByText('Runs')).toBeInTheDocument();
    });

    // Check the actual count values
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument(); // agent_count
      expect(screen.getByText('2')).toBeInTheDocument(); // pipeline_count
      expect(screen.getByText('7')).toBeInTheDocument(); // runs total
    });
  });

  it('shows Trigger Run section with flow selector', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Trigger Run')).toBeInTheDocument();
      expect(screen.getByLabelText('Flow')).toBeInTheDocument();
    });
  });

  it('shows flow options in selector', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('flow-alpha')).toBeInTheDocument();
      expect(screen.getByText('flow-beta')).toBeInTheDocument();
    });
  });

  it('Run button is disabled when no flow selected', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      const runButton = screen.getByRole('button', { name: 'Run' });
      expect(runButton).toBeDisabled();
    });
  });

  it('Run button is enabled when a flow is selected', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    // Wait for flows to load so select options are present
    await waitFor(() => {
      expect(screen.getByText('flow-alpha')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Flow'), { target: { value: 'flow-alpha' } });

    await waitFor(() => {
      const runButton = screen.getByRole('button', { name: 'Run' });
      expect(runButton).not.toBeDisabled();
    });
  });

  it('shows "Running..." when mutation is pending', async () => {
    // Make triggerRun never resolve so mutation stays pending
    vi.mocked(api.triggerRun).mockReturnValue(new Promise(() => {}));

    render(<Dashboard />, { wrapper: createWrapper() });

    // Wait for flows to load so select options are present
    await waitFor(() => {
      expect(screen.getByText('flow-alpha')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Flow'), { target: { value: 'flow-alpha' } });

    // Wait for button to be enabled before clicking
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run' })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Run' }));

    await waitFor(() => {
      expect(screen.getByText('Running...')).toBeInTheDocument();
    });
  });
});
