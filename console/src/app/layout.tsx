'use client';

import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard' },
  { href: '/agents', label: 'Agents' },
  { href: '/flows', label: 'Flows' },
  { href: '/runs', label: 'Runs' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [queryClient] = useState(() => new QueryClient());

  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100">
        <QueryClientProvider client={queryClient}>
          <div className="flex h-screen">
            <nav className="w-56 border-r border-gray-800 bg-gray-900 p-4 flex flex-col gap-1">
              <h1 className="text-lg font-bold mb-4 px-2 text-white">MiniAutoGen</h1>
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-2 rounded-md text-sm transition-colors ${
                    pathname === item.href
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <main className="flex-1 overflow-auto p-6">{children}</main>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}
