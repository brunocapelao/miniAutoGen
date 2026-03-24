import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/runs',
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
    getRuns: vi.fn(),
  },
}));

import { api } from '@/lib/api-client';
import RunsPage from '@/app/runs/page';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('RunsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows "No runs yet" when items is empty', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/No runs yet/)).toBeInTheDocument();
    });
  });

  it('renders run rows when data exists', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: [
        { run_id: 'abc12345-1111', pipeline: 'my-flow', status: 'completed', events: 10 },
        { run_id: 'def67890-2222', pipeline: 'other-flow', status: 'running', events: 5 },
      ],
      total: 2,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('my-flow')).toBeInTheDocument();
      expect(screen.getByText('other-flow')).toBeInTheDocument();
    });
  });

  it('shows pagination controls when totalPages > 1', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => ({
        run_id: `run-${i}-abcdefgh`,
        pipeline: `flow-${i}`,
        status: 'completed',
        events: i,
      })),
      total: 45,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Previous')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
    });
  });

  it('Previous button is disabled on first page', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => ({
        run_id: `run-${i}-abcdefgh`,
        pipeline: `flow-${i}`,
        status: 'completed',
        events: i,
      })),
      total: 45,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Previous')).toBeDisabled();
    });
  });

  it('Next button is enabled on first page when more pages exist', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => ({
        run_id: `run-${i}-abcdefgh`,
        pipeline: `flow-${i}`,
        status: 'completed',
        events: i,
      })),
      total: 45,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Next')).not.toBeDisabled();
    });
  });

  it('Next button click increments page', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => ({
        run_id: `run-${i}-abcdefgh`,
        pipeline: `flow-${i}`,
        status: 'completed',
        events: i,
      })),
      total: 45,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 3 (45 runs)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Next'));

    await waitFor(() => {
      // After clicking Next, page becomes 1 (index), showing "Page 2 of 3"
      // The query re-runs with new offset — mock returns same data
      expect(screen.getByText('Page 2 of 3 (45 runs)')).toBeInTheDocument();
    });
  });
});
