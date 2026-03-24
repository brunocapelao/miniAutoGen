'use client';

import { Handle, Position, type NodeProps } from '@xyflow/react';

type AgentNodeData = {
  label: string;
  role?: string;
  engineType?: string;
};

export function AgentNode({ data }: NodeProps) {
  const d = data as AgentNodeData;
  const isLeader = d.role === 'leader';
  return (
    <div className={`bg-gray-800/90 border rounded-lg px-4 py-3 min-w-[140px] shadow-lg backdrop-blur-sm ${
      isLeader ? 'border-purple-500/50' : 'border-gray-600/50'
    }`}>
      <Handle type="target" position={Position.Top} className="!bg-blue-500 !w-2 !h-2" />
      <div className="font-mono text-sm font-bold text-white">{d.label}</div>
      {d.role && (
        <div className={`text-xs mt-1 ${isLeader ? 'text-purple-400' : 'text-gray-500'}`}>
          {d.role}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-blue-500 !w-2 !h-2" />
    </div>
  );
}
