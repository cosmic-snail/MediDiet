import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { intakeRecords, menuItems, patientProfile } from '../fixtures';
import { MediDietApiError, createMediDietApiClient } from './medidietApi';

describe('MediDiet HTTP API client', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('seeds patient, intake records, and menu before recommendation', async () => {
    fetchMock
      .mockResolvedValueOnce(okJson({ patients: [], intakeRecordCounts: {}, todayMenuCount: 0, nutritionistReviewCounts: {} }))
      .mockResolvedValue(okJson({ stored: true }));
    const client = createMediDietApiClient('/api');

    await client.seedDemoData({ patientProfile, intakeRecords, menuItems });

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/debug/state', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/patients/demo-patient',
      expect.objectContaining({ method: 'PUT' })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/patients/demo-patient/intake-records',
      expect.objectContaining({ method: 'POST' })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/menus/today', expect.objectContaining({ method: 'PUT' }));
    const menuRequest = fetchMock.mock.calls[3][1] as RequestInit;
    expect(JSON.parse(String(menuRequest.body)).items.map((item: { itemId: string }) => item.itemId)).toEqual([
      'steamed-fish-set'
    ]);
  });

  it('does not append duplicate intake records when backend state is already seeded', async () => {
    fetchMock
      .mockResolvedValueOnce(
        okJson({
          patients: ['demo-patient'],
          intakeRecordCounts: { 'demo-patient': 1 },
          todayMenuCount: 1,
          nutritionistReviewCounts: {}
        })
      )
      .mockResolvedValue(okJson({ stored: true }));
    const client = createMediDietApiClient('/api');

    await client.seedDemoData({ patientProfile, intakeRecords, menuItems });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/debug/state', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/patients/demo-patient', expect.objectContaining({ method: 'PUT' }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/menus/today', expect.objectContaining({ method: 'PUT' }));
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/intake-records'))).toBe(false);
  });

  it('requests a debug recommendation and maps the response', async () => {
    fetchMock.mockResolvedValue(
      okJson({
        outcome: 'recommended',
        recommendedItems: [],
        explanation: {
          patient: '后端推荐解释',
          clinician: '后端审核解释',
          llm: { usedFallback: false, fallbackReason: null }
        },
        nutritionistReviews: [],
        traceId: 'trace-http-002',
        trace: {
          traceId: 'trace-http-002',
          patientId: 'demo-patient',
          ruleVersion: 'baseline-2026-05-15',
          outcome: 'recommended',
          riskLevel: 'low',
          createdAt: '2026-05-19T08:00:00+00:00',
          safetyEvents: [],
          exclusions: {},
          scores: {},
          patientExplanation: '后端推荐解释',
          clinicianExplanation: {
            ruleVersion: 'baseline-2026-05-15',
            matchedTags: [],
            llmBoundary: 'backend'
          }
        }
      })
    );
    const client = createMediDietApiClient('/api');

    const recommendation = await client.requestRecommendation({ patientId: 'demo-patient', mealLabel: 3 });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/recommendations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ patientId: 'demo-patient', mealLabel: 3, temporaryTasteTags: [], debug: true })
      })
    );
    expect(recommendation.traceId).toBe('trace-http-002');
    expect(recommendation.patientExplanation).toBe('后端推荐解释');
  });

  it('throws structured API errors', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(409, {
        error: { code: 'MENU_NOT_CONFIGURED', message: 'Today menu has not been configured', details: {} }
      })
    );
    const client = createMediDietApiClient('/api');

    await expect(client.requestRecommendation({ patientId: 'demo-patient', mealLabel: 3 })).rejects.toMatchObject({
      code: 'MENU_NOT_CONFIGURED',
      message: 'Today menu has not been configured'
    } satisfies Partial<MediDietApiError>);
  });
});

function okJson(body: unknown): Response {
  return jsonResponse(200, body);
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body)
  } as Response;
}
