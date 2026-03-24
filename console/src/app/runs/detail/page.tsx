'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useRunEvents } from '@/hooks/useRunEvents';
import { useApprovals, useResolveApproval } from '@/hooks/useApi';
import { RunStatus } from '@/components/run/RunStatus';
import { EventFeed } from '@/components/run/EventFeed';
import { FlowCanvas } from '@/components/flow-graph/FlowCanvas';
import { ApprovalList } from '@/components/approval/ApprovalList';
import type { RunSummary, Flow, Approval } from '@/types/api';

function RunDetailContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id') ?? '';
  const { data: run } = useQuery<RunSummary>({
    queryKey: ['run', id],
    queryFn: () => api.getRun(id),
    enabled: !!id,
    refetchInterval: 3000,
  });
  const { events, isLive } = useRunEvents(id);
  const { data: approvals } = useApprovals(id);
  const resolveApproval = useResolveApproval(id);

  // Flow query must be above early returns (React hooks rules)
  const pipeline = run?.pipeline;
  const flowQuery = useQuery<Flow>({
    queryKey: ['flow', pipeline],
    queryFn: () => api.getFlow(pipeline!),
    enabled: !!pipeline,
  });

  if (!id) {
    return <p className="text-gray-400">No run ID specified.</p>;
  }

  const flow = flowQuery.data;
  const participants = flow?.participants ?? [];
  const leader = flow?.leader ?? null;
  const mode = flow?.mode ?? '';
  const pendingApprovals: Approval[] = approvals ?? [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-4 mb-4 px-2">
        <h2 className="text-2xl font-bold">
          Run <span className="font-mono text-gray-400">{id.slice(0, 8)}</span>
        </h2>
        {run && <RunStatus status={run.status} />}
        {isLive && (
          <span className="text-xs text-green-400 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            LIVE
          </span>
        )}
        {run?.pipeline ? (
          <span className="text-sm text-gray-500">Flow: {run.pipeline}</span>
        ) : null}
      </div>

      {/* Main content: Graph + Events side by side */}
      <div className="flex flex-1 gap-4 min-h-0">
        {/* Left: Flow Graph */}
        {participants.length > 0 && (
          <div className="w-1/2 border border-gray-700 rounded-lg overflow-hidden">
            <div className="text-xs text-gray-500 px-3 py-1 border-b border-gray-700">
              Flow Graph
            </div>
            <FlowCanvas participants={participants} leader={leader} mode={mode} />
          </div>
        )}

        {/* Right: Event Feed */}
        <div className={participants.length > 0 ? 'w-1/2' : 'w-full'}>
          <div className="text-xs text-gray-500 mb-1">
            Events ({events.length})
          </div>
          <EventFeed events={events} />
        </div>
      </div>

      {/* Approval List (manages its own modal) */}
      <ApprovalList
        approvals={pendingApprovals}
        onResolve={(requestId, decision, reason) =>
          resolveApproval.mutate({ requestId, decision, reason })
        }
      />
    </div>
  );
}

export default function RunDetailPage() {
  return (
    <Suspense fallback={<p className="text-gray-400">Loading...</p>}>
      <RunDetailContent />
    </Suspense>
  );
}
