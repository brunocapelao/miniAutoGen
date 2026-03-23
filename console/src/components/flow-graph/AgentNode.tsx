'use client';

import { Handle, Position, type NodeProps } from '@xyflow/react';

type AgentNodeData = {
  label: string;
  role?: string;
  engineType?: string;
};

export function AgentNode({ data }: NodeProps) {
  const d = data as AgentNodeData;
  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 min-w-[140px] shadow-lg">
      <Handle type="target" position={Position.Top} className="!bg-blue-500" />
      <div className="font-mono text-sm font-bold text-white">{d.label}</div>
      {d.role && <div className="text-xs text-gray-400 mt-1">{d.role}</div>}
      {d.engineType && <div className="text-xs text-gray-500 mt-0.5">{d.engineType}</div>}
      <Handle type="source" position={Position.Bottom} className="!bg-blue-500" />
    </div>
  );
}
