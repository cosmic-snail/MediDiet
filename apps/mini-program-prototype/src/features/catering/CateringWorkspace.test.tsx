import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createInitialPrototypeState } from '../../state';
import { CateringWorkspace } from './CateringWorkspace';

describe('CateringWorkspace', () => {
  it('shows menu data quality and fulfillment status', () => {
    render(<CateringWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('清蒸鱼套餐')).toBeInTheDocument();
    expect(screen.getByText('糙米鸡胸套餐')).toBeInTheDocument();
    expect(screen.getByText('nutritionConfidence 0.62')).toBeInTheDocument();
    expect(screen.getByText('待准备')).toBeInTheDocument();
  });

  it('updates availability and fulfillment status', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<CateringWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '下架清蒸鱼套餐' }));
    await user.click(screen.getByRole('button', { name: '标记已备餐' }));

    expect(onStateChange).toHaveBeenCalledTimes(2);
    expect(typeof onStateChange.mock.calls[0][0]).toBe('function');
    expect(typeof onStateChange.mock.calls[1][0]).toBe('function');
  });

  it('does not offer fulfillment actions for non-pending statuses', () => {
    const onStateChange = vi.fn();
    const state = {
      ...createInitialPrototypeState(),
      fulfillments: [
        {
          ...createInitialPrototypeState().fulfillments[0],
          fulfillmentId: 'delivered-order',
          status: 'delivered' as const
        },
        {
          ...createInitialPrototypeState().fulfillments[0],
          fulfillmentId: 'prepared-order',
          status: 'prepared' as const
        }
      ]
    };

    render(<CateringWorkspace state={state} onStateChange={onStateChange} />);

    expect(screen.getByText('已送达')).toBeInTheDocument();
    expect(screen.getByText('已备餐')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '标记已备餐' })).not.toBeInTheDocument();
    expect(onStateChange).not.toHaveBeenCalled();
  });

  it('shows an empty state when there are no confirmed meals', () => {
    render(
      <CateringWorkspace state={{ ...createInitialPrototypeState(), fulfillments: [] }} onStateChange={vi.fn()} />
    );

    expect(screen.getByText('暂无已确认餐食')).toBeInTheDocument();
    expect(screen.getByText('患者选择或营养师确认后会出现在这里。')).toBeInTheDocument();
  });
});
