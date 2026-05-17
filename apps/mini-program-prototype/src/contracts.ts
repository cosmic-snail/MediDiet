export type Role = 'patient' | 'dietitian' | 'catering';
export type Outcome = 'recommended' | 'downgraded' | 'refused' | 'human_review_required';
export type RiskLevel = 'low' | 'medium' | 'high';
export type PatientState = 'showRecommendation' | 'showRefusal' | 'showReviewWait';
export type DataSource = 'patient_reported' | 'clinician_entered' | 'his_emr' | 'merchant_label' | 'human_curated' | 'system_estimated';
export type ReviewDecision = 'approve' | 'modify' | 'reject';
export type FulfillmentStatus = 'pending' | 'prepared' | 'delivered' | 'cancelled';

export type MealLabel = 1 | 2 | 3 | 4;

export interface EnvelopeDto {
  schemaVersion: string;
  sourceSystem: string;
  sourceVersion: string;
  requestId: string;
  createdAt: string;
}

export interface NutrientsDto {
  energyKcal: number;
  carbsG: number;
  proteinG: number;
  fatG: number;
  sodiumMg: number;
  sugarG: number;
  fiberG: number;
}

export interface PatientProfileDto {
  patientId: string;
  displayName: string;
  age: number;
  heightCm: number;
  weightKg: number;
  conditions: string[];
  allergens: string[];
  contraindications: string[];
  tasteTags: string[];
  dislikedIngredients: string[];
  maxPriceCents: number;
  maxDistanceMeters: number;
  keyRiskFieldsConfirmed: boolean;
  source: DataSource;
}

export interface IntakeRecordDto {
  intakeId: string;
  foodLabel: string;
  occurredAt: string;
  mealLabel: MealLabel;
  portion: string;
  nutrients: NutrientsDto;
  confidence: number;
  source: DataSource;
  manuallyCorrected: boolean;
}

export interface MenuItemDto {
  itemId: string;
  merchantId: string;
  name: string;
  category: string;
  ingredients: string[];
  allergens: string[];
  tasteTags: string[];
  nutritionTags: string[];
  contraindicationTags: string[];
  nutrients: NutrientsDto;
  nutritionConfidence: number;
  source: DataSource;
  priceCents: number;
  distanceMeters: number;
  merchantReliability: number;
  available: boolean;
  updatedAt: string;
}

export interface SafetyEventDto {
  code: number;
  codeName: string;
  severity: RiskLevel;
  patientId: string;
  entityId?: string;
  measuredValue?: number;
  limitValue?: number;
}

export interface MatchRejectionDto {
  code: number;
  codeName: string;
  itemId: string;
}

export interface RecommendationTraceDto {
  traceId: string;
  patientId: string;
  ruleVersion: string;
  outcome: Outcome;
  riskLevel: RiskLevel;
  createdAt: string;
  safetyEvents: SafetyEventDto[];
  exclusions: Record<string, MatchRejectionDto>;
  scores: Record<string, number>;
  patientExplanation: string;
  clinicianExplanation: {
    ruleVersion: string;
    matchedTags: Array<{ kind: string; value: string }>;
    llmBoundary: string;
  };
}

export interface RecommendationResponseDto {
  outcome: Outcome;
  riskLevel: RiskLevel;
  traceId: string;
  recommendedItems: MenuItemDto[];
  patientExplanation: string;
  reviewStatus: 'pending' | 'completed' | null;
  trace: RecommendationTraceDto;
}

export interface ReviewCaseDto {
  traceId: string;
  patientDisplayName: string;
  mealLabel: MealLabel;
  riskLevel: RiskLevel;
  reason: string;
  status: 'pending' | 'approved' | 'modified' | 'rejected';
  requestedAt: string;
  trace: RecommendationTraceDto;
}

export interface FulfillmentDto {
  fulfillmentId: string;
  patientDisplayName: string;
  itemName: string;
  mealLabel: MealLabel;
  status: FulfillmentStatus;
}

export function mealLabelName(label: MealLabel): string {
  return {
    1: '早餐',
    2: '午餐',
    3: '晚餐',
    4: '加餐'
  }[label];
}

export function outcomeToPatientState(outcome: Outcome): PatientState {
  if (outcome === 'recommended' || outcome === 'downgraded') {
    return 'showRecommendation';
  }
  if (outcome === 'refused') {
    return 'showRefusal';
  }
  return 'showReviewWait';
}

export function riskPriority(riskLevel: RiskLevel): number {
  return {
    low: 1,
    medium: 2,
    high: 3
  }[riskLevel];
}

export function formatPrice(cents: number): string {
  return `¥${(cents / 100).toFixed(2)}`;
}
