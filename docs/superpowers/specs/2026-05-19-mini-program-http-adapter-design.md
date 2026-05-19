# Mini Program HTTP Adapter Design

## Goal

Adapt `apps/mini-program-prototype` so the patient recommendation flow can call the FastAPI HTTP service already exposed by `src/medidiet/server.py`, while preserving the existing three-role prototype and deterministic local fixtures as UI state.

## Backend Contract

The frontend will target the current local FastAPI server:

- `GET /health`
- `PUT /patients/{patient_id}`
- `POST /patients/{patient_id}/intake-records`
- `PUT /menus/today`
- `POST /recommendations`
- `GET /debug/state`

In development, Vite will proxy `/api/*` to `http://127.0.0.1:8000/*`. The API base path will default to `/api` and can be overridden by `VITE_MEDIDIET_API_BASE_URL`.

## Frontend Design

Add a small API boundary under `src/api/`:

- `medidietApi.ts` owns fetch calls, HTTP errors, and demo seeding.
- `adapters.ts` converts the existing frontend DTOs into backend payloads and converts backend recommendation responses back to `RecommendationResponseDto`.

The current `contracts.ts`, fixtures, and role workspaces remain the UI contract. This keeps the prototype stable while making the recommendation button exercise the real backend.

## Patient Flow

On app startup, the frontend will seed the backend with:

- demo patient profile
- current intake records
- current menu items

The patient "获取下一餐推荐" action will call `POST /recommendations` with `debug: true`, then display the backend recommendation, refusal, or human-review state using the existing patient card.

If the backend is unavailable or returns a structured error, the page will show a compact service status/error message and preserve the last local UI state.

## Boundaries

This change does not attempt to make all roles backend-driven. The current backend does not yet provide full GET endpoints for patients, menus, review queues, or fulfillment state. Dietitian review and catering management therefore remain prototype-local.

## Verification

- Adapter unit tests cover payload conversion, response conversion, and structured error parsing.
- App-level tests cover successful backend recommendation and backend failure fallback.
- Existing frontend tests must continue to pass.
- Build must pass.
