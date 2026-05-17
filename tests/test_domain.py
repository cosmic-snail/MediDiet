import unittest

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    ConceptDefinition,
    ConceptRegistry,
    Confidence,
    DataSource,
    MenuItem,
    Nutrients,
    Outcome,
    PatientProfile,
    Preference,
)


class DomainSmokeTest(unittest.TestCase):
    def test_package_imports(self):
        import medidiet

        self.assertEqual(medidiet.__version__, "0.1.0")


class DomainModelTest(unittest.TestCase):
    def setUp(self):
        self.registry = ConceptRegistry(
            [
                ConceptDefinition(ConceptCode(CodeKind.CONDITION, "hypertension"), "高血压", aliases=("高血压", "hypertension")),
                ConceptDefinition(ConceptCode(CodeKind.ALLERGEN, "peanut"), "花生", aliases=("花生", "peanut")),
                ConceptDefinition(ConceptCode(CodeKind.ALLERGEN, "shrimp"), "虾", aliases=("虾", "shrimp")),
                ConceptDefinition(ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium"), "高钠禁忌"),
                ConceptDefinition(ConceptCode(CodeKind.TASTE_TAG, "light"), "清淡"),
                ConceptDefinition(ConceptCode(CodeKind.INGREDIENT, "chicken"), "鸡肉"),
            ]
        )

    def test_registry_returns_registered_concept_codes(self):
        code = self.registry.require(CodeKind.CONDITION, "hypertension")

        self.assertEqual(code.kind, CodeKind.CONDITION)
        self.assertEqual(code.value, "hypertension")
        self.assertEqual(self.registry.resolve_alias(CodeKind.ALLERGEN, "花生").value, "peanut")

    def test_registry_rejects_unknown_or_malformed_codes(self):
        with self.assertRaises(ValueError):
            self.registry.require(CodeKind.CONDITION, "kidney_disease")
        with self.assertRaises(ValueError):
            ConceptCode(CodeKind.CONDITION, "")
        with self.assertRaises(ValueError):
            ConceptCode(CodeKind.CONDITION, "High Sodium")
        with self.assertRaises(ValueError):
            ConceptCode(CodeKind.CONDITION, " high_sodium")

    def test_patient_profile_uses_concept_codes_for_medical_constraints(self):
        hypertension = self.registry.require(CodeKind.CONDITION, "hypertension")
        peanut = self.registry.require(CodeKind.ALLERGEN, "peanut")
        high_sodium = self.registry.require(CodeKind.CONTRAINDICATION, "high_sodium")
        light = self.registry.require(CodeKind.TASTE_TAG, "light")

        profile = PatientProfile(
            patient_id="p-1",
            age=45,
            height_cm=170.5,
            weight_kg=80.2,
            conditions={hypertension},
            allergens={peanut},
            contraindications={high_sodium},
            preferences=Preference(taste_tags={light}),
            key_risk_fields_confirmed=False,
            source=DataSource.PATIENT_REPORTED,
        )

        self.assertFalse(profile.key_risk_fields_confirmed)
        self.assertIn(hypertension, profile.conditions)
        self.assertIn(peanut, profile.allergens)
        self.assertIn(high_sodium, profile.contraindications)
        self.assertIn(light, profile.preferences.taste_tags)

    def test_patient_profile_rejects_wrong_code_kinds(self):
        peanut = self.registry.require(CodeKind.ALLERGEN, "peanut")
        hypertension = self.registry.require(CodeKind.CONDITION, "hypertension")

        with self.assertRaises(TypeError):
            PatientProfile(
                patient_id="p-1",
                age=45,
                height_cm=170,
                weight_kg=80,
                conditions={peanut},
                allergens=set(),
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )
        with self.assertRaises(TypeError):
            PatientProfile(
                patient_id="p-1",
                age=45,
                height_cm=170,
                weight_kg=80,
                conditions={hypertension},
                allergens={hypertension},
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )

    def test_patient_profile_rejects_invalid_numeric_boundaries(self):
        hypertension = self.registry.require(CodeKind.CONDITION, "hypertension")

        for field, value in [("age", -1), ("age", 200), ("height_cm", 0), ("weight_kg", -10)]:
            payload = dict(
                patient_id="p-1",
                age=45,
                height_cm=170,
                weight_kg=80,
                conditions={hypertension},
                allergens=set(),
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )
            payload[field] = value
            with self.assertRaises(ValueError):
                PatientProfile(**payload)

    def test_nutrients_accept_float_values_and_add(self):
        total = Nutrients(energy_kcal=100.5, carbs_g=10.25, protein_g=5.5, fat_g=2, sodium_mg=300.5, sugar_g=1, fiber_g=2)
        total += Nutrients(energy_kcal=50.25, carbs_g=5.25, protein_g=3, fat_g=1, sodium_mg=100.25, sugar_g=2, fiber_g=1)

        self.assertAlmostEqual(total.energy_kcal, 150.75)
        self.assertAlmostEqual(total.carbs_g, 15.5)
        self.assertAlmostEqual(total.sodium_mg, 400.75)
        self.assertEqual(total.sugar_g, 3)

    def test_nutrients_reject_negative_non_finite_and_absurd_values(self):
        for kwargs in [
            {"sodium_mg": -1},
            {"energy_kcal": float("inf")},
            {"sodium_mg": 1_000_001},
        ]:
            with self.assertRaises(ValueError):
                Nutrients(**kwargs)

    def test_menu_item_allergen_matching_uses_code_sets(self):
        peanut = self.registry.require(CodeKind.ALLERGEN, "peanut")
        shrimp = self.registry.require(CodeKind.ALLERGEN, "shrimp")
        light = self.registry.require(CodeKind.TASTE_TAG, "light")
        chicken = self.registry.require(CodeKind.INGREDIENT, "chicken")

        item = MenuItem(
            item_id="m-1",
            merchant_id="shop-1",
            name="Peanut Chicken Bowl",
            ingredients={chicken},
            allergens={peanut},
            taste_tags={light},
            nutrients=Nutrients(energy_kcal=560, carbs_g=55, protein_g=32, fat_g=22, sodium_mg=900, sugar_g=8, fiber_g=4),
            nutrition_confidence=Confidence(0.9),
            source=DataSource.MERCHANT_LABEL,
            price_cents=3200,
            distance_meters=900,
            merchant_reliability=0.8,
        )

        self.assertTrue(item.contains_allergen(peanut))
        self.assertFalse(item.contains_allergen(shrimp))
        self.assertEqual(Outcome.RECOMMENDED.value, "recommended")


if __name__ == "__main__":
    unittest.main()
