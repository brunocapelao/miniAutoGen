// API response types matching backend exactly

export type Workspace = {
  project_name: string;
  project_root: string;
  agent_count: number;
  pipeline_count: number;
  engine_count: number;
};

export type Agent = {
  name: string;
  role: string;
  goal?: string;
  engine_type: string;
  engine_profile?: string;
  temperature?: number;
};

export type Flow = {
  name: string;
  mode: string;
  target: string;
  participants: string[];
  leader: string | null;
  max_rounds?: number;
};

export type RunSummary = {
  run_id: string;
  pipeline: string;
  status: string;
  started?: string;
  events: number;
};

export type RunEvent = {
  type: string;
  timestamp: string;
  run_id: string;
  scope: string;
  payload: Record<string, unknown>;
};

export type Approval = {
  request_id: string;
  agent_name: string;
  action: string;
  requested_at: string;
};

export type Page<T> = {
  items: T[];
  total: number;
  offset: number;
  limit: number;
};
