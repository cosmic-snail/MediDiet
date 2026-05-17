import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

describe('App role workbench', () => {
  it('renders the role workbench and switches roles', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole('heading', { name: 'MediDiet 角色工作台' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '患者工作台' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '营养师' }));
    expect(screen.getByRole('heading', { name: '营养师工作台' })).toBeInTheDocument();
  });

  it('returns completed dietitian review results to the patient workspace', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '模拟等待营养师审核' }));
    expect(screen.getByText('推荐状态：等待营养师审核')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '营养师' }));
    await user.click(screen.getByRole('button', { name: '确认推荐' }));
    expect(screen.getByText('暂无待审核推荐')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '患者' }));
    expect(screen.getByRole('heading', { name: '清蒸鱼套餐' })).toBeInTheDocument();
    expect(screen.getByText(/营养师已确认/)).toBeInTheDocument();
    expect(screen.getByText('推荐状态：已生成推荐')).toBeInTheDocument();
  });
});
