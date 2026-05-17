from __future__ import annotations

from datetime import datetime, timezone

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
from medidiet.rules import load_baseline_rule_pack


DEMO_NOW = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)


def demo_request() -> tuple[PatientProfile, list[IntakeRecord], list[MenuItem], MealLabel]:
    rule_pack = load_baseline_rule_pack()
    patient = PatientProfile(
        patient_id="demo-patient",
        age=52,
        height_cm=170,
        weight_kg=80,
        conditions={
            rule_pack.concepts.require(CodeKind.CONDITION, "hypertension"),
            rule_pack.concepts.require(CodeKind.CONDITION, "diabetes"),
        },
        allergens={ConceptCode(CodeKind.ALLERGEN, "shrimp")},
        contraindications=set(),
        preferences=Preference(
            taste_tags={ConceptCode(CodeKind.TASTE_TAG, "light")},
            max_price_cents=4000,
            max_distance_meters=2000,
        ),
        key_risk_fields_confirmed=True,
        source=DataSource.PATIENT_REPORTED,
    )
    intake_records = [
        IntakeRecord(
            food_label="salty noodles",
            occurred_at=DEMO_NOW,
            meal_label=MealLabel.LUNCH,
            portion="one bowl",
            nutrients=Nutrients(energy_kcal=620, carbs_g=80, protein_g=20, fat_g=18, sodium_mg=600, sugar_g=6, fiber_g=4),
            confidence=Confidence(0.86),
            source=DataSource.SYSTEM_ESTIMATED,
        )
    ]
    menu_items = [
        MenuItem(
            item_id="steamed-fish-set",
            merchant_id="canteen-1",
            name="Steamed fish set",
            ingredients={
                ConceptCode(CodeKind.INGREDIENT, "fish"),
                ConceptCode(CodeKind.INGREDIENT, "brown_rice"),
                ConceptCode(CodeKind.INGREDIENT, "greens"),
            },
            allergens=set(),
            taste_tags={ConceptCode(CodeKind.TASTE_TAG, "light")},
            nutrition_tags={
                rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "low_sodium"),
                rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "controlled_carbs"),
                rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "vegetable_rich"),
                rule_pack.concepts.require(CodeKind.NUTRITION_TAG, "lean_protein"),
            },
            contraindication_tags=set(),
            nutrients=Nutrients(energy_kcal=560, carbs_g=55, protein_g=35, fat_g=16, sodium_mg=430, sugar_g=5, fiber_g=7),
            nutrition_confidence=Confidence(0.92),
            source=DataSource.HUMAN_CURATED,
            price_cents=3600,
            distance_meters=500,
            merchant_reliability=0.95,
        ),
        MenuItem(
            item_id="closed-fried-pork-rice",
            merchant_id="delivery-1",
            name="Fried pork rice",
            ingredients={ConceptCode(CodeKind.INGREDIENT, "pork"), ConceptCode(CodeKind.INGREDIENT, "white_rice")},
            allergens=set(),
            taste_tags=set(),
            nutrition_tags=set(),
            contraindication_tags={rule_pack.concepts.require(CodeKind.CONTRAINDICATION, "deep_fried")},
            nutrients=Nutrients(energy_kcal=650, carbs_g=70, protein_g=28, fat_g=26, sodium_mg=680, sugar_g=8, fiber_g=2),
            nutrition_confidence=Confidence(0.8),
            source=DataSource.SYSTEM_ESTIMATED,
            price_cents=3200,
            distance_meters=900,
            merchant_reliability=0.7,
            available=False,
        ),
    ]
    return patient, intake_records, menu_items, MealLabel.DINNER
