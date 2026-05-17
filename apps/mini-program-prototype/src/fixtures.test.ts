import { intakeRecords, menuItems, recommendedResponse, reviewCases } from './fixtures';

describe('prototype fixtures', () => {
  it('contains a recommendation with trace id and patient explanation', () => {
    expect(recommendedResponse.traceId).toBe('trace-7c4e3608');
    expect(recommendedResponse.patientExplanation).toContain('低钠');
  });

  it('contains menu items that exercise available, low-confidence, and unavailable states', () => {
    expect(menuItems.some((item) => item.available)).toBe(true);
    expect(menuItems.some((item) => item.nutritionConfidence < 0.7)).toBe(true);
    expect(menuItems.some((item) => !item.available)).toBe(true);
  });

  it('contains intake records and review cases tied to recommendation workflow', () => {
    expect(intakeRecords[0].mealLabel).toBe(2);
    expect(reviewCases[0].trace.outcome).toBe('human_review_required');
  });
});
