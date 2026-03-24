import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mock next/navigation — useSearchParams controlled per test
const mockSearchParams = { get: vi.fn((key: string) => key === 'name' ? 'build' : null) };
vi.mock('next/navigation', () => ({
  useSearchParams: () => mockSearchParams,
  usePathname: () => '/flows',
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
    getFlows: vi.fn(),
    getFlow: vi.fn(),
  },
}));

// Mock FlowCanvas to avoid xyflow complexity
vi.mock('@/components/flow-graph/FlowCanvas', () => ({
  FlowCanvas: ({ participants }: { participants: string[] }) => (
    <div data-testid="flow-canvas">Canvas: {participants.join(', ')}</div>
  ),
}));

import { api } from '@/lib/api-client';
import FlowsPage from '@/app/flows/page';
import FlowDetailPage from '@/app/flows/detail/page';

const mockFlows = [
  { name: 'build', mode: 'workflow', target: '', participants: ['a1', 'a2'], leader: null },
  { name: 'review', mode: 'deliberation', target: '', participants: ['a1', 'a2', 'a3'], leader: 'a1' },
];

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('Flows Page E2E', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Flows heading', async () => {
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Flows')).toBeInTheDocument();
    });
  });

  it('renders flow cards with names', async () => {
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('build')).toBeInTheDocument();
      expect(screen.getByText('review')).toBeInTheDocument();
    });
  });

  it('renders mode badges for flows', async () => {
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('workflow')).toBeInTheDocument();
      expect(screen.getByText('deliberation')).toBeInTheDocument();
    });
  });

  it('renders participant count for each flow', async () => {
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/2 agents: a1, a2/)).toBeInTheDocument();
      expect(screen.getByText(/3 agents: a1, a2, a3/)).toBeInTheDocument();
    });
  });

  it('renders leader info for flows that have a leader', async () => {
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Leader: a1')).toBeInTheDocument();
    });
  });

  it('each flow card is a link to the detail page', async () => {
    vi.mocked(api.getFlows).mockResolvedValue(mockFlows);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      const buildLink = screen.getByRole('link', { name: /build/ });
      expect(buildLink).toHaveAttribute('href', '/flows/detail?name=build');
      const reviewLink = screen.getByRole('link', { name: /review/ });
      expect(reviewLink).toHaveAttribute('href', '/flows/detail?name=review');
    });
  });

  it('renders empty flows grid when no flows returned', async () => {
    vi.mocked(api.getFlows).mockResolvedValue([]);

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Flows')).toBeInTheDocument();
      expect(screen.queryByText('build')).not.toBeInTheDocument();
    });
  });

  it('shows error state when flows query fails', async () => {
    vi.mocked(api.getFlows).mockRejectedValue(new Error('Server error'));

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load flows')).toBeInTheDocument();
    });
  });

  it('shows retry button on flows error', async () => {
    vi.mocked(api.getFlows).mockRejectedValue(new Error('Server error'));

    render(<FlowsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });
});

describe('Flow Detail Page E2E', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders flow name and mode badge', async () => {
    vi.mocked(api.getFlow).mockResolvedValue({
      name: 'build',
      mode: 'workflow',
      target: '',
      participants: ['a1', 'a2'],
      leader: null,
    });

    render(<FlowDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // 'build' appears in both breadcrumb and h2 — use getAllByText
      const buildElements = screen.getAllByText('build');
      expect(buildElements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('workflow')).toBeInTheDocument();
    });
  });

  it('renders breadcrumb navigation', async () => {
    vi.mocked(api.getFlow).mockResolvedValue({
      name: 'build',
      mode: 'workflow',
      target: '',
      participants: ['a1', 'a2'],
      leader: null,
    });

    render(<FlowDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Flows' })).toHaveAttribute('href', '/flows');
    });
  });

  it('renders flow canvas with participants', async () => {
    vi.mocked(api.getFlow).mockResolvedValue({
      name: 'build',
      mode: 'workflow',
      target: '',
      participants: ['a1', 'a2'],
      leader: null,
    });

    render(<FlowDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('flow-canvas')).toBeInTheDocument();
      expect(screen.getByText(/Canvas: a1, a2/)).toBeInTheDocument();
    });
  });

  it('shows leader info when flow has a leader', async () => {
    vi.mocked(api.getFlow).mockResolvedValue({
      name: 'review',
      mode: 'deliberation',
      target: '',
      participants: ['a1', 'a2', 'a3'],
      leader: 'a1',
    });

    render(<FlowDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('a1')).toBeInTheDocument();
      expect(screen.getByText('Leader:')).toBeInTheDocument();
    });
  });

  it('shows error state when flow fails to load', async () => {
    vi.mocked(api.getFlow).mockRejectedValue(new Error('Not found'));

    render(<FlowDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Flow not found or failed to load')).toBeInTheDocument();
    });
  });
});
