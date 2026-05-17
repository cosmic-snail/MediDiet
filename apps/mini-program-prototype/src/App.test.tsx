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
});
