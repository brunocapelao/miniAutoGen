'use client';

import type { RunEvent } from '@/types/api';

export function EventFeed({ events }: { events: RunEvent[] }) {
  return (
    <div className="border border-gray-800 rounded-lg overflow-auto max-h-96 bg-gray-900">
      <table className="w-full text-xs font-mono">
        <thead className="sticky top-0 bg-gray-900">
          <tr className="border-b border-gray-800">
            <th className="text-left p-2 text-gray-400">Time</th>
            <th className="text-left p-2 text-gray-400">Type</th>
            <th className="text-left p-2 text-gray-400">Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, i) => (
            <tr key={i} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/50">
              <td className="p-2 text-gray-500 whitespace-nowrap">
                {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '-'}
              </td>
              <td className="p-2">{event.type}</td>
              <td className="p-2 text-gray-500 truncate max-w-xs">{event.scope || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
