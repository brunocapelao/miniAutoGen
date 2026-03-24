import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock ReactFlow since it needs DOM measurements unavailable in jsdom
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ nodes, edges }: { nodes: unknown[]; edges: unknown[] }) => (
    <div
      data-testid="react-flow"
      data-nodes={nodes.length}
      data-edges={edges.length}
    />
  ),
  Background: () => null,
  Controls: () => null,
}));

// Mock AgentNode as well since it's imported inside FlowCanvas
vi.mock('@/components/flow-graph/AgentNode', () => ({
  AgentNode: () => <div data-testid="agent-node" />,
}));

// Also mock the CSS import
vi.mock('@xyflow/react/dist/style.css', () => ({}));

import { FlowCanvas } from '@/components/flow-graph/FlowCanvas';

describe('FlowCanvas', () => {
  it('renders with correct number of nodes for given participants', () => {
    render(
      <FlowCanvas participants={['Alice', 'Bob', 'Charlie']} mode="workflow" />
    );
    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '3');
  });

  it('workflow mode creates sequential edges (n-1 edges for n participants)', () => {
    render(
      <FlowCanvas participants={['A', 'B', 'C', 'D']} mode="workflow" />
    );
    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '4');
    expect(flow).toHaveAttribute('data-edges', '3');
  });

  it('group_chat mode creates hub-spoke edges', () => {
    // With 4 participants, hub has 3 spokes
    render(
      <FlowCanvas participants={['hub', 'b', 'c', 'd']} leader="hub" mode="group_chat" />
    );
    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '4');
    expect(flow).toHaveAttribute('data-edges', '3');
  });

  it('debate mode also creates hub-spoke edges', () => {
    render(
      <FlowCanvas participants={['leader', 'p1', 'p2']} leader="leader" mode="debate" />
    );
    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '3');
    expect(flow).toHaveAttribute('data-edges', '2');
  });

  it('empty participants renders with 0 nodes', () => {
    render(<FlowCanvas participants={[]} />);
    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '0');
    expect(flow).toHaveAttribute('data-edges', '0');
  });

  it('unknown mode creates no edges', () => {
    render(
      <FlowCanvas participants={['X', 'Y', 'Z']} mode="unknown_mode" />
    );
    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '3');
    expect(flow).toHaveAttribute('data-edges', '0');
  });
});
