# MediDiet Mini-Program Prototype

This is a mobile-first browser prototype for the MediDiet three-role WeChat mini-program design.

Chinese usage guide: [README.zh.md](./README.zh.md)

## What It Demonstrates

- Patient role: profile confirmation, intake records, next-meal recommendation, refused result, and human-review wait state.
- Dietitian role: pending review queue, `RecommendationTrace` evidence, and approve/modify/reject actions.
- Catering role: `MenuItem` data quality, availability updates, nutrition values, and lightweight fulfillment status.

## Contract Alignment

The prototype mirrors the recommendation engine contract documented in:

- `../../docs/superpowers/specs/2026-05-15-hospital-diet-agent-recommendation-engine-design.zh.md`
- `../../docs/superpowers/specs/2026-05-17-medidiet-mini-program-frontend-design.zh.md`
- `../../docs/superpowers/plans/2026-05-17-medidiet-mini-program-prototype.zh.md`

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

For backend-connected recommendation calls, start the FastAPI service from the repository root:

```bash
uvicorn medidiet.server:app --app-dir src --reload
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000/*`. Override the API base URL with `VITE_MEDIDIET_API_BASE_URL` when needed.

The patient "next meal recommendation" action now seeds demo data through the HTTP service and calls `POST /recommendations`. The client reads `GET /debug/state` first so repeated demo clicks do not append duplicate intake records, and it only submits available menu items with nutrition confidence of at least `0.7` to the backend recommendation pool.

## Boundaries

This prototype does not implement real WeChat Mini Program runtime APIs, image recognition, payment, or production clinical rules. Dietitian review actions and catering fulfillment remain local deterministic flows while the patient recommendation action is connected to the local FastAPI service.
