import {
  addCorrectedIntake,
  createInitialPrototypeState,
  requestRecommendation,
  selectWorkbenchSummary,
  submitReviewDecision,
  updateFulfillmentStatus,
  updateMenuItemAvailability
} from './state';

describe('prototype state machine', () => {
  it('summarizes workbench counts by role', () => {
    const state = createInitialPrototypeState();

    expect(selectWorkbenchSummary(state, 'patient').primaryCount).toBe(1);
    expect(selectWorkbenchSummary(state, 'dietitian').primaryCount).toBe(1);
    expect(selectWorkbenchSummary(state, 'catering').secondaryCount).toBeGreaterThan(0);
  });

  it('adds manually corrected intake records', () => {
    const state = createInitialPrototypeState();
    const next = addCorrectedIntake(state, '低糖酸奶', 4);

    expect(next.intakeRecords).toHaveLength(state.intakeRecords.length + 1);
    expect(next.intakeRecords.at(-1)?.manuallyCorrected).toBe(true);
  });

  it('creates recommended and review-required recommendation states', () => {
    const state = createInitialPrototypeState();

    expect(requestRecommendation(state, 'recommended').recommendation?.outcome).toBe('recommended');
    expect(requestRecommendation(state, 'review').recommendation?.outcome).toBe('human_review_required');
  });

  it('writes review decisions back to queue and recommendation', () => {
    const state = createInitialPrototypeState();
    const reviewState = requestRecommendation(state, 'review');
    const next = submitReviewDecision(reviewState, 'trace-review-001', 'approve');

    expect(next.reviewCases[0].status).toBe('approved');
    expect(next.recommendation?.reviewStatus).toBe('completed');
    expect(next.recommendation?.traceId).toBe('trace-review-001');
    expect(next.recommendation?.outcome).toBe('recommended');
    expect(next.recommendation?.recommendedItems[0]?.name).toBe('清蒸鱼套餐');
    expect(next.recommendation?.patientExplanation).toContain('营养师已确认');
    expect(next.recommendation?.trace.scores).toHaveProperty('steamed-fish-set');
  });

  it('writes rejected review decisions as patient-facing refusal states', () => {
    const state = createInitialPrototypeState();
    const reviewState = requestRecommendation(state, 'review');
    const next = submitReviewDecision(reviewState, 'trace-review-001', 'reject');

    expect(next.reviewCases[0].status).toBe('rejected');
    expect(next.recommendation?.reviewStatus).toBe('completed');
    expect(next.recommendation?.outcome).toBe('refused');
    expect(next.recommendation?.recommendedItems).toHaveLength(0);
    expect(next.recommendation?.patientExplanation).toContain('营养师未通过');
    expect(next.recommendation?.trace.patientExplanation).toContain('营养师未通过');
  });

  it('leaves recommendation and review cases unchanged for unknown review trace ids', () => {
    const state = createInitialPrototypeState();
    const next = submitReviewDecision(state, 'trace-unknown', 'approve');

    expect(next).toBe(state);
    expect(next.recommendation).toBe(state.recommendation);
    expect(next.reviewCases).toBe(state.reviewCases);
  });

  it('does not mutate the current recommendation when reviewing a different trace', () => {
    const state = createInitialPrototypeState();
    const next = submitReviewDecision(state, 'trace-review-001', 'approve');

    expect(next.reviewCases[0].status).toBe('approved');
    expect(next.recommendation).toBe(state.recommendation);
    expect(next.recommendation?.traceId).toBe('trace-7c4e3608');
    expect(next.recommendation?.reviewStatus).toBeNull();
  });

  it('does not throw when review mode has an empty review queue', () => {
    const state = { ...createInitialPrototypeState(), recommendation: null, reviewCases: [] };

    expect(() => requestRecommendation(state, 'review')).not.toThrow();
    expect(requestRecommendation(state, 'review').recommendation).toBeNull();
  });

  it('updates menu availability and fulfillment status', () => {
    const state = createInitialPrototypeState();

    expect(updateMenuItemAvailability(state, 'steamed-fish-set', false).menuItems[0].available).toBe(false);
    expect(updateFulfillmentStatus(state, 'fulfillment-001', 'prepared').fulfillments[0].status).toBe('prepared');
  });
});
