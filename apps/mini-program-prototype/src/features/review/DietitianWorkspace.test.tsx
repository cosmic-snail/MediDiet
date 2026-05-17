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
});
