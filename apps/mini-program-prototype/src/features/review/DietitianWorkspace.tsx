import { AlertTriangle, CheckCircle, ClipboardCheck, Edit3, XCircle } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';
import { mealLabelName } from '../../contracts';
import { submitReviewDecision, type PrototypeState } from '../../state';

interface DietitianWorkspaceProps {
  state: PrototypeState;
  onStateChange: Dispatch<SetStateAction<PrototypeState>>;
}

export function DietitianWorkspace({ state, onStateChange }: DietitianWorkspaceProps) {
  const pendingCases = state.reviewCases.filter((item) => item.status === 'pending');
  const activeCase = state.reviewCases.find((item) => item.status === 'pending');
  const safetyEvent = activeCase?.trace.safetyEvents[0];
  const exclusionEntries = activeCase ? Object.values(activeCase.trace.exclusions) : [];
  const scoreEntries = activeCase ? Object.entries(activeCase.trace.scores) : [];
  const matchedTags = activeCase?.trace.clinicianExplanation.matchedTags ?? [];

  if (!activeCase) {
    return (
      <section className="card">
        <p className="eyebrow">营养师审核</p>
        <h2>暂无待审核推荐</h2>
        <p className="muted">新的 human_review_required 推荐会出现在这里。</p>
      </section>
    );
  }

  return (
    <div className="workspace-stack">
      <section className="hero-panel review-hero">
        <div>
          <p className="eyebrow">营养师审核</p>
          <h2>{pendingCases.length} 条待审核</h2>
          <p>优先处理高风险、低置信度和资料未确认的推荐请求。</p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">审核队列</p>
            <h2>
              {activeCase.patientDisplayName} · {mealLabelName(activeCase.mealLabel)}
            </h2>
          </div>
          <span className="status danger">{activeCase.riskLevel}</span>
        </div>
        <p className="muted">{activeCase.reason}</p>
        <p className="trace-id">{activeCase.traceId}</p>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">Trace 证据链</p>
            <h2>{activeCase.trace.ruleVersion}</h2>
          </div>
          <ClipboardCheck size={20} aria-hidden="true" />
        </div>
        <div className="evidence-grid">
          <div>
            <span>Outcome</span>
            <strong>{activeCase.trace.outcome}</strong>
          </div>
          <div>
            <span>Risk</span>
            <strong>{activeCase.trace.riskLevel}</strong>
          </div>
          <div>
            <span>Safety</span>
            <strong>{safetyEvent?.codeName ?? '无'}</strong>
          </div>
          <div>
            <span>Rule</span>
            <strong>{activeCase.trace.ruleVersion}</strong>
          </div>
          <div>
            <span>Exclusions</span>
            <strong>{exclusionEntries.length}</strong>
          </div>
          <div>
            <span>Scores</span>
            <strong>{scoreEntries.length}</strong>
          </div>
        </div>
        <div className="trace-detail-grid">
          <div>
            <span>排除项</span>
            {exclusionEntries.length > 0 ? (
              exclusionEntries.map((item) => (
                <p key={`${item.itemId}-${item.code}`}>{`${item.itemId} · ${item.codeName}`}</p>
              ))
            ) : (
              <p>暂无排除项</p>
            )}
          </div>
          <div>
            <span>评分</span>
            {scoreEntries.length > 0 ? (
              scoreEntries.map(([itemId, score]) => <p key={itemId}>{`${itemId} · ${score.toFixed(1)}`}</p>)
            ) : (
              <p>暂无评分</p>
            )}
          </div>
          <div>
            <span>命中标签</span>
            {matchedTags.length > 0 ? (
              matchedTags.map((item) => <p key={`${item.kind}-${item.value}`}>{`${item.kind} · ${item.value}`}</p>)
            ) : (
              <p>待人工判断</p>
            )}
          </div>
        </div>
        <div className="result-panel warning-panel">
          <AlertTriangle size={18} aria-hidden="true" />
          <p>{activeCase.trace.patientExplanation}</p>
          <p>{activeCase.trace.clinicianExplanation.llmBoundary}</p>
        </div>
      </section>

      <section className="card">
        <p className="eyebrow">审核动作</p>
        <div className="button-row">
          <button
            className="primary-button"
            type="button"
            onClick={() => onStateChange((current) => submitReviewDecision(current, activeCase.traceId, 'approve'))}
          >
            <CheckCircle size={18} aria-hidden="true" />
            确认推荐
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => onStateChange((current) => submitReviewDecision(current, activeCase.traceId, 'modify'))}
          >
            <Edit3 size={18} aria-hidden="true" />
            修改推荐
          </button>
          <button
            className="secondary-button danger-action"
            type="button"
            onClick={() => onStateChange((current) => submitReviewDecision(current, activeCase.traceId, 'reject'))}
          >
            <XCircle size={18} aria-hidden="true" />
            驳回推荐
          </button>
        </div>
      </section>
    </div>
  );
}
