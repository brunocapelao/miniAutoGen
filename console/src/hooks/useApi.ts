'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export function useWorkspace() {
  return useQuery({
    queryKey: ['workspace'],
    queryFn: api.getWorkspace,
  });
}

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
  });
}

export function useAgent(name: string) {
  return useQuery({
    queryKey: ['agent', name],
    queryFn: () => api.getAgent(name),
    enabled: !!name,
  });
}

export function useFlows() {
  return useQuery({
    queryKey: ['flows'],
    queryFn: api.getFlows,
  });
}

export function useFlow(name: string) {
  return useQuery({
    queryKey: ['flow', name],
    queryFn: () => api.getFlow(name),
    enabled: !!name,
  });
}

export function useRuns(offset = 0, limit = 20) {
  return useQuery({
    queryKey: ['runs', offset, limit],
    queryFn: () => api.getRuns(offset, limit),
    refetchInterval: 3000,
  });
}

export function useRun(id: string) {
  return useQuery({
    queryKey: ['run', id],
    queryFn: () => api.getRun(id),
    enabled: !!id,
  });
}

export function useApprovals(runId: string) {
  return useQuery({
    queryKey: ['approvals', runId],
    queryFn: () => api.getApprovals(runId),
    enabled: !!runId,
    refetchInterval: 2000,
  });
}

export function useTriggerRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ flowName, input }: { flowName: string; input?: string }) =>
      api.triggerRun(flowName, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}

export function useResolveApproval(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, decision, reason }: {
      requestId: string;
      decision: 'approved' | 'denied';
      reason?: string;
    }) => api.resolveApproval(runId, requestId, decision, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals', runId] });
    },
  });
}
