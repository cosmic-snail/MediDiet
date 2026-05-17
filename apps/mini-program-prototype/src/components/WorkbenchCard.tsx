import type { ReactNode } from 'react';

interface WorkbenchCardProps {
  label: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

export function WorkbenchCard({ label, title, children, action }: WorkbenchCardProps) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <p className="eyebrow">{label}</p>
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      <div>{children}</div>
    </section>
  );
}
