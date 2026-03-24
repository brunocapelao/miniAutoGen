import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ApprovalList } from '@/components/approval/ApprovalList';
import type { Approval } from '@/types/api';

describe('ApprovalList', () => {
  const approvals: Approval[] = [
    { request_id: 'req1', agent_name: 'architect', action: 'deploy', requested_at: '2026-03-23T10:00:00Z' },
  ];

  it('renders nothing when empty', () => {
    const { container } = render(<ApprovalList approvals={[]} onResolve={vi.fn()} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows pending approval count', () => {
    render(<ApprovalList approvals={approvals} onResolve={vi.fn()} />);
    expect(screen.getByText('Pending Approvals (1)')).toBeInTheDocument();
  });

  it('shows agent name and action', () => {
    render(<ApprovalList approvals={approvals} onResolve={vi.fn()} />);
    expect(screen.getByText('architect')).toBeInTheDocument();
    expect(screen.getByText('deploy')).toBeInTheDocument();
  });

  it('opens modal on Review click', () => {
    render(<ApprovalList approvals={approvals} onResolve={vi.fn()} />);
    fireEvent.click(screen.getByText('Review'));
    expect(screen.getByText('Approval Request')).toBeInTheDocument();
  });
});
