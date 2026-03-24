import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ErrorBoundary } from '@/components/ErrorBoundary';

function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Test error message');
  return <div>OK</div>;
}

describe('ErrorBoundary', () => {
  // Suppress React's console.error output for expected errors
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('shows error message when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });

  it('shows "Something went wrong" text when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('shows "Try again" button when error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Try again')).toBeInTheDocument();
  });

  it('Try again button resets error state and re-renders children', () => {
    // We use a wrapper component with state to control shouldThrow
    // After the error boundary resets, the child should no longer throw
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Rerender with non-throwing child before clicking Try again
    rerender(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    fireEvent.click(screen.getByText('Try again'));
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('uses custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom fallback UI</div>}>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Custom fallback UI')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });
});
