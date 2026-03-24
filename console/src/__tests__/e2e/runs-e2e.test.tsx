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

const mockRuns = {
  items: [
    { run_id: 'abc12345-1234-1234-1234-123456789012', pipeline: 'build', status: 'completed', started: '2026-03-24T10:00:00Z', events: 12 },
    { run_id: 'def67890-1234-1234-1234-123456789012', pipeline: 'review', status: 'running', started: '2026-03-24T10:05:00Z', events: 3 },
    { run_id: 'ghi11111-1234-1234-1234-123456789012', pipeline: 'build', status: 'failed', started: '2026-03-24T09:00:00Z', events: 8 },
  ],
  total: 50,
  offset: 0,
  limit: 20,
};

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

describe('Runs Page E2E', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Runs heading', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Runs')).toBeInTheDocument();
    });
  });

  it('renders run table with all column headers', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Run ID')).toBeInTheDocument();
      expect(screen.getByText('Flow')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Events')).toBeInTheDocument();
    });
  });

  it('renders all run rows with truncated IDs', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('abc12345...')).toBeInTheDocument();
      expect(screen.getByText('def67890...')).toBeInTheDocument();
      expect(screen.getByText('ghi11111...')).toBeInTheDocument();
    });
  });

  it('renders pipeline names in the Flow column', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      const buildItems = screen.getAllByText('build');
      expect(buildItems.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('review')).toBeInTheDocument();
    });
  });

  it('renders status badges with correct text', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('COMPLETED')).toBeInTheDocument();
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
      expect(screen.getByText('FAILED')).toBeInTheDocument();
    });
  });

  it('renders event counts', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });
  });

  it('each run ID is a link to the detail page', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      const link = screen.getByText('abc12345...');
      expect(link.closest('a')).toHaveAttribute('href', '/runs/detail?id=abc12345-1234-1234-1234-123456789012');
    });
  });

  it('shows "No runs yet" empty state when items is empty', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No runs yet')).toBeInTheDocument();
    });
  });

  it('shows descriptive message in empty state', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Execute a flow to see run history here')).toBeInTheDocument();
    });
  });

  it('shows "Go to Dashboard" link in empty state', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'Go to Dashboard' });
      expect(link).toHaveAttribute('href', '/');
    });
  });

  it('shows pagination with correct page info when total > PAGE_SIZE', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns); // total=50, limit=20 => 3 pages

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 3 (50 runs)')).toBeInTheDocument();
    });
  });

  it('Previous button is disabled on first page', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Previous')).toBeDisabled();
    });
  });

  it('Next button is enabled on first page when more pages exist', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Next')).not.toBeDisabled();
    });
  });

  it('Next button advances to page 2', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Page 1 of 3 (50 runs)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Next'));

    await waitFor(() => {
      expect(screen.getByText('Page 2 of 3 (50 runs)')).toBeInTheDocument();
    });
  });

  it('Previous button becomes enabled on page 2', async () => {
    vi.mocked(api.getRuns).mockResolvedValue(mockRuns);

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Next')).not.toBeDisabled();
    });

    fireEvent.click(screen.getByText('Next'));

    await waitFor(() => {
      expect(screen.getByText('Previous')).not.toBeDisabled();
    });
  });

  it('shows error state when runs query fails', async () => {
    vi.mocked(api.getRuns).mockRejectedValue(new Error('Failed to fetch'));

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load runs')).toBeInTheDocument();
    });
  });

  it('shows retry button on error state', async () => {
    vi.mocked(api.getRuns).mockRejectedValue(new Error('Failed to fetch'));

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });

  it('does not show pagination when total fits in one page', async () => {
    vi.mocked(api.getRuns).mockResolvedValue({
      items: mockRuns.items,
      total: 3,
      offset: 0,
      limit: 20,
    });

    render(<RunsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.queryByText('Previous')).not.toBeInTheDocument();
      expect(screen.queryByText('Next')).not.toBeInTheDocument();
    });
  });
});
