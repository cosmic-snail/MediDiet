import type {
  DataSource,
  IntakeRecordDto,
  MenuItemDto,
  NutrientsDto,
  Outcome,
  PatientProfileDto,
  RecommendationResponseDto,
  RecommendationTraceDto,
  RiskLevel
} from '../contracts';

type ConceptKind = 'condition' | 'allergen' | 'contraindication' | 'nutrition_tag' | 'taste_tag' | 'ingredient';

export interface BackendConceptCode {
  kind: ConceptKind;
  value: string;
}

export interface BackendNutrientsPayload {
  energyKcal: number;
  carbsG: number;
  proteinG: number;
  fatG: number;
  sodiumMg: number;
  sugarG: number;
  fiberG: number;
}

export interface BackendPatientPayload {
  age: number;
  heightCm: number;
  weightKg: number;
  conditions: BackendConceptCode[];
  allergens: BackendConceptCode[];
  contraindications: BackendConceptCode[];
  preferences: {
    tasteTags: BackendConceptCode[];
    dislikedIngredients: BackendConceptCode[];
    maxPriceCents: number;
    maxDistanceMeters: number;
  };
  keyRiskFieldsConfirmed: boolean;
}

export interface BackendIntakeRecordPayload {
  foodLabel: string;
  occurredAt: string;
  mealLabel: number;
  portion: string;
  nutrients: BackendNutrientsPayload;
  confidence: number;
  manuallyCorrected: boolean;
}

export interface BackendMenuItemPayload {
  itemId: string;
  name: string;
  nutrients: BackendNutrientsPayload;
  ingredients: BackendConceptCode[];
  allergens: BackendConceptCode[];
  tasteTags: BackendConceptCode[];
  nutritionTags: BackendConceptCode[];
  contraindicationTags: BackendConceptCode[];
  merchantId: string;
  nutritionConfidence: number;
  source: DataSource;
  priceCents: number;
  distanceMeters: number;
  merchantReliability: number;
  available: boolean;
}

export interface BackendMenuPayload {
  items: BackendMenuItemPayload[];
}

export interface BackendRecommendationResponse {
  outcome: Outcome;
  recommendedItems: BackendRecommendationMenuItem[];
  explanation: {
    patient: string;
    clinician: string;
    llm: {
      usedFallback: boolean;
      fallbackReason: number | null;
    };
  };
  nutritionistReviews: unknown[];
  traceId: string;
  trace?: RecommendationTraceDto;
}

interface BackendRecommendationMenuItem {
  itemId: string;
  merchantId?: string;
  name: string;
  nutrients: BackendNutrientsPayload;
  nutritionTags?: BackendConceptCode[];
  tasteTags?: BackendConceptCode[];
  available?: boolean;
}

export function toBackendPatientPayload(profile: PatientProfileDto): BackendPatientPayload {
  return {
    age: profile.age,
    heightCm: profile.heightCm,
    weightKg: profile.weightKg,
    conditions: toConceptCodes('condition', profile.conditions),
    allergens: toConceptCodes('allergen', profile.allergens),
    contraindications: toConceptCodes('contraindication', profile.contraindications),
    preferences: {
      tasteTags: toConceptCodes('taste_tag', profile.tasteTags),
      dislikedIngredients: toConceptCodes('ingredient', profile.dislikedIngredients),
      maxPriceCents: profile.maxPriceCents,
      maxDistanceMeters: profile.maxDistanceMeters
    },
    keyRiskFieldsConfirmed: profile.keyRiskFieldsConfirmed
  };
}

export function toBackendIntakeRecordPayload(record: IntakeRecordDto): BackendIntakeRecordPayload {
  return {
    foodLabel: record.foodLabel,
    occurredAt: record.occurredAt,
    mealLabel: record.mealLabel,
    portion: record.portion,
    nutrients: toBackendNutrients(record.nutrients),
    confidence: record.confidence,
    manuallyCorrected: record.manuallyCorrected
  };
}

export function toBackendMenuPayload(items: MenuItemDto[]): BackendMenuPayload {
  return {
    items: items.map((item) => ({
      itemId: item.itemId,
      name: item.name,
      nutrients: toBackendNutrients(item.nutrients),
      ingredients: toConceptCodes('ingredient', item.ingredients),
      allergens: toConceptCodes('allergen', item.allergens),
      tasteTags: toConceptCodes('taste_tag', item.tasteTags),
      nutritionTags: toConceptCodes('nutrition_tag', item.nutritionTags),
      contraindicationTags: toConceptCodes('contraindication', item.contraindicationTags),
      merchantId: item.merchantId,
      nutritionConfidence: item.nutritionConfidence,
      source: item.source,
      priceCents: item.priceCents,
      distanceMeters: item.distanceMeters,
      merchantReliability: item.merchantReliability,
      available: item.available
    }))
  };
}

export function toRecommendationResponseDto(response: BackendRecommendationResponse): RecommendationResponseDto {
  const trace = response.trace ?? fallbackTrace(response);

  return {
    outcome: response.outcome,
    riskLevel: trace.riskLevel,
    traceId: response.traceId,
    recommendedItems: response.recommendedItems.map(toFrontendMenuItem),
    patientExplanation: response.explanation.patient,
    reviewStatus: response.outcome === 'human_review_required' ? 'pending' : null,
    trace: {
      ...trace,
      patientExplanation: response.explanation.patient
    }
  };
}

function toBackendNutrients(nutrients: NutrientsDto): BackendNutrientsPayload {
  return { ...nutrients };
}

function toConceptCodes(kind: ConceptKind, values: string[]): BackendConceptCode[] {
  return values.map((value) => ({ kind, value }));
}

function conceptValues(values: BackendConceptCode[] | undefined): string[] {
  return values?.map((item) => item.value) ?? [];
}

function toFrontendMenuItem(item: BackendRecommendationMenuItem): MenuItemDto {
  return {
    itemId: item.itemId,
    merchantId: item.merchantId ?? 'hospital-canteen',
    name: item.name,
    category: '推荐餐食',
    ingredients: [],
    allergens: [],
    tasteTags: conceptValues(item.tasteTags),
    nutritionTags: conceptValues(item.nutritionTags),
    contraindicationTags: [],
    nutrients: item.nutrients,
    nutritionConfidence: 1,
    source: 'human_curated',
    priceCents: 0,
    distanceMeters: 0,
    merchantReliability: 1,
    available: item.available ?? true,
    updatedAt: new Date().toISOString()
  };
}

function fallbackTrace(response: BackendRecommendationResponse): RecommendationTraceDto {
  const riskLevel: RiskLevel = response.outcome === 'recommended' ? 'low' : 'high';

  return {
    traceId: response.traceId,
    patientId: 'unknown',
    ruleVersion: 'unknown',
    outcome: response.outcome,
    riskLevel,
    createdAt: new Date().toISOString(),
    safetyEvents: [],
    exclusions: {},
    scores: {},
    patientExplanation: response.explanation.patient,
    clinicianExplanation: {
      ruleVersion: 'unknown',
      matchedTags: [],
      llmBoundary: response.explanation.clinician
    }
  };
}
