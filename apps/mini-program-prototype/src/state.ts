import type {
  FulfillmentDto,
  FulfillmentStatus,
  IntakeRecordDto,
  MealLabel,
  MenuItemDto,
  PatientProfileDto,
  RecommendationResponseDto,
  ReviewCaseDto,
  ReviewDecision,
  Role
} from './contracts';
import {
  fulfillments,
  intakeRecordsByPatientId,
  menuItems,
  patientProfiles,
  recommendationsByPatientId,
  recommendedResponse,
  reviewCases
} from './fixtures';

export interface PrototypeState {
  activeRole: Role;
  patients: PatientProfileDto[];
  activePatientId: string;
  intakeRecordsByPatientId: Record<string, IntakeRecordDto[]>;
  menuItems: MenuItemDto[];
  recommendationsByPatientId: Record<string, RecommendationResponseDto | null>;
  reviewCases: ReviewCaseDto[];
  fulfillments: FulfillmentDto[];
}

export interface WorkbenchSummary {
  title: string;
  primaryLabel: string;
  primaryCount: number;
  secondaryLabel: string;
  secondaryCount: number;
}

export function createInitialPrototypeState(): PrototypeState {
  return {
    activeRole: 'patient',
    patients: [...patientProfiles],
    activePatientId: patientProfiles[0].patientId,
    intakeRecordsByPatientId: cloneIntakeRecordsByPatientId(intakeRecordsByPatientId),
    menuItems: [...menuItems],
    recommendationsByPatientId: { ...recommendationsByPatientId },
    reviewCases: [...reviewCases],
    fulfillments: [...fulfillments]
  };
}

export function setActiveRole(state: PrototypeState, activeRole: Role): PrototypeState {
  return { ...state, activeRole };
}

export function selectActivePatient(state: PrototypeState): PatientProfileDto {
  return state.patients.find((patient) => patient.patientId === state.activePatientId) ?? state.patients[0];
}

export function selectActivePatientIntakeRecords(state: PrototypeState): IntakeRecordDto[] {
  return state.intakeRecordsByPatientId[selectActivePatient(state).patientId] ?? [];
}

export function selectActivePatientRecommendation(state: PrototypeState): RecommendationResponseDto | null {
  return state.recommendationsByPatientId[selectActivePatient(state).patientId] ?? null;
}

export function setActivePatient(state: PrototypeState, patientId: string): PrototypeState {
  if (!state.patients.some((patient) => patient.patientId === patientId)) {
    return state;
  }

  return { ...state, activePatientId: patientId };
}

export function selectWorkbenchSummary(state: PrototypeState, role: Role): WorkbenchSummary {
  if (role === 'patient') {
    return {
      title: '患者工作台',
      primaryLabel: '今日摄入',
      primaryCount: selectActivePatientIntakeRecords(state).length,
      secondaryLabel: '推荐状态',
      secondaryCount: selectActivePatientRecommendation(state) ? 1 : 0
    };
  }

  if (role === 'dietitian') {
    return {
      title: '营养师工作台',
      primaryLabel: '待审核',
      primaryCount: state.reviewCases.filter((item) => item.status === 'pending').length,
      secondaryLabel: '高风险',
      secondaryCount: state.reviewCases.filter((item) => item.riskLevel === 'high').length
    };
  }

  return {
    title: '配餐管理工作台',
    primaryLabel: '可推荐菜品',
    primaryCount: state.menuItems.filter((item) => item.available).length,
    secondaryLabel: '数据待补',
    secondaryCount: state.menuItems.filter((item) => item.nutritionConfidence < 0.7 || item.nutrients.fiberG === 0).length
  };
}

export function addCorrectedIntake(state: PrototypeState, foodLabel: string, mealLabel: MealLabel): PrototypeState {
  const patientId = selectActivePatient(state).patientId;
  const currentRecords = state.intakeRecordsByPatientId[patientId] ?? [];
  const nextRecord: IntakeRecordDto = {
    intakeId: `manual-${patientId}-${currentRecords.length + 1}`,
    foodLabel,
    occurredAt: '2026-05-17T18:10:00+08:00',
    mealLabel,
    portion: '一份',
    nutrients: {
      energyKcal: 180,
      carbsG: 18,
      proteinG: 10,
      fatG: 5,
      sodiumMg: 120,
      sugarG: 6,
      fiberG: 2
    },
    confidence: 1,
    source: 'patient_reported',
    manuallyCorrected: true
  };

  return {
    ...state,
    intakeRecordsByPatientId: {
      ...state.intakeRecordsByPatientId,
      [patientId]: [...currentRecords, nextRecord]
    }
  };
}

export function requestRecommendation(state: PrototypeState, mode: 'recommended' | 'refused' | 'review'): PrototypeState {
  const patientId = selectActivePatient(state).patientId;

  if (mode === 'review') {
    const reviewCase = state.reviewCases.find((item) => item.trace.patientId === patientId);
    if (!reviewCase) {
      return applyBackendRecommendation(state, patientId, null);
    }

    return applyBackendRecommendation(state, patientId, {
      outcome: 'human_review_required',
      riskLevel: reviewCase.riskLevel,
      traceId: reviewCase.traceId,
      recommendedItems: [],
      patientExplanation: reviewCase.trace.patientExplanation,
      reviewStatus: 'pending',
      trace: reviewCase.trace
    });
  }

  if (mode === 'refused') {
    return applyBackendRecommendation(state, patientId, {
      ...recommendedResponse,
      outcome: 'refused',
      riskLevel: 'high',
      recommendedItems: [],
      patientExplanation: '当前候选餐食不满足安全和营养要求，暂不建议自动推荐。',
      reviewStatus: null,
      trace: {
        ...recommendedResponse.trace,
        patientId,
        outcome: 'refused',
        riskLevel: 'high',
        patientExplanation: '当前候选餐食不满足安全和营养要求，暂不建议自动推荐。'
      }
    });
  }

  return applyBackendRecommendation(state, patientId, {
    ...recommendedResponse,
    trace: {
      ...recommendedResponse.trace,
      patientId
    }
  });
}

export function applyBackendRecommendation(
  state: PrototypeState,
  patientId: string,
  recommendation: RecommendationResponseDto | null
): PrototypeState {
  return {
    ...state,
    recommendationsByPatientId: {
      ...state.recommendationsByPatientId,
      [patientId]: recommendation
    }
  };
}

function selectReviewedRecommendationItem(state: PrototypeState): MenuItemDto | undefined {
  return (
    state.menuItems.find((item) => item.available && item.nutritionConfidence >= 0.7) ??
    state.menuItems.find((item) => item.available)
  );
}

export function submitReviewDecision(
  state: PrototypeState,
  traceId: string,
  decision: ReviewDecision
): PrototypeState {
  const reviewCase = state.reviewCases.find((item) => item.traceId === traceId);
  if (!reviewCase) {
    return state;
  }

  const status: ReviewCaseDto['status'] =
    decision === 'approve' ? 'approved' : decision === 'modify' ? 'modified' : 'rejected';
  const patientId = reviewCase.trace.patientId;
  const existingRecommendation = state.recommendationsByPatientId[patientId] ?? null;
  const matchingRecommendation = existingRecommendation?.traceId === traceId ? existingRecommendation : null;
  const baseRecommendation: RecommendationResponseDto = matchingRecommendation ?? {
    outcome: reviewCase.trace.outcome,
    riskLevel: reviewCase.riskLevel,
    traceId: reviewCase.traceId,
    recommendedItems: [],
    patientExplanation: reviewCase.trace.patientExplanation,
    reviewStatus: 'pending',
    trace: reviewCase.trace
  };
  const reviewedItem = selectReviewedRecommendationItem(state);
  const approvedExplanation =
    decision === 'modify'
      ? '营养师已调整推荐方案，可选择这份餐食，并继续少放酱汁、控制主食份量。'
      : '营养师已确认这份餐食可以选择，请继续少放酱汁、控制主食份量。';
  const rejectedExplanation = '营养师未通过本次自动推荐，请等待线下补充评估或重新提交摄入信息。';
  const nextOutcome = decision === 'reject' || !reviewedItem ? 'refused' : 'recommended';
  const nextExplanation = nextOutcome === 'recommended' ? approvedExplanation : rejectedExplanation;

  return {
    ...state,
    recommendationsByPatientId: {
      ...state.recommendationsByPatientId,
      [patientId]: {
        ...baseRecommendation,
        traceId: reviewCase.traceId,
        reviewStatus: 'completed',
        outcome: nextOutcome,
        riskLevel: nextOutcome === 'recommended' ? 'medium' : 'high',
        recommendedItems: nextOutcome === 'recommended' && reviewedItem ? [reviewedItem] : [],
        patientExplanation: nextExplanation,
        trace: {
          ...reviewCase.trace,
          outcome: nextOutcome,
          riskLevel: nextOutcome === 'recommended' ? 'medium' : 'high',
          scores: nextOutcome === 'recommended' && reviewedItem ? { [reviewedItem.itemId]: 38.4 } : {},
          patientExplanation: nextExplanation,
          clinicianExplanation: {
            ...reviewCase.trace.clinicianExplanation,
            matchedTags:
              nextOutcome === 'recommended' && reviewedItem
                ? reviewedItem.nutritionTags.map((value) => ({ kind: 'nutrition_tag', value }))
                : []
          }
        }
      }
    },
    reviewCases: state.reviewCases.map((item) => (item.traceId === traceId ? { ...item, status } : item))
  };
}

export function updateMenuItemAvailability(state: PrototypeState, itemId: string, available: boolean): PrototypeState {
  return {
    ...state,
    menuItems: state.menuItems.map((item) => (item.itemId === itemId ? { ...item, available } : item))
  };
}

export function updateFulfillmentStatus(
  state: PrototypeState,
  fulfillmentId: string,
  status: FulfillmentStatus
): PrototypeState {
  return {
    ...state,
    fulfillments: state.fulfillments.map((item) => (item.fulfillmentId === fulfillmentId ? { ...item, status } : item))
  };
}

function cloneIntakeRecordsByPatientId(
  recordsByPatientId: Record<string, IntakeRecordDto[]>
): Record<string, IntakeRecordDto[]> {
  return Object.fromEntries(
    Object.entries(recordsByPatientId).map(([patientId, records]) => [patientId, [...records]])
  );
}
