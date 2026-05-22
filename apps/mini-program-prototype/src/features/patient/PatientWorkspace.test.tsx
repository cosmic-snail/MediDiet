import type { Dispatch, SetStateAction } from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  createInitialPrototypeState,
  requestRecommendation,
  selectActivePatientIntakeRecords,
  setActivePatient,
  type PrototypeState
} from '../../state';
import { PatientWorkspace } from './PatientWorkspace';

function applyCapturedUpdater(
  onStateChange: ReturnType<typeof vi.fn<[SetStateAction<PrototypeState>], void>>,
  state: PrototypeState
) {
  const updater = onStateChange.mock.calls.at(-1)?.[0];

  expect(typeof updater).toBe('function');

  return (updater as (current: PrototypeState) => PrototypeState)(state);
}

describe('PatientWorkspace', () => {
  it('shows intake, profile confirmation, and recommendation result', () => {
    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('关键风险字段已确认')).toBeInTheDocument();
    expect(screen.getByText('咸汤面')).toBeInTheDocument();
    expect(screen.getByText('清蒸鱼套餐')).toBeInTheDocument();
    expect(screen.getByText('trace-7c4e3608')).toBeInTheDocument();
  });

  it('renders the active patient selector with 王女士 health details', () => {
    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByLabelText('当前患者')).toHaveValue('demo-patient');
    const healthRegion = screen.getByRole('region', { name: '健康资料' });

    expect(within(healthRegion).getByRole('heading', { name: '王女士' })).toBeInTheDocument();
    expect(
      within(healthRegion).getByText('高血压、糖尿病、虾过敏 · 偏好清淡 · 预算 ¥40.00')
    ).toBeInTheDocument();
  });

  it('emits a functional updater when selecting the CKD patient', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn<[SetStateAction<PrototypeState>], void>();
    const state = createInitialPrototypeState();

    render(
      <PatientWorkspace state={state} onStateChange={onStateChange as Dispatch<SetStateAction<PrototypeState>>} />
    );

    await user.selectOptions(screen.getByLabelText('当前患者'), 'demo-patient-ckd');

    const next = applyCapturedUpdater(onStateChange, state);
    expect(next.activePatientId).toBe('demo-patient-ckd');
  });

  it('renders CKD patient details and hides the recommendation result when none exists', () => {
    const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');

    render(<PatientWorkspace state={state} onStateChange={vi.fn()} />);

    expect(screen.getByLabelText('当前患者')).toHaveValue('demo-patient-ckd');
    const healthRegion = screen.getByRole('region', { name: '健康资料' });

    expect(within(healthRegion).getByRole('heading', { name: '李先生' })).toBeInTheDocument();
    expect(
      within(healthRegion).getByText('慢性肾病、高血压、花生过敏 · 偏好清淡 · 预算 ¥35.00')
    ).toBeInTheDocument();
    expect(screen.getByText('白粥配咸菜')).toBeInTheDocument();
    expect(screen.queryByText('推荐结果')).not.toBeInTheDocument();
  });

  it('appends manual intake only to the active CKD patient records', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn<[SetStateAction<PrototypeState>], void>();
    const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');

    render(
      <PatientWorkspace state={state} onStateChange={onStateChange as Dispatch<SetStateAction<PrototypeState>>} />
    );

    await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));

    const next = applyCapturedUpdater(onStateChange, state);
    expect(selectActivePatientIntakeRecords(next).map((record) => record.foodLabel)).toEqual([
      '白粥配咸菜',
      '低糖酸奶'
    ]);
    expect(next.intakeRecordsByPatientId['demo-patient'].map((record) => record.foodLabel)).toEqual(['咸汤面']);
  });

  it('can add a manually corrected intake and request review mode', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));
    await user.click(screen.getByRole('button', { name: '模拟等待营养师审核' }));

    expect(onStateChange).toHaveBeenCalledTimes(2);
  });

  it('passes functional updater callbacks for refusal and review actions', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn<[SetStateAction<PrototypeState>], void>();

    render(
      <PatientWorkspace
        state={createInitialPrototypeState()}
        onStateChange={onStateChange as Dispatch<SetStateAction<PrototypeState>>}
      />
    );

    await user.click(screen.getByRole('button', { name: '模拟拒绝推荐' }));
    await user.click(screen.getByRole('button', { name: '模拟等待营养师审核' }));

    expect(onStateChange.mock.calls).toHaveLength(2);
    expect(onStateChange.mock.calls.every(([updater]) => typeof updater === 'function')).toBe(true);
  });

  it('shows refusal state with a refusal status marker', () => {
    const state = requestRecommendation(createInitialPrototypeState(), 'refused');

    render(<PatientWorkspace state={state} onStateChange={vi.fn()} />);

    expect(screen.getByText('推荐状态：拒绝推荐')).toBeInTheDocument();
    expect(screen.getByText('当前候选餐食不满足安全和营养要求，暂不建议自动推荐。')).toBeInTheDocument();
  });

  it('passes functional updater callbacks for patient actions', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);

    await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));

    expect(typeof onStateChange.mock.calls[0][0]).toBe('function');
  });
});
