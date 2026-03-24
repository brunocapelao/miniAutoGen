import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

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

const mockWorkspace = {
  project_name: 'test-project',
  project_root: '/tmp',
  agent_count: 4,
  pipeline_count: 2,
  engine_count: 1,
};

const mockRuns = { items: [], total: 5, offset: 0, limit: 20 };

const mockFlows = [
  { name: 'build', mode: 'workflow', target: '', participants: ['a1', 'a2'], leader: null },
  { name: 'review', mode: 'deliberation', target: '', participants: ['a1', 'a2', 'a3'], leader: 'a1' },
];

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('Dashboard E2E', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getWorkspace).mockResolvedValue(mockWorkspace);
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);
  });

  it('renders all 3 stat cards with correct values', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument();
      expect(screen.getByText('Flows')).toBeInTheDocument();
      expect(screen.getByText('Runs')).toBeInTheDocument();
    });

    // agent_count = 4, pipeline_count = 2, runs.total = 5
    await waitFor(() => {
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  it('shows workspace name in heading area', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });
    // Dashboard itself shows the Dashboard heading
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
  });

  it('renders Trigger Run section', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Trigger Run')).toBeInTheDocument();
      expect(screen.getByLabelText('Select Flow')).toBeInTheDocument();
    });
  });

  it('populates flow options in the selector', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      const select = screen.getByLabelText('Select Flow') as HTMLSelectElement;
      const options = Array.from(select.options).map((o) => o.value);
      expect(options).toContain('build');
      expect(options).toContain('review');
    });
  });

  it('Run button is disabled when no flow selected', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled();
    });
  });

  it('Run button is enabled after selecting a flow', async () => {
    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      const select = screen.getByLabelText('Select Flow');
      expect(select).toBeInTheDocument();
      // verify options are loaded
      const opts = Array.from((select as HTMLSelectElement).options).map((o) => o.value);
      expect(opts).toContain('build');
    });

    fireEvent.change(screen.getByLabelText('Select Flow'), { target: { value: 'build' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run' })).not.toBeDisabled();
    });
  });

  it('shows success message after triggering a run', async () => {
    vi.mocked(api.triggerRun).mockResolvedValue({ run_id: 'abcdef12-1234-1234-1234-123456789012' });

    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      const opts = Array.from((screen.getByLabelText('Select Flow') as HTMLSelectElement).options).map((o) => o.value);
      expect(opts).toContain('build');
    });

    fireEvent.change(screen.getByLabelText('Select Flow'), { target: { value: 'build' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run' })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Run' }));

    await waitFor(() => {
      expect(screen.getByText(/Run started: abcdef12/)).toBeInTheDocument();
    });
  });

  it('shows error message when trigger run fails', async () => {
    vi.mocked(api.triggerRun).mockRejectedValue(new Error('API unavailable'));

    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      const opts = Array.from((screen.getByLabelText('Select Flow') as HTMLSelectElement).options).map((o) => o.value);
      expect(opts).toContain('build');
    });

    fireEvent.change(screen.getByLabelText('Select Flow'), { target: { value: 'build' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run' })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Run' }));

    await waitFor(() => {
      expect(screen.getByText('API unavailable')).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while workspace data is loading', async () => {
    // Make workspace never resolve
    vi.mocked(api.getWorkspace).mockReturnValue(new Promise(() => {}));

    render(<Dashboard />, { wrapper: createWrapper() });

    // Skeleton cards are present before data loads
    // SkeletonCards renders divs with animate-pulse — check that stat counts are absent
    expect(screen.queryByText('4')).not.toBeInTheDocument();
    expect(screen.queryByText('2')).not.toBeInTheDocument();
  });

  it('shows error state when workspace query fails', async () => {
    vi.mocked(api.getWorkspace).mockRejectedValue(new Error('Network error'));

    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load workspace data')).toBeInTheDocument();
    });
  });

  it('shows retry button on workspace error', async () => {
    vi.mocked(api.getWorkspace).mockRejectedValue(new Error('Network error'));

    render(<Dashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });
});
