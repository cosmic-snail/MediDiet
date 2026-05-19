import type { Dispatch, SetStateAction } from 'react';
import { AlertTriangle, Camera, CheckCircle, Clock3, PlusCircle } from 'lucide-react';
import { formatPrice, mealLabelName, outcomeToPatientState } from '../../contracts';
import { patientProfile } from '../../fixtures';
import { addCorrectedIntake, requestRecommendation, type PrototypeState } from '../../state';

interface PatientWorkspaceProps {
  state: PrototypeState;
  onStateChange: Dispatch<SetStateAction<PrototypeState>>;
  onRequestRecommendation?: () => void;
  recommendationPending?: boolean;
  serviceError?: string | null;
}

export function PatientWorkspace({
  state,
  onStateChange,
  onRequestRecommendation,
  recommendationPending = false,
  serviceError
}: PatientWorkspaceProps) {
  const recommendation = state.recommendation;
  const patientState = recommendation ? outcomeToPatientState(recommendation.outcome) : null;
  const recommendedItem = recommendation?.recommendedItems[0];
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

      {serviceError && (
        <section className="card service-error" role="status">
          <p className="eyebrow">后端服务</p>
          <h2>推荐服务暂不可用</h2>
          <p>{serviceError}</p>
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">健康资料</p>
            <h2>{patientProfile.displayName}</h2>
          </div>
          <span className="status good">关键风险字段已确认</span>
        </div>
        <p className="muted">
          高血压、糖尿病、虾过敏 · 偏好清淡 · 预算 {formatPrice(patientProfile.maxPriceCents)}
        </p>
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
          {state.intakeRecords.map((record) => (
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
