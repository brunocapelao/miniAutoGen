import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryError } from '@/components/QueryError';

describe('QueryError', () => {
  it('shows default message', () => {
    render(<QueryError error={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows custom message', () => {
    render(<QueryError error={null} message="Custom error" />);
    expect(screen.getByText('Custom error')).toBeInTheDocument();
  });

  it('shows error details', () => {
    render(<QueryError error={new Error('Network timeout')} />);
    expect(screen.getByText('Network timeout')).toBeInTheDocument();
  });

  it('calls onRetry when button clicked', () => {
    const onRetry = vi.fn();
    render(<QueryError error={null} onRetry={onRetry} />);
    fireEvent.click(screen.getByText('Retry'));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('hides retry button when no onRetry', () => {
    render(<QueryError error={null} />);
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
  });
});
