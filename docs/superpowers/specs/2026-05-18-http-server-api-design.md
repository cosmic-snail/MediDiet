# MediDiet HTTP Server API Design

Date: 2026-05-18
Status: Ready for user review
Scope: Local/development HTTP server for front-end integration

## Goal

Add an HTTP server layer so the mini-program/front-end can submit patient data, meal intake records, nutritionist review notes, and today's hospital menu, then request a meal recommendation with LLM-enhanced explanations.

The HTTP server is an adapter over the existing deterministic recommendation engine. It must not duplicate recommendation rules or allow the LLM to change the recommendation result.

## Chosen Approach

Use **FastAPI + Pydantic + uvicorn** with an application service layer.

The server will use in-memory state for the MVP:

- Patient profiles.
- Structured intake records.
- Today's hospital menu.
- Nutritionist review notes.

The in-memory design supports front-end integration without introducing a database yet. Production persistence, authentication, authorization, audit logging, and rate limiting remain future work.

## Architecture

The design uses three layers:

1. **HTTP Layer**
   - Exposes REST endpoints.
   - Defines Pydantic request and response models.
   - Converts JSON payloads into service DTOs.
   - Maps service errors into uniform HTTP error responses.
   - Provides OpenAPI documentation through FastAPI.

2. **Application Service Layer**
   - Owns the in-memory store.
   - Converts simplified or full front-end menu payloads into `MenuItem`.
   - Converts patient, preference, and intake payloads into domain models.
   - Merges long-term patient taste preferences with per-request temporary taste preferences.
   - Calls `RecommendationEngine`.
   - Calls `LLMContextSanitizer` and `LLMExplanationEnhancer`.
   - Assembles front-end-facing recommendation responses.

3. **Core Domain Layer**
   - Keeps existing rule-based behavior in `RecommendationEngine`.
   - Keeps safety gates, nutrition calculation, meal planning, menu matching, trace generation, and LLM post-processing unchanged except where explicit integration is required.

Recommended modules:

- `src/medidiet/service.py`
- `src/medidiet/server.py`
- `tests/test_service.py`
- `tests/test_http_server.py`

## API Endpoints

### `GET /health`

Returns service status, package version, and rule pack version.

### `PUT /patients/{patient_id}`

Creates or replaces a full patient profile.

The request includes:

- Age, height, and weight.
- Conditions.
- Allergens.
- Contraindications.
- Long-term preferences.
- Whether key risk fields are confirmed.

Recommendation requests only pass `patientId`; patient clinical context is loaded from memory.

### `POST /patients/{patient_id}/intake-records`

Appends one structured meal intake record for a patient.

The request includes:

- Food label.
- Occurrence time.
- Meal label.
- Portion description.
- Nutrients.
- Confidence.
- Whether the record was manually corrected.

The MVP does not accept images or call an image recognition service.

### `PUT /menus/today`

Stores today's hospital menu.

The endpoint accepts both simplified and full menu item payloads:

- Full payloads can provide all `MenuItem` fields.
- Simplified payloads can omit optional operational fields.

Service defaults for simplified menu items:

- `priceCents = 0`
- `distanceMeters = 0`
- `merchantReliability = 1.0`
- `source = human_curated`
- `nutritionConfidence = 0.95`
- `available = true`

### `POST /reviews/nutritionist`

Records nutritionist review notes.

Review notes are stored and returned in recommendation responses, but they do not affect recommendation outcome, menu ranking, rule behavior, or LLM prompt context in the MVP.

### `POST /recommendations`

Runs a recommendation.

Request fields:

- `patientId`
- `mealLabel`
- `temporaryTasteTags`
- Optional `debug`

Behavior:

1. Validate request payload.
2. Load patient profile by `patientId`.
3. Load patient intake records from memory.
4. Load today's hospital menu from memory.
5. Merge long-term and temporary taste preferences for this request only.
6. Call `RecommendationEngine.recommend(...)`.
7. Enhance the explanation with the configured LLM provider when available.
8. Fall back to rule explanation if LLM is not configured or fails.
9. Return outcome, recommended menu, explanations, nutritionist reviews, and trace id.

### `GET /debug/state`

Returns a development-only summary of in-memory state.

This endpoint is for local/front-end integration debugging. It must be removed, disabled, or protected before production use.

## Data Contracts

### Concept Codes

Front-end code values use structured objects:

```json
{
  "kind": "condition",
  "value": "hypertension"
}
```

Supported `kind` values mirror `CodeKind`:

- `condition`
- `allergen`
- `contraindication`
- `nutrition_tag`
- `taste_tag`
- `ingredient`

Each field must use the correct kind. For example, `conditions` only accepts `condition`; `temporaryTasteTags` only accepts `taste_tag`.

### Meal Label

`mealLabel` uses the existing integer enum:

- `1`: breakfast
- `2`: lunch
- `3`: dinner
- `4`: snack

### Patient Profile Request

```json
{
  "age": 65,
  "heightCm": 170,
  "weightKg": 72,
  "conditions": [{"kind": "condition", "value": "hypertension"}],
  "allergens": [{"kind": "allergen", "value": "peanut"}],
  "contraindications": [{"kind": "contraindication", "value": "high_sodium"}],
  "preferences": {
    "tasteTags": [{"kind": "taste_tag", "value": "light"}],
    "dislikedIngredients": [],
    "maxPriceCents": 3000,
    "maxDistanceMeters": 1000
  },
  "keyRiskFieldsConfirmed": true
}
```

### Recommendation Request

```json
{
  "patientId": "patient-001",
  "mealLabel": 3,
  "temporaryTasteTags": [
    {"kind": "taste_tag", "value": "light"}
  ]
}
```

### Recommendation Response

```json
{
  "outcome": "recommended",
  "recommendedItems": [],
  "explanation": {
    "patient": "这份餐食符合当前营养规则...",
    "clinician": "{...}",
    "llm": {
      "usedFallback": false,
      "fallbackReason": null
    }
  },
  "nutritionistReviews": [],
  "traceId": "trace-..."
}
```

If `debug=true`, the response may include full trace JSON for development and test inspection.

## Error Handling

All HTTP errors use the same response shape:

```json
{
  "error": {
    "code": "PATIENT_NOT_FOUND",
    "message": "Patient profile not found",
    "details": {}
  }
}
```

Error codes:

- `PATIENT_NOT_FOUND`: HTTP 404.
- `MENU_NOT_CONFIGURED`: HTTP 409.
- `INVALID_CODE_KIND`: HTTP 422.
- `INVALID_MEAL_LABEL`: HTTP 422.
- `INVALID_NUTRIENTS`: HTTP 422.
- `INTERNAL_ERROR`: HTTP 500.

LLM failures do not make `POST /recommendations` fail. They are reported in the response as:

```json
{
  "usedFallback": true,
  "fallbackReason": 6002
}
```

## Security Boundaries

MVP assumptions:

- No real authentication.
- Intended only for local or trusted internal development.
- No original images.
- No complete medical record free text.
- No API key in committed files.
- `.env` remains local and ignored by git.

Production requirements before external use:

- User authentication.
- Patient authorization.
- Operation audit trail.
- HTTPS.
- Request rate limiting.
- Log and trace redaction.
- Protection or removal of `/debug/state`.

LLM safety:

- LLM receives only sanitized recommendation context.
- LLM does not receive `patient_id`.
- LLM cannot change `outcome`, recommended menu, exclusions, safety events, or scores.
- Nutritionist review notes are not passed into the LLM prompt in the MVP.

## Testing Strategy

### DTO and Conversion Tests

- Reject wrong `CodeKind` in each field.
- Convert simplified menu payloads to `MenuItem` with defaults.
- Reject invalid `mealLabel`.
- Reject negative, non-finite, or absurd nutrients.

### Application Service Tests

- Recommend after creating a patient and today's menu.
- Use appended intake records during recommendation.
- Return `MENU_NOT_CONFIGURED` when no menu has been set.
- Apply temporary taste tags only to the current request.
- Preserve patient long-term preferences after temporary taste usage.
- Record nutritionist reviews and return them in recommendation responses.
- Confirm nutritionist reviews do not alter outcome or ranking.

### HTTP Tests

- `GET /health` returns version and rule version.
- `PUT /patients/{patient_id}` stores a patient.
- `POST /patients/{patient_id}/intake-records` appends an intake record.
- `PUT /menus/today` accepts simplified and full menu items.
- `POST /reviews/nutritionist` records notes.
- `POST /recommendations` returns outcome, menu, explanations, LLM fallback metadata, and trace id.
- Missing patient, missing menu, and invalid payloads return the uniform error shape.

### LLM Tests

- Offline HTTP tests use a mock or missing provider and remain deterministic.
- LLM failure returns successful recommendation response with `usedFallback=true`.
- Real DeepSeek smoke test remains opt-in through environment variables.

## Out of Scope

- Database persistence.
- Real authentication and authorization.
- External HIS/EMR integration.
- Image upload or image recognition.
- Nutritionist override of recommendation results.
- Passing nutritionist review notes into LLM prompts.
- Production deployment configuration.
