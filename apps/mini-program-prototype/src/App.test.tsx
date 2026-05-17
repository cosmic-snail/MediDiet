import { render, screen } from '@testing-library/react';
import App from './App';

describe('App scaffold', () => {
  it('renders the MediDiet prototype shell', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'MediDiet 角色工作台' })).toBeInTheDocument();
    expect(screen.getByText('推荐引擎微信小程序原型')).toBeInTheDocument();
  });
});
