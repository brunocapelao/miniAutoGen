'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useEventStream } from '@/hooks/useEventStream';

const EVENT_TYPES = [
  'All',
  'run_started',
  'run_finished',
  'component_started',
  'component_finished',
  'llm_call_started',
  'llm_call_finished',
  'tool_call',
  'approval_requested',
  'error',
];

const TYPE_COLORS: Record<string, string> = {
  run_started: 'bg-green-900 text-green-300',
  run_finished: 'bg-blue-900 text-blue-300',
  component_started: 'bg-cyan-900 text-cyan-300',
  component_finished: 'bg-cyan-900 text-cyan-300',
  llm_call_started: 'bg-purple-900 text-purple-300',
  llm_call_finished: 'bg-purple-900 text-purple-300',
  tool_call: 'bg-yellow-900 text-yellow-300',
  approval_requested: 'bg-orange-900 text-orange-300',
  error: 'bg-red-900 text-red-300',
};

function typeBadgeClass(type: string): string {
  return TYPE_COLORS[type] ?? 'bg-gray-800 text-gray-300';
}

function truncateId(id?: string): string {
  if (!id) return '-';
  return id.length > 8 ? id.slice(0, 8) + '...' : id;
}

export default function LogsPage() {
  const { events, connected, clear } = useEventStream();
  const [typeFilter, setTypeFilter] = useState('All');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = typeFilter === 'All'
    ? events
    : events.filter((e) => e.type === typeFilter);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered.length, autoScroll]);

  const handleExport = useCallback(() => {
    const blob = new Blob([JSON.stringify(filtered, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `miniautogen-logs-${new Date().toISOString().slice(0, 19)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filtered]);

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-white">Logs</h1>
          <span className="flex items-center gap-1.5 text-xs text-gray-400">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                connected ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={clear}
            className="px-3 py-1.5 text-xs rounded-md bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
          >
            Clear
          </button>
          <button
            onClick={handleExport}
            className="px-3 py-1.5 text-xs rounded-md bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
          >
            Export JSON
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <label className="text-xs text-gray-400">Filter by type:</label>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-gray-800 text-gray-200 text-xs rounded-md px-2 py-1.5 border border-gray-700 focus:outline-none focus:border-blue-500"
        >
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button
          onClick={() => setAutoScroll((v) => !v)}
          className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
            autoScroll
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
        >
          Auto-scroll {autoScroll ? 'ON' : 'OFF'}
        </button>
        <span className="text-xs text-gray-500 ml-auto">
          {filtered.length} event{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Event list */}
      <div
        ref={scrollRef}
        className="border border-gray-800 rounded-lg overflow-auto flex-1 bg-gray-900"
        style={{ maxHeight: 'calc(100vh - 200px)' }}
      >
        <table className="w-full text-xs font-mono">
          <thead className="sticky top-0 bg-gray-900 z-10">
            <tr className="border-b border-gray-800">
              <th className="text-left p-2 text-gray-400">Time</th>
              <th className="text-left p-2 text-gray-400">Type</th>
              <th className="text-left p-2 text-gray-400">Scope</th>
              <th className="text-left p-2 text-gray-400">Run ID</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="p-8 text-center text-gray-500">
                  {connected
                    ? 'Waiting for events...'
                    : 'Not connected to event stream'}
                </td>
              </tr>
            ) : (
              filtered.map((event, i) => (
                <tr
                  key={i}
                  className="border-b border-gray-800 last:border-0 hover:bg-gray-800/50"
                >
                  <td className="p-2 text-gray-500 whitespace-nowrap">
                    {event.timestamp
                      ? new Date(event.timestamp).toLocaleTimeString()
                      : '-'}
                  </td>
                  <td className="p-2">
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${typeBadgeClass(
                        event.type
                      )}`}
                    >
                      {event.type}
                    </span>
                  </td>
                  <td className="p-2 text-gray-400 truncate max-w-xs">
                    {event.scope || '-'}
                  </td>
                  <td className="p-2 text-gray-500 font-mono">
                    {truncateId(event.run_id)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
