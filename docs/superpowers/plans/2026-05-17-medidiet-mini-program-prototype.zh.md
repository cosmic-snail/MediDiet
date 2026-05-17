# MediDiet Mini-Program Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first interactive prototype for the confirmed MediDiet three-role WeChat mini-program design, using mock data and contracts aligned with the existing recommendation engine.

**Architecture:** Add a standalone Vite + React + TypeScript prototype under `apps/mini-program-prototype`. Keep the prototype service-free: typed DTOs mirror the Python engine API, fixture data simulates `PatientProfile`, `IntakeRecord`, `MenuItem`, `RecommendationResult`, and `RecommendationTrace`, and a small state reducer drives role switching, patient recommendation states, review decisions, menu annotation, and fulfillment status. The UI is split by role so it can later be ported to a real mini-program framework or wired to HTTP APIs.

**Tech Stack:** Node.js, Vite, React, TypeScript, Vitest, Testing Library, jsdom, lucide-react, CSS modules via plain CSS.

---

## Scope Check

This plan implements the interactive prototype requested by the approved frontend spec:

- Spec: `docs/superpowers/specs/2026-05-17-medidiet-mini-program-frontend-design.zh.md`
- Output: a runnable browser prototype with mobile-sized layouts and deterministic mock behavior.
- Not included: real WeChat Mini Program build tooling, real HTTP API server, real image recognition, real payment/order flow, HIS/EMR integration, rule management backend.

The implementation should not change the existing Python recommendation engine. It should only consume its documented contract shape.

## File Structure

Create a new standalone frontend prototype:

- `apps/mini-program-prototype/package.json` - app scripts and dependencies.
- `apps/mini-program-prototype/index.html` - Vite entry HTML.
- `apps/mini-program-prototype/tsconfig.json` - TypeScript app config.
- `apps/mini-program-prototype/tsconfig.node.json` - TypeScript config for Vite config.
- `apps/mini-program-prototype/vite.config.ts` - Vite + Vitest config.
- `apps/mini-program-prototype/src/main.tsx` - React entrypoint.
- `apps/mini-program-prototype/src/App.tsx` - top-level state wiring and layout.
- `apps/mini-program-prototype/src/contracts.ts` - frontend DTOs mirroring recommendation engine concepts.
- `apps/mini-program-prototype/src/fixtures.ts` - deterministic patient, intake, menu, trace, review, and fulfillment fixtures.
- `apps/mini-program-prototype/src/state.ts` - pure state transitions for prototype interactions.
- `apps/mini-program-prototype/src/components/RoleSwitcher.tsx` - role selector.
- `apps/mini-program-prototype/src/components/WorkbenchCard.tsx` - reusable workbench metric/action card.
- `apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx` - patient workflow UI.
- `apps/mini-program-prototype/src/features/review/DietitianWorkspace.tsx` - review queue and trace UI.
- `apps/mini-program-prototype/src/features/catering/CateringWorkspace.tsx` - menu annotation and fulfillment UI.
- `apps/mini-program-prototype/src/styles.css` - mobile-first visual system.
- `apps/mini-program-prototype/src/test/setup.ts` - Vitest DOM setup.
- `apps/mini-program-prototype/src/**/*.test.ts` and `src/**/*.test.tsx` - unit and interaction tests.
- `apps/mini-program-prototype/README.md` - local runbook and API-contract notes.

## Commands

Run from `apps/mini-program-prototype` unless noted:

- Install dependencies: `npm install`
- Run tests: `npm run test`
- Run build: `npm run build`
- Run dev server: `npm run dev -- --host 127.0.0.1`

---

### Task 1: Scaffold the Prototype App

**Files:**
- Create: `apps/mini-program-prototype/package.json`
- Create: `apps/mini-program-prototype/index.html`
- Create: `apps/mini-program-prototype/tsconfig.json`
- Create: `apps/mini-program-prototype/tsconfig.node.json`
- Create: `apps/mini-program-prototype/vite.config.ts`
- Create: `apps/mini-program-prototype/src/main.tsx`
- Create: `apps/mini-program-prototype/src/App.tsx`
- Create: `apps/mini-program-prototype/src/styles.css`
- Create: `apps/mini-program-prototype/src/test/setup.ts`
- Create: `apps/mini-program-prototype/src/App.test.tsx`

- [ ] **Step 1: Create the package and tooling files**

Create `apps/mini-program-prototype/package.json`:

```json
{
  "name": "medidiet-mini-program-prototype",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "vite": "^6.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "jsdom": "^25.0.1",
    "typescript": "^5.7.2",
    "vitest": "^2.1.8"
  }
}
```

Create `apps/mini-program-prototype/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MediDiet Mini Program Prototype</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `apps/mini-program-prototype/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `apps/mini-program-prototype/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

Create `apps/mini-program-prototype/vite.config.ts`:

```ts
/// <reference types="vitest" />

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true
  }
});
```

- [ ] **Step 2: Create the initial failing smoke test**

Create `apps/mini-program-prototype/src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import App from './App';

describe('App scaffold', () => {
  it('renders the MediDiet prototype shell', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'MediDiet 角色工作台' })).toBeInTheDocument();
    expect(screen.getByText('推荐引擎微信小程序原型')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the smoke test and verify it fails before implementation**

Run:

```bash
cd apps/mini-program-prototype
npm install
npm run test -- src/App.test.tsx
```

Expected: FAIL with an import error for `./App` or missing DOM setup, because the app files have not been created yet.

- [ ] **Step 4: Add the minimal React app shell**

Create `apps/mini-program-prototype/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

Create `apps/mini-program-prototype/src/App.tsx`:

```tsx
import './styles.css';

export default function App() {
  return (
    <main className="app-shell">
      <section className="phone-frame">
        <p className="eyebrow">推荐引擎微信小程序原型</p>
        <h1>MediDiet 角色工作台</h1>
        <p className="lede">患者、营养师、配餐管理在同一小程序内按角色权限工作。</p>
      </section>
    </main>
  );
}
```

Create `apps/mini-program-prototype/src/main.tsx`:

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `apps/mini-program-prototype/src/styles.css`:

```css
:root {
  color: #172033;
  background: #e9edf2;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
input,
select,
textarea {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  padding: 24px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.phone-frame {
  width: min(100%, 430px);
  min-height: 760px;
  background: #f8fafc;
  border: 1px solid #d6dde8;
  border-radius: 28px;
  box-shadow: 0 24px 80px rgba(24, 35, 55, 0.18);
  padding: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #526071;
  font-size: 13px;
}

h1 {
  margin: 0 0 10px;
  font-size: 26px;
  letter-spacing: 0;
}

.lede {
  margin: 0;
  color: #526071;
  line-height: 1.6;
}
```

- [ ] **Step 5: Run smoke test and build**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/App.test.tsx
npm run build
```

Expected:

- PASS for `renders the MediDiet prototype shell`.
- Build finishes with Vite output in `dist/`.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype
git commit -m "feat: scaffold mini-program prototype"
```

---

### Task 2: Add Typed API Contracts and Fixture Data

**Files:**
- Create: `apps/mini-program-prototype/src/contracts.ts`
- Create: `apps/mini-program-prototype/src/contracts.test.ts`
- Create: `apps/mini-program-prototype/src/fixtures.ts`
- Create: `apps/mini-program-prototype/src/fixtures.test.ts`

- [ ] **Step 1: Write failing contract tests**

Create `apps/mini-program-prototype/src/contracts.test.ts`:

```ts
import { mealLabelName, outcomeToPatientState, riskPriority } from './contracts';

describe('frontend recommendation contracts', () => {
  it('maps numeric MealLabel values to patient-facing names', () => {
    expect(mealLabelName(1)).toBe('早餐');
    expect(mealLabelName(2)).toBe('午餐');
    expect(mealLabelName(3)).toBe('晚餐');
    expect(mealLabelName(4)).toBe('加餐');
  });

  it('maps recommendation outcomes to stable UI states', () => {
    expect(outcomeToPatientState('recommended')).toBe('showRecommendation');
    expect(outcomeToPatientState('refused')).toBe('showRefusal');
    expect(outcomeToPatientState('human_review_required')).toBe('showReviewWait');
  });

  it('orders review queue by risk priority', () => {
    expect(riskPriority('high')).toBeGreaterThan(riskPriority('medium'));
    expect(riskPriority('medium')).toBeGreaterThan(riskPriority('low'));
  });
});
```

- [ ] **Step 2: Implement frontend contracts**

Create `apps/mini-program-prototype/src/contracts.ts`:

```ts
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
```

- [ ] **Step 3: Run contract tests**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/contracts.test.ts
```

Expected: PASS for all three contract tests.

- [ ] **Step 4: Add deterministic fixture data**

Create `apps/mini-program-prototype/src/fixtures.ts`:

```ts
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
```

- [ ] **Step 5: Write and run fixture tests**

Create `apps/mini-program-prototype/src/fixtures.test.ts`:

```ts
import { intakeRecords, menuItems, recommendedResponse, reviewCases } from './fixtures';

describe('prototype fixtures', () => {
  it('contains a recommendation with trace id and patient explanation', () => {
    expect(recommendedResponse.traceId).toBe('trace-7c4e3608');
    expect(recommendedResponse.patientExplanation).toContain('低钠');
  });

  it('contains menu items that exercise available, low-confidence, and unavailable states', () => {
    expect(menuItems.some((item) => item.available)).toBe(true);
    expect(menuItems.some((item) => item.nutritionConfidence < 0.7)).toBe(true);
    expect(menuItems.some((item) => !item.available)).toBe(true);
  });

  it('contains intake records and review cases tied to recommendation workflow', () => {
    expect(intakeRecords[0].mealLabel).toBe(2);
    expect(reviewCases[0].trace.outcome).toBe('human_review_required');
  });
});
```

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/contracts.test.ts src/fixtures.test.ts
```

Expected: PASS for contract and fixture tests.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype/src/contracts.ts apps/mini-program-prototype/src/contracts.test.ts apps/mini-program-prototype/src/fixtures.ts apps/mini-program-prototype/src/fixtures.test.ts
git commit -m "feat: add frontend recommendation contracts"
```

---

### Task 3: Add the Prototype State Machine

**Files:**
- Create: `apps/mini-program-prototype/src/state.ts`
- Create: `apps/mini-program-prototype/src/state.test.ts`

- [ ] **Step 1: Write failing state-machine tests**

Create `apps/mini-program-prototype/src/state.test.ts`:

```ts
import {
  addCorrectedIntake,
  createInitialPrototypeState,
  requestRecommendation,
  selectWorkbenchSummary,
  submitReviewDecision,
  updateFulfillmentStatus,
  updateMenuItemAvailability
} from './state';

describe('prototype state machine', () => {
  it('summarizes workbench counts by role', () => {
    const state = createInitialPrototypeState();

    expect(selectWorkbenchSummary(state, 'patient').primaryCount).toBe(1);
    expect(selectWorkbenchSummary(state, 'dietitian').primaryCount).toBe(1);
    expect(selectWorkbenchSummary(state, 'catering').secondaryCount).toBeGreaterThan(0);
  });

  it('adds manually corrected intake records', () => {
    const state = createInitialPrototypeState();
    const next = addCorrectedIntake(state, '低糖酸奶', 4);

    expect(next.intakeRecords).toHaveLength(state.intakeRecords.length + 1);
    expect(next.intakeRecords.at(-1)?.manuallyCorrected).toBe(true);
  });

  it('creates recommended and review-required recommendation states', () => {
    const state = createInitialPrototypeState();

    expect(requestRecommendation(state, 'recommended').recommendation?.outcome).toBe('recommended');
    expect(requestRecommendation(state, 'review').recommendation?.outcome).toBe('human_review_required');
  });

  it('writes review decisions back to queue and recommendation', () => {
    const state = createInitialPrototypeState();
    const next = submitReviewDecision(state, 'trace-review-001', 'approve');

    expect(next.reviewCases[0].status).toBe('approved');
    expect(next.recommendation?.reviewStatus).toBe('completed');
  });

  it('updates menu availability and fulfillment status', () => {
    const state = createInitialPrototypeState();

    expect(updateMenuItemAvailability(state, 'steamed-fish-set', false).menuItems[0].available).toBe(false);
    expect(updateFulfillmentStatus(state, 'fulfillment-001', 'prepared').fulfillments[0].status).toBe('prepared');
  });
});
```

- [ ] **Step 2: Implement the pure state transitions**

Create `apps/mini-program-prototype/src/state.ts`:

```ts
import type {
  FulfillmentDto,
  FulfillmentStatus,
  IntakeRecordDto,
  MenuItemDto,
  MealLabel,
  RecommendationResponseDto,
  ReviewCaseDto,
  ReviewDecision,
  Role
} from './contracts';
import { fulfillments, intakeRecords, menuItems, recommendedResponse, reviewCases } from './fixtures';

export interface PrototypeState {
  activeRole: Role;
  intakeRecords: IntakeRecordDto[];
  menuItems: MenuItemDto[];
  recommendation: RecommendationResponseDto | null;
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
    intakeRecords: [...intakeRecords],
    menuItems: [...menuItems],
    recommendation: recommendedResponse,
    reviewCases: [...reviewCases],
    fulfillments: [...fulfillments]
  };
}

export function setActiveRole(state: PrototypeState, activeRole: Role): PrototypeState {
  return { ...state, activeRole };
}

export function selectWorkbenchSummary(state: PrototypeState, role: Role): WorkbenchSummary {
  if (role === 'patient') {
    return {
      title: '患者工作台',
      primaryLabel: '今日摄入',
      primaryCount: state.intakeRecords.length,
      secondaryLabel: '推荐状态',
      secondaryCount: state.recommendation ? 1 : 0
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
  const nextRecord: IntakeRecordDto = {
    intakeId: `manual-${state.intakeRecords.length + 1}`,
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

  return { ...state, intakeRecords: [...state.intakeRecords, nextRecord] };
}

export function requestRecommendation(state: PrototypeState, mode: 'recommended' | 'refused' | 'review'): PrototypeState {
  if (mode === 'review') {
    const reviewCase = state.reviewCases[0];
    return {
      ...state,
      recommendation: {
        outcome: 'human_review_required',
        riskLevel: reviewCase.riskLevel,
        traceId: reviewCase.traceId,
        recommendedItems: [],
        patientExplanation: reviewCase.trace.patientExplanation,
        reviewStatus: 'pending',
        trace: reviewCase.trace
      }
    };
  }

  if (mode === 'refused') {
    return {
      ...state,
      recommendation: {
        ...recommendedResponse,
        outcome: 'refused',
        riskLevel: 'high',
        recommendedItems: [],
        patientExplanation: '当前候选餐食不满足安全和营养要求，暂不建议自动推荐。',
        reviewStatus: null,
        trace: {
          ...recommendedResponse.trace,
          outcome: 'refused',
          riskLevel: 'high',
          patientExplanation: '当前候选餐食不满足安全和营养要求，暂不建议自动推荐。'
        }
      }
    };
  }

  return { ...state, recommendation: recommendedResponse };
}

export function submitReviewDecision(
  state: PrototypeState,
  traceId: string,
  decision: ReviewDecision
): PrototypeState {
  const status: ReviewCaseDto['status'] =
    decision === 'approve' ? 'approved' : decision === 'modify' ? 'modified' : 'rejected';
  return {
    ...state,
    recommendation: state.recommendation
      ? {
          ...state.recommendation,
          reviewStatus: 'completed',
          outcome: decision === 'reject' ? 'refused' : 'recommended'
        }
      : state.recommendation,
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
```

- [ ] **Step 3: Run state-machine tests**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/state.test.ts
```

Expected: PASS for all state-machine tests.

- [ ] **Step 4: Commit**

Run:

```bash
git add apps/mini-program-prototype/src/state.ts apps/mini-program-prototype/src/state.test.ts
git commit -m "feat: add prototype recommendation state machine"
```

---

### Task 4: Build the Role Workbench Shell

**Files:**
- Create: `apps/mini-program-prototype/src/components/RoleSwitcher.tsx`
- Create: `apps/mini-program-prototype/src/components/RoleSwitcher.test.tsx`
- Create: `apps/mini-program-prototype/src/components/WorkbenchCard.tsx`
- Modify: `apps/mini-program-prototype/src/App.tsx`
- Modify: `apps/mini-program-prototype/src/styles.css`
- Modify: `apps/mini-program-prototype/src/App.test.tsx`

- [ ] **Step 1: Write role-switcher tests**

Create `apps/mini-program-prototype/src/components/RoleSwitcher.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RoleSwitcher } from './RoleSwitcher';

describe('RoleSwitcher', () => {
  it('renders all role options and emits changes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<RoleSwitcher activeRole="patient" onChange={onChange} />);
    await user.click(screen.getByRole('button', { name: '营养师' }));

    expect(screen.getByRole('button', { name: '患者' })).toHaveAttribute('aria-pressed', 'true');
    expect(onChange).toHaveBeenCalledWith('dietitian');
  });
});
```

- [ ] **Step 2: Implement role switcher and reusable workbench card**

Create `apps/mini-program-prototype/src/components/RoleSwitcher.tsx`:

```tsx
import { ChefHat, ShieldCheck, UserRound } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Role } from '../contracts';

interface RoleSwitcherProps {
  activeRole: Role;
  onChange: (role: Role) => void;
}

const roles: Array<{ role: Role; label: string; Icon: LucideIcon }> = [
  { role: 'patient', label: '患者', Icon: UserRound },
  { role: 'dietitian', label: '营养师', Icon: ShieldCheck },
  { role: 'catering', label: '配餐', Icon: ChefHat }
];

export function RoleSwitcher({ activeRole, onChange }: RoleSwitcherProps) {
  return (
    <div className="role-switcher" aria-label="角色切换">
      {roles.map(({ role, label, Icon }) => (
        <button
          className="role-button"
          key={role}
          type="button"
          aria-pressed={activeRole === role}
          onClick={() => onChange(role)}
        >
          <Icon aria-hidden="true" size={16} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
```

Create `apps/mini-program-prototype/src/components/WorkbenchCard.tsx`:

```tsx
import type { ReactNode } from 'react';

interface WorkbenchCardProps {
  label: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

export function WorkbenchCard({ label, title, children, action }: WorkbenchCardProps) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <p className="eyebrow">{label}</p>
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      <div>{children}</div>
    </section>
  );
}
```

- [ ] **Step 3: Replace `App.tsx` with the role workbench shell**

Replace `apps/mini-program-prototype/src/App.tsx`:

```tsx
import { useMemo, useState } from 'react';
import './styles.css';
import { RoleSwitcher } from './components/RoleSwitcher';
import { WorkbenchCard } from './components/WorkbenchCard';
import type { Role } from './contracts';
import { createInitialPrototypeState, selectWorkbenchSummary, setActiveRole } from './state';

export default function App() {
  const [state, setState] = useState(createInitialPrototypeState);
  const summary = useMemo(() => selectWorkbenchSummary(state, state.activeRole), [state]);

  function handleRoleChange(role: Role) {
    setState((current) => setActiveRole(current, role));
  }

  return (
    <main className="app-shell">
      <section className="phone-frame">
        <header className="top-bar">
          <div>
            <p className="eyebrow">推荐引擎微信小程序原型</p>
            <h1>MediDiet 角色工作台</h1>
          </div>
        </header>

        <RoleSwitcher activeRole={state.activeRole} onChange={handleRoleChange} />

        <WorkbenchCard label="今日概览" title={summary.title}>
          <div className="metric-grid">
            <div className="metric">
              <span>{summary.primaryCount}</span>
              <p>{summary.primaryLabel}</p>
            </div>
            <div className="metric">
              <span>{summary.secondaryCount}</span>
              <p>{summary.secondaryLabel}</p>
            </div>
          </div>
        </WorkbenchCard>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Extend styles for the role shell**

Append to `apps/mini-program-prototype/src/styles.css`:

```css
.top-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.role-switcher {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 4px;
  border: 1px solid #d6dde8;
  border-radius: 14px;
  background: #eef2f7;
  margin-bottom: 16px;
}

.role-button {
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #526071;
  padding: 9px 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
}

.role-button[aria-pressed="true"] {
  background: #ffffff;
  color: #172033;
  box-shadow: 0 6px 18px rgba(24, 35, 55, 0.08);
}

.card {
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 14px;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.card h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric {
  border-radius: 8px;
  background: #f4f7fb;
  padding: 12px;
}

.metric span {
  display: block;
  font-size: 26px;
  font-weight: 700;
}

.metric p {
  margin: 4px 0 0;
  color: #526071;
}
```

- [ ] **Step 5: Update and run app tests**

Replace `apps/mini-program-prototype/src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

describe('App role workbench', () => {
  it('renders the role workbench and switches roles', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole('heading', { name: 'MediDiet 角色工作台' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '患者工作台' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '营养师' }));
    expect(screen.getByRole('heading', { name: '营养师工作台' })).toBeInTheDocument();
  });
});
```

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/App.test.tsx src/components/RoleSwitcher.test.tsx
```

Expected: PASS for app shell and role switcher tests.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype/src
git commit -m "feat: add role workbench shell"
```

---

### Task 5: Implement the Patient Workspace

**Files:**
- Create: `apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx`
- Create: `apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx`
- Modify: `apps/mini-program-prototype/src/App.tsx`
- Modify: `apps/mini-program-prototype/src/styles.css`

- [ ] **Step 1: Write failing patient workspace tests**

Create `apps/mini-program-prototype/src/features/patient/PatientWorkspace.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createInitialPrototypeState } from '../../state';
import { PatientWorkspace } from './PatientWorkspace';

describe('PatientWorkspace', () => {
  it('shows intake, profile confirmation, and recommendation result', () => {
    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('关键风险字段已确认')).toBeInTheDocument();
    expect(screen.getByText('咸汤面')).toBeInTheDocument();
    expect(screen.getByText('清蒸鱼套餐')).toBeInTheDocument();
    expect(screen.getByText('trace-7c4e3608')).toBeInTheDocument();
  });

  it('can add a manually corrected intake and request review mode', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<PatientWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '手动补录低糖酸奶' }));
    await user.click(screen.getByRole('button', { name: '模拟等待营养师审核' }));

    expect(onStateChange).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Implement the patient workspace**

Create `apps/mini-program-prototype/src/features/patient/PatientWorkspace.tsx`:

```tsx
import { AlertTriangle, Camera, CheckCircle, Clock3, PlusCircle } from 'lucide-react';
import { formatPrice, mealLabelName, outcomeToPatientState } from '../../contracts';
import { patientProfile } from '../../fixtures';
import {
  addCorrectedIntake,
  requestRecommendation,
  type PrototypeState
} from '../../state';

interface PatientWorkspaceProps {
  state: PrototypeState;
  onStateChange: (state: PrototypeState) => void;
}

export function PatientWorkspace({ state, onStateChange }: PatientWorkspaceProps) {
  const recommendation = state.recommendation;
  const patientState = recommendation ? outcomeToPatientState(recommendation.outcome) : null;
  const recommendedItem = recommendation?.recommendedItems[0];

  return (
    <div className="workspace-stack">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">晚餐前</p>
          <h2>今晚建议清淡控主食</h2>
          <p>午餐钠摄入偏高，晚餐推荐会优先低钠、控糖和足量蛋白。</p>
        </div>
        <button
          className="primary-button"
          type="button"
          onClick={() => onStateChange(requestRecommendation(state, 'recommended'))}
        >
          <CheckCircle size={18} aria-hidden="true" />
          获取下一餐推荐
        </button>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">健康资料</p>
            <h2>{patientProfile.displayName}</h2>
          </div>
          <span className="status good">关键风险字段已确认</span>
        </div>
        <p className="muted">高血压、糖尿病、虾过敏 · 偏好清淡 · 预算 {formatPrice(patientProfile.maxPriceCents)}</p>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">今日摄入</p>
            <h2>拍照优先，手动兜底</h2>
          </div>
          <Camera size={20} aria-hidden="true" />
        </div>
        <div className="list">
          {state.intakeRecords.map((record) => (
            <div className="list-row" key={record.intakeId}>
              <div>
                <strong>{record.foodLabel}</strong>
                <p>{mealLabelName(record.mealLabel)} · {record.portion} · 置信度 {Math.round(record.confidence * 100)}%</p>
              </div>
              <span>{record.nutrients.sodiumMg}mg 钠</span>
            </div>
          ))}
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => onStateChange(addCorrectedIntake(state, '低糖酸奶', 4))}
        >
          <PlusCircle size={18} aria-hidden="true" />
          手动补录低糖酸奶
        </button>
      </section>

      {recommendation && (
        <section className="card">
          <div className="card-head">
            <div>
              <p className="eyebrow">推荐结果</p>
              <h2>{patientState === 'showRecommendation' ? recommendedItem?.name : '需要处理'}</h2>
            </div>
            {patientState === 'showReviewWait' ? <Clock3 size={20} aria-hidden="true" /> : <CheckCircle size={20} aria-hidden="true" />}
          </div>

          {patientState === 'showRecommendation' && recommendedItem && (
            <div className="result-panel good-panel">
              <p>{recommendation.patientExplanation}</p>
              <div className="tag-row">
                {recommendedItem.nutritionTags.map((tag) => <span key={tag}>{tag}</span>)}
              </div>
              <p className="trace-id">{recommendation.traceId}</p>
            </div>
          )}

          {patientState === 'showRefusal' && (
            <div className="result-panel danger-panel">
              <AlertTriangle size={18} aria-hidden="true" />
              <p>{recommendation.patientExplanation}</p>
              <p className="trace-id">{recommendation.traceId}</p>
            </div>
          )}

          {patientState === 'showReviewWait' && (
            <div className="result-panel warning-panel">
              <Clock3 size={18} aria-hidden="true" />
              <p>{recommendation.patientExplanation}</p>
              <p className="trace-id">{recommendation.traceId}</p>
            </div>
          )}

          <div className="button-row">
            <button className="secondary-button" type="button" onClick={() => onStateChange(requestRecommendation(state, 'refused'))}>
              模拟拒绝推荐
            </button>
            <button className="secondary-button" type="button" onClick={() => onStateChange(requestRecommendation(state, 'review'))}>
              模拟等待营养师审核
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Wire patient workspace into `App.tsx`**

Modify `apps/mini-program-prototype/src/App.tsx` by adding the import:

```tsx
import { PatientWorkspace } from './features/patient/PatientWorkspace';
```

Then render it under the summary card:

```tsx
{state.activeRole === 'patient' && <PatientWorkspace state={state} onStateChange={setState} />}
```

The resulting `App.tsx` still keeps the role workbench header and switcher from Task 4.

- [ ] **Step 4: Append patient UI styles**

Append to `apps/mini-program-prototype/src/styles.css`:

```css
.workspace-stack {
  display: grid;
  gap: 14px;
}

.hero-panel {
  background: #172033;
  color: #ffffff;
  border-radius: 8px;
  padding: 18px;
  display: grid;
  gap: 16px;
}

.hero-panel h2 {
  margin: 0 0 8px;
  font-size: 22px;
  letter-spacing: 0;
}

.hero-panel p {
  margin: 0;
  color: #d9e1ea;
  line-height: 1.6;
}

.primary-button,
.secondary-button {
  border: 0;
  border-radius: 8px;
  min-height: 42px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.primary-button {
  background: #2f6fed;
  color: #ffffff;
}

.secondary-button {
  background: #eef2f7;
  color: #172033;
}

.muted {
  color: #526071;
  line-height: 1.6;
}

.status {
  border-radius: 999px;
  padding: 5px 9px;
  font-size: 12px;
}

.status.good {
  background: #dcfce7;
  color: #166534;
}

.list {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
}

.list-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #edf1f6;
  padding-bottom: 10px;
}

.list-row p {
  margin: 4px 0 0;
  color: #526071;
  font-size: 13px;
}

.result-panel {
  border-radius: 8px;
  padding: 12px;
  display: grid;
  gap: 10px;
}

.good-panel {
  background: #f0fdf4;
}

.warning-panel {
  background: #fffbeb;
}

.danger-panel {
  background: #fef2f2;
}

.tag-row,
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-row span {
  border-radius: 999px;
  background: #e0e7ff;
  color: #3730a3;
  padding: 5px 9px;
  font-size: 12px;
}

.trace-id {
  margin: 0;
  color: #526071;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}
```

- [ ] **Step 5: Run patient tests and full tests**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/features/patient/PatientWorkspace.test.tsx src/App.test.tsx
npm run test
```

Expected:

- Patient workspace tests PASS.
- App test still PASS.
- Full test suite PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype/src
git commit -m "feat: add patient recommendation workspace"
```

---

### Task 6: Implement the Dietitian Review Workspace

**Files:**
- Create: `apps/mini-program-prototype/src/features/review/DietitianWorkspace.tsx`
- Create: `apps/mini-program-prototype/src/features/review/DietitianWorkspace.test.tsx`
- Modify: `apps/mini-program-prototype/src/App.tsx`
- Modify: `apps/mini-program-prototype/src/styles.css`

- [ ] **Step 1: Write failing review workspace tests**

Create `apps/mini-program-prototype/src/features/review/DietitianWorkspace.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createInitialPrototypeState } from '../../state';
import { DietitianWorkspace } from './DietitianWorkspace';

describe('DietitianWorkspace', () => {
  it('shows pending review cases and trace evidence', () => {
    render(<DietitianWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('trace-review-001')).toBeInTheDocument();
    expect(screen.getByText('LOW_CONFIDENCE_INTAKE')).toBeInTheDocument();
    expect(screen.getByText('baseline-2026-05-15')).toBeInTheDocument();
  });

  it('submits approve, modify, and reject decisions', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<DietitianWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '确认推荐' }));
    await user.click(screen.getByRole('button', { name: '修改推荐' }));
    await user.click(screen.getByRole('button', { name: '驳回推荐' }));

    expect(onStateChange).toHaveBeenCalledTimes(3);
  });
});
```

- [ ] **Step 2: Implement dietitian review workspace**

Create `apps/mini-program-prototype/src/features/review/DietitianWorkspace.tsx`:

```tsx
import { AlertTriangle, CheckCircle, ClipboardCheck, Edit3, XCircle } from 'lucide-react';
import { mealLabelName } from '../../contracts';
import { submitReviewDecision, type PrototypeState } from '../../state';

interface DietitianWorkspaceProps {
  state: PrototypeState;
  onStateChange: (state: PrototypeState) => void;
}

export function DietitianWorkspace({ state, onStateChange }: DietitianWorkspaceProps) {
  const activeCase = state.reviewCases[0];
  const safetyEvent = activeCase.trace.safetyEvents[0];

  return (
    <div className="workspace-stack">
      <section className="hero-panel review-hero">
        <div>
          <p className="eyebrow">营养师审核</p>
          <h2>{state.reviewCases.filter((item) => item.status === 'pending').length} 条待审核</h2>
          <p>优先处理高风险、低置信度和资料未确认的推荐请求。</p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">审核队列</p>
            <h2>{activeCase.patientDisplayName} · {mealLabelName(activeCase.mealLabel)}</h2>
          </div>
          <span className="status danger">{activeCase.riskLevel}</span>
        </div>
        <p className="muted">{activeCase.reason}</p>
        <p className="trace-id">{activeCase.traceId}</p>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">Trace 证据链</p>
            <h2>{activeCase.trace.ruleVersion}</h2>
          </div>
          <ClipboardCheck size={20} aria-hidden="true" />
        </div>
        <div className="evidence-grid">
          <div>
            <span>Outcome</span>
            <strong>{activeCase.trace.outcome}</strong>
          </div>
          <div>
            <span>Risk</span>
            <strong>{activeCase.trace.riskLevel}</strong>
          </div>
          <div>
            <span>Safety</span>
            <strong>{safetyEvent?.codeName ?? '无'}</strong>
          </div>
          <div>
            <span>Rule</span>
            <strong>{activeCase.trace.ruleVersion}</strong>
          </div>
        </div>
        <div className="result-panel warning-panel">
          <AlertTriangle size={18} aria-hidden="true" />
          <p>{activeCase.trace.patientExplanation}</p>
          <p>{activeCase.trace.clinicianExplanation.llmBoundary}</p>
        </div>
      </section>

      <section className="card">
        <p className="eyebrow">审核动作</p>
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => onStateChange(submitReviewDecision(state, activeCase.traceId, 'approve'))}>
            <CheckCircle size={18} aria-hidden="true" />
            确认推荐
          </button>
          <button className="secondary-button" type="button" onClick={() => onStateChange(submitReviewDecision(state, activeCase.traceId, 'modify'))}>
            <Edit3 size={18} aria-hidden="true" />
            修改推荐
          </button>
          <button className="secondary-button danger-action" type="button" onClick={() => onStateChange(submitReviewDecision(state, activeCase.traceId, 'reject'))}>
            <XCircle size={18} aria-hidden="true" />
            驳回推荐
          </button>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Wire review workspace into `App.tsx`**

Add import:

```tsx
import { DietitianWorkspace } from './features/review/DietitianWorkspace';
```

Render after the patient workspace condition:

```tsx
{state.activeRole === 'dietitian' && <DietitianWorkspace state={state} onStateChange={setState} />}
```

- [ ] **Step 4: Append review UI styles**

Append to `apps/mini-program-prototype/src/styles.css`:

```css
.review-hero {
  background: #263246;
}

.status.danger {
  background: #fee2e2;
  color: #991b1b;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.evidence-grid div {
  border-radius: 8px;
  background: #f4f7fb;
  padding: 10px;
}

.evidence-grid span {
  display: block;
  color: #526071;
  font-size: 12px;
  margin-bottom: 4px;
}

.evidence-grid strong {
  word-break: break-word;
}

.danger-action {
  background: #fee2e2;
  color: #991b1b;
}
```

- [ ] **Step 5: Run review tests and full tests**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/features/review/DietitianWorkspace.test.tsx src/App.test.tsx
npm run test
```

Expected:

- Review workspace tests PASS.
- App test still PASS.
- Full test suite PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype/src
git commit -m "feat: add dietitian review workspace"
```

---

### Task 7: Implement the Catering Management Workspace

**Files:**
- Create: `apps/mini-program-prototype/src/features/catering/CateringWorkspace.tsx`
- Create: `apps/mini-program-prototype/src/features/catering/CateringWorkspace.test.tsx`
- Modify: `apps/mini-program-prototype/src/App.tsx`
- Modify: `apps/mini-program-prototype/src/styles.css`

- [ ] **Step 1: Write failing catering workspace tests**

Create `apps/mini-program-prototype/src/features/catering/CateringWorkspace.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createInitialPrototypeState } from '../../state';
import { CateringWorkspace } from './CateringWorkspace';

describe('CateringWorkspace', () => {
  it('shows menu data quality and fulfillment status', () => {
    render(<CateringWorkspace state={createInitialPrototypeState()} onStateChange={vi.fn()} />);

    expect(screen.getByText('清蒸鱼套餐')).toBeInTheDocument();
    expect(screen.getByText('糙米鸡胸套餐')).toBeInTheDocument();
    expect(screen.getByText('nutritionConfidence 0.62')).toBeInTheDocument();
    expect(screen.getByText('待准备')).toBeInTheDocument();
  });

  it('updates availability and fulfillment status', async () => {
    const user = userEvent.setup();
    const onStateChange = vi.fn();

    render(<CateringWorkspace state={createInitialPrototypeState()} onStateChange={onStateChange} />);
    await user.click(screen.getByRole('button', { name: '下架清蒸鱼套餐' }));
    await user.click(screen.getByRole('button', { name: '标记已备餐' }));

    expect(onStateChange).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Implement catering workspace**

Create `apps/mini-program-prototype/src/features/catering/CateringWorkspace.tsx`:

```tsx
import { ChefHat, Save, ToggleLeft } from 'lucide-react';
import { formatPrice, mealLabelName } from '../../contracts';
import {
  updateFulfillmentStatus,
  updateMenuItemAvailability,
  type PrototypeState
} from '../../state';

interface CateringWorkspaceProps {
  state: PrototypeState;
  onStateChange: (state: PrototypeState) => void;
}

const fulfillmentLabels = {
  pending: '待准备',
  prepared: '已备餐',
  delivered: '已送达',
  cancelled: '取消'
};

export function CateringWorkspace({ state, onStateChange }: CateringWorkspaceProps) {
  const primaryItem = state.menuItems[0];

  return (
    <div className="workspace-stack">
      <section className="hero-panel catering-hero">
        <div>
          <p className="eyebrow">配餐管理</p>
          <h2>菜单数据维护优先</h2>
          <p>维护营养值、过敏原、禁忌标签、置信度和可售状态，让推荐候选更可信。</p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">菜单列表</p>
            <h2>今日菜品</h2>
          </div>
          <ChefHat size={20} aria-hidden="true" />
        </div>
        <div className="list">
          {state.menuItems.map((item) => (
            <div className="list-row" key={item.itemId}>
              <div>
                <strong>{item.name}</strong>
                <p>{formatPrice(item.priceCents)} · nutritionConfidence {item.nutritionConfidence}</p>
                <p>{item.nutritionTags.join('、') || '营养标签待补'}</p>
              </div>
              <span className={item.available ? 'status good' : 'status danger'}>
                {item.available ? '可售' : '下架'}
              </span>
            </div>
          ))}
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => onStateChange(updateMenuItemAvailability(state, primaryItem.itemId, false))}
        >
          <ToggleLeft size={18} aria-hidden="true" />
          下架{primaryItem.name}
        </button>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">菜品详情</p>
            <h2>{primaryItem.name}</h2>
          </div>
          <Save size={20} aria-hidden="true" />
        </div>
        <div className="nutrition-grid">
          <div>能量 <strong>{primaryItem.nutrients.energyKcal} kcal</strong></div>
          <div>碳水 <strong>{primaryItem.nutrients.carbsG}g</strong></div>
          <div>蛋白质 <strong>{primaryItem.nutrients.proteinG}g</strong></div>
          <div>钠 <strong>{primaryItem.nutrients.sodiumMg}mg</strong></div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">轻量履约</p>
            <h2>已确认餐食</h2>
          </div>
        </div>
        {state.fulfillments.map((fulfillment) => (
          <div className="list-row" key={fulfillment.fulfillmentId}>
            <div>
              <strong>{fulfillment.patientDisplayName} · {fulfillment.itemName}</strong>
              <p>{mealLabelName(fulfillment.mealLabel)} · {fulfillmentLabels[fulfillment.status]}</p>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={() => onStateChange(updateFulfillmentStatus(state, fulfillment.fulfillmentId, 'prepared'))}
            >
              标记已备餐
            </button>
          </div>
        ))}
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Wire catering workspace into `App.tsx`**

Add import:

```tsx
import { CateringWorkspace } from './features/catering/CateringWorkspace';
```

Render after the review workspace condition:

```tsx
{state.activeRole === 'catering' && <CateringWorkspace state={state} onStateChange={setState} />}
```

- [ ] **Step 4: Append catering UI styles**

Append to `apps/mini-program-prototype/src/styles.css`:

```css
.catering-hero {
  background: #21362d;
}

.nutrition-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.nutrition-grid div {
  border-radius: 8px;
  background: #f4f7fb;
  padding: 10px;
  color: #526071;
}

.nutrition-grid strong {
  display: block;
  color: #172033;
  margin-top: 4px;
}
```

- [ ] **Step 5: Run catering tests and full tests**

Run:

```bash
cd apps/mini-program-prototype
npm run test -- src/features/catering/CateringWorkspace.test.tsx src/App.test.tsx
npm run test
```

Expected:

- Catering workspace tests PASS.
- App test still PASS.
- Full test suite PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype/src
git commit -m "feat: add catering management workspace"
```

---

### Task 8: Final Responsive QA, Documentation, and Verification

**Files:**
- Create: `apps/mini-program-prototype/README.md`
- Modify: `apps/mini-program-prototype/src/styles.css`

- [ ] **Step 1: Add responsive finishing styles**

Append to `apps/mini-program-prototype/src/styles.css`:

```css
@media (max-width: 480px) {
  .app-shell {
    padding: 0;
  }

  .phone-frame {
    width: 100%;
    min-height: 100vh;
    border: 0;
    border-radius: 0;
    box-shadow: none;
    padding: 18px;
  }

  .top-bar {
    margin-bottom: 14px;
  }

  h1 {
    font-size: 24px;
  }

  .button-row {
    display: grid;
  }
}
```

- [ ] **Step 2: Create the prototype README**

Create `apps/mini-program-prototype/README.md`:

```md
# MediDiet Mini-Program Prototype

This is a mobile-first browser prototype for the MediDiet three-role WeChat mini-program design.

## What It Demonstrates

- Patient role: profile confirmation, intake records, next-meal recommendation, refused result, and human-review wait state.
- Dietitian role: pending review queue, `RecommendationTrace` evidence, and approve/modify/reject actions.
- Catering role: `MenuItem` data quality, availability updates, nutrition values, and lightweight fulfillment status.

## Contract Alignment

The prototype mirrors the recommendation engine contract documented in:

- `../../.worktrees/recommendation-engine-core/docs/api.md`
- `../../docs/superpowers/specs/2026-05-17-medidiet-mini-program-frontend-design.zh.md`

Important mapped concepts:

- `PatientProfile`
- `IntakeRecord`
- `MenuItem`
- `MealLabel`
- `RecommendationResult`
- `RecommendationTrace`

## Commands

```bash
npm install
npm run test
npm run build
npm run dev -- --host 127.0.0.1
```

## Boundaries

This prototype does not implement real WeChat Mini Program runtime APIs, HTTP services, image recognition, payment, or production clinical rules. It is intentionally service-free and deterministic so the product flow can be reviewed before implementation hardens.
```

- [ ] **Step 3: Run all automated verification**

Run:

```bash
cd apps/mini-program-prototype
npm run test
npm run build
```

Expected:

- All Vitest tests PASS.
- TypeScript build PASS.
- Vite production build PASS.

- [ ] **Step 4: Run local dev server for visual QA**

Run:

```bash
cd apps/mini-program-prototype
npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a local URL such as `http://127.0.0.1:5173/`.

Open that URL in the in-app browser and verify:

- Desktop viewport shows one centered phone frame.
- Mobile viewport around `390x844` fills the width without horizontal scrolling.
- Role switching shows patient, dietitian, and catering workspaces.
- Patient buttons update recommendation state.
- Dietitian actions update review state.
- Catering buttons update availability and fulfillment state.

- [ ] **Step 5: Check repository status**

Run:

```bash
git status --short
```

Expected:

- Only prototype files under `apps/mini-program-prototype` are modified or untracked.
- Existing unrelated untracked files such as `SUPERPOWERS_USAGE.md` and `v1版本升级方案.md` are not staged.

- [ ] **Step 6: Commit**

Run:

```bash
git add apps/mini-program-prototype
git commit -m "docs: add mini-program prototype runbook"
```

---

## Final Verification Checklist

After all tasks are complete, run:

```bash
cd apps/mini-program-prototype
npm run test
npm run build
```

Then run from repository root:

```bash
git status --short
git log --oneline -5
```

Expected:

- Prototype test suite passes.
- Prototype build passes.
- The recent commit history contains the incremental prototype commits.
- No unrelated user files are staged.

## Self-Review

Spec coverage:

- Role workbench and multi-role switching are covered by Task 4.
- Patient profile, intake records, recommendation states, refused state, and human-review wait state are covered by Task 5.
- Dietitian review queue, trace evidence, and approve/modify/reject decisions are covered by Task 6.
- Catering menu data quality, availability, nutrition values, and lightweight fulfillment are covered by Task 7.
- DTO alignment with `PatientProfile`, `IntakeRecord`, `MenuItem`, `MealLabel`, `RecommendationResult`, and `RecommendationTrace` is covered by Task 2 and Task 3.
- Responsive mobile QA, runbook, tests, and build verification are covered by Task 8.

Placeholder scan:

- The plan contains no unfinished placeholder markers or placeholder instructions.
- Spread syntax such as `{ ...state }` appears only inside real TypeScript code blocks.

Type consistency:

- `Role`, `MealLabel`, `Outcome`, `RiskLevel`, `ReviewDecision`, and `FulfillmentStatus` are defined in Task 2 and reused consistently.
- `PrototypeState` is defined in Task 3 and passed unchanged into patient, review, and catering workspaces.
- Review decisions map to `ReviewCaseDto['status']`, keeping state updates type-safe.
