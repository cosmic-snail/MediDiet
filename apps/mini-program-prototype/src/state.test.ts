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
    const next = submitReviewDecision(state, 'trace-review-001', 'approve');

    expect(next.reviewCases[0].status).toBe('approved');
    expect(next.recommendation?.reviewStatus).toBe('completed');
  });

  it('updates menu availability and fulfillment status', () => {
    const state = createInitialPrototypeState();

    expect(updateMenuItemAvailability(state, 'steamed-fish-set', false).menuItems[0].available).toBe(false);
    expect(updateFulfillmentStatus(state, 'fulfillment-001', 'prepared').fulfillments[0].status).toBe('prepared');
  });
});
