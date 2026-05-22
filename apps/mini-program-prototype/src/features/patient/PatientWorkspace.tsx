import type { Dispatch, SetStateAction } from 'react';
import { AlertTriangle, Camera, CheckCircle, Clock3, PlusCircle } from 'lucide-react';
import { formatPrice, mealLabelName, outcomeToPatientState, type PatientProfileDto } from '../../contracts';
import {
  addCorrectedIntake,
  requestRecommendation,
  selectActivePatient,
  selectActivePatientIntakeRecords,
  selectActivePatientRecommendation,
  setActivePatient,
  type PrototypeState
} from '../../state';

interface PatientWorkspaceProps {
  state: PrototypeState;
  onStateChange: Dispatch<SetStateAction<PrototypeState>>;
  onRequestRecommendation?: () => void;
  recommendationPending?: boolean;
  serviceError?: string | null;
}

const conditionLabels: Record<string, string> = {
  ckd: '慢性肾病',
  diabetes: '糖尿病',
  hypertension: '高血压'
};

const allergenLabels: Record<string, string> = {
  peanut: '花生过敏',
  shrimp: '虾过敏'
};

const tasteLabels: Record<string, string> = {
  light: '清淡'
};

function formatPatientSummary(patient: PatientProfileDto) {
  const risks = [
    ...patient.conditions.map((item) => conditionLabels[item] ?? item),
    ...patient.allergens.map((item) => allergenLabels[item] ?? item)
  ];
  const tastes = patient.tasteTags.map((item) => tasteLabels[item] ?? item).join('、');

  return `${risks.join('、')} · 偏好${tastes} · 预算 ${formatPrice(patient.maxPriceCents)}`;
}

export function PatientWorkspace({
  state,
  onStateChange,
  onRequestRecommendation,
  recommendationPending = false,
  serviceError
}: PatientWorkspaceProps) {
  const activePatient = selectActivePatient(state);
  const intakeRecords = selectActivePatientIntakeRecords(state);
  const recommendation = selectActivePatientRecommendation(state);
  const patientState = recommendation ? outcomeToPatientState(recommendation.outcome) : null;
  const recommendedItem = recommendation?.recommendedItems[0];
  const riskConfirmationLabel = activePatient.keyRiskFieldsConfirmed
    ? '关键风险字段已确认'
    : '关键风险字段待确认';
  const riskConfirmationStatus = activePatient.keyRiskFieldsConfirmed ? 'good' : 'danger';
  const patientStatusLabel =
    patientState === 'showRefusal'
      ? '拒绝推荐'
      : patientState === 'showReviewWait'
        ? '等待营养师审核'
        : '已生成推荐';

  return (
    <div className="workspace-stack">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">晚餐前</p>
          <h2>今晚建议清淡控主食</h2>
          <p>午餐钠摄入偏高，晚餐推荐会优先低钠、控糖和足量蛋白。</p>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={recommendationPending}
          onClick={() =>
            onRequestRecommendation
              ? onRequestRecommendation()
              : onStateChange((current) => requestRecommendation(current, 'recommended'))
          }
        >
          <CheckCircle size={18} aria-hidden="true" />
          {recommendationPending ? '正在请求推荐' : '获取下一餐推荐'}
        </button>
      </section>

      <section className="card patient-identity-card">
        <div>
          <label className="select-label" htmlFor="active-patient">
            当前患者
          </label>
          <select
            id="active-patient"
            className="patient-select"
            value={state.activePatientId}
            onChange={(event) => {
              const nextPatientId = event.currentTarget.value;
              onStateChange((current) => setActivePatient(current, nextPatientId));
            }}
          >
            {state.patients.map((patient) => (
              <option key={patient.patientId} value={patient.patientId}>
                {patient.displayName}
              </option>
            ))}
          </select>
          <p className="muted">
            {activePatient.age}岁 · {riskConfirmationLabel}
          </p>
        </div>
      </section>

      {serviceError && (
        <section className="card service-error" role="status">
          <p className="eyebrow">后端服务</p>
          <h2>推荐服务暂不可用</h2>
          <p>{serviceError}</p>
        </section>
      )}

      <section className="card" role="region" aria-label="健康资料">
        <div className="card-head">
          <div>
            <p className="eyebrow">健康资料</p>
            <h2>{activePatient.displayName}</h2>
          </div>
          <span className={`status ${riskConfirmationStatus}`}>{riskConfirmationLabel}</span>
        </div>
        <p className="muted">{formatPatientSummary(activePatient)}</p>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">今日摄入</p>
            <h2>拍照优先，手动兜底</h2>
          </div>
          <Camera size={20} aria-hidden="true" />
        </div>
        <div className="list">
          {intakeRecords.map((record) => (
            <div className="list-row" key={record.intakeId}>
              <div>
                <strong>{record.foodLabel}</strong>
                <p>
                  {mealLabelName(record.mealLabel)} · {record.portion} · 置信度{' '}
                  {Math.round(record.confidence * 100)}%
                </p>
              </div>
              <span>{record.nutrients.sodiumMg}mg 钠</span>
            </div>
          ))}
        </div>
        {intakeRecords.length === 0 && <p className="muted">暂无今日摄入记录。</p>}
        <button
          className="secondary-button"
          type="button"
          onClick={() => onStateChange((current) => addCorrectedIntake(current, '低糖酸奶', 4))}
        >
          <PlusCircle size={18} aria-hidden="true" />
          手动补录低糖酸奶
        </button>
      </section>

      {recommendation && (
        <section className="card">
          <div className="card-head">
            <div>
              <p className="eyebrow">推荐结果</p>
              <h2>{patientState === 'showRecommendation' ? recommendedItem?.name : '需要处理'}</h2>
              <p className="eyebrow">推荐状态：{patientStatusLabel}</p>
            </div>
            {patientState === 'showRefusal' ? (
              <AlertTriangle size={20} aria-hidden="true" />
            ) : patientState === 'showReviewWait' ? (
              <Clock3 size={20} aria-hidden="true" />
            ) : (
              <CheckCircle size={20} aria-hidden="true" />
            )}
          </div>

          {patientState === 'showRecommendation' && recommendedItem && (
            <div className="result-panel good-panel">
              <p>{recommendation.patientExplanation}</p>
              <div className="tag-row">
                {recommendedItem.nutritionTags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
              <p className="trace-id">{recommendation.traceId}</p>
            </div>
          )}

          {patientState === 'showRefusal' && (
            <div className="result-panel danger-panel">
              <AlertTriangle size={18} aria-hidden="true" />
              <p>{recommendation.patientExplanation}</p>
              <p className="trace-id">{recommendation.traceId}</p>
            </div>
          )}

          {patientState === 'showReviewWait' && (
            <div className="result-panel warning-panel">
              <Clock3 size={18} aria-hidden="true" />
              <p>{recommendation.patientExplanation}</p>
              <p className="trace-id">{recommendation.traceId}</p>
            </div>
          )}

          <div className="button-row">
            <button
              className="secondary-button"
              type="button"
              onClick={() => onStateChange((current) => requestRecommendation(current, 'refused'))}
            >
              模拟拒绝推荐
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => onStateChange((current) => requestRecommendation(current, 'review'))}
            >
              模拟等待营养师审核
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
