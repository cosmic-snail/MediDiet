import { useMemo, useState } from 'react';
import './styles.css';
import { MediDietApiError, createMediDietApiClient } from './api/medidietApi';
import { RoleSwitcher } from './components/RoleSwitcher';
import { WorkbenchCard } from './components/WorkbenchCard';
import type { Role } from './contracts';
import { CateringWorkspace } from './features/catering/CateringWorkspace';
import { PatientWorkspace } from './features/patient/PatientWorkspace';
import { DietitianWorkspace } from './features/review/DietitianWorkspace';
import {
  applyBackendRecommendation,
  createInitialPrototypeState,
  selectActivePatient,
  selectActivePatientIntakeRecords,
  selectWorkbenchSummary,
  setActiveRole
} from './state';

const medidietApi = createMediDietApiClient();

export default function App() {
  const [state, setState] = useState(createInitialPrototypeState);
  const [recommendationPending, setRecommendationPending] = useState(false);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const summary = useMemo(() => selectWorkbenchSummary(state, state.activeRole), [state]);

  function handleRoleChange(role: Role) {
    setState((current) => setActiveRole(current, role));
  }

  async function handleBackendRecommendationRequest() {
    setRecommendationPending(true);
    setServiceError(null);

    try {
      const activePatient = selectActivePatient(state);
      const activePatientIntakeRecords = selectActivePatientIntakeRecords(state);
      await medidietApi.seedDemoData({
        patientProfile: activePatient,
        intakeRecords: activePatientIntakeRecords,
        menuItems: state.menuItems
      });
      const recommendation = await medidietApi.requestRecommendation({
        patientId: activePatient.patientId,
        mealLabel: 3
      });
      setState((current) => applyBackendRecommendation(current, activePatient.patientId, recommendation));
    } catch (error) {
      setServiceError(formatServiceError(error));
    } finally {
      setRecommendationPending(false);
    }
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

        {state.activeRole === 'patient' && (
          <PatientWorkspace
            state={state}
            onStateChange={setState}
            onRequestRecommendation={handleBackendRecommendationRequest}
            recommendationPending={recommendationPending}
            serviceError={serviceError}
          />
        )}
        {state.activeRole === 'dietitian' && <DietitianWorkspace state={state} onStateChange={setState} />}
        {state.activeRole === 'catering' && <CateringWorkspace state={state} onStateChange={setState} />}
      </section>
    </main>
  );
}

function formatServiceError(error: unknown): string {
  if (error instanceof MediDietApiError) {
    return `${error.code}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '推荐服务请求失败，请稍后重试。';
}
