'use client';

export function SkeletonRow({ cols = 3 }: { cols?: number }) {
  return (
    <tr className="border-b border-gray-800 last:border-0">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="p-3">
          <div className="h-4 bg-gray-800 rounded animate-pulse w-3/4" />
        </td>
      ))}
    </tr>
  );
}

export function SkeletonTable({ rows = 5, cols = 3 }: { rows?: number; cols?: number }) {
  return (
    <div className="border border-gray-800 rounded-lg bg-gray-900">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-800">
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} className="text-left p-3">
                <div className="h-3 bg-gray-800 rounded animate-pulse w-16" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonRow key={i} cols={cols} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="border border-gray-800 rounded-lg p-4 bg-gray-900">
      <div className="h-3 bg-gray-800 rounded animate-pulse w-20 mb-2" />
      <div className="h-8 bg-gray-800 rounded animate-pulse w-12" />
    </div>
  );
}

export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
