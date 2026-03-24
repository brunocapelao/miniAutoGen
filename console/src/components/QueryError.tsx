'use client';

type QueryErrorProps = {
  error: Error | null;
  message?: string;
  onRetry?: () => void;
};

export function QueryError({ error, message, onRetry }: QueryErrorProps) {
  return (
    <div className="border border-red-500/30 bg-red-500/5 rounded-lg p-4">
      <p className="text-red-400 text-sm font-medium">{message || 'Failed to load data'}</p>
      {error && <p className="text-xs text-gray-500 mt-1">{error.message}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-white rounded transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
