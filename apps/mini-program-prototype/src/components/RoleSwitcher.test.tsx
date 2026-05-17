import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RoleSwitcher } from './RoleSwitcher';

describe('RoleSwitcher', () => {
  it('renders all role options and emits changes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<RoleSwitcher activeRole="patient" onChange={onChange} />);
    await user.click(screen.getByRole('button', { name: '营养师' }));

    expect(screen.getByRole('button', { name: '患者' })).toHaveAttribute('aria-pressed', 'true');
    expect(onChange).toHaveBeenCalledWith('dietitian');
  });
});
