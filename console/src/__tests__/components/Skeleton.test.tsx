import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SkeletonTable, SkeletonCards, SkeletonCard, SkeletonRow } from '@/components/Skeleton';

describe('SkeletonTable', () => {
  it('renders correct number of rows and columns', () => {
    const { container } = render(<SkeletonTable rows={3} cols={4} />);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(3);
    const firstRowCells = rows[0].querySelectorAll('td');
    expect(firstRowCells).toHaveLength(4);
  });

  it('uses default values', () => {
    const { container } = render(<SkeletonTable />);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(5);
  });
});

describe('SkeletonCards', () => {
  it('renders correct number of cards', () => {
    const { container } = render(<SkeletonCards count={4} />);
    const cards = container.querySelectorAll('.animate-pulse');
    expect(cards.length).toBeGreaterThanOrEqual(4);
  });
});

describe('SkeletonCard', () => {
  it('renders a card with animate-pulse elements', () => {
    const { container } = render(<SkeletonCard />);
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
  });
});

describe('SkeletonRow', () => {
  it('renders correct number of cells', () => {
    const { container } = render(
      <table>
        <tbody>
          <SkeletonRow cols={3} />
        </tbody>
      </table>
    );
    expect(container.querySelectorAll('td')).toHaveLength(3);
  });
});
