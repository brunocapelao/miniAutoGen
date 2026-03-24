import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RunStatus } from '@/components/run/RunStatus';

describe('RunStatus', () => {
  it('renders status text uppercased', () => {
    render(<RunStatus status="completed" />);
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
  });

  it('applies green classes for completed', () => {
    const { container } = render(<RunStatus status="completed" />);
    expect(container.firstChild).toHaveClass('text-green-400');
  });

  it('applies yellow classes for running', () => {
    const { container } = render(<RunStatus status="running" />);
    expect(container.firstChild).toHaveClass('text-yellow-400');
  });

  it('applies red classes for failed', () => {
    const { container } = render(<RunStatus status="failed" />);
    expect(container.firstChild).toHaveClass('text-red-400');
  });

  it('applies gray classes for unknown status', () => {
    const { container } = render(<RunStatus status="unknown" />);
    expect(container.firstChild).toHaveClass('text-gray-400');
  });
});
