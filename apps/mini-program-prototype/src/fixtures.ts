import type {
  FulfillmentDto,
  IntakeRecordDto,
  MenuItemDto,
  PatientProfileDto,
  RecommendationResponseDto,
  RecommendationTraceDto,
  ReviewCaseDto
} from './contracts';

export const patientProfile: PatientProfileDto = {
  patientId: 'demo-patient',
  displayName: '王女士',
  age: 52,
  heightCm: 170,
  weightKg: 80,
  conditions: ['hypertension', 'diabetes'],
  allergens: ['shrimp'],
  contraindications: [],
  tasteTags: ['light'],
  dislikedIngredients: ['cilantro'],
  maxPriceCents: 4000,
  maxDistanceMeters: 2000,
  keyRiskFieldsConfirmed: true,
  source: 'patient_reported'
};

export const intakeRecords: IntakeRecordDto[] = [
  {
    intakeId: 'intake-lunch-001',
    foodLabel: '咸汤面',
    occurredAt: '2026-05-17T12:10:00+08:00',
    mealLabel: 2,
    portion: '一碗',
    nutrients: {
      energyKcal: 620,
      carbsG: 80,
      proteinG: 20,
      fatG: 18,
      sodiumMg: 600,
      sugarG: 6,
      fiberG: 4
    },
    confidence: 0.86,
    source: 'system_estimated',
    manuallyCorrected: false
  }
];

export const menuItems: MenuItemDto[] = [
  {
    itemId: 'steamed-fish-set',
    merchantId: 'canteen-1',
    name: '清蒸鱼套餐',
    category: '套餐',
    ingredients: ['fish', 'brown_rice', 'greens'],
    allergens: [],
    tasteTags: ['light'],
    nutritionTags: ['low_sodium', 'controlled_carbs', 'vegetable_rich', 'lean_protein'],
    contraindicationTags: [],
    nutrients: {
      energyKcal: 560,
      carbsG: 55,
      proteinG: 35,
      fatG: 16,
      sodiumMg: 430,
      sugarG: 5,
      fiberG: 7
    },
    nutritionConfidence: 0.92,
    source: 'human_curated',
    priceCents: 3600,
    distanceMeters: 500,
    merchantReliability: 0.95,
    available: true,
    updatedAt: '2026-05-17T09:30:00+08:00'
  },
  {
    itemId: 'brown-rice-chicken-set',
    merchantId: 'canteen-1',
    name: '糙米鸡胸套餐',
    category: '套餐',
    ingredients: ['chicken', 'brown_rice', 'broccoli'],
    allergens: [],
    tasteTags: ['light'],
    nutritionTags: ['controlled_carbs', 'lean_protein'],
    contraindicationTags: [],
    nutrients: {
      energyKcal: 610,
      carbsG: 62,
      proteinG: 38,
      fatG: 17,
      sodiumMg: 520,
      sugarG: 5,
      fiberG: 0
    },
    nutritionConfidence: 0.62,
    source: 'system_estimated',
    priceCents: 3400,
    distanceMeters: 500,
    merchantReliability: 0.88,
    available: true,
    updatedAt: '2026-05-17T08:30:00+08:00'
  },
  {
    itemId: 'fried-pork-rice',
    merchantId: 'delivery-1',
    name: '炸猪排饭',
    category: '盖饭',
    ingredients: ['pork', 'white_rice'],
    allergens: [],
    tasteTags: ['savory'],
    nutritionTags: [],
    contraindicationTags: ['deep_fried'],
    nutrients: {
      energyKcal: 760,
      carbsG: 82,
      proteinG: 26,
      fatG: 32,
      sodiumMg: 980,
      sugarG: 8,
      fiberG: 2
    },
    nutritionConfidence: 0.8,
    source: 'system_estimated',
    priceCents: 3200,
    distanceMeters: 900,
    merchantReliability: 0.7,
    available: false,
    updatedAt: '2026-05-17T08:00:00+08:00'
  }
];

export const recommendedTrace: RecommendationTraceDto = {
  traceId: 'trace-7c4e3608',
  patientId: 'demo-patient',
  ruleVersion: 'baseline-2026-05-15',
  outcome: 'recommended',
  riskLevel: 'low',
  createdAt: '2026-05-17T17:00:00+08:00',
  safetyEvents: [],
  exclusions: {
    'fried-pork-rice': {
      code: 5001,
      codeName: 'UNAVAILABLE',
      itemId: 'fried-pork-rice'
    }
  },
  scores: {
    'steamed-fish-set': 43.9633
  },
  patientExplanation: '这份餐食符合当前营养规则，重点考虑控主食、低钠、蔬菜丰富，建议少放酱汁。',
  clinicianExplanation: {
    ruleVersion: 'baseline-2026-05-15',
    matchedTags: [
      { kind: 'nutrition_tag', value: 'controlled_carbs' },
      { kind: 'nutrition_tag', value: 'low_sodium' },
      { kind: 'nutrition_tag', value: 'vegetable_rich' }
    ],
    llmBoundary: 'Explanation is generated only from rule hits, nutrition facts, and scored candidates.'
  }
};

export const recommendedResponse: RecommendationResponseDto = {
  outcome: 'recommended',
  riskLevel: 'low',
  traceId: recommendedTrace.traceId,
  recommendedItems: [menuItems[0]],
  patientExplanation: recommendedTrace.patientExplanation,
  reviewStatus: null,
  trace: recommendedTrace
};

export const reviewRequiredTrace: RecommendationTraceDto = {
  ...recommendedTrace,
  traceId: 'trace-review-001',
  outcome: 'human_review_required',
  riskLevel: 'high',
  safetyEvents: [
    {
      code: 1003,
      codeName: 'LOW_CONFIDENCE_INTAKE',
      severity: 'high',
      patientId: 'demo-patient',
      entityId: 'intake-lunch-001'
    }
  ],
  patientExplanation: '当前信息需要营养师确认后再推荐餐食。'
};

export const reviewCases: ReviewCaseDto[] = [
  {
    traceId: reviewRequiredTrace.traceId,
    patientDisplayName: '李先生',
    mealLabel: 3,
    riskLevel: 'high',
    reason: '照片估算置信度低，需要确认摄入记录',
    status: 'pending',
    requestedAt: '2026-05-17T16:40:00+08:00',
    trace: reviewRequiredTrace
  }
];

export const fulfillments: FulfillmentDto[] = [
  {
    fulfillmentId: 'fulfillment-001',
    patientDisplayName: '王女士',
    itemName: '清蒸鱼套餐',
    mealLabel: 3,
    status: 'pending'
  }
];
