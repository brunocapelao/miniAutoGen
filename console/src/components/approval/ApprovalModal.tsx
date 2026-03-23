'use client';

import { useState } from 'react';

type Approval = {
  request_id: string;
  agent_name: string;
  action: string;
  requested_at: string;
};

type ApprovalModalProps = {
  approval: Approval;
  onResolve: (requestId: string, decision: 'approved' | 'denied', reason?: string) => void;
  onClose: () => void;
};

export function ApprovalModal({ approval, onResolve, onClose }: ApprovalModalProps) {
  const [reason, setReason] = useState('');

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-modal-title"
    >
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-md shadow-xl">
        <h3 id="approval-modal-title" className="text-lg font-bold mb-4">
          Approval Request
        </h3>

        <div className="space-y-2 mb-4 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Agent</span>
            <span className="font-mono">{approval.agent_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Action</span>
            <span className="font-mono">{approval.action}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Requested</span>
            <span>{new Date(approval.requested_at).toLocaleString()}</span>
          </div>
        </div>

        <div className="mb-4">
          <label htmlFor="approval-reason" className="block text-sm text-gray-400 mb-1">
            Reason (optional)
          </label>
          <textarea
            id="approval-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Add a reason..."
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            rows={2}
          />
        </div>

        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onResolve(approval.request_id, 'denied', reason || undefined)}
            className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
          >
            Deny
          </button>
          <button
            type="button"
            onClick={() => onResolve(approval.request_id, 'approved', reason || undefined)}
            className="px-4 py-2 text-sm bg-green-600 hover:bg-green-700 text-white rounded transition-colors"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
