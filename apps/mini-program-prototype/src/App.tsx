import { useMemo, useState } from 'react';
import './styles.css';
import { RoleSwitcher } from './components/RoleSwitcher';
import { WorkbenchCard } from './components/WorkbenchCard';
import type { Role } from './contracts';
import { PatientWorkspace } from './features/patient/PatientWorkspace';
import { DietitianWorkspace } from './features/review/DietitianWorkspace';
import { createInitialPrototypeState, selectWorkbenchSummary, setActiveRole } from './state';

export default function App() {
  const [state, setState] = useState(createInitialPrototypeState);
  const summary = useMemo(() => selectWorkbenchSummary(state, state.activeRole), [state]);

  function handleRoleChange(role: Role) {
    setState((current) => setActiveRole(current, role));
  }

  return (
    <main className="app-shell">
      <section className="phone-frame">
        <header className="top-bar">
          <div>
            <p className="eyebrow">推荐引擎微信小程序原型</p>
            <h1>MediDiet 角色工作台</h1>
          </div>
        </header>

        <RoleSwitcher activeRole={state.activeRole} onChange={handleRoleChange} />

        <WorkbenchCard label="今日概览" title={summary.title}>
          <div className="metric-grid">
            <div className="metric">
              <span>{summary.primaryCount}</span>
              <p>{summary.primaryLabel}</p>
            </div>
            <div className="metric">
              <span>{summary.secondaryCount}</span>
              <p>{summary.secondaryLabel}</p>
            </div>
          </div>
        </WorkbenchCard>

        {state.activeRole === 'patient' && <PatientWorkspace state={state} onStateChange={setState} />}
        {state.activeRole === 'dietitian' && <DietitianWorkspace state={state} onStateChange={setState} />}
      </section>
    </main>
  );
}
