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
        return JSONResponse(
            status_code=_status_code_for_error(exc.code),
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


app = create_app()
