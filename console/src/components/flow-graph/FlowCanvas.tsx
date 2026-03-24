'use client';

import { useMemo } from 'react';
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AgentNode } from './AgentNode';

const nodeTypes = { agent: AgentNode };

type FlowCanvasProps = {
  participants: string[];
  leader?: string | null;
  mode?: string;
};

export function FlowCanvas({ participants, leader, mode }: FlowCanvasProps) {
  const { nodes, edges } = useMemo(() => {
    const ns: Node[] = participants.map((name, i) => ({
      id: name,
      type: 'agent',
      position: { x: 200 * i, y: 100 },
      data: {
        label: name,
        role: name === leader ? 'leader' : 'participant',
      },
    }));

    const es: Edge[] = [];
    if (mode === 'workflow') {
      for (let i = 0; i < participants.length - 1; i++) {
        es.push({
          id: `e-${participants[i]}-${participants[i + 1]}`,
          source: participants[i],
          target: participants[i + 1],
          animated: true,
        });
      }
    } else if (mode === 'group_chat' || mode === 'debate' || mode === 'deliberation') {
      const hub = leader || participants[0];
      for (const p of participants) {
        if (p !== hub) {
          es.push({
            id: `e-${hub}-${p}`,
            source: hub,
            target: p,
            animated: true,
            style: { stroke: '#8b5cf6' },
            type: 'default',
          });
        }
      }
    }

    return { nodes: ns, edges: es };
  }, [participants, leader, mode]);

  return (
    <div className="h-[400px] border border-gray-700 rounded-lg bg-gray-950 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#374151" gap={20} />
        <Controls
          className="!bg-gray-800/80 !border-gray-700 !rounded-lg !shadow-lg"
          showZoom={true}
          showFitView={true}
          showInteractive={false}
        />
      </ReactFlow>
    </div>
  );
}
