import { ChefHat, ShieldCheck, UserRound } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Role } from '../contracts';

interface RoleSwitcherProps {
  activeRole: Role;
  onChange: (role: Role) => void;
}

const roles: Array<{ role: Role; label: string; Icon: LucideIcon }> = [
  { role: 'patient', label: '患者', Icon: UserRound },
  { role: 'dietitian', label: '营养师', Icon: ShieldCheck },
  { role: 'catering', label: '配餐', Icon: ChefHat }
];

export function RoleSwitcher({ activeRole, onChange }: RoleSwitcherProps) {
  return (
    <div className="role-switcher" aria-label="角色切换">
      {roles.map(({ role, label, Icon }) => (
        <button
          className="role-button"
          key={role}
          type="button"
          aria-pressed={activeRole === role}
          onClick={() => onChange(role)}
        >
          <Icon aria-hidden="true" size={16} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
