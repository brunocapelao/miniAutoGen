import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EventFeed } from '@/components/run/EventFeed';
import type { RunEvent } from '@/types/api';

describe('EventFeed', () => {
  const events: RunEvent[] = [
    { type: 'run_started', timestamp: '2026-03-23T10:00:00Z', run_id: 'r1', scope: 'test', payload: {} },
    { type: 'component_finished', timestamp: '2026-03-23T10:01:00Z', run_id: 'r1', scope: 'agent1', payload: {} },
  ];

  it('renders all events', () => {
    render(<EventFeed events={events} />);
    expect(screen.getByText('run_started')).toBeInTheDocument();
    expect(screen.getByText('component_finished')).toBeInTheDocument();
  });

  it('shows scope', () => {
    render(<EventFeed events={events} />);
    expect(screen.getByText('agent1')).toBeInTheDocument();
  });

  it('renders empty table with no events', () => {
    const { container } = render(<EventFeed events={[]} />);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(0);
  });
});
