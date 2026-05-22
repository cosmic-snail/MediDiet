import type { IntakeRecordDto, MealLabel, MenuItemDto, PatientProfileDto, RecommendationResponseDto } from '../contracts';
import {
  type BackendRecommendationResponse,
  toBackendIntakeRecordPayload,
  toBackendMenuPayload,
  toBackendPatientPayload,
  toRecommendationResponseDto
} from './adapters';

export class MediDietApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'MediDietApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface SeedDemoDataInput {
  patientProfile: PatientProfileDto;
  intakeRecords: IntakeRecordDto[];
  menuItems: MenuItemDto[];
}

export interface RecommendationRequestInput {
  patientId: string;
  mealLabel: MealLabel;
}

export interface MediDietApiClient {
  seedDemoData(input: SeedDemoDataInput): Promise<void>;
  requestRecommendation(input: RecommendationRequestInput): Promise<RecommendationResponseDto>;
}

interface DebugStateResponse {
  patients: string[];
  intakeRecordCounts: Record<string, number>;
  todayMenuCount: number;
  nutritionistReviewCounts: Record<string, number>;
}

export function createMediDietApiClient(baseUrl = defaultBaseUrl()): MediDietApiClient {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, '');

  return {
    async seedDemoData(input) {
      const state = await request<DebugStateResponse>(`${normalizedBaseUrl}/debug/state`, {
        method: 'GET'
      });

      await request(`${normalizedBaseUrl}/patients/${input.patientProfile.patientId}`, {
        method: 'PUT',
        body: toBackendPatientPayload(input.patientProfile)
      });

      const seededCount = state.intakeRecordCounts[input.patientProfile.patientId] ?? 0;
      const recordsToSeed = input.intakeRecords.slice(seededCount);
      for (const record of recordsToSeed) {
        await request(`${normalizedBaseUrl}/patients/${input.patientProfile.patientId}/intake-records`, {
          method: 'POST',
          body: toBackendIntakeRecordPayload(record)
        });
      }

      await request(`${normalizedBaseUrl}/menus/today`, {
        method: 'PUT',
        body: toBackendMenuPayload(selectBackendRecommendationMenuItems(input.menuItems))
      });
    },

    async requestRecommendation(input) {
      const response = await request<BackendRecommendationResponse>(`${normalizedBaseUrl}/recommendations`, {
        method: 'POST',
        body: {
          patientId: input.patientId,
          mealLabel: input.mealLabel,
          temporaryTasteTags: [],
          debug: true
        }
      });

      return toRecommendationResponseDto(response);
    }
  };
}

function selectBackendRecommendationMenuItems(menuItems: MenuItemDto[]): MenuItemDto[] {
  return menuItems.filter((item) => item.available && item.nutritionConfidence >= 0.7);
}

async function request<T = unknown>(url: string, init: { method: string; body?: unknown }): Promise<T> {
  const response = await fetch(url, {
    method: init.method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body)
  });
  const body = await response.json();

  if (!response.ok) {
    const error = isErrorResponse(body)
      ? body.error
      : { code: `HTTP_${response.status}`, message: 'MediDiet service request failed', details: {} };
    throw new MediDietApiError(response.status, error.code, error.message, error.details);
  }

  return body as T;
}

function isErrorResponse(value: unknown): value is {
  error: { code: string; message: string; details: Record<string, unknown> };
} {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as { error?: unknown }).error === 'object' &&
    (value as { error?: unknown }).error !== null
  );
}

function defaultBaseUrl(): string {
  return import.meta.env.VITE_MEDIDIET_API_BASE_URL ?? '/api';
}
