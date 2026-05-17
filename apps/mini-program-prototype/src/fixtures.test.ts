import { intakeRecords, menuItems, patientProfile, recommendedResponse, reviewCases } from './fixtures';

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

  it('keeps the review fixture tied to the demo patient identity', () => {
    expect(reviewCases[0].trace.patientId).toBe(patientProfile.patientId);
    expect(reviewCases[0].patientDisplayName).toBe(patientProfile.displayName);
  });

  it('keeps the review trace free of completed recommendation artifacts', () => {
    expect(reviewCases[0].trace.scores).toEqual({});
    expect(reviewCases[0].trace.exclusions).toEqual({});
    expect(reviewCases[0].trace.clinicianExplanation.matchedTags).toEqual([]);
  });
});
