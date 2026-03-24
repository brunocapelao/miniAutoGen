import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ApprovalModal } from '@/components/approval/ApprovalModal';
import type { Approval } from '@/types/api';

const mockApproval: Approval = {
  request_id: 'req-abc-123',
  agent_name: 'ResearchAgent',
  action: 'web_search',
  requested_at: '2024-01-15T10:30:00Z',
};

describe('ApprovalModal', () => {
  it('renders approval details (agent name, action, requested_at)', () => {
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('ResearchAgent')).toBeInTheDocument();
    expect(screen.getByText('web_search')).toBeInTheDocument();
    // The requested_at is formatted via toLocaleString, just check the date label exists
    expect(screen.getByText('Requested')).toBeInTheDocument();
  });

  it('Approve button calls onResolve with approved decision', () => {
    const onResolve = vi.fn();
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={onResolve}
        onClose={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('Approve'));
    expect(onResolve).toHaveBeenCalledWith('req-abc-123', 'approved', undefined);
  });

  it('Deny button calls onResolve with denied decision', () => {
    const onResolve = vi.fn();
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={onResolve}
        onClose={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('Deny'));
    expect(onResolve).toHaveBeenCalledWith('req-abc-123', 'denied', undefined);
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={vi.fn()}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('passes reason to onResolve when textarea has value', () => {
    const onResolve = vi.fn();
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={onResolve}
        onClose={vi.fn()}
      />
    );
    const textarea = screen.getByPlaceholderText('Add a reason...');
    fireEvent.change(textarea, { target: { value: 'Not safe to execute' } });
    fireEvent.click(screen.getByText('Deny'));
    expect(onResolve).toHaveBeenCalledWith('req-abc-123', 'denied', 'Not safe to execute');
  });

  it('passes reason to onResolve on approve when textarea has value', () => {
    const onResolve = vi.fn();
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={onResolve}
        onClose={vi.fn()}
      />
    );
    const textarea = screen.getByPlaceholderText('Add a reason...');
    fireEvent.change(textarea, { target: { value: 'Looks fine' } });
    fireEvent.click(screen.getByText('Approve'));
    expect(onResolve).toHaveBeenCalledWith('req-abc-123', 'approved', 'Looks fine');
  });

  it('has aria-modal and role="dialog" attributes', () => {
    render(
      <ApprovalModal
        approval={mockApproval}
        onResolve={vi.fn()}
        onClose={vi.fn()}
      />
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });
});
