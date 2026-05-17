import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createInitialPrototypeState } from '../../state';
import { DietitianWorkspace } from './DietitianWorkspace';

describe('DietitianWorkspace', () => {
  it('shows pending review cases and trace evidence', () => {
    render(<DietitianWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('trace-review-001')).toBeInTheDocument();
    expect(screen.getByText('LOW_CONFIDENCE_INTAKE')).toBeInTheDocument();
    expect(screen.getAllByText('baseline-2026-05-15')).toHaveLength(2);
  });

  it('submits approve, modify, and reject decisions with functional updates', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<DietitianWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '确认推荐' }));
    await user.click(screen.getByRole('button', { name: '修改推荐' }));
    await user.click(screen.getByRole('button', { name: '驳回推荐' }));

    expect(onStateChange).toHaveBeenCalledTimes(3);
    expect(onStateChange.mock.calls.every(([argument]) => typeof argument === 'function')).toBe(true);
  });

  it('shows empty state without actions when all review cases are completed', () => {
    const initialState = createInitialPrototypeState();
    const completedStatuses = ['approved', 'rejected', 'modified'] as const;
    const state = {
      ...initialState,
      reviewCases: completedStatuses.map((status, index) => ({
        ...initialState.reviewCases[0],
        traceId: `trace-completed-${index + 1}`,
        status
      }))
    };

    render(<DietitianWorkspace state={state} onStateChange={vi.fn()} />);

    expect(screen.getByText('暂无待审核推荐')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '确认推荐' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '修改推荐' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '驳回推荐' })).not.toBeInTheDocument();
  });

  it('shows a later pending case when the first case is completed', () => {
    const initialState = createInitialPrototypeState();
    const completedCase = { ...initialState.reviewCases[0], status: 'modified' as const };
    const pendingCase = {
      ...initialState.reviewCases[0],
      traceId: 'trace-review-002',
      reason: '第二个待审核病例',
      trace: { ...initialState.reviewCases[0].trace, traceId: 'trace-review-002' }
    };
    const state = { ...initialState, reviewCases: [completedCase, pendingCase] };

    render(<DietitianWorkspace state={state} onStateChange={vi.fn()} />);

    expect(screen.getByText('trace-review-002')).toBeInTheDocument();
    expect(screen.getByText('第二个待审核病例')).toBeInTheDocument();
    expect(screen.queryByText('trace-review-001')).not.toBeInTheDocument();
  });
});
