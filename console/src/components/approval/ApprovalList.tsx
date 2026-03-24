'use client';

import { useState } from 'react';
import { ApprovalModal } from './ApprovalModal';
import type { Approval } from '@/types/api';

type ApprovalListProps = {
  approvals: Approval[];
  onResolve: (requestId: string, decision: 'approved' | 'denied', reason?: string) => void;
};

export function ApprovalList({ approvals, onResolve }: ApprovalListProps) {
  const [selected, setSelected] = useState<Approval | null>(null);

  if (approvals.length === 0) return null;

  return (
    <div>
      <h3 className="font-bold mb-2 text-yellow-400">
        Pending Approvals ({approvals.length})
      </h3>
      <div className="space-y-2">
        {approvals.map((a) => (
          <div
            key={a.request_id}
            className="flex items-center justify-between border border-yellow-500/30 bg-yellow-500/5 rounded-lg p-3"
          >
            <div className="text-sm">
              <span className="font-mono">{a.agent_name}</span>
              <span className="text-gray-400 mx-2">wants to</span>
              <span className="font-mono">{a.action}</span>
            </div>
            <button
              type="button"
              onClick={() => setSelected(a)}
              className="px-3 py-1 text-xs bg-yellow-600 hover:bg-yellow-700 text-white rounded transition-colors"
            >
              Review
            </button>
          </div>
        ))}
      </div>
      {selected && (
        <ApprovalModal
          approval={selected}
          onResolve={(id, decision, reason) => {
            onResolve(id, decision, reason);
            setSelected(null);
          }}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
