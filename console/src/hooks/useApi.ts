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

export function useEngines() {
  return useQuery({
    queryKey: ['engines'],
    queryFn: api.getEngines,
  });
}

export function useEngine(name: string) {
  return useQuery({
    queryKey: ['engine', name],
    queryFn: () => api.getEngine(name),
    enabled: !!name,
  });
}

export function useCreateEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; provider: string; model: string; kind?: string; temperature?: number; api_key_env?: string; endpoint?: string }) =>
      api.createEngine(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['engines'] });
    },
  });
}

export function useUpdateEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Record<string, unknown> }) =>
      api.updateEngine(name, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['engines'] });
      queryClient.invalidateQueries({ queryKey: ['engine', variables.name] });
    },
  });
}

export function useDeleteEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteEngine(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['engines'] });
    },
  });
}

export function useConfigDetail() {
  return useQuery({
    queryKey: ['configDetail'],
    queryFn: api.getConfigDetail,
  });
}

export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; role: string; goal: string; engine_profile: string; temperature?: number }) =>
      api.createAgent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}

export function useUpdateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Record<string, unknown> }) =>
      api.updateAgent(name, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      queryClient.invalidateQueries({ queryKey: ['agent', variables.name] });
    },
  });
}

export function useDeleteAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteAgent(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}

export function useCreateFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; mode?: string; participants?: string[]; leader?: string; target?: string }) =>
      api.createFlow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
    },
  });
}

export function useUpdateFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Record<string, unknown> }) =>
      api.updateFlow(name, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      queryClient.invalidateQueries({ queryKey: ['flow', variables.name] });
    },
  });
}

export function useDeleteFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteFlow(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
    },
  });
}
