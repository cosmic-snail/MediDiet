import { mealLabelName, outcomeToPatientState, riskPriority } from './contracts';

describe('frontend recommendation contracts', () => {
  it('maps numeric MealLabel values to patient-facing names', () => {
    expect(mealLabelName(1)).toBe('早餐');
    expect(mealLabelName(2)).toBe('午餐');
    expect(mealLabelName(3)).toBe('晚餐');
    expect(mealLabelName(4)).toBe('加餐');
  });

  it('maps recommendation outcomes to stable UI states', () => {
    expect(outcomeToPatientState('recommended')).toBe('showRecommendation');
    expect(outcomeToPatientState('refused')).toBe('showRefusal');
    expect(outcomeToPatientState('human_review_required')).toBe('showReviewWait');
  });

  it('orders review queue by risk priority', () => {
    expect(riskPriority('high')).toBeGreaterThan(riskPriority('medium'));
    expect(riskPriority('medium')).toBeGreaterThan(riskPriority('low'));
  });
});
