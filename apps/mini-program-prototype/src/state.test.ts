import {
  addCorrectedIntake,
  applyBackendRecommendation,
  createInitialPrototypeState,
  requestRecommendation,
  selectActivePatient,
  selectActivePatientIntakeRecords,
  selectActivePatientRecommendation,
  selectWorkbenchSummary,
  setActivePatient,
  submitReviewDecision,
  updateFulfillmentStatus,
  updateMenuItemAvailability
} from './state';
import { recommendedResponse } from './fixtures';

describe('prototype state machine', () => {
  it('initializes multiple patients and defaults to the demo patient', () => {
    const state = createInitialPrototypeState();

    expect(state.patients.map((patient) => patient.patientId)).toEqual(['demo-patient', 'demo-patient-ckd']);
    expect(state.activePatientId).toBe('demo-patient');
    expect(selectActivePatient(state).displayName).toBe('王女士');
    expect(selectActivePatientIntakeRecords(state).map((record) => record.foodLabel)).toEqual(['咸汤面']);
    expect(selectActivePatientRecommendation(state)?.traceId).toBe('trace-7c4e3608');
  });

  it('switches the active patient and uses that patient for summaries', () => {
    const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');

    expect(state.activePatientId).toBe('demo-patient-ckd');
    expect(selectActivePatient(state).displayName).toBe('李先生');
    expect(selectActivePatientIntakeRecords(state).map((record) => record.foodLabel)).toEqual(['白粥配咸菜']);
    expect(selectActivePatientRecommendation(state)).toBeNull();
    expect(selectWorkbenchSummary(state, 'patient')).toMatchObject({
      primaryCount: 1,
      secondaryCount: 0
    });
  });

  it('keeps the current patient when switching to an unknown patient id', () => {
    const state = createInitialPrototypeState();
    const next = setActivePatient(state, 'missing-patient');

    expect(next).toBe(state);
    expect(selectActivePatient(next).patientId).toBe('demo-patient');
  });

  it('adds manually corrected intake records only to the active patient', () => {
    const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');
    const next = addCorrectedIntake(state, '低糖酸奶', 4);

    expect(next.intakeRecordsByPatientId['demo-patient']).toHaveLength(1);
    expect(next.intakeRecordsByPatientId['demo-patient-ckd']).toHaveLength(2);
    expect(next.intakeRecordsByPatientId['demo-patient-ckd'].at(-1)?.foodLabel).toBe('低糖酸奶');
    expect(selectActivePatientIntakeRecords(next).at(-1)?.manuallyCorrected).toBe(true);
  });

  it('creates simulated recommendation states only for the active patient', () => {
    const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');
    const next = requestRecommendation(state, 'refused');

    expect(next.recommendationsByPatientId['demo-patient']?.traceId).toBe('trace-7c4e3608');
    expect(next.recommendationsByPatientId['demo-patient-ckd']?.outcome).toBe('refused');
    expect(selectActivePatientRecommendation(next)?.outcome).toBe('refused');
  });

  it('writes backend recommendations to the requested patient id', () => {
    const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');
    const backendRecommendation = {
      ...recommendedResponse,
      traceId: 'trace-http-ckd',
      trace: {
        ...recommendedResponse.trace,
        traceId: 'trace-http-ckd',
        patientId: 'demo-patient-ckd'
      }
    };
    const next = applyBackendRecommendation(state, 'demo-patient-ckd', backendRecommendation);

    expect(next.recommendationsByPatientId['demo-patient']?.traceId).toBe('trace-7c4e3608');
    expect(next.recommendationsByPatientId['demo-patient-ckd']?.traceId).toBe('trace-http-ckd');
    expect(selectActivePatientRecommendation(next)?.traceId).toBe('trace-http-ckd');
  });

  it('summarizes workbench counts by role', () => {
    const state = createInitialPrototypeState();

    expect(selectWorkbenchSummary(state, 'patient').primaryCount).toBe(1);
    expect(selectWorkbenchSummary(state, 'dietitian').primaryCount).toBe(1);
    expect(selectWorkbenchSummary(state, 'catering').secondaryCount).toBeGreaterThan(0);
  });

  it('adds manually corrected intake records', () => {
    const state = createInitialPrototypeState();
    const next = addCorrectedIntake(state, '低糖酸奶', 4);

    expect(selectActivePatientIntakeRecords(next)).toHaveLength(selectActivePatientIntakeRecords(state).length + 1);
    expect(selectActivePatientIntakeRecords(next).at(-1)?.manuallyCorrected).toBe(true);
  });

  it('creates recommended and review-required recommendation states', () => {
    const state = createInitialPrototypeState();

    expect(selectActivePatientRecommendation(requestRecommendation(state, 'recommended'))?.outcome).toBe('recommended');
    expect(selectActivePatientRecommendation(requestRecommendation(state, 'review'))?.outcome).toBe(
      'human_review_required'
    );
  });

  it('writes review decisions back to queue and recommendation', () => {
    const state = createInitialPrototypeState();
    const reviewState = requestRecommendation(state, 'review');
    const next = submitReviewDecision(reviewState, 'trace-review-001', 'approve');

    expect(next.reviewCases[0].status).toBe('approved');
    expect(selectActivePatientRecommendation(next)?.reviewStatus).toBe('completed');
    expect(selectActivePatientRecommendation(next)?.traceId).toBe('trace-review-001');
    expect(selectActivePatientRecommendation(next)?.outcome).toBe('recommended');
    expect(selectActivePatientRecommendation(next)?.recommendedItems[0]?.name).toBe('清蒸鱼套餐');
    expect(selectActivePatientRecommendation(next)?.patientExplanation).toContain('营养师已确认');
    expect(selectActivePatientRecommendation(next)?.trace.scores).toHaveProperty('steamed-fish-set');
  });

  it('writes rejected review decisions as patient-facing refusal states', () => {
    const state = createInitialPrototypeState();
    const reviewState = requestRecommendation(state, 'review');
    const next = submitReviewDecision(reviewState, 'trace-review-001', 'reject');

    expect(next.reviewCases[0].status).toBe('rejected');
    expect(selectActivePatientRecommendation(next)?.reviewStatus).toBe('completed');
    expect(selectActivePatientRecommendation(next)?.outcome).toBe('refused');
    expect(selectActivePatientRecommendation(next)?.recommendedItems).toHaveLength(0);
    expect(selectActivePatientRecommendation(next)?.patientExplanation).toContain('营养师未通过');
    expect(selectActivePatientRecommendation(next)?.trace.patientExplanation).toContain('营养师未通过');
  });

  it('leaves recommendation and review cases unchanged for unknown review trace ids', () => {
    const state = createInitialPrototypeState();
    const next = submitReviewDecision(state, 'trace-unknown', 'approve');

    expect(next).toBe(state);
    expect(next.recommendationsByPatientId).toBe(state.recommendationsByPatientId);
    expect(next.reviewCases).toBe(state.reviewCases);
  });

  it('writes queued review decisions to the patient view when the current trace differs', () => {
    const state = createInitialPrototypeState();
    const next = submitReviewDecision(state, 'trace-review-001', 'reject');

    expect(next.reviewCases[0].status).toBe('rejected');
    expect(selectActivePatientRecommendation(next)).not.toBe(selectActivePatientRecommendation(state));
    expect(selectActivePatientRecommendation(next)?.traceId).toBe('trace-review-001');
    expect(selectActivePatientRecommendation(next)?.reviewStatus).toBe('completed');
    expect(selectActivePatientRecommendation(next)?.outcome).toBe('refused');
    expect(selectActivePatientRecommendation(next)?.recommendedItems).toHaveLength(0);
    expect(selectActivePatientRecommendation(next)?.patientExplanation).toContain('营养师未通过');
  });

  it('does not throw when review mode has an empty review queue', () => {
    const state = {
      ...createInitialPrototypeState(),
      recommendationsByPatientId: { 'demo-patient': null },
      reviewCases: []
    };

    expect(() => requestRecommendation(state, 'review')).not.toThrow();
    expect(selectActivePatientRecommendation(requestRecommendation(state, 'review'))).toBeNull();
  });

  it('updates menu availability and fulfillment status', () => {
    const state = createInitialPrototypeState();

    expect(updateMenuItemAvailability(state, 'steamed-fish-set', false).menuItems[0].available).toBe(false);
    expect(updateFulfillmentStatus(state, 'fulfillment-001', 'prepared').fulfillments[0].status).toBe('prepared');
  });
});
