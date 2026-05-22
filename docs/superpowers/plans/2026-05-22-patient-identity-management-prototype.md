# Patient Identity Management Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add front-end prototype support for multiple patient identities, current-patient switching, and patient-scoped intake and recommendation state.

**Architecture:** Keep identity management local to the React/Vite prototype. `fixtures.ts` owns demo patient data, `state.ts` owns patient-scoped state transitions and selectors, `PatientWorkspace.tsx` renders the current patient selector and scoped data, and `App.tsx` sends the active patient context to the existing HTTP API client.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, Testing Library, existing `lucide-react` icons.

---

## File Structure

- Modify `apps/mini-program-prototype/src/fixtures.ts`
  - Add `patientProfiles`, `intakeRecordsByPatientId`, and `recommendationsByPatientId`.
  - Preserve `patientProfile` and `intakeRecords` exports as compatibility aliases for existing API adapter tests.
- Modify `apps/mini-program-prototype/src/state.ts`
  - Add `patients`, `activePatientId`, patient-scoped intake records, and patient-scoped recommendations to `PrototypeState`.
  - Add selectors and patient-scoped update functions.
- Modify `apps/mini-program-prototype/src/state.test.ts`
  - Cover initial multi-patient state, switching, scoped intake updates, scoped recommendations, and backend recommendation writes.
- Modify `apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx`
  - Render current patient selector.
  - Replace hard-coded `patientProfile` usage with state selectors.
  - Render current-patient health summary, intake records, and recommendation result.
- Modify `apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx`
  - Cover current-patient selector and patient-scoped UI behavior.
- Modify `apps/mini-program-prototype/src/App.tsx`
  - Seed and request backend recommendation using the active patient profile and active patient intake records.
  - Store backend recommendation under that patient id.
- Modify `apps/mini-program-prototype/src/App.test.tsx`
  - Cover backend recommendation request for a switched patient.
- Modify `apps/mini-program-prototype/src/styles.css`
  - Add small, stable styles for the patient identity row and native select.
- Modify `apps/mini-program-prototype/README.zh.md`
  - Document the new prototype patient identity switch behavior.

---

### Task 1: Patient-Scoped State And Fixtures

**Files:**
- Modify: `apps/mini-program-prototype/src/fixtures.ts`
- Modify: `apps/mini-program-prototype/src/state.ts`
- Test: `apps/mini-program-prototype/src/state.test.ts`

- [ ] **Step 1: Write failing state tests**

Add these imports to `apps/mini-program-prototype/src/state.test.ts`:

```ts
import { recommendedResponse } from './fixtures';
```

Update the existing import from `./state` so it includes the new selectors and state operation:

```ts
import {
  addCorrectedIntake,
  applyBackendRecommendation,
  createInitialPrototypeState,
  requestRecommendation,
  selectActivePatient,
  selectActivePatientIntakeRecords,
  selectActivePatientRecommendation,
  selectWorkbenchSummary,
  setActivePatient,
  submitReviewDecision,
  updateFulfillmentStatus,
  updateMenuItemAvailability
} from './state';
```

Add these tests inside `describe('prototype state machine', () => { ... })`:

```ts
it('initializes multiple patients and defaults to the demo patient', () => {
  const state = createInitialPrototypeState();

  expect(state.patients.map((patient) => patient.patientId)).toEqual(['demo-patient', 'demo-patient-ckd']);
  expect(state.activePatientId).toBe('demo-patient');
  expect(selectActivePatient(state).displayName).toBe('王女士');
  expect(selectActivePatientIntakeRecords(state).map((record) => record.foodLabel)).toEqual(['咸汤面']);
  expect(selectActivePatientRecommendation(state)?.traceId).toBe('trace-7c4e3608');
});

it('switches the active patient and uses that patient for summaries', () => {
  const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');

  expect(state.activePatientId).toBe('demo-patient-ckd');
  expect(selectActivePatient(state).displayName).toBe('李先生');
  expect(selectActivePatientIntakeRecords(state).map((record) => record.foodLabel)).toEqual(['白粥配咸菜']);
  expect(selectActivePatientRecommendation(state)).toBeNull();
  expect(selectWorkbenchSummary(state, 'patient')).toMatchObject({
    primaryCount: 1,
    secondaryCount: 0
  });
});

it('keeps the current patient when switching to an unknown patient id', () => {
  const state = createInitialPrototypeState();
  const next = setActivePatient(state, 'missing-patient');

  expect(next).toBe(state);
  expect(selectActivePatient(next).patientId).toBe('demo-patient');
});

it('adds manually corrected intake records only to the active patient', () => {
  const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');
  const next = addCorrectedIntake(state, '低糖酸奶', 4);

  expect(next.intakeRecordsByPatientId['demo-patient']).toHaveLength(1);
  expect(next.intakeRecordsByPatientId['demo-patient-ckd']).toHaveLength(2);
  expect(next.intakeRecordsByPatientId['demo-patient-ckd'].at(-1)?.foodLabel).toBe('低糖酸奶');
  expect(selectActivePatientIntakeRecords(next).at(-1)?.manuallyCorrected).toBe(true);
});

it('creates simulated recommendation states only for the active patient', () => {
  const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');
  const next = requestRecommendation(state, 'refused');

  expect(next.recommendationsByPatientId['demo-patient']?.traceId).toBe('trace-7c4e3608');
  expect(next.recommendationsByPatientId['demo-patient-ckd']?.outcome).toBe('refused');
  expect(selectActivePatientRecommendation(next)?.outcome).toBe('refused');
});

it('writes backend recommendations to the requested patient id', () => {
  const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');
  const backendRecommendation = {
    ...recommendedResponse,
    traceId: 'trace-http-ckd',
    trace: {
      ...recommendedResponse.trace,
      traceId: 'trace-http-ckd',
      patientId: 'demo-patient-ckd'
    }
  };
  const next = applyBackendRecommendation(state, 'demo-patient-ckd', backendRecommendation);

  expect(next.recommendationsByPatientId['demo-patient']?.traceId).toBe('trace-7c4e3608');
  expect(next.recommendationsByPatientId['demo-patient-ckd']?.traceId).toBe('trace-http-ckd');
  expect(selectActivePatientRecommendation(next)?.traceId).toBe('trace-http-ckd');
});
```

- [ ] **Step 2: Run state tests to verify they fail**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/state.test.ts
```

Expected: FAIL because `applyBackendRecommendation`, `selectActivePatient`, `selectActivePatientIntakeRecords`, `selectActivePatientRecommendation`, `setActivePatient`, `patients`, `activePatientId`, `intakeRecordsByPatientId`, and `recommendationsByPatientId` do not exist yet.

- [ ] **Step 3: Add multi-patient fixture data**

In `apps/mini-program-prototype/src/fixtures.ts`, replace the single-patient export section at the top with this code:

```ts
export const patientProfiles: PatientProfileDto[] = [
  {
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
  },
  {
    patientId: 'demo-patient-ckd',
    displayName: '李先生',
    age: 66,
    heightCm: 168,
    weightKg: 70,
    conditions: ['ckd', 'hypertension'],
    allergens: ['peanut'],
    contraindications: ['high_sodium'],
    tasteTags: ['light'],
    dislikedIngredients: ['organ_meat'],
    maxPriceCents: 3500,
    maxDistanceMeters: 1200,
    keyRiskFieldsConfirmed: true,
    source: 'clinician_entered'
  }
];

export const patientProfile: PatientProfileDto = patientProfiles[0];
```

Replace the existing `export const intakeRecords: IntakeRecordDto[] = [...]` block with this code:

```ts
export const intakeRecordsByPatientId: Record<string, IntakeRecordDto[]> = {
  'demo-patient': [
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
  ],
  'demo-patient-ckd': [
    {
      intakeId: 'intake-breakfast-ckd-001',
      foodLabel: '白粥配咸菜',
      occurredAt: '2026-05-17T07:40:00+08:00',
      mealLabel: 1,
      portion: '一碗',
      nutrients: {
        energyKcal: 310,
        carbsG: 58,
        proteinG: 7,
        fatG: 4,
        sodiumMg: 520,
        sugarG: 2,
        fiberG: 1
      },
      confidence: 0.78,
      source: 'patient_reported',
      manuallyCorrected: true
    }
  ]
};

export const intakeRecords: IntakeRecordDto[] = intakeRecordsByPatientId['demo-patient'];
```

After `recommendedResponse`, add this export:

```ts
export const recommendationsByPatientId: Record<string, RecommendationResponseDto | null> = {
  'demo-patient': recommendedResponse,
  'demo-patient-ckd': null
};
```

- [ ] **Step 4: Implement patient-scoped state**

In `apps/mini-program-prototype/src/state.ts`, update the imports from `./contracts` and `./fixtures`:

```ts
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
```

Replace `PrototypeState` with:

```ts
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
```

Replace `createInitialPrototypeState` with:

```ts
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
```

Add these selectors after `setActiveRole`:

```ts
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
```

Update the patient branch in `selectWorkbenchSummary`:

```ts
  if (role === 'patient') {
    return {
      title: '患者工作台',
      primaryLabel: '今日摄入',
      primaryCount: selectActivePatientIntakeRecords(state).length,
      secondaryLabel: '推荐状态',
      secondaryCount: selectActivePatientRecommendation(state) ? 1 : 0
    };
  }
```

Replace `addCorrectedIntake` with:

```ts
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
```

In `requestRecommendation`, replace each returned `recommendation` update with `recommendationsByPatientId`. Use this full function:

```ts
export function requestRecommendation(state: PrototypeState, mode: 'recommended' | 'refused' | 'review'): PrototypeState {
  const patientId = selectActivePatient(state).patientId;

  if (mode === 'review') {
    const reviewCase = state.reviewCases.find((item) => item.trace.patientId === patientId);
    if (!reviewCase) {
      return {
        ...state,
        recommendationsByPatientId: {
          ...state.recommendationsByPatientId,
          [patientId]: null
        }
      };
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
```

Add `applyBackendRecommendation` before `selectReviewedRecommendationItem`:

```ts
export function applyBackendRecommendation(
  state: PrototypeState,
  patientId: string,
  recommendation: RecommendationResponseDto
): PrototypeState {
  return {
    ...state,
    recommendationsByPatientId: {
      ...state.recommendationsByPatientId,
      [patientId]: recommendation
    }
  };
}
```

Update `submitReviewDecision` to read and write patient-scoped recommendations. Replace:

```ts
  const matchingRecommendation = state.recommendation?.traceId === traceId ? state.recommendation : null;
```

with:

```ts
  const patientId = reviewCase.trace.patientId;
  const existingRecommendation = state.recommendationsByPatientId[patientId] ?? null;
  const matchingRecommendation = existingRecommendation?.traceId === traceId ? existingRecommendation : null;
```

Inside the final returned object in `submitReviewDecision`, replace the top-level `recommendation: { ... }` property with:

```ts
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
```

At the bottom of `state.ts`, add:

```ts
function cloneIntakeRecordsByPatientId(
  recordsByPatientId: Record<string, IntakeRecordDto[]>
): Record<string, IntakeRecordDto[]> {
  return Object.fromEntries(
    Object.entries(recordsByPatientId).map(([patientId, records]) => [patientId, [...records]])
  );
}
```

- [ ] **Step 5: Update existing state tests that reference old top-level fields**

In `apps/mini-program-prototype/src/state.test.ts`, replace old top-level state field assertions:

```ts
expect(selectWorkbenchSummary(state, 'patient').primaryCount).toBe(1);
```

Keep this assertion unchanged because `selectWorkbenchSummary` remains the public API.

Replace:

```ts
expect(next.intakeRecords).toHaveLength(state.intakeRecords.length + 1);
expect(next.intakeRecords.at(-1)?.manuallyCorrected).toBe(true);
```

with:

```ts
expect(selectActivePatientIntakeRecords(next)).toHaveLength(selectActivePatientIntakeRecords(state).length + 1);
expect(selectActivePatientIntakeRecords(next).at(-1)?.manuallyCorrected).toBe(true);
```

Replace:

```ts
expect(requestRecommendation(state, 'recommended').recommendation?.outcome).toBe('recommended');
expect(requestRecommendation(state, 'review').recommendation?.outcome).toBe('human_review_required');
```

with:

```ts
expect(selectActivePatientRecommendation(requestRecommendation(state, 'recommended'))?.outcome).toBe('recommended');
expect(selectActivePatientRecommendation(requestRecommendation(state, 'review'))?.outcome).toBe(
  'human_review_required'
);
```

Replace all remaining `next.recommendation` assertions in this file with `selectActivePatientRecommendation(next)`. For example:

```ts
expect(selectActivePatientRecommendation(next)?.reviewStatus).toBe('completed');
expect(selectActivePatientRecommendation(next)?.traceId).toBe('trace-review-001');
expect(selectActivePatientRecommendation(next)?.outcome).toBe('recommended');
expect(selectActivePatientRecommendation(next)?.recommendedItems[0]?.name).toBe('清蒸鱼套餐');
expect(selectActivePatientRecommendation(next)?.patientExplanation).toContain('营养师已确认');
expect(selectActivePatientRecommendation(next)?.trace.scores).toHaveProperty('steamed-fish-set');
```

For the unknown trace id test, replace:

```ts
expect(next.recommendation).toBe(state.recommendation);
```

with:

```ts
expect(next.recommendationsByPatientId).toBe(state.recommendationsByPatientId);
```

For the empty review queue test, replace:

```ts
const state = { ...createInitialPrototypeState(), recommendation: null, reviewCases: [] };

expect(() => requestRecommendation(state, 'review')).not.toThrow();
expect(requestRecommendation(state, 'review').recommendation).toBeNull();
```

with:

```ts
const state = {
  ...createInitialPrototypeState(),
  recommendationsByPatientId: { 'demo-patient': null },
  reviewCases: []
};

expect(() => requestRecommendation(state, 'review')).not.toThrow();
expect(selectActivePatientRecommendation(requestRecommendation(state, 'review'))).toBeNull();
```

- [ ] **Step 6: Run state tests to verify they pass**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/state.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit state changes**

Run:

```bash
git add apps/mini-program-prototype/src/fixtures.ts apps/mini-program-prototype/src/state.ts apps/mini-program-prototype/src/state.test.ts
git commit -m "feat: add patient-scoped prototype state"
```

Expected: commit succeeds with only the three listed files staged.

---

### Task 2: Patient Workspace Identity Selector

**Files:**
- Modify: `apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx`
- Modify: `apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx`
- Modify: `apps/mini-program-prototype/src/styles.css`

- [ ] **Step 1: Write failing PatientWorkspace tests**

Update imports in `apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx`:

```ts
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  createInitialPrototypeState,
  requestRecommendation,
  selectActivePatientIntakeRecords,
  setActivePatient
} from '../../state';
import { PatientWorkspace } from './PatientWorkspace';
```

Add these tests:

```ts
it('shows the active patient identity selector and scoped health summary', () => {
  render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

  expect(screen.getByLabelText('当前患者')).toHaveValue('demo-patient');
  expect(screen.getByRole('heading', { name: '王女士' })).toBeInTheDocument();
  expect(screen.getByText('高血压、糖尿病、虾过敏 · 偏好清淡 · 预算 ¥40.00')).toBeInTheDocument();
});

it('emits an active patient switch when a different patient is selected', async () => {
  const user = userEvent.setup();
  const onStateChange = vi.fn();

  render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
  await user.selectOptions(screen.getByLabelText('当前患者'), 'demo-patient-ckd');

  expect(onStateChange).toHaveBeenCalledTimes(1);
  expect(typeof onStateChange.mock.calls[0][0]).toBe('function');
  const next = onStateChange.mock.calls[0][0](createInitialPrototypeState());
  expect(next.activePatientId).toBe('demo-patient-ckd');
});

it('renders intake records and no recommendation result for a patient without an initial recommendation', () => {
  const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');

  render(<PatientWorkspace state={state} onStateChange={vi.fn()} />);

  expect(screen.getByLabelText('当前患者')).toHaveValue('demo-patient-ckd');
  expect(screen.getByRole('heading', { name: '李先生' })).toBeInTheDocument();
  expect(screen.getByText('慢性肾病、高血压、花生过敏 · 偏好清淡 · 预算 ¥35.00')).toBeInTheDocument();
  expect(screen.getByText('白粥配咸菜')).toBeInTheDocument();
  expect(screen.queryByText('推荐结果')).not.toBeInTheDocument();
});

it('adds manually corrected intake to the currently selected patient', async () => {
  const user = userEvent.setup();
  const onStateChange = vi.fn();
  const state = setActivePatient(createInitialPrototypeState(), 'demo-patient-ckd');

  render(<PatientWorkspace state={state} onStateChange={onStateChange} />);
  await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));

  const next = onStateChange.mock.calls[0][0](state);
  expect(selectActivePatientIntakeRecords(next).map((record) => record.foodLabel)).toEqual([
    '白粥配咸菜',
    '低糖酸奶'
  ]);
});
```

Update the first existing test to assert within the health section instead of relying on the old hard-coded fixture:

```ts
const healthCard = screen.getByRole('region', { name: '健康资料' });
expect(within(healthCard).getByRole('heading', { name: '王女士' })).toBeInTheDocument();
```

- [ ] **Step 2: Run PatientWorkspace tests to verify they fail**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/features/patient/PatientWorkspace.test.tsx
```

Expected: FAIL because the current component does not render a current-patient selector, still imports `patientProfile`, and still reads old top-level intake and recommendation fields.

- [ ] **Step 3: Implement current-patient rendering**

In `apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx`, replace imports with:

```ts
import type { Dispatch, SetStateAction } from 'react';
import { AlertTriangle, Camera, CheckCircle, Clock3, PlusCircle, UserRound } from 'lucide-react';
import { formatPrice, mealLabelName, outcomeToPatientState } from '../../contracts';
import {
  addCorrectedIntake,
  requestRecommendation,
  selectActivePatient,
  selectActivePatientIntakeRecords,
  selectActivePatientRecommendation,
  setActivePatient,
  type PrototypeState
} from '../../state';
```

At the start of `PatientWorkspace`, replace the old recommendation lookup with:

```ts
  const patient = selectActivePatient(state);
  const intakeRecords = selectActivePatientIntakeRecords(state);
  const recommendation = selectActivePatientRecommendation(state);
```

After the hero panel and service error block, add the current patient selector section:

```tsx
      <section className="card patient-identity-card" aria-label="当前患者身份">
        <div className="card-head">
          <div>
            <p className="eyebrow">当前患者</p>
            <h2>{patient.displayName}</h2>
          </div>
          <UserRound size={20} aria-hidden="true" />
        </div>
        <label className="field-label" htmlFor="active-patient">
          当前患者
        </label>
        <select
          id="active-patient"
          className="patient-select"
          value={patient.patientId}
          onChange={(event) => onStateChange((current) => setActivePatient(current, event.target.value))}
        >
          {state.patients.map((item) => (
            <option key={item.patientId} value={item.patientId}>
              {item.displayName} · {item.age}岁
            </option>
          ))}
        </select>
      </section>
```

Change the health card opening tag to expose a region name for tests:

```tsx
      <section className="card" aria-label="健康资料">
```

Replace the health card body with current patient data:

```tsx
        <div className="card-head">
          <div>
            <p className="eyebrow">健康资料</p>
            <h2>{patient.displayName}</h2>
          </div>
          <span className={patient.keyRiskFieldsConfirmed ? 'status good' : 'status danger'}>
            {patient.keyRiskFieldsConfirmed ? '关键风险字段已确认' : '关键风险字段待确认'}
          </span>
        </div>
        <p className="muted">{formatPatientSummary(patient)}</p>
```

Replace `state.intakeRecords.map` with:

```tsx
          {intakeRecords.map((record) => (
```

After the intake list, add this empty state before the manual intake button:

```tsx
        {intakeRecords.length === 0 && <p className="muted">暂无今日摄入记录。</p>}
```

At the bottom of the file, add these helpers:

```ts
function formatPatientSummary(patient: ReturnType<typeof selectActivePatient>): string {
  const conditions = patient.conditions.map(displayConcept);
  const allergens = patient.allergens.map((value) => `${displayConcept(value)}过敏`);
  const risks = [...conditions, ...allergens];
  const riskText = risks.length > 0 ? risks.join('、') : '暂无慢病或过敏标记';
  const tasteText = patient.tasteTags.length > 0 ? patient.tasteTags.map(displayConcept).join('、') : '未设置';

  return `${riskText} · 偏好${tasteText} · 预算 ${formatPrice(patient.maxPriceCents)}`;
}

function displayConcept(value: string): string {
  return (
    {
      hypertension: '高血压',
      diabetes: '糖尿病',
      ckd: '慢性肾病',
      gout: '痛风',
      shrimp: '虾',
      peanut: '花生',
      high_sodium: '高钠',
      light: '清淡',
      savory: '咸鲜',
      cilantro: '香菜',
      organ_meat: '动物内脏'
    }[value] ?? value.replaceAll('_', ' ')
  );
}
```

- [ ] **Step 4: Add patient identity styles**

Append these styles to `apps/mini-program-prototype/src/styles.css` near the existing form/button styles:

```css
.patient-identity-card {
  display: grid;
  gap: 10px;
}

.field-label {
  color: #526071;
  font-size: 13px;
}

.patient-select {
  width: 100%;
  min-height: 42px;
  border: 1px solid #d6dde8;
  border-radius: 8px;
  background: #ffffff;
  color: #172033;
  padding: 0 12px;
}
```

- [ ] **Step 5: Run PatientWorkspace tests to verify they pass**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/features/patient/PatientWorkspace.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit PatientWorkspace changes**

Run:

```bash
git add apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx apps/mini-program-prototype/src/styles.css
git commit -m "feat: add patient identity selector"
```

Expected: commit succeeds with only the three listed files staged.

---

### Task 3: Active Patient Backend Recommendation Flow

**Files:**
- Modify: `apps/mini-program-prototype/src/App.tsx`
- Modify: `apps/mini-program-prototype/src/App.test.tsx`

- [ ] **Step 1: Write failing App test for switched-patient backend requests**

Add this test to `apps/mini-program-prototype/src/App.test.tsx` after the existing backend recommendation test:

```ts
it('requests backend recommendation for the currently selected patient', async () => {
  fetchMock
    .mockResolvedValueOnce(okJson({ patients: [], intakeRecordCounts: {}, todayMenuCount: 0, nutritionistReviewCounts: {} }))
    .mockResolvedValueOnce(okJson({ stored: true }))
    .mockResolvedValueOnce(okJson({ patientId: 'demo-patient-ckd', intakeRecordCount: 1 }))
    .mockResolvedValueOnce(okJson({ menuItemCount: 1 }))
    .mockResolvedValueOnce(
      okJson({
        outcome: 'recommended',
        recommendedItems: [],
        explanation: {
          patient: '李先生的后端推荐解释',
          clinician: 'clinician',
          llm: { usedFallback: false, fallbackReason: null }
        },
        nutritionistReviews: [],
        traceId: 'trace-http-ckd-ui',
        trace: {
          traceId: 'trace-http-ckd-ui',
          patientId: 'demo-patient-ckd',
          ruleVersion: 'baseline-2026-05-15',
          outcome: 'recommended',
          riskLevel: 'low',
          createdAt: '2026-05-19T08:00:00+00:00',
          safetyEvents: [],
          exclusions: {},
          scores: {},
          patientExplanation: '李先生的后端推荐解释',
          clinicianExplanation: {
            ruleVersion: 'baseline-2026-05-15',
            matchedTags: [],
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
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    '/api/patients/demo-patient-ckd',
    expect.objectContaining({ method: 'PUT' })
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    '/api/patients/demo-patient-ckd/intake-records',
    expect.objectContaining({ method: 'POST' })
  );
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/recommendations',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ patientId: 'demo-patient-ckd', mealLabel: 3, temporaryTasteTags: [], debug: true })
    })
  );
});
```

Update the direct queue rejection test so it still checks the active patient:

```ts
expect(screen.getByLabelText('当前患者')).toHaveValue('demo-patient');
```

- [ ] **Step 2: Run App tests to verify they fail**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/App.test.tsx
```

Expected: FAIL because `App.tsx` still imports global `patientProfile` and `intakeRecords`, and still writes the backend recommendation to the old top-level state shape.

- [ ] **Step 3: Implement active-patient backend flow**

In `apps/mini-program-prototype/src/App.tsx`, remove this import:

```ts
import { intakeRecords, menuItems, patientProfile } from './fixtures';
```

Replace the `./state` import with:

```ts
import {
  applyBackendRecommendation,
  createInitialPrototypeState,
  selectActivePatient,
  selectActivePatientIntakeRecords,
  selectWorkbenchSummary,
  setActiveRole
} from './state';
```

In `handleBackendRecommendationRequest`, add current-patient selectors before the `try` block:

```ts
    const activePatient = selectActivePatient(state);
    const activePatientIntakeRecords = selectActivePatientIntakeRecords(state);
```

Replace the body of the `try` block with:

```ts
      await medidietApi.seedDemoData({
        patientProfile: activePatient,
        intakeRecords: activePatientIntakeRecords,
        menuItems: state.menuItems
      });
      const recommendation = await medidietApi.requestRecommendation({
        patientId: activePatient.patientId,
        mealLabel: 3
      });
      setState((current) => applyBackendRecommendation(current, activePatient.patientId, recommendation));
```

- [ ] **Step 4: Run App tests to verify they pass**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/App.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit App backend flow changes**

Run:

```bash
git add apps/mini-program-prototype/src/App.tsx apps/mini-program-prototype/src/App.test.tsx
git commit -m "feat: request recommendations for active patient"
```

Expected: commit succeeds with only the two listed files staged.

---

### Task 4: Documentation And Full Verification

**Files:**
- Modify: `apps/mini-program-prototype/README.zh.md`

- [ ] **Step 1: Update prototype README**

In `apps/mini-program-prototype/README.zh.md`, replace section `4.2 查看健康资料` with:

```md
### 4.2 切换患者身份与查看健康资料

患者工作台会展示当前患者身份，并提供患者切换控件。当前原型内置两个演示患者，用于验证同一个前端原型中不同患者资料、摄入记录和推荐结果不会串台。

切换患者后，以下内容会同步更新：

- 今日概览中的摄入数量和推荐状态。
- 健康资料卡片中的慢病、过敏原、口味偏好和预算范围。
- 今日摄入列表。
- 推荐结果。

健康资料卡片展示患者关键风险信息，例如：

- 高血压。
- 糖尿病。
- 慢性肾病。
- 过敏原。
- 口味偏好。
- 关键风险字段是否已确认。

后续对接真实接口时，这部分应来自登录后的患者绑定关系和 `PatientProfile`。当前原型只做本地身份切换，不实现真实登录、认证、授权或家属绑定。
```

In section `4.4 查看推荐结果`, replace:

```md
当前点击“获取下一餐推荐”会先读取 `GET /debug/state`，再把演示患者、必要的摄入记录和推荐候选菜单写入后端内存服务，最后调用 `POST /recommendations` 获取真实推荐结果。
```

with:

```md
当前点击“获取下一餐推荐”会先读取 `GET /debug/state`，再把当前患者、当前患者的摄入记录和推荐候选菜单写入后端内存服务，最后调用 `POST /recommendations` 获取真实推荐结果。
```

- [ ] **Step 2: Run the full front-end test suite**

Run:

```bash
cd apps/mini-program-prototype
npm run test
```

Expected: PASS for all front-end tests.

- [ ] **Step 3: Run the front-end build**

Run:

```bash
cd apps/mini-program-prototype
npm run build
```

Expected: PASS. TypeScript must report no errors.

- [ ] **Step 4: Commit docs and verification-ready state**

Run:

```bash
git add apps/mini-program-prototype/README.zh.md
git commit -m "docs: describe patient identity switching"
```

Expected: commit succeeds with only the README staged.

- [ ] **Step 5: Inspect final git status**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated files may remain dirty. The implementation files from this plan should be committed.

---

## Self-Review

Spec coverage:

- Multiple patient profiles: Task 1 updates `fixtures.ts` and tests two patient ids.
- Current patient selector: Task 2 adds selector UI and tests switching.
- Scoped health summary: Task 2 renders current patient conditions, allergens, preferences, and budget.
- Scoped intake records: Task 1 changes state; Task 2 tests visible intake switching.
- Scoped recommendations: Task 1 changes state and tests simulated and backend recommendation writes.
- Active-patient backend request: Task 3 tests and implements current patient seeding and recommendation calls.
- No backend API expansion: Task 3 continues to use the existing API client.
- Existing dietitian and catering flows: Task 1 updates `submitReviewDecision`; Task 3 runs `App.test.tsx`, which covers dietitian review returning to patient.
- Documentation: Task 4 updates the prototype README.

Placeholder scan:

- The plan contains no unresolved placeholder markers.
- Each test and implementation step includes concrete code or exact commands.

Type consistency:

- State fields are consistently named `patients`, `activePatientId`, `intakeRecordsByPatientId`, and `recommendationsByPatientId`.
- The write helper is consistently named `applyBackendRecommendation(state, patientId, recommendation)`.
- Selectors are consistently named `selectActivePatient`, `selectActivePatientIntakeRecords`, and `selectActivePatientRecommendation`.

Implementation note:

- The review-mode recommendation lookup intentionally does not fall back to another patient's review case. If no review case matches the active patient, the active patient's recommendation remains `null`; this avoids cross-patient trace leakage.
