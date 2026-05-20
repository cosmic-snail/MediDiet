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
from medidiet.ports import KnowledgePort
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
    try:
        return ConceptCode(kind, input_code.value)
    except ValueError as exc:
        raise ServiceError(
            ServiceErrorCode.INVALID_CODE_KIND,
            str(exc),
            {"expectedKind": expected_kind.value, "actualKind": kind.value, "value": input_code.value},
        ) from exc


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
        knowledge: KnowledgePort | None = None,
        now: datetime | None = None,
    ):
        self.rule_pack = rule_pack or load_baseline_rule_pack()
        self.store = store or InMemoryRecommendationStore()
        self.llm_provider = llm_provider
        self.knowledge = knowledge
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
        engine = RecommendationEngine(self.rule_pack, now=self.now, knowledge=self.knowledge)
        result = engine.recommend(
            patient_for_request,
            self.store.intake_records.get(input_request.patient_id, []),
            list(self.store.today_menu),
            input_request.meal_label,
        )
        enhanced = self._enhance_explanation(result, patient_for_request, input_request.meal_label)
        reviews = tuple(
            review.to_dict() for review in self.store.nutritionist_reviews.get(input_request.patient_id, [])[-5:]
        )

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
