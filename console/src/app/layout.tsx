'use client';

import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { api } from '@/lib/api-client';

const ICONS: Record<string, React.ReactNode> = {
  '/': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  ),
  '/agents': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <circle cx="9" cy="7" r="4" />
      <path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" strokeDasharray="2 2" />
      <path d="M21 21v-2a4 4 0 0 0-3-3.87" strokeDasharray="2 2" />
    </svg>
  ),
  '/flows': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="6" r="3" />
      <path d="M6 15V6h12" />
    </svg>
  ),
  '/runs': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <polygon points="5,3 19,12 5,21" />
    </svg>
  ),
  '/logs': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  ),
  '/settings': (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
};

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard' },
  { href: '/agents', label: 'Agents' },
  { href: '/flows', label: 'Flows' },
  { href: '/runs', label: 'Runs' },
  { href: '/logs', label: 'Logs' },
  { href: '/settings', label: 'Settings' },
];

function Sidebar() {
  const pathname = usePathname();
  const { data: workspace } = useQuery({
    queryKey: ['workspace'],
    queryFn: api.getWorkspace,
  });

  return (
    <nav className="w-56 border-r border-gray-800 bg-gray-900 p-4 flex flex-col">
      <div className="mb-3">
        <h1 className="text-lg font-bold px-2 text-white">MiniAutoGen</h1>
        {workspace?.project_name && (
          <p className="text-xs text-gray-500 px-2 mt-0.5 truncate" title={workspace.project_name}>
            {workspace.project_name}
          </p>
        )}
      </div>
      <div className="border-b border-gray-800 mb-3" />
      <div className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
              pathname === item.href
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
            }`}
          >
            <span className={pathname === item.href ? 'text-white' : 'text-gray-500'}>
              {ICONS[item.href]}
            </span>
            {item.label}
          </Link>
        ))}
      </div>
      <div className="border-t border-gray-800 pt-3 mt-3">
        <p className="px-2 text-xs text-gray-600">v0.1.0</p>
      </div>
    </nav>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100">
        <QueryClientProvider client={queryClient}>
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto p-6">
              <ErrorBoundary>{children}</ErrorBoundary>
            </main>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}
