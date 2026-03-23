import { create } from 'zustand';

type ConnectionState = {
  status: 'disconnected' | 'connecting' | 'connected';
  activeRunId: string | null;
  setStatus: (status: ConnectionState['status']) => void;
  setActiveRunId: (runId: string | null) => void;
};

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: 'disconnected',
  activeRunId: null,
  setStatus: (status) => set({ status }),
  setActiveRunId: (activeRunId) => set({ activeRunId }),
}));
