import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/agents',
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock api-client
vi.mock('@/lib/api-client', () => ({
  api: {
    getAgents: vi.fn(),
  },
}));

import { api } from '@/lib/api-client';
import AgentsPage from '@/app/agents/page';

const mockAgents = [
  { name: 'architect', role: 'Designs the game structure', engine_type: 'gemini', engine_profile: 'gemini' },
  { name: 'developer', role: 'Writes Python code', engine_type: 'openai', engine_profile: 'gpt4' },
  { name: 'tester', role: 'Writes tests', engine_type: 'gemini', engine_profile: 'gemini' },
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

describe('Agents Page E2E', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Agents heading', async () => {
    vi.mocked(api.getAgents).mockResolvedValue(mockAgents);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument();
    });
  });

  it('renders agent table with all column headers', async () => {
    vi.mocked(api.getAgents).mockResolvedValue(mockAgents);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Agent')).toBeInTheDocument();
      expect(screen.getByText('Role')).toBeInTheDocument();
      expect(screen.getByText('Engine')).toBeInTheDocument();
    });
  });

  it('renders all agent rows with names', async () => {
    vi.mocked(api.getAgents).mockResolvedValue(mockAgents);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('architect')).toBeInTheDocument();
      expect(screen.getByText('developer')).toBeInTheDocument();
      expect(screen.getByText('tester')).toBeInTheDocument();
    });
  });

  it('renders agent role descriptions', async () => {
    vi.mocked(api.getAgents).mockResolvedValue(mockAgents);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Designs the game structure')).toBeInTheDocument();
      expect(screen.getByText('Writes Python code')).toBeInTheDocument();
      expect(screen.getByText('Writes tests')).toBeInTheDocument();
    });
  });

  it('renders avatar initials for each agent', async () => {
    vi.mocked(api.getAgents).mockResolvedValue(mockAgents);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Initials are first 2 chars of name (uppercase via CSS, but text content is lowercase)
      expect(screen.getByText('ar')).toBeInTheDocument(); // architect
      expect(screen.getByText('de')).toBeInTheDocument(); // developer
      expect(screen.getByText('te')).toBeInTheDocument(); // tester
    });
  });

  it('renders engine type badge for each agent', async () => {
    vi.mocked(api.getAgents).mockResolvedValue(mockAgents);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // gemini appears twice (architect + tester)
      const geminiBadges = screen.getAllByText('gemini');
      expect(geminiBadges.length).toBeGreaterThanOrEqual(2);
      // openai appears once (developer)
      expect(screen.getByText('openai')).toBeInTheDocument();
    });
  });

  it('renders empty table when no agents returned', async () => {
    vi.mocked(api.getAgents).mockResolvedValue([]);

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument();
      // Table still renders but no rows
      expect(screen.getByText('Agent')).toBeInTheDocument(); // header
      expect(screen.queryByText('architect')).not.toBeInTheDocument();
    });
  });

  it('shows error state with message when agents query fails', async () => {
    vi.mocked(api.getAgents).mockRejectedValue(new Error('Connection refused'));

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load agents')).toBeInTheDocument();
    });
  });

  it('shows retry button on error state', async () => {
    vi.mocked(api.getAgents).mockRejectedValue(new Error('Connection refused'));

    render(<AgentsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });
});
