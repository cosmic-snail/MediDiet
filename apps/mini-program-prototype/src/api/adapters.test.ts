import { describe, expect, it } from 'vitest';
import { intakeRecords, menuItems, patientProfile } from '../fixtures';
import {
  toBackendIntakeRecordPayload,
  toBackendMenuPayload,
  toBackendPatientPayload,
  toRecommendationResponseDto
} from './adapters';

describe('HTTP DTO adapters', () => {
  it('maps patient profile strings into backend concept code payloads', () => {
    const payload = toBackendPatientPayload(patientProfile);

    expect(payload.conditions).toEqual([
      { kind: 'condition', value: 'hypertension' },
      { kind: 'condition', value: 'diabetes' }
    ]);
    expect(payload.preferences.tasteTags).toEqual([{ kind: 'taste_tag', value: 'light' }]);
    expect(payload.preferences.dislikedIngredients).toEqual([{ kind: 'ingredient', value: 'cilantro' }]);
    expect(payload.keyRiskFieldsConfirmed).toBe(true);
  });

  it('maps intake records and menu items into backend payloads', () => {
    const intakePayload = toBackendIntakeRecordPayload(intakeRecords[0]);
    const menuPayload = toBackendMenuPayload(menuItems);

    expect(intakePayload.foodLabel).toBe('咸汤面');
    expect(intakePayload.nutrients.sodiumMg).toBe(600);
    expect(menuPayload.items[0].nutritionTags).toContainEqual({ kind: 'nutrition_tag', value: 'low_sodium' });
    expect(menuPayload.items[0].ingredients).toContainEqual({ kind: 'ingredient', value: 'fish' });
    expect(menuPayload.items[0].nutritionConfidence).toBe(0.92);
  });

  it('maps backend recommendation responses into frontend recommendation DTOs', () => {
    const response = toRecommendationResponseDto({
      outcome: 'recommended',
      recommendedItems: [
        {
          itemId: 'steamed-fish-set',
          merchantId: 'hospital-canteen',
          name: '清蒸鱼套餐',
          nutrients: {
            energyKcal: 560,
            carbsG: 55,
            proteinG: 35,
            fatG: 16,
            sodiumMg: 430,
            sugarG: 5,
            fiberG: 7
          },
          nutritionTags: [{ kind: 'nutrition_tag', value: 'low_sodium' }],
          tasteTags: [{ kind: 'taste_tag', value: 'light' }],
          available: true
        }
      ],
      explanation: {
        patient: '后端返回的患者解释',
        clinician: '后端返回的营养师解释',
        llm: { usedFallback: false, fallbackReason: null }
      },
      nutritionistReviews: [],
      traceId: 'trace-http-001',
      trace: {
        traceId: 'trace-http-001',
        patientId: 'demo-patient',
        ruleVersion: 'baseline-2026-05-15',
        outcome: 'recommended',
        riskLevel: 'low',
        createdAt: '2026-05-19T08:00:00+00:00',
        safetyEvents: [],
        exclusions: {},
        scores: { 'steamed-fish-set': 42 },
        patientExplanation: '后端返回的患者解释',
        clinicianExplanation: {
          ruleVersion: 'baseline-2026-05-15',
          matchedTags: [{ kind: 'nutrition_tag', value: 'low_sodium' }],
          llmBoundary: 'backend'
        }
      }
    });

    expect(response.traceId).toBe('trace-http-001');
    expect(response.patientExplanation).toBe('后端返回的患者解释');
    expect(response.recommendedItems[0].name).toBe('清蒸鱼套餐');
    expect(response.recommendedItems[0].nutritionTags).toEqual(['low_sodium']);
    expect(response.trace.clinicianExplanation.llmBoundary).toBe('backend');
  });
});
