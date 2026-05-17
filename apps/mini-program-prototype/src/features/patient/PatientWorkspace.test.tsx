import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createInitialPrototypeState, requestRecommendation } from '../../state';
import { PatientWorkspace } from './PatientWorkspace';

describe('PatientWorkspace', () => {
  it('shows intake, profile confirmation, and recommendation result', () => {
    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('关键风险字段已确认')).toBeInTheDocument();
    expect(screen.getByText('咸汤面')).toBeInTheDocument();
    expect(screen.getByText('清蒸鱼套餐')).toBeInTheDocument();
    expect(screen.getByText('trace-7c4e3608')).toBeInTheDocument();
  });

  it('can add a manually corrected intake and request review mode', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));
    await user.click(screen.getByRole('button', { name: '模拟等待营养师审核' }));

    expect(onStateChange).toHaveBeenCalledTimes(2);
  });

  it('shows refusal state with a refusal status marker', () => {
    const state = requestRecommendation(createInitialPrototypeState(), 'refused');

    render(<PatientWorkspace state={state} onStateChange={vi.fn()} />);

    expect(screen.getByText('推荐状态：拒绝推荐')).toBeInTheDocument();
    expect(screen.getByText('当前候选餐食不满足安全和营养要求，暂不建议自动推荐。')).toBeInTheDocument();
  });

  it('passes functional updater callbacks for patient actions', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);

    await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));

    expect(typeof onStateChange.mock.calls[0][0]).toBe('function');
  });
});
