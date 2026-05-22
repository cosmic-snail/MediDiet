import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, vi } from 'vitest';
import App from './App';

describe('App role workbench', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the role workbench and switches roles', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole('heading', { name: 'MediDiet 角色工作台' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '患者工作台' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '营养师' }));
    expect(screen.getByRole('heading', { name: '营养师工作台' })).toBeInTheDocument();
  });

  it('returns completed dietitian review results to the patient workspace', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '模拟等待营养师审核' }));
    expect(screen.getByText('推荐状态：等待营养师审核')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '营养师' }));
    await user.click(screen.getByRole('button', { name: '确认推荐' }));
    expect(screen.getByText('暂无待审核推荐')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '患者' }));
    expect(screen.getByRole('heading', { name: '清蒸鱼套餐' })).toBeInTheDocument();
    expect(screen.getByText(/营养师已确认/)).toBeInTheDocument();
    expect(screen.getByText('推荐状态：已生成推荐')).toBeInTheDocument();
  });

  it('returns direct queue rejections to the patient workspace', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '营养师' }));
    await user.click(screen.getByRole('button', { name: '驳回推荐' }));
    await user.click(screen.getByRole('button', { name: '患者' }));

    expect(screen.getByRole('heading', { name: '需要处理' })).toBeInTheDocument();
    expect(screen.getByText(/营养师未通过/)).toBeInTheDocument();
    expect(screen.getByText('推荐状态：拒绝推荐')).toBeInTheDocument();
  });

  it('requests backend recommendation from the patient workspace', async () => {
    fetchMock
      .mockResolvedValueOnce(okJson({ patients: [], intakeRecordCounts: {}, todayMenuCount: 0, nutritionistReviewCounts: {} }))
      .mockResolvedValueOnce(okJson({ stored: true }))
      .mockResolvedValueOnce(okJson({ patientId: 'demo-patient', intakeRecordCount: 1 }))
      .mockResolvedValueOnce(okJson({ menuItemCount: 1 }))
      .mockResolvedValueOnce(
        okJson({
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
            patient: '来自后端 HTTP 服务的推荐解释',
            clinician: 'clinician',
            llm: { usedFallback: false, fallbackReason: null }
          },
          nutritionistReviews: [],
          traceId: 'trace-http-ui',
          trace: {
            traceId: 'trace-http-ui',
            patientId: 'demo-patient',
            ruleVersion: 'baseline-2026-05-15',
            outcome: 'recommended',
            riskLevel: 'low',
            createdAt: '2026-05-19T08:00:00+00:00',
            safetyEvents: [],
            exclusions: {},
            scores: { 'steamed-fish-set': 42 },
            patientExplanation: '来自后端 HTTP 服务的推荐解释',
            clinicianExplanation: {
              ruleVersion: 'baseline-2026-05-15',
              matchedTags: [{ kind: 'nutrition_tag', value: 'low_sodium' }],
              llmBoundary: 'backend'
            }
          }
        })
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '获取下一餐推荐' }));

    expect(await screen.findByText('来自后端 HTTP 服务的推荐解释')).toBeInTheDocument();
    expect(screen.getByText('trace-http-ui')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/recommendations', expect.objectContaining({ method: 'POST' }));
  });

  it('requests backend recommendation for the active patient', async () => {
    fetchMock
      .mockResolvedValueOnce(okJson({ patients: [], intakeRecordCounts: {}, todayMenuCount: 0, nutritionistReviewCounts: {} }))
      .mockResolvedValueOnce(okJson({ stored: true }))
      .mockResolvedValueOnce(okJson({ patientId: 'demo-patient-ckd', intakeRecordCount: 1 }))
      .mockResolvedValueOnce(okJson({ menuItemCount: 1 }))
      .mockResolvedValueOnce(
        okJson({
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
            patient: '李先生的后端推荐解释',
            clinician: 'clinician',
            llm: { usedFallback: false, fallbackReason: null }
          },
          nutritionistReviews: [],
          traceId: 'trace-http-ckd',
          trace: {
            traceId: 'trace-http-ckd',
            patientId: 'demo-patient-ckd',
            ruleVersion: 'baseline-2026-05-15',
            outcome: 'recommended',
            riskLevel: 'low',
            createdAt: '2026-05-19T08:00:00+00:00',
            safetyEvents: [],
            exclusions: {},
            scores: { 'steamed-fish-set': 42 },
            patientExplanation: '李先生的后端推荐解释',
            clinicianExplanation: {
              ruleVersion: 'baseline-2026-05-15',
              matchedTags: [{ kind: 'nutrition_tag', value: 'low_sodium' }],
              llmBoundary: 'backend'
            }
          }
        })
      );
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText('当前患者'), 'demo-patient-ckd');
    await user.click(screen.getByRole('button', { name: '获取下一餐推荐' }));

    expect(await screen.findByText('李先生的后端推荐解释')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/patients/demo-patient-ckd',
      expect.objectContaining({ method: 'PUT' })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/patients/demo-patient-ckd/intake-records',
      expect.objectContaining({ method: 'POST' })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/recommendations',
      expect.objectContaining({
        body: expect.stringContaining('"patientId":"demo-patient-ckd"'),
        method: 'POST'
      })
    );
  });

  it('shows backend errors without clearing the current recommendation', async () => {
    fetchMock
      .mockResolvedValueOnce(okJson({ patients: [], intakeRecordCounts: {}, todayMenuCount: 0, nutritionistReviewCounts: {} }))
      .mockResolvedValueOnce(okJson({ stored: true }))
      .mockResolvedValueOnce(okJson({ patientId: 'demo-patient', intakeRecordCount: 1 }))
      .mockResolvedValueOnce(okJson({ menuItemCount: 1 }))
      .mockResolvedValueOnce(
        jsonResponse(409, {
          error: { code: 'MENU_NOT_CONFIGURED', message: 'Today menu has not been configured', details: {} }
        })
      );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '获取下一餐推荐' }));

    expect(await screen.findByText(/MENU_NOT_CONFIGURED/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('trace-7c4e3608')).toBeInTheDocument());
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
