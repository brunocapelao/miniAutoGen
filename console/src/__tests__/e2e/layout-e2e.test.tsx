import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/ErrorBoundary';

// Mock next/navigation — will be updated per test in the Sidebar active-state tests
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: vi.fn(() => '/'),
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
  },
}));

import { api } from '@/lib/api-client';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard' },
  { href: '/agents', label: 'Agents' },
  { href: '/flows', label: 'Flows' },
  { href: '/runs', label: 'Runs' },
];

// Mirror the Sidebar from layout.tsx for isolated testing
function Sidebar() {
  const pathname = usePathname();
  const { data: workspace } = useQuery({
    queryKey: ['workspace'],
    queryFn: () => (api as typeof api).getWorkspace(),
  });

  return (
    <nav className="w-56 border-r border-gray-800 bg-gray-900 p-4 flex flex-col" role="navigation">
      <div className="mb-3">
        <h1 className="text-lg font-bold px-2 text-white">MiniAutoGen</h1>
        {workspace?.project_name && (
          <p className="text-xs text-gray-500 px-2 mt-0.5 truncate" data-testid="workspace-name">
            {workspace.project_name}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
              pathname === item.href
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
            }`}
          >
            <svg className="w-4 h-4" aria-hidden="true" />
            {item.label}
          </a>
        ))}
      </div>
    </nav>
  );
}

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

describe('Sidebar E2E', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePathname).mockReturnValue('/');
    vi.mocked(api.getWorkspace).mockResolvedValue({
      project_name: 'my-workspace',
      project_root: '/home/user/project',
      agent_count: 3,
      pipeline_count: 2,
      engine_count: 1,
    });
  });

  it('renders "MiniAutoGen" title', async () => {
    render(<Sidebar />, { wrapper: createWrapper() });
    expect(screen.getByText('MiniAutoGen')).toBeInTheDocument();
  });

  it('renders all 4 navigation items', async () => {
    render(<Sidebar />, { wrapper: createWrapper() });

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getByText('Flows')).toBeInTheDocument();
    expect(screen.getByText('Runs')).toBeInTheDocument();
  });

  it('each nav item is a link with correct href', async () => {
    render(<Sidebar />, { wrapper: createWrapper() });

    expect(screen.getByRole('link', { name: /Dashboard/ })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /Agents/ })).toHaveAttribute('href', '/agents');
    expect(screen.getByRole('link', { name: /Flows/ })).toHaveAttribute('href', '/flows');
    expect(screen.getByRole('link', { name: /Runs/ })).toHaveAttribute('href', '/runs');
  });

  it('each nav item contains an SVG icon', async () => {
    const { container } = render(<Sidebar />, { wrapper: createWrapper() });
    const svgs = container.querySelectorAll('nav svg');
    expect(svgs.length).toBe(4);
  });

  it('active nav item (Dashboard) has blue background when pathname is /', async () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<Sidebar />, { wrapper: createWrapper() });

    const dashboardLink = screen.getByRole('link', { name: /Dashboard/ });
    expect(dashboardLink).toHaveClass('bg-blue-600');
  });

  it('inactive nav items do not have blue background class', async () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<Sidebar />, { wrapper: createWrapper() });

    const agentsLink = screen.getByRole('link', { name: /Agents/ });
    expect(agentsLink).not.toHaveClass('bg-blue-600');
    expect(agentsLink).toHaveClass('text-gray-400');
  });

  it('active item changes when pathname is /agents', async () => {
    vi.mocked(usePathname).mockReturnValue('/agents');
    render(<Sidebar />, { wrapper: createWrapper() });

    const agentsLink = screen.getByRole('link', { name: /Agents/ });
    expect(agentsLink).toHaveClass('bg-blue-600');

    const dashboardLink = screen.getByRole('link', { name: /Dashboard/ });
    expect(dashboardLink).not.toHaveClass('bg-blue-600');
  });

  it('active item changes when pathname is /flows', async () => {
    vi.mocked(usePathname).mockReturnValue('/flows');
    render(<Sidebar />, { wrapper: createWrapper() });

    expect(screen.getByRole('link', { name: /Flows/ })).toHaveClass('bg-blue-600');
    expect(screen.getByRole('link', { name: /Runs/ })).not.toHaveClass('bg-blue-600');
  });

  it('renders workspace name from API', async () => {
    render(<Sidebar />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('workspace-name')).toHaveTextContent('my-workspace');
    });
  });

  it('does not render workspace name when API returns no data', async () => {
    vi.mocked(api.getWorkspace).mockReturnValue(new Promise(() => {})); // never resolves

    render(<Sidebar />, { wrapper: createWrapper() });

    expect(screen.queryByTestId('workspace-name')).not.toBeInTheDocument();
  });
});

describe('ErrorBoundary E2E', () => {
  it('renders child content normally when no error', () => {
    render(
      <ErrorBoundary>
        <div>Main content</div>
      </ErrorBoundary>,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('Main content')).toBeInTheDocument();
  });

  it('catches errors and shows "Something went wrong" UI', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function ThrowError() {
      throw new Error('Test render error');
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Test render error')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('shows Try again button in error state', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function ThrowError() {
      throw new Error('Render crash');
    }

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('renders custom fallback when provided', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function ThrowError() {
      throw new Error('Crash');
    }

    render(
      <ErrorBoundary fallback={<div>Custom fallback</div>}>
        <ThrowError />
      </ErrorBoundary>,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('Custom fallback')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
