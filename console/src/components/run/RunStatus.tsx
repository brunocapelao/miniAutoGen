'use client';

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-500/10 text-green-400 border-green-500/20',
  running: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  failed: 'bg-red-500/10 text-red-400 border-red-500/20',
};

export function RunStatus({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  return (
    <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${color}`}>
      {status.toUpperCase()}
    </span>
  );
}
