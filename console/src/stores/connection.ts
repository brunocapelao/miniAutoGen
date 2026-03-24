import { create } from 'zustand';

type ConnectionState = {
  status: 'disconnected' | 'connecting' | 'connected' | 'polling';
  runId: string | null;
  setStatus: (status: ConnectionState['status']) => void;
  setRunId: (runId: string | null) => void;
};

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: 'disconnected',
  runId: null,
  setStatus: (status) => set({ status }),
  setRunId: (runId) => set({ runId }),
}));
