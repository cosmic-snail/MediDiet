# HTTP Server API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI HTTP server with in-memory state so front-end clients can submit patients, intake records, nutritionist reviews, today's menu, and request LLM-enhanced recommendations.

**Architecture:** Add `service.py` as a pure application service layer over the existing deterministic engine and LLM post-processor. Add `server.py` as the FastAPI adapter with Pydantic request/response models and uniform error mapping. Keep all recommendation decisions inside `RecommendationEngine`; HTTP and service layers only validate, convert, orchestrate, and serialize.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, uvicorn, `unittest`, FastAPI `TestClient`, existing MediDiet domain/engine/LLM modules.

---

## File Structure

Create:

- `src/medidiet/service.py` - application DTOs, in-memory store, conversion helpers, service errors, recommendation orchestration.
- `src/medidiet/server.py` - FastAPI app factory, HTTP request/response models, endpoint wiring, exception handlers.
- `tests/test_service.py` - service-level TDD coverage without HTTP.
- `tests/test_http_server.py` - HTTP endpoint tests with FastAPI `TestClient`.
- `tests/test_http_llm_smoke.py` - opt-in HTTP recommendation smoke test using a real OpenAI-compatible LLM.

Modify:

- `pyproject.toml` - add `fastapi` and `uvicorn` dependencies.
- `docs/api.md` - document HTTP endpoints and payloads.
- `docs/software-design.md` - add server/service modules to architecture.
- `docs/testing.md` - add HTTP/service test coverage and updated test count after implementation.
- `docs/usage.md` - add local server run command and example requests.

Do not modify:

- `RecommendationEngine` selection logic.
- Existing safety, nutrition, planner, matcher, and rule behavior.
- Real `.env` contents. `.env` is ignored and must not be staged.

---

### Task 1: Add HTTP Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Write a dependency import check command**

Run this before editing:

```bash
PYTHONPATH=src python - <<'PY'
try:
    import fastapi
    import httpx
    import uvicorn
except ModuleNotFoundError as exc:
    raise SystemExit(f"missing dependency: {exc.name}")
print("fastapi, httpx, and uvicorn importable")
PY
```

Expected: It may fail with `missing dependency: fastapi` or `missing dependency: uvicorn` before dependencies are installed.

- [ ] **Step 2: Add project dependencies**

Modify `pyproject.toml` so the `[project]` table contains:

```toml
[project]
name = "medidiet"
version = "0.1.1"
description = "Hospital diet agent recommendation engine core"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110,<1.0",
    "httpx>=0.27,<1.0",
    "uvicorn>=0.29,<1.0",
]
```

Keep the existing `[tool.setuptools.packages.find]` section unchanged.

- [ ] **Step 3: Install editable package dependencies**

Run:

```bash
python -m pip install -e .
```

Expected: command exits 0 and installs FastAPI/uvicorn if absent.

- [ ] **Step 4: Verify imports**

Run:

```bash
PYTHONPATH=src python - <<'PY'
import fastapi
import httpx
import uvicorn
print("fastapi", fastapi.__version__)
print("httpx", httpx.__version__)
print("uvicorn", uvicorn.__version__)
PY
```

Expected: command exits 0 and prints both versions.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml
git commit -m "chore: add FastAPI server dependencies"
```

---

### Task 2: Service DTOs and Domain Conversion

**Files:**
- Create: `src/medidiet/service.py`
- Create: `tests/test_service.py`

- [ ] **Step 1: Write failing service conversion tests**

Create `tests/test_service.py` with this content:

```python
from datetime import datetime, timezone
import unittest

from medidiet.domain import CodeKind, DataSource, MealLabel


class ServiceConversionTest(unittest.TestCase):
    def test_patient_input_converts_to_domain_profile(self):
        from medidiet.service import (
            ConceptCodeInput,
            PatientProfileInput,
            PreferenceInput,
            patient_profile_from_input,
        )

        patient = patient_profile_from_input(
            "patient-001",
            PatientProfileInput(
                age=65,
                height_cm=170,
                weight_kg=72,
                conditions=(ConceptCodeInput(kind="condition", value="hypertension"),),
                allergens=(ConceptCodeInput(kind="allergen", value="peanut"),),
                contraindications=(ConceptCodeInput(kind="contraindication", value="high_sodium"),),
                preferences=PreferenceInput(
                    taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),),
                    disliked_ingredients=(),
                    max_price_cents=3000,
                    max_distance_meters=1000,
                ),
                key_risk_fields_confirmed=True,
            ),
        )

        self.assertEqual(patient.patient_id, "patient-001")
        self.assertEqual(next(iter(patient.conditions)).kind, CodeKind.CONDITION)
        self.assertEqual(next(iter(patient.allergens)).kind, CodeKind.ALLERGEN)
        self.assertEqual(next(iter(patient.preferences.taste_tags)).value, "light")
        self.assertEqual(patient.source, DataSource.PATIENT_REPORTED)

    def test_rejects_wrong_code_kind_for_patient_fields(self):
        from medidiet.service import ConceptCodeInput, PatientProfileInput, ServiceError, patient_profile_from_input

        with self.assertRaises(ServiceError) as ctx:
            patient_profile_from_input(
                "patient-001",
                PatientProfileInput(
                    age=65,
                    height_cm=170,
                    weight_kg=72,
                    conditions=(ConceptCodeInput(kind="allergen", value="peanut"),),
                    allergens=(),
                    contraindications=(),
                    key_risk_fields_confirmed=True,
                ),
            )

        self.assertEqual(ctx.exception.code, "INVALID_CODE_KIND")

    def test_simplified_menu_input_uses_safe_defaults(self):
        from medidiet.service import ConceptCodeInput, MenuItemInput, NutrientsInput, menu_item_from_input

        item = menu_item_from_input(
            MenuItemInput(
                item_id="steamed-fish-set",
                name="Steamed fish set",
                ingredients=(ConceptCodeInput(kind="ingredient", value="fish"),),
                allergens=(),
                taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),),
                nutrition_tags=(ConceptCodeInput(kind="nutrition_tag", value="low_sodium"),),
                contraindication_tags=(),
                nutrients=NutrientsInput(
                    energy_kcal=520,
                    carbs_g=58,
                    protein_g=34,
                    fat_g=14,
                    sodium_mg=520,
                    sugar_g=6,
                    fiber_g=7,
                ),
            )
        )

        self.assertEqual(item.item_id, "steamed-fish-set")
        self.assertEqual(item.merchant_id, "hospital-canteen")
        self.assertEqual(item.source, DataSource.HUMAN_CURATED)
        self.assertEqual(item.nutrition_confidence.value, 0.95)
        self.assertEqual(item.price_cents, 0)
        self.assertTrue(item.available)

    def test_intake_input_converts_to_domain_record(self):
        from medidiet.service import IntakeRecordInput, NutrientsInput, intake_record_from_input

        occurred_at = datetime(2026, 5, 18, 8, 0, tzinfo=timezone.utc)
        record = intake_record_from_input(
            IntakeRecordInput(
                food_label="Breakfast porridge",
                occurred_at=occurred_at,
                meal_label=MealLabel.BREAKFAST,
                portion="1 bowl",
                nutrients=NutrientsInput(energy_kcal=180, carbs_g=30, protein_g=6, fat_g=3),
                confidence=0.92,
                manually_corrected=False,
            )
        )

        self.assertEqual(record.food_label, "Breakfast porridge")
        self.assertEqual(record.meal_label, MealLabel.BREAKFAST)
        self.assertEqual(record.source, DataSource.PATIENT_REPORTED)
        self.assertEqual(record.confidence.value, 0.92)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_service.ServiceConversionTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.service'`.

- [ ] **Step 3: Implement service DTOs and conversion helpers**

Create `src/medidiet/service.py` with this initial implementation:

```python
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    Confidence,
    DataSource,
    IntakeRecord,
    MealLabel,
    MenuItem,
    Nutrients,
    PatientProfile,
    Preference,
)
from medidiet.engine import RecommendationEngine, RecommendationResult
from medidiet.llm import (
    LLMConfig,
    LLMContextSanitizer,
    LLMEnhancedExplanation,
    LLMExplanationEnhancer,
    LLMProviderPort,
    OpenAICompatibleLLMProvider,
)
from medidiet.rules import RulePack, load_baseline_rule_pack


class ServiceErrorCode(str, Enum):
    PATIENT_NOT_FOUND = "PATIENT_NOT_FOUND"
    MENU_NOT_CONFIGURED = "MENU_NOT_CONFIGURED"
    INVALID_CODE_KIND = "INVALID_CODE_KIND"
    INVALID_MEAL_LABEL = "INVALID_MEAL_LABEL"
    INVALID_NUTRIENTS = "INVALID_NUTRIENTS"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ServiceError(Exception):
    def __init__(self, code: str | ServiceErrorCode, message: str, details: dict[str, object] | None = None):
        self.code = code.value if isinstance(code, ServiceErrorCode) else code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True)
class ConceptCodeInput:
    kind: str
    value: str


@dataclass(frozen=True)
class NutrientsInput:
    energy_kcal: float = 0
    carbs_g: float = 0
    protein_g: float = 0
    fat_g: float = 0
    sodium_mg: float = 0
    sugar_g: float = 0
    fiber_g: float = 0


@dataclass(frozen=True)
class PreferenceInput:
    taste_tags: tuple[ConceptCodeInput, ...] = ()
    disliked_ingredients: tuple[ConceptCodeInput, ...] = ()
    max_price_cents: int | None = None
    max_distance_meters: int | None = None


@dataclass(frozen=True)
class PatientProfileInput:
    age: int
    height_cm: float
    weight_kg: float
    conditions: tuple[ConceptCodeInput, ...] = ()
    allergens: tuple[ConceptCodeInput, ...] = ()
    contraindications: tuple[ConceptCodeInput, ...] = ()
    preferences: PreferenceInput = field(default_factory=PreferenceInput)
    key_risk_fields_confirmed: bool = False


@dataclass(frozen=True)
class IntakeRecordInput:
    food_label: str
    occurred_at: datetime
    meal_label: MealLabel
    portion: str
    nutrients: NutrientsInput
    confidence: float
    manually_corrected: bool = False


@dataclass(frozen=True)
class MenuItemInput:
    item_id: str
    name: str
    nutrients: NutrientsInput
    ingredients: tuple[ConceptCodeInput, ...] = ()
    allergens: tuple[ConceptCodeInput, ...] = ()
    taste_tags: tuple[ConceptCodeInput, ...] = ()
    nutrition_tags: tuple[ConceptCodeInput, ...] = ()
    contraindication_tags: tuple[ConceptCodeInput, ...] = ()
    merchant_id: str = "hospital-canteen"
    nutrition_confidence: float = 0.95
    source: DataSource = DataSource.HUMAN_CURATED
    price_cents: int = 0
    distance_meters: int = 0
    merchant_reliability: float = 1.0
    available: bool = True


@dataclass(frozen=True)
class NutritionistReviewInput:
    patient_id: str
    reviewer_id: str
    note: str
    created_at: datetime


@dataclass(frozen=True)
class NutritionistReview:
    patient_id: str
    reviewer_id: str
    note: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "patientId": self.patient_id,
            "reviewerId": self.reviewer_id,
            "note": self.note,
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class RecommendationRequestInput:
    patient_id: str
    meal_label: MealLabel
    temporary_taste_tags: tuple[ConceptCodeInput, ...] = ()
    debug: bool = False


@dataclass(frozen=True)
class RecommendationServiceResult:
    outcome: str
    recommended_items: tuple[dict[str, object], ...]
    patient_explanation: str
    clinician_explanation: str
    llm_used_fallback: bool
    llm_fallback_reason: int | None
    nutritionist_reviews: tuple[dict[str, object], ...]
    trace_id: str
    trace: dict[str, object] | None = None


def concept_code_from_input(input_code: ConceptCodeInput, expected_kind: CodeKind) -> ConceptCode:
    try:
        kind = CodeKind(input_code.kind)
    except ValueError as exc:
        raise ServiceError(
            ServiceErrorCode.INVALID_CODE_KIND,
            f"Unsupported code kind: {input_code.kind}",
            {"expectedKind": expected_kind.value, "actualKind": input_code.kind},
        ) from exc
    if kind is not expected_kind:
        raise ServiceError(
            ServiceErrorCode.INVALID_CODE_KIND,
            f"Expected {expected_kind.value} code",
            {"expectedKind": expected_kind.value, "actualKind": kind.value, "value": input_code.value},
        )
    return ConceptCode(kind, input_code.value)


def code_set_from_inputs(values: tuple[ConceptCodeInput, ...], expected_kind: CodeKind) -> set[ConceptCode]:
    return {concept_code_from_input(value, expected_kind) for value in values}


def nutrients_from_input(input_nutrients: NutrientsInput) -> Nutrients:
    try:
        return Nutrients(
            energy_kcal=input_nutrients.energy_kcal,
            carbs_g=input_nutrients.carbs_g,
            protein_g=input_nutrients.protein_g,
            fat_g=input_nutrients.fat_g,
            sodium_mg=input_nutrients.sodium_mg,
            sugar_g=input_nutrients.sugar_g,
            fiber_g=input_nutrients.fiber_g,
        )
    except ValueError as exc:
        raise ServiceError(ServiceErrorCode.INVALID_NUTRIENTS, str(exc)) from exc


def preference_from_input(input_preference: PreferenceInput) -> Preference:
    return Preference(
        disliked_ingredients=code_set_from_inputs(input_preference.disliked_ingredients, CodeKind.INGREDIENT),
        taste_tags=code_set_from_inputs(input_preference.taste_tags, CodeKind.TASTE_TAG),
        max_price_cents=input_preference.max_price_cents,
        max_distance_meters=input_preference.max_distance_meters,
    )


def patient_profile_from_input(patient_id: str, input_profile: PatientProfileInput) -> PatientProfile:
    return PatientProfile(
        patient_id=patient_id,
        age=input_profile.age,
        height_cm=input_profile.height_cm,
        weight_kg=input_profile.weight_kg,
        conditions=code_set_from_inputs(input_profile.conditions, CodeKind.CONDITION),
        allergens=code_set_from_inputs(input_profile.allergens, CodeKind.ALLERGEN),
        contraindications=code_set_from_inputs(input_profile.contraindications, CodeKind.CONTRAINDICATION),
        preferences=preference_from_input(input_profile.preferences),
        key_risk_fields_confirmed=input_profile.key_risk_fields_confirmed,
        source=DataSource.PATIENT_REPORTED,
    )


def intake_record_from_input(input_record: IntakeRecordInput) -> IntakeRecord:
    if not isinstance(input_record.meal_label, MealLabel):
        raise ServiceError(ServiceErrorCode.INVALID_MEAL_LABEL, "mealLabel must be a valid MealLabel")
    return IntakeRecord(
        food_label=input_record.food_label,
        occurred_at=input_record.occurred_at,
        meal_label=input_record.meal_label,
        portion=input_record.portion,
        nutrients=nutrients_from_input(input_record.nutrients),
        confidence=Confidence(input_record.confidence),
        source=DataSource.PATIENT_REPORTED,
        manually_corrected=input_record.manually_corrected,
    )


def menu_item_from_input(input_item: MenuItemInput) -> MenuItem:
    return MenuItem(
        item_id=input_item.item_id,
        merchant_id=input_item.merchant_id,
        name=input_item.name,
        ingredients=code_set_from_inputs(input_item.ingredients, CodeKind.INGREDIENT),
        allergens=code_set_from_inputs(input_item.allergens, CodeKind.ALLERGEN),
        taste_tags=code_set_from_inputs(input_item.taste_tags, CodeKind.TASTE_TAG),
        nutrients=nutrients_from_input(input_item.nutrients),
        nutrition_confidence=Confidence(input_item.nutrition_confidence),
        source=input_item.source,
        price_cents=input_item.price_cents,
        distance_meters=input_item.distance_meters,
        merchant_reliability=input_item.merchant_reliability,
        nutrition_tags=code_set_from_inputs(input_item.nutrition_tags, CodeKind.NUTRITION_TAG),
        contraindication_tags=code_set_from_inputs(input_item.contraindication_tags, CodeKind.CONTRAINDICATION),
        available=input_item.available,
    )
```

The imports of `replace`, `RecommendationEngine`, `RecommendationResult`, LLM classes, and rule pack will be used in Task 3. Leave them in place.

- [ ] **Step 4: Run conversion tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_service.ServiceConversionTest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/service.py tests/test_service.py
git commit -m "feat: add HTTP service DTO conversions"
```

---

### Task 3: In-Memory Recommendation Application Service

**Files:**
- Modify: `src/medidiet/service.py`
- Modify: `tests/test_service.py`

- [ ] **Step 1: Append failing application service tests**

Append this to `tests/test_service.py`:

```python
class RecommendationApplicationServiceTest(unittest.TestCase):
    def patient_input(self):
        from medidiet.service import ConceptCodeInput, PatientProfileInput, PreferenceInput

        return PatientProfileInput(
            age=65,
            height_cm=170,
            weight_kg=72,
            conditions=(ConceptCodeInput(kind="condition", value="hypertension"),),
            allergens=(),
            contraindications=(),
            preferences=PreferenceInput(taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),)),
            key_risk_fields_confirmed=True,
        )

    def safe_menu(self):
        from medidiet.service import ConceptCodeInput, MenuItemInput, NutrientsInput

        return (
            MenuItemInput(
                item_id="steamed-fish-set",
                name="Steamed fish set",
                ingredients=(ConceptCodeInput(kind="ingredient", value="fish"),),
                taste_tags=(ConceptCodeInput(kind="taste_tag", value="light"),),
                nutrition_tags=(
                    ConceptCodeInput(kind="nutrition_tag", value="low_sodium"),
                    ConceptCodeInput(kind="nutrition_tag", value="controlled_carbs"),
                    ConceptCodeInput(kind="nutrition_tag", value="vegetable_rich"),
                ),
                nutrients=NutrientsInput(
                    energy_kcal=520,
                    carbs_g=58,
                    protein_g=34,
                    fat_g=14,
                    sodium_mg=520,
                    sugar_g=6,
                    fiber_g=7,
                ),
            ),
        )

    def test_recommends_after_patient_and_menu_are_configured(self):
        from medidiet.llm import MockLLMProvider
        from medidiet.service import RecommendationRequestInput, RecommendationService

        service = RecommendationService(llm_provider=MockLLMProvider(explanation_payload={
            "patientExplanation": "LLM safe patient explanation.",
            "clinicianExplanation": "LLM safe clinician explanation.",
        }))
        service.upsert_patient("patient-001", self.patient_input())
        service.replace_today_menu(self.safe_menu())

        result = service.recommend(
            RecommendationRequestInput(patient_id="patient-001", meal_label=MealLabel.DINNER)
        )

        self.assertEqual(result.outcome, "recommended")
        self.assertEqual(result.recommended_items[0]["itemId"], "steamed-fish-set")
        self.assertEqual(result.patient_explanation, "LLM safe patient explanation.")
        self.assertFalse(result.llm_used_fallback)
        self.assertIsNone(result.llm_fallback_reason)

    def test_returns_menu_not_configured_before_menu_upload(self):
        from medidiet.service import RecommendationRequestInput, RecommendationService, ServiceError

        service = RecommendationService()
        service.upsert_patient("patient-001", self.patient_input())

        with self.assertRaises(ServiceError) as ctx:
            service.recommend(RecommendationRequestInput(patient_id="patient-001", meal_label=MealLabel.DINNER))

        self.assertEqual(ctx.exception.code, "MENU_NOT_CONFIGURED")

    def test_temporary_taste_tags_do_not_mutate_patient_preferences(self):
        from medidiet.service import ConceptCodeInput, RecommendationRequestInput, RecommendationService

        service = RecommendationService()
        service.upsert_patient("patient-001", self.patient_input())
        service.replace_today_menu(self.safe_menu())

        service.recommend(
            RecommendationRequestInput(
                patient_id="patient-001",
                meal_label=MealLabel.DINNER,
                temporary_taste_tags=(ConceptCodeInput(kind="taste_tag", value="mild"),),
            )
        )

        stored_patient = service.store.patients["patient-001"]
        self.assertEqual({code.value for code in stored_patient.preferences.taste_tags}, {"light"})

    def test_records_reviews_but_does_not_change_outcome(self):
        from medidiet.service import NutritionistReviewInput, RecommendationRequestInput, RecommendationService

        service = RecommendationService()
        service.upsert_patient("patient-001", self.patient_input())
        service.replace_today_menu(self.safe_menu())
        service.record_nutritionist_review(
            NutritionistReviewInput(
                patient_id="patient-001",
                reviewer_id="nutritionist-1",
                note="请人工复核晚餐。",
                created_at=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
            )
        )

        result = service.recommend(
            RecommendationRequestInput(patient_id="patient-001", meal_label=MealLabel.DINNER)
        )

        self.assertEqual(result.outcome, "recommended")
        self.assertEqual(result.nutritionist_reviews[0]["note"], "请人工复核晚餐。")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_service.RecommendationApplicationServiceTest -v
```

Expected: FAIL with `ImportError: cannot import name 'RecommendationService'`.

- [ ] **Step 3: Implement in-memory store and service**

Append these definitions to `src/medidiet/service.py`:

```python
@dataclass
class InMemoryRecommendationStore:
    patients: dict[str, PatientProfile] = field(default_factory=dict)
    intake_records: dict[str, list[IntakeRecord]] = field(default_factory=dict)
    today_menu: list[MenuItem] = field(default_factory=list)
    nutritionist_reviews: dict[str, list[NutritionistReview]] = field(default_factory=dict)


class RecommendationService:
    def __init__(
        self,
        rule_pack: RulePack | None = None,
        store: InMemoryRecommendationStore | None = None,
        llm_provider: LLMProviderPort | None = None,
        now: datetime | None = None,
    ):
        self.rule_pack = rule_pack or load_baseline_rule_pack()
        self.store = store or InMemoryRecommendationStore()
        self.llm_provider = llm_provider
        self.now = now

    def upsert_patient(self, patient_id: str, input_profile: PatientProfileInput) -> PatientProfile:
        patient = patient_profile_from_input(patient_id, input_profile)
        self.store.patients[patient_id] = patient
        return patient

    def append_intake_record(self, patient_id: str, input_record: IntakeRecordInput) -> IntakeRecord:
        if patient_id not in self.store.patients:
            raise ServiceError(ServiceErrorCode.PATIENT_NOT_FOUND, "Patient profile not found", {"patientId": patient_id})
        record = intake_record_from_input(input_record)
        self.store.intake_records.setdefault(patient_id, []).append(record)
        return record

    def replace_today_menu(self, input_items: tuple[MenuItemInput, ...]) -> tuple[MenuItem, ...]:
        self.store.today_menu = [menu_item_from_input(item) for item in input_items]
        return tuple(self.store.today_menu)

    def record_nutritionist_review(self, input_review: NutritionistReviewInput) -> NutritionistReview:
        if input_review.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        review = NutritionistReview(
            patient_id=input_review.patient_id,
            reviewer_id=input_review.reviewer_id,
            note=input_review.note,
            created_at=input_review.created_at,
        )
        self.store.nutritionist_reviews.setdefault(input_review.patient_id, []).append(review)
        return review

    def recommend(self, input_request: RecommendationRequestInput) -> RecommendationServiceResult:
        patient = self.store.patients.get(input_request.patient_id)
        if patient is None:
            raise ServiceError(
                ServiceErrorCode.PATIENT_NOT_FOUND,
                "Patient profile not found",
                {"patientId": input_request.patient_id},
            )
        if not self.store.today_menu:
            raise ServiceError(ServiceErrorCode.MENU_NOT_CONFIGURED, "Today menu has not been configured")
        if not isinstance(input_request.meal_label, MealLabel):
            raise ServiceError(ServiceErrorCode.INVALID_MEAL_LABEL, "mealLabel must be a valid MealLabel")

        patient_for_request = self._patient_with_temporary_tastes(patient, input_request.temporary_taste_tags)
        engine = RecommendationEngine(self.rule_pack, now=self.now)
        result = engine.recommend(
            patient_for_request,
            self.store.intake_records.get(input_request.patient_id, []),
            list(self.store.today_menu),
            input_request.meal_label,
        )
        enhanced = self._enhance_explanation(result, patient_for_request, input_request.meal_label)
        reviews = tuple(review.to_dict() for review in self.store.nutritionist_reviews.get(input_request.patient_id, [])[-5:])

        return RecommendationServiceResult(
            outcome=result.outcome.value,
            recommended_items=tuple(_menu_item_to_dict(item) for item in result.recommended_items),
            patient_explanation=enhanced.patient_explanation,
            clinician_explanation=enhanced.clinician_explanation,
            llm_used_fallback=enhanced.used_fallback,
            llm_fallback_reason=int(enhanced.fallback_reason) if enhanced.fallback_reason is not None else None,
            nutritionist_reviews=reviews,
            trace_id=result.trace.trace_id,
            trace=result.trace.to_dict() if input_request.debug else None,
        )

    def debug_state(self) -> dict[str, object]:
        return {
            "patients": sorted(self.store.patients.keys()),
            "intakeRecordCounts": {patient_id: len(records) for patient_id, records in self.store.intake_records.items()},
            "todayMenuCount": len(self.store.today_menu),
            "nutritionistReviewCounts": {
                patient_id: len(reviews) for patient_id, reviews in self.store.nutritionist_reviews.items()
            },
        }

    def _patient_with_temporary_tastes(
        self,
        patient: PatientProfile,
        temporary_taste_tags: tuple[ConceptCodeInput, ...],
    ) -> PatientProfile:
        if not temporary_taste_tags:
            return patient
        merged_tastes = set(patient.preferences.taste_tags)
        merged_tastes.update(code_set_from_inputs(temporary_taste_tags, CodeKind.TASTE_TAG))
        return replace(patient, preferences=replace(patient.preferences, taste_tags=merged_tastes))

    def _enhance_explanation(
        self,
        result: RecommendationResult,
        patient: PatientProfile,
        meal_label: MealLabel,
    ) -> LLMEnhancedExplanation:
        provider = self.llm_provider
        if provider is None:
            config = LLMConfig.from_env()
            if config.provider == "openai_compatible" and config.base_url and config.api_key and config.model:
                provider = OpenAICompatibleLLMProvider(config)
        context = LLMContextSanitizer().sanitize(result, patient, meal_label)
        return LLMExplanationEnhancer(provider).enhance(context, result)


def _menu_item_to_dict(item: MenuItem) -> dict[str, object]:
    return {
        "itemId": item.item_id,
        "merchantId": item.merchant_id,
        "name": item.name,
        "nutrients": {
            "energyKcal": item.nutrients.energy_kcal,
            "carbsG": item.nutrients.carbs_g,
            "proteinG": item.nutrients.protein_g,
            "fatG": item.nutrients.fat_g,
            "sodiumMg": item.nutrients.sodium_mg,
            "sugarG": item.nutrients.sugar_g,
            "fiberG": item.nutrients.fiber_g,
        },
        "nutritionTags": [_concept_to_dict(code) for code in sorted(item.nutrition_tags, key=_concept_sort_key)],
        "tasteTags": [_concept_to_dict(code) for code in sorted(item.taste_tags, key=_concept_sort_key)],
        "available": item.available,
    }


def _concept_to_dict(code: ConceptCode) -> dict[str, str]:
    return {"kind": code.kind.value, "value": code.value}


def _concept_sort_key(code: ConceptCode) -> tuple[str, str]:
    return (code.kind.value, code.value)
```

- [ ] **Step 4: Run service tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_service -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/service.py tests/test_service.py
git commit -m "feat: add in-memory recommendation service"
```

---

### Task 4: FastAPI Server Endpoints

**Files:**
- Create: `src/medidiet/server.py`
- Create: `tests/test_http_server.py`

- [ ] **Step 1: Write failing HTTP tests**

Create `tests/test_http_server.py` with this content:

```python
from datetime import datetime, timezone
import unittest

from fastapi.testclient import TestClient


def patient_payload():
    return {
        "age": 65,
        "heightCm": 170,
        "weightKg": 72,
        "conditions": [{"kind": "condition", "value": "hypertension"}],
        "allergens": [],
        "contraindications": [],
        "preferences": {
            "tasteTags": [{"kind": "taste_tag", "value": "light"}],
            "dislikedIngredients": [],
            "maxPriceCents": 3000,
            "maxDistanceMeters": 1000,
        },
        "keyRiskFieldsConfirmed": True,
    }


def menu_payload():
    return {
        "items": [
            {
                "itemId": "steamed-fish-set",
                "name": "Steamed fish set",
                "ingredients": [{"kind": "ingredient", "value": "fish"}],
                "allergens": [],
                "tasteTags": [{"kind": "taste_tag", "value": "light"}],
                "nutritionTags": [
                    {"kind": "nutrition_tag", "value": "low_sodium"},
                    {"kind": "nutrition_tag", "value": "controlled_carbs"},
                    {"kind": "nutrition_tag", "value": "vegetable_rich"},
                ],
                "contraindicationTags": [],
                "nutrients": {
                    "energyKcal": 520,
                    "carbsG": 58,
                    "proteinG": 34,
                    "fatG": 14,
                    "sodiumMg": 520,
                    "sugarG": 6,
                    "fiberG": 7,
                },
            }
        ]
    }


class HTTPServerTest(unittest.TestCase):
    def make_client(self):
        from medidiet.llm import MockLLMProvider
        from medidiet.server import create_app
        from medidiet.service import RecommendationService

        service = RecommendationService(
            llm_provider=MockLLMProvider(
                explanation_payload={
                    "patientExplanation": "LLM patient explanation.",
                    "clinicianExplanation": "LLM clinician explanation.",
                }
            )
        )
        return TestClient(create_app(service))

    def test_health_returns_versions(self):
        client = self.make_client()

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["version"], "0.1.1")
        self.assertEqual(body["ruleVersion"], "baseline-2026-05-15")

    def test_recommendation_flow_returns_llm_explanation(self):
        client = self.make_client()
        self.assertEqual(client.put("/patients/patient-001", json=patient_payload()).status_code, 200)
        self.assertEqual(client.put("/menus/today", json=menu_payload()).status_code, 200)
        review_response = client.post(
            "/reviews/nutritionist",
            json={
                "patientId": "patient-001",
                "reviewerId": "nutritionist-1",
                "note": "请人工复核。",
                "createdAt": "2026-05-18T09:00:00+00:00",
            },
        )
        self.assertEqual(review_response.status_code, 200)

        response = client.post(
            "/recommendations",
            json={
                "patientId": "patient-001",
                "mealLabel": 3,
                "temporaryTasteTags": [{"kind": "taste_tag", "value": "light"}],
                "debug": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["outcome"], "recommended")
        self.assertEqual(body["recommendedItems"][0]["itemId"], "steamed-fish-set")
        self.assertEqual(body["explanation"]["patient"], "LLM patient explanation.")
        self.assertFalse(body["explanation"]["llm"]["usedFallback"])
        self.assertEqual(body["nutritionistReviews"][0]["note"], "请人工复核。")
        self.assertIn("traceId", body)
        self.assertIn("trace", body)

    def test_missing_patient_uses_uniform_error_response(self):
        client = self.make_client()

        response = client.post("/recommendations", json={"patientId": "missing", "mealLabel": 3})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "PATIENT_NOT_FOUND")

    def test_invalid_code_kind_returns_422(self):
        client = self.make_client()
        payload = patient_payload()
        payload["conditions"] = [{"kind": "allergen", "value": "peanut"}]

        response = client.put("/patients/patient-001", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_CODE_KIND")

    def test_intake_endpoint_appends_record(self):
        client = self.make_client()
        client.put("/patients/patient-001", json=patient_payload())

        response = client.post(
            "/patients/patient-001/intake-records",
            json={
                "foodLabel": "Breakfast porridge",
                "occurredAt": "2026-05-18T08:00:00+00:00",
                "mealLabel": 1,
                "portion": "1 bowl",
                "nutrients": {"energyKcal": 180, "carbsG": 30, "proteinG": 6, "fatG": 3},
                "confidence": 0.92,
                "manuallyCorrected": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intakeRecordCount"], 1)

    def test_debug_state_returns_counts(self):
        client = self.make_client()
        client.put("/patients/patient-001", json=patient_payload())
        client.put("/menus/today", json=menu_payload())

        response = client.get("/debug/state")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["todayMenuCount"], 1)
        self.assertEqual(response.json()["patients"], ["patient-001"])

    def test_validation_errors_use_uniform_error_response(self):
        client = self.make_client()

        response = client.put("/menus/today", json={"items": [{"itemId": "bad", "name": "Missing nutrients"}]})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_http_server -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'medidiet.server'`.

- [ ] **Step 3: Implement FastAPI server**

Create `src/medidiet/server.py` with this content:

```python
from __future__ import annotations

from datetime import datetime
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from medidiet.domain import DataSource, MealLabel
from medidiet.service import (
    ConceptCodeInput,
    IntakeRecordInput,
    MenuItemInput,
    NutrientsInput,
    NutritionistReviewInput,
    PatientProfileInput,
    PreferenceInput,
    RecommendationRequestInput,
    RecommendationService,
    ServiceError,
)


class ConceptCodeModel(BaseModel):
    kind: str
    value: str

    def to_input(self) -> ConceptCodeInput:
        return ConceptCodeInput(kind=self.kind, value=self.value)


class NutrientsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    energy_kcal: float = Field(0, alias="energyKcal")
    carbs_g: float = Field(0, alias="carbsG")
    protein_g: float = Field(0, alias="proteinG")
    fat_g: float = Field(0, alias="fatG")
    sodium_mg: float = Field(0, alias="sodiumMg")
    sugar_g: float = Field(0, alias="sugarG")
    fiber_g: float = Field(0, alias="fiberG")

    def to_input(self) -> NutrientsInput:
        return NutrientsInput(
            energy_kcal=self.energy_kcal,
            carbs_g=self.carbs_g,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            sodium_mg=self.sodium_mg,
            sugar_g=self.sugar_g,
            fiber_g=self.fiber_g,
        )


class PreferenceModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    taste_tags: list[ConceptCodeModel] = Field(default_factory=list, alias="tasteTags")
    disliked_ingredients: list[ConceptCodeModel] = Field(default_factory=list, alias="dislikedIngredients")
    max_price_cents: int | None = Field(None, alias="maxPriceCents")
    max_distance_meters: int | None = Field(None, alias="maxDistanceMeters")

    def to_input(self) -> PreferenceInput:
        return PreferenceInput(
            taste_tags=tuple(code.to_input() for code in self.taste_tags),
            disliked_ingredients=tuple(code.to_input() for code in self.disliked_ingredients),
            max_price_cents=self.max_price_cents,
            max_distance_meters=self.max_distance_meters,
        )


class PatientProfileModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    age: int
    height_cm: float = Field(alias="heightCm")
    weight_kg: float = Field(alias="weightKg")
    conditions: list[ConceptCodeModel] = Field(default_factory=list)
    allergens: list[ConceptCodeModel] = Field(default_factory=list)
    contraindications: list[ConceptCodeModel] = Field(default_factory=list)
    preferences: PreferenceModel = Field(default_factory=PreferenceModel)
    key_risk_fields_confirmed: bool = Field(False, alias="keyRiskFieldsConfirmed")

    def to_input(self) -> PatientProfileInput:
        return PatientProfileInput(
            age=self.age,
            height_cm=self.height_cm,
            weight_kg=self.weight_kg,
            conditions=tuple(code.to_input() for code in self.conditions),
            allergens=tuple(code.to_input() for code in self.allergens),
            contraindications=tuple(code.to_input() for code in self.contraindications),
            preferences=self.preferences.to_input(),
            key_risk_fields_confirmed=self.key_risk_fields_confirmed,
        )


class IntakeRecordModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    food_label: str = Field(alias="foodLabel")
    occurred_at: datetime = Field(alias="occurredAt")
    meal_label: int = Field(alias="mealLabel")
    portion: str
    nutrients: NutrientsModel
    confidence: float
    manually_corrected: bool = Field(False, alias="manuallyCorrected")

    def to_input(self) -> IntakeRecordInput:
        return IntakeRecordInput(
            food_label=self.food_label,
            occurred_at=self.occurred_at,
            meal_label=MealLabel(self.meal_label),
            portion=self.portion,
            nutrients=self.nutrients.to_input(),
            confidence=self.confidence,
            manually_corrected=self.manually_corrected,
        )


class MenuItemModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(alias="itemId")
    name: str
    nutrients: NutrientsModel
    ingredients: list[ConceptCodeModel] = Field(default_factory=list)
    allergens: list[ConceptCodeModel] = Field(default_factory=list)
    taste_tags: list[ConceptCodeModel] = Field(default_factory=list, alias="tasteTags")
    nutrition_tags: list[ConceptCodeModel] = Field(default_factory=list, alias="nutritionTags")
    contraindication_tags: list[ConceptCodeModel] = Field(default_factory=list, alias="contraindicationTags")
    merchant_id: str = Field("hospital-canteen", alias="merchantId")
    nutrition_confidence: float = Field(0.95, alias="nutritionConfidence")
    source: DataSource = DataSource.HUMAN_CURATED
    price_cents: int = Field(0, alias="priceCents")
    distance_meters: int = Field(0, alias="distanceMeters")
    merchant_reliability: float = Field(1.0, alias="merchantReliability")
    available: bool = True

    def to_input(self) -> MenuItemInput:
        return MenuItemInput(
            item_id=self.item_id,
            name=self.name,
            nutrients=self.nutrients.to_input(),
            ingredients=tuple(code.to_input() for code in self.ingredients),
            allergens=tuple(code.to_input() for code in self.allergens),
            taste_tags=tuple(code.to_input() for code in self.taste_tags),
            nutrition_tags=tuple(code.to_input() for code in self.nutrition_tags),
            contraindication_tags=tuple(code.to_input() for code in self.contraindication_tags),
            merchant_id=self.merchant_id,
            nutrition_confidence=self.nutrition_confidence,
            source=self.source,
            price_cents=self.price_cents,
            distance_meters=self.distance_meters,
            merchant_reliability=self.merchant_reliability,
            available=self.available,
        )


class TodayMenuModel(BaseModel):
    items: list[MenuItemModel]


class NutritionistReviewModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    patient_id: str = Field(alias="patientId")
    reviewer_id: str = Field(alias="reviewerId")
    note: str
    created_at: datetime = Field(alias="createdAt")

    def to_input(self) -> NutritionistReviewInput:
        return NutritionistReviewInput(
            patient_id=self.patient_id,
            reviewer_id=self.reviewer_id,
            note=self.note,
            created_at=self.created_at,
        )


class RecommendationRequestModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    patient_id: str = Field(alias="patientId")
    meal_label: int = Field(alias="mealLabel")
    temporary_taste_tags: list[ConceptCodeModel] = Field(default_factory=list, alias="temporaryTasteTags")
    debug: bool = False

    def to_input(self) -> RecommendationRequestInput:
        return RecommendationRequestInput(
            patient_id=self.patient_id,
            meal_label=MealLabel(self.meal_label),
            temporary_taste_tags=tuple(code.to_input() for code in self.temporary_taste_tags),
            debug=self.debug,
        )


def create_app(service: RecommendationService | None = None) -> FastAPI:
    service = service or RecommendationService()
    app = FastAPI(title="MediDiet HTTP API", version=_package_version())
    app.state.service = service

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        status_code = _status_code_for_error(exc.code)
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_MEAL_LABEL", "message": str(exc), "details": {}}},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request payload validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": _package_version(),
            "ruleVersion": service.rule_pack.version,
        }

    @app.put("/patients/{patient_id}")
    def put_patient(patient_id: str, payload: PatientProfileModel) -> dict[str, object]:
        patient = service.upsert_patient(patient_id, payload.to_input())
        return {"patientId": patient.patient_id, "stored": True}

    @app.post("/patients/{patient_id}/intake-records")
    def post_intake_record(patient_id: str, payload: IntakeRecordModel) -> dict[str, object]:
        service.append_intake_record(patient_id, payload.to_input())
        return {"patientId": patient_id, "intakeRecordCount": len(service.store.intake_records.get(patient_id, []))}

    @app.put("/menus/today")
    def put_today_menu(payload: TodayMenuModel) -> dict[str, object]:
        items = service.replace_today_menu(tuple(item.to_input() for item in payload.items))
        return {"menuItemCount": len(items)}

    @app.post("/reviews/nutritionist")
    def post_nutritionist_review(payload: NutritionistReviewModel) -> dict[str, object]:
        review = service.record_nutritionist_review(payload.to_input())
        return {"stored": True, "review": review.to_dict()}

    @app.post("/recommendations")
    def post_recommendation(payload: RecommendationRequestModel) -> dict[str, object]:
        result = service.recommend(payload.to_input())
        response: dict[str, object] = {
            "outcome": result.outcome,
            "recommendedItems": list(result.recommended_items),
            "explanation": {
                "patient": result.patient_explanation,
                "clinician": result.clinician_explanation,
                "llm": {
                    "usedFallback": result.llm_used_fallback,
                    "fallbackReason": result.llm_fallback_reason,
                },
            },
            "nutritionistReviews": list(result.nutritionist_reviews),
            "traceId": result.trace_id,
        }
        if result.trace is not None:
            response["trace"] = result.trace
        return response

    @app.get("/debug/state")
    def debug_state() -> dict[str, object]:
        return service.debug_state()

    return app


app = create_app()


def _status_code_for_error(code: str) -> int:
    if code == "PATIENT_NOT_FOUND":
        return 404
    if code == "MENU_NOT_CONFIGURED":
        return 409
    if code in {"INVALID_CODE_KIND", "INVALID_MEAL_LABEL", "INVALID_NUTRIENTS"}:
        return 422
    return 500


def _package_version() -> str:
    try:
        return version("medidiet")
    except PackageNotFoundError:
        return "0.1.1"
```

- [ ] **Step 4: Run HTTP tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_http_server -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/server.py tests/test_http_server.py
git commit -m "feat: add FastAPI HTTP server endpoints"
```

---

### Task 5: HTTP Error Robustness and LLM Fallback Behavior

**Files:**
- Modify: `src/medidiet/server.py`
- Modify: `tests/test_http_server.py`

- [ ] **Step 1: Append robustness tests**

Append this to `tests/test_http_server.py`:

```python
class HTTPServerFallbackTest(unittest.TestCase):
    def test_recommendation_succeeds_with_llm_provider_error(self):
        from medidiet.llm import MockLLMProvider
        from medidiet.server import create_app
        from medidiet.service import RecommendationService

        service = RecommendationService(llm_provider=MockLLMProvider(error=RuntimeError("provider down")))
        client = TestClient(create_app(service))
        client.put("/patients/patient-001", json=patient_payload())
        client.put("/menus/today", json=menu_payload())

        response = client.post("/recommendations", json={"patientId": "patient-001", "mealLabel": 3})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["outcome"], "recommended")
        self.assertTrue(body["explanation"]["llm"]["usedFallback"])
        self.assertEqual(body["explanation"]["llm"]["fallbackReason"], 6002)

    def test_missing_menu_returns_409(self):
        from medidiet.server import create_app
        from medidiet.service import RecommendationService

        client = TestClient(create_app(RecommendationService()))
        client.put("/patients/patient-001", json=patient_payload())

        response = client.post("/recommendations", json={"patientId": "patient-001", "mealLabel": 3})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "MENU_NOT_CONFIGURED")
```

- [ ] **Step 2: Run robustness tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_http_server.HTTPServerFallbackTest -v
```

Expected: PASS. If this fails, stop this task and use the systematic-debugging skill before changing code.

- [ ] **Step 3: Run service and HTTP tests together**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_service tests.test_http_server -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add tests/test_http_server.py
git commit -m "test: cover HTTP recommendation fallback behavior"
```

---

### Task 6: Public API and Documentation

**Files:**
- Modify: `src/medidiet/__init__.py`
- Modify: `tests/test_public_api.py`
- Modify: `docs/api.md`
- Modify: `docs/software-design.md`
- Modify: `docs/testing.md`
- Modify: `docs/usage.md`

- [ ] **Step 1: Write failing public API export test**

Append this method to `PublicApiTest` in `tests/test_public_api.py`:

```python
    def test_http_service_exports_are_available(self):
        from medidiet import RecommendationService, create_app

        self.assertEqual(RecommendationService.__name__, "RecommendationService")
        self.assertEqual(create_app.__name__, "create_app")
```

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api.PublicApiTest.test_http_service_exports_are_available -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 2: Export stable HTTP entrypoints**

Modify `src/medidiet/__init__.py`:

```python
from medidiet.server import create_app
from medidiet.service import RecommendationService
```

Add these names to `__all__`:

```python
    "RecommendationService",
    "create_app",
```

Also update the exact `medidiet.__all__` assertion in `tests/test_public_api.py` to include those two strings.

- [ ] **Step 3: Update docs**

In `docs/api.md`, add this section after the current public API section:

````markdown
## HTTP Server API

MediDiet also exposes a local FastAPI server for front-end integration.

Run:

```bash
uvicorn medidiet.server:app --app-dir src --reload
```

Key endpoints:

- `GET /health`
- `PUT /patients/{patient_id}`
- `POST /patients/{patient_id}/intake-records`
- `PUT /menus/today`
- `POST /reviews/nutritionist`
- `POST /recommendations`
- `GET /debug/state`

The server keeps MVP state in memory. It is intended for local or trusted internal development and does not include production authentication.
````

In `docs/software-design.md`:

- Add `service.py` and `server.py` to the directory tree.
- Add module responsibility rows:

```markdown
| `service.py` | In-memory application service for HTTP workflows and domain conversion. | `RecommendationService`, `InMemoryRecommendationStore` |
| `server.py` | FastAPI adapter and HTTP error mapping. | `create_app`, `app` |
```

In `docs/testing.md`:

- Add `tests/test_service.py`, `tests/test_http_server.py`, and `tests/test_http_llm_smoke.py` to the test file overview.
- Update the total test count after running the full suite in Task 8.

In `docs/usage.md`, add:

````markdown
## Local HTTP Server

Install dependencies:

```bash
python -m pip install -e .
```

Run the API:

```bash
uvicorn medidiet.server:app --app-dir src --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```
````

- [ ] **Step 4: Run public API and docs-adjacent tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_public_api tests.test_http_server -v
git diff --check
```

Expected: PASS and no whitespace errors.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/medidiet/__init__.py tests/test_public_api.py docs/api.md docs/software-design.md docs/testing.md docs/usage.md
git commit -m "docs: expose HTTP server API"
```

---

### Task 7: Opt-In HTTP Recommendation Test With Real LLM

**Files:**
- Create: `tests/test_http_llm_smoke.py`
- Modify: `docs/testing.md`
- Modify: `docs/usage.md`

- [ ] **Step 1: Write skipped-by-default HTTP LLM smoke test**

Create `tests/test_http_llm_smoke.py` with this content:

```python
import os
import unittest

from fastapi.testclient import TestClient

from medidiet.server import create_app
from medidiet.service import RecommendationService


def _smoke_enabled() -> bool:
    required = (
        "MEDIDIET_LLM_SMOKE_TEST",
        "MEDIDIET_LLM_PROVIDER",
        "MEDIDIET_LLM_BASE_URL",
        "MEDIDIET_LLM_API_KEY",
        "MEDIDIET_LLM_MODEL",
    )
    return os.getenv("MEDIDIET_LLM_SMOKE_TEST") == "1" and all(os.getenv(name) for name in required)


def patient_payload():
    return {
        "age": 65,
        "heightCm": 170,
        "weightKg": 72,
        "conditions": [{"kind": "condition", "value": "hypertension"}],
        "allergens": [],
        "contraindications": [],
        "preferences": {
            "tasteTags": [{"kind": "taste_tag", "value": "light"}],
            "dislikedIngredients": [],
            "maxPriceCents": 3000,
            "maxDistanceMeters": 1000,
        },
        "keyRiskFieldsConfirmed": True,
    }


def menu_payload():
    return {
        "items": [
            {
                "itemId": "steamed-fish-set",
                "name": "Steamed fish set",
                "ingredients": [{"kind": "ingredient", "value": "fish"}],
                "allergens": [],
                "tasteTags": [{"kind": "taste_tag", "value": "light"}],
                "nutritionTags": [
                    {"kind": "nutrition_tag", "value": "low_sodium"},
                    {"kind": "nutrition_tag", "value": "controlled_carbs"},
                    {"kind": "nutrition_tag", "value": "vegetable_rich"},
                ],
                "contraindicationTags": [],
                "nutrients": {
                    "energyKcal": 520,
                    "carbsG": 58,
                    "proteinG": 34,
                    "fatG": 14,
                    "sodiumMg": 520,
                    "sugarG": 6,
                    "fiberG": 7,
                },
            }
        ]
    }


@unittest.skipUnless(
    _smoke_enabled(),
    "HTTP LLM smoke test requires MEDIDIET_LLM_SMOKE_TEST=1 and complete LLM env vars",
)
class HTTPLLMSmokeTest(unittest.TestCase):
    def test_http_recommendation_returns_real_llm_explanation(self):
        client = TestClient(create_app(RecommendationService()))
        self.assertEqual(client.put("/patients/patient-001", json=patient_payload()).status_code, 200)
        self.assertEqual(client.put("/menus/today", json=menu_payload()).status_code, 200)

        response = client.post(
            "/recommendations",
            json={
                "patientId": "patient-001",
                "mealLabel": 3,
                "temporaryTasteTags": [{"kind": "taste_tag", "value": "light"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["outcome"], "recommended")
        self.assertFalse(
            body["explanation"]["llm"]["usedFallback"],
            f"LLM fallback reason: {body['explanation']['llm']['fallbackReason']}",
        )
        self.assertIsNone(body["explanation"]["llm"]["fallbackReason"])
        self.assertGreater(len(body["explanation"]["patient"].strip()), 0)
        self.assertEqual(body["recommendedItems"][0]["itemId"], "steamed-fish-set")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run smoke test without env and verify it skips**

Run:

```bash
env -u MEDIDIET_LLM_SMOKE_TEST -u MEDIDIET_LLM_PROVIDER -u MEDIDIET_LLM_BASE_URL -u MEDIDIET_LLM_API_KEY -u MEDIDIET_LLM_MODEL PYTHONPATH=src python -m unittest tests.test_http_llm_smoke -v
```

Expected: OK with `skipped=1`.

- [ ] **Step 3: Run smoke test with `.env` when the user asks for real API validation**

Run only when `.env` has valid LLM credentials and the user explicitly wants the real call:

```bash
set -a; source .env; set +a
PYTHONPATH=src python -m unittest tests.test_http_llm_smoke -v
```

Expected: PASS. The test calls the HTTP recommendation endpoint through FastAPI `TestClient`, uses the real OpenAI-compatible LLM provider through `RecommendationService`, and asserts `usedFallback=false`.

- [ ] **Step 4: Document the opt-in HTTP LLM smoke test**

Add this paragraph to the LLM testing section in `docs/testing.md`:

```markdown
`tests/test_http_llm_smoke.py` verifies the full HTTP recommendation path with a real OpenAI-compatible LLM provider. It is skipped by default and only runs when `MEDIDIET_LLM_SMOKE_TEST=1` and complete LLM environment variables are set.
```

Add this command to the LLM section in `docs/usage.md`:

```bash
set -a; source .env; set +a
PYTHONPATH=src python -m unittest tests.test_http_llm_smoke -v
```

- [ ] **Step 5: Run offline tests and commit**

Run:

```bash
env -u MEDIDIET_LLM_SMOKE_TEST -u MEDIDIET_LLM_PROVIDER -u MEDIDIET_LLM_BASE_URL -u MEDIDIET_LLM_API_KEY -u MEDIDIET_LLM_MODEL PYTHONPATH=src python -m unittest tests.test_http_llm_smoke -v
git diff --check
```

Expected: HTTP LLM smoke test reports `OK (skipped=1)` and `git diff --check` prints nothing.

Commit:

```bash
git add tests/test_http_llm_smoke.py docs/testing.md docs/usage.md
git commit -m "test: add opt-in HTTP LLM smoke test"
```

---

### Task 8: Full Verification and Local Server Smoke Check

- [ ] **Step 1: Run full offline test suite**

Run:

```bash
env -u MEDIDIET_LLM_SMOKE_TEST -u MEDIDIET_LLM_PROVIDER -u MEDIDIET_LLM_BASE_URL -u MEDIDIET_LLM_API_KEY -u MEDIDIET_LLM_MODEL PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS. The real DeepSeek smoke test should be skipped unless explicitly enabled.

- [ ] **Step 2: Run CLI smoke check**

Run:

```bash
PYTHONPATH=src python -m medidiet.cli
```

Expected: command exits 0 and prints trace JSON with `"outcome": "recommended"`.

- [ ] **Step 3: Start local HTTP server briefly**

Run:

```bash
PYTHONPATH=src uvicorn medidiet.server:app --host 127.0.0.1 --port 8000
```

Expected: server starts and logs that Uvicorn is running on `http://127.0.0.1:8000`.

Leave the process running for Step 4.

- [ ] **Step 4: Check health endpoint from another shell**

Run:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected response contains:

```json
{"status":"ok","version":"0.1.1","ruleVersion":"baseline-2026-05-15"}
```

Stop the uvicorn process with `Ctrl-C`.

- [ ] **Step 5: Run whitespace and git status checks**

Run:

```bash
git diff --check
git status --short --branch
```

Expected:

- `git diff --check` prints nothing.
- Only pre-existing unrelated untracked local files remain.
- `.env` remains ignored and is not staged.

## Final Verification

After all tasks are complete, run:

```bash
env -u MEDIDIET_LLM_SMOKE_TEST -u MEDIDIET_LLM_PROVIDER -u MEDIDIET_LLM_BASE_URL -u MEDIDIET_LLM_API_KEY -u MEDIDIET_LLM_MODEL PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m medidiet.cli
git diff --check
git status --short --branch
git log --oneline -8
```

Optional real LLM smoke test only when `.env` is configured and the user explicitly asks for it:

```bash
set -a; source .env; set +a
PYTHONPATH=src python -m unittest tests.test_llm_deepseek_smoke -v
PYTHONPATH=src python -m unittest tests.test_http_llm_smoke -v
```

## Expected Commit Series

1. `chore: add FastAPI server dependencies`
2. `feat: add HTTP service DTO conversions`
3. `feat: add in-memory recommendation service`
4. `feat: add FastAPI HTTP server endpoints`
5. `test: cover HTTP recommendation fallback behavior`
6. `docs: expose HTTP server API`
7. `test: add opt-in HTTP LLM smoke test`
