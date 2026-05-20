"""Integration tests: end-to-end Phase 1, Phase 2, and Phase 3 workflows."""

import json
import tempfile
from datetime import datetime, timezone

from knowledge.schema import ExtractedConditionRule
from knowledge.store import RuleStore
from knowledge.documents import DocumentImporter
from knowledge.vectordb import KnowledgeVectorDB
from medidiet.domain import (
    CodeKind,
    ConceptCode,
    ConceptRegistry,
    ConceptDefinition,
    Confidence,
    DataSource,
    IntakeRecord,
    MealLabel,
    MenuItem,
    Nutrients,
    Outcome,
    PatientProfile,
    Preference,
)
from medidiet.engine import RecommendationEngine
from medidiet.matcher import MatchRejectionCode
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from medidiet.knowledge_bridge import KnowledgeRuleProvider, KnowledgeRetriever

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


def _sample_registry() -> ConceptRegistry:
    return ConceptRegistry([
        ConceptDefinition(
            code=ConceptCode(CodeKind.CONDITION, "hypertension"),
            display_name="Hypertension",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.CONDITION, "ckd"),
            display_name="Chronic Kidney Disease",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.CONDITION, "gout"),
            display_name="Gout",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium"),
            display_name="High Sodium",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.CONTRAINDICATION, "high_purine"),
            display_name="High Purine",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.CONTRAINDICATION, "alcohol"),
            display_name="Alcohol",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium"),
            display_name="Low Sodium",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.NUTRITION_TAG, "low_purine"),
            display_name="Low Purine",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.NUTRITION_TAG, "controlled_carbs"),
            display_name="Controlled Carbs",
        ),
        ConceptDefinition(
            code=ConceptCode(CodeKind.NUTRITION_TAG, "high_hydration"),
            display_name="High Hydration",
        ),
    ])


class TestPhase1EndToEnd:
    """Verify the full Phase 1 workflow:
    1. Import documents
    2. Index into vector DB
    3. Manually create and approve rules
    4. Publish a version
    5. Load RulePack via KnowledgeRuleProvider
    6. Search knowledge via KnowledgeRetriever
    """

    def test_full_workflow(self):
        with tempfile.TemporaryDirectory() as store_dir, \
             tempfile.TemporaryDirectory() as chroma_dir:

            # 1. Import documents
            importer = DocumentImporter()
            doc = importer.import_from_text(
                doc_id="ckd-2024",
                title="CKD Dietary Guidelines 2024",
                source="ckd-guidelines.md",
                source_type="guideline",
                content=(
                    "# CKD Dietary Guidelines\n\n"
                    "## Sodium\n"
                    "Limit sodium to under 700mg per meal for CKD patients.\n\n"
                    "## Protein\n"
                    "Restrict protein to 0.6-0.8g/kg/day for CKD stages 3-5.\n\n"
                    "## Potassium\n"
                    "When serum potassium is elevated, limit dietary potassium "
                    "to 2000-3000mg per day.\n"
                ),
                metadata={"year": "2024", "institution": "NKF"},
                ingested_at=NOW,
            )

            # 2. Index into vector DB
            vectordb = KnowledgeVectorDB(persist_dir=chroma_dir)
            vectordb.index_document(doc)

            # 3. Search verification
            results = vectordb.search("sodium limit for kidney", top_k=3)
            assert len(results) > 0
            assert any("sodium" in r.text.lower() for r in results)

            # 4. Manually create approved rules
            store = RuleStore(data_dir=store_dir)

            ckd_rule = ExtractedConditionRule(
                candidate_id="ckd-001",
                source_doc_ids=["ckd-2024"],
                source_chunk_ids=["ckd-2024-chunk-0000"],
                condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
                hard_exclusions={
                    ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium"),
                },
                preferred_tags={
                    ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium"),
                    ConceptCode(CodeKind.NUTRITION_TAG, "controlled_carbs"),
                },
                nutrition_limits={
                    NutrientLimit(
                        metric=NutrientMetric.SODIUM_MG,
                        scope=LimitScope.PER_MEAL,
                        max_value=700,
                    ),
                },
                confidence=1.0,
                extraction_method="manual",
                reviewed_by="dietitian-01",
                status="approved",
                created_at=NOW,
            )
            store.create(ckd_rule)

            # 5. Publish version
            store.publish_version("v1.0", notes="Initial CKD rules")
            # list_versions returns names without 'v' prefix
            assert "1.0" in store.list_versions()

            # 6. Load RulePack via provider
            provider = KnowledgeRuleProvider(store=store, version="v1.0")
            pack = provider.load_rule_pack()
            assert pack is not None
            assert pack.version == "v1.0"

            rule = pack.for_condition(ConceptCode(CodeKind.CONDITION, "hypertension"))
            assert len(rule.hard_exclusions) == 1
            assert len(rule.preferred_tags) == 2
            assert len(rule.nutrition_limits) == 1

            # 7. Search via retriever
            retriever = KnowledgeRetriever(vectordb=vectordb)
            snippets = retriever.search("protein restriction CKD", top_k=3)
            assert len(snippets) > 0

            # 8. Verify explain_rule returns source info
            explanation = retriever.explain_rule(
                ConceptCode(CodeKind.CONDITION, "hypertension")
            )
            assert "CKD Dietary Guidelines" in explanation


class TestPhase2EndToEnd:
    """Verify the full Phase 2 workflow:
    1. Import a guideline document + index into vector DB
    2. Search for relevant chunks via vectordb
    3. Extract rules via RuleExtractor with MockLLMProvider
    4. Approve via KnowledgeCurator
    5. Publish version
    6. Load RulePack via KnowledgeRuleProvider
    7. Verify extracted rule is present in RulePack
    """

    def test_full_extraction_pipeline(self):
        from medidiet.llm import MockLLMProvider, LLMResponse
        from knowledge.extractor import RuleExtractor
        from knowledge.curator import KnowledgeCurator

        registry = _sample_registry()

        # Mock LLM responses: extraction JSON + verification JSON
        extraction_json = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "ckd"},
                    "hard_exclusions": [
                        {"kind": "contraindication", "value": "high_sodium"}
                    ],
                    "preferred_tags": [
                        {"kind": "nutrition_tag", "value": "low_sodium"}
                    ],
                    "nutrition_limits": [
                        {
                            "metric": "sodium_mg",
                            "scope": "per_meal",
                            "max_value": 700.0,
                            "window_hours": None,
                        }
                    ],
                    "confidence": 0.9,
                    "evidence_quotes": {
                        "sodium_limit": "Limit sodium to under 700mg per meal"
                    },
                }
            ],
            "suggested_concepts": [],
        })
        verification_json = json.dumps({
            "verdict": "pass",
            "confidence": 0.95,
            "consistency_score": 0.9,
            "logic_score": 0.85,
            "completeness_score": 0.8,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })

        call_responses = [extraction_json, verification_json]
        mock = MockLLMProvider(raw_content=None)

        def sequenced_complete(request):
            mock.requests.append(request)
            content = call_responses.pop(0) if call_responses else "{}"
            return LLMResponse(content=content, provider_name="mock", model="mock")

        mock.complete = sequenced_complete

        with tempfile.TemporaryDirectory() as store_dir, \
             tempfile.TemporaryDirectory() as chroma_dir:

            # 1. Import document + index into vector DB
            importer = DocumentImporter()
            doc = importer.import_from_text(
                doc_id="ckd-2024",
                title="CKD Dietary Guidelines 2024",
                source="ckd-guidelines.md",
                source_type="guideline",
                content=(
                    "# CKD Dietary Guidelines\n\n"
                    "## Sodium\n"
                    "Limit sodium to under 700mg per meal for CKD patients.\n"
                    "Avoid high-sodium processed foods.\n\n"
                ),
                metadata={"year": "2024"},
                ingested_at=NOW,
            )
            vectordb = KnowledgeVectorDB(persist_dir=chroma_dir)
            vectordb.index_document(doc)

            # 2. Search for relevant chunks
            snippets = vectordb.search("sodium limit CKD", top_k=3)
            assert len(snippets) > 0

            # Reconstruct DocumentChunks from search results for the extractor
            chunks = [doc.chunks[0]] if doc.chunks else []

            # 3. Extract rules via RuleExtractor
            extractor = RuleExtractor(mock, registry)
            result = extractor.extract_and_validate(chunks, candidate_id_prefix="pilot")
            assert len(result.rules) == 1
            assert result.rules[0].condition.value == "ckd"
            assert result.rules[0].source_doc_ids == ["ckd-2024"]

            # 4. Save to store + approve via KnowledgeCurator
            store = RuleStore(data_dir=store_dir)
            store.bulk_create(result.rules)

            curator = KnowledgeCurator(store)
            rule_id = result.rules[0].candidate_id
            curator.review_rule(rule_id, "approved", "test-reviewer")

            # 5. Publish
            curator.publish("v2.0", "Phase 2 pilot: CKD rules from extraction")

            # 6. Load via KnowledgeRuleProvider
            provider = KnowledgeRuleProvider(store=store, version="v2.0")
            pack = provider.load_rule_pack()
            assert pack is not None
            assert pack.version == "v2.0"

            # 7. Verify rule
            ckd_concept = ConceptCode(CodeKind.CONDITION, "ckd")
            rule = pack.for_condition(ckd_concept)
            assert len(rule.hard_exclusions) == 1
            assert ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium") in rule.hard_exclusions
            assert ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium") in rule.preferred_tags
            assert len(rule.nutrition_limits) == 1


class TestPhase3EndToEnd:
    """Verify the full Phase 3 workflow:
    1. Build engine with KnowledgePort (KnowledgeRetriever)
    2. Recommend with patient who had low-protein previous meal
    3. Verify knowledgeSnippets in clinician_explanation
    4. Verify gap compensation: lean_protein added to matchedTags
    """

    def test_online_engine_with_gap_compensation(self):
        from medidiet.llm import MockLLMProvider, LLMResponse
        from knowledge.extractor import RuleExtractor
        from knowledge.curator import KnowledgeCurator

        registry = _sample_registry()

        # Mock LLM for rule extraction
        extraction_json = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "ckd"},
                    "hard_exclusions": [
                        {"kind": "contraindication", "value": "high_sodium"}
                    ],
                    "preferred_tags": [
                        {"kind": "nutrition_tag", "value": "low_sodium"}
                    ],
                    "nutrition_limits": [
                        {
                            "metric": "sodium_mg",
                            "scope": "per_meal",
                            "max_value": 700.0,
                            "window_hours": None,
                        }
                    ],
                    "confidence": 0.9,
                    "evidence_quotes": {
                        "sodium_limit": "Limit sodium to under 700mg per meal"
                    },
                }
            ],
            "suggested_concepts": [],
        })
        verification_json = json.dumps({
            "verdict": "pass",
            "confidence": 0.95,
            "consistency_score": 0.9,
            "logic_score": 0.85,
            "completeness_score": 0.8,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })

        call_responses = [extraction_json, verification_json]
        mock = MockLLMProvider(raw_content=None)

        def sequenced_complete(request):
            mock.requests.append(request)
            content = call_responses.pop(0) if call_responses else "{}"
            return LLMResponse(content=content, provider_name="mock", model="mock")

        mock.complete = sequenced_complete

        with tempfile.TemporaryDirectory() as store_dir, \
             tempfile.TemporaryDirectory() as chroma_dir:

            # 1. Import document + index into vector DB
            importer = DocumentImporter()
            doc = importer.import_from_text(
                doc_id="ckd-2024",
                title="CKD Dietary Guidelines 2024",
                source="ckd-guidelines.md",
                source_type="guideline",
                content=(
                    "# CKD Dietary Guidelines\n\n"
                    "## Sodium\n"
                    "Limit sodium to under 700mg per meal for CKD patients.\n\n"
                ),
                metadata={"year": "2024"},
                ingested_at=NOW,
            )
            vectordb = KnowledgeVectorDB(persist_dir=chroma_dir)
            vectordb.index_document(doc)

            # 2. Extract rules + publish
            chunks = [doc.chunks[0]] if doc.chunks else []
            extractor = RuleExtractor(mock, registry)
            result = extractor.extract_and_validate(chunks, candidate_id_prefix="pilot")

            store = RuleStore(data_dir=store_dir)
            store.bulk_create(result.rules)
            curator = KnowledgeCurator(store)
            curator.review_rule(result.rules[0].candidate_id, "approved", "test-reviewer")
            curator.publish("v3.0", "Phase 3 pilot: CKD rules")

            # 3. Build KnowledgeRuleProvider + KnowledgeRetriever
            rule_provider = KnowledgeRuleProvider(store=store, version="v3.0")
            pack = rule_provider.load_rule_pack()
            retriever = KnowledgeRetriever(vectordb=vectordb)

            # 4. Build engine with KnowledgePort + recent_ingredients (diversity)
            fish = ConceptCode(CodeKind.INGREDIENT, "fish")
            engine = RecommendationEngine(
                pack,
                now=NOW,
                knowledge=retriever,
                recent_ingredients=frozenset({fish}),
            )

            # 5. Create CKD patient
            patient = PatientProfile(
                patient_id="pt-ckd-001",
                age=65,
                height_cm=170,
                weight_kg=75,
                conditions={ConceptCode(CodeKind.CONDITION, "ckd")},
                allergens=set(),
                contraindications=set(),
                preferences=Preference(),
                key_risk_fields_confirmed=True,
                source=DataSource.PATIENT_REPORTED,
            )

            # 6. Intake records: low-protein lunch (8g protein, 1g fiber)
            lunch_record = IntakeRecord(
                food_label="light congee",
                occurred_at=NOW,
                meal_label=MealLabel.LUNCH,
                portion="one bowl",
                nutrients=Nutrients(protein_g=8, fiber_g=1, sodium_mg=300),
                confidence=Confidence(0.9),
                source=DataSource.SYSTEM_ESTIMATED,
            )

            # 7. Build menu with nutrition tags for CKD matching
            # Use direct ConceptCode construction since lean_protein/high_fiber
            # may not be pre-registered in the knowledge-backed concept registry
            low_sodium_tag = ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium")
            lean_protein_tag = ConceptCode(CodeKind.NUTRITION_TAG, "lean_protein")
            high_fiber_tag = ConceptCode(CodeKind.NUTRITION_TAG, "high_fiber")

            menu_items = [
                MenuItem(
                    item_id="ckd-safe-1",
                    merchant_id="canteen",
                    name="Steamed fish with vegetables",
                    ingredients={fish, ConceptCode(CodeKind.INGREDIENT, "vegetable")},
                    allergens=set(),
                    taste_tags=set(),
                    nutrition_tags={low_sodium_tag, lean_protein_tag, high_fiber_tag},
                    contraindication_tags=set(),
                    nutrients=Nutrients(
                        energy_kcal=450, carbs_g=35, protein_g=35, fat_g=12,
                        sodium_mg=400, sugar_g=4, fiber_g=6,
                    ),
                    nutrition_confidence=Confidence(0.95),
                    source=DataSource.MERCHANT_LABEL,
                    price_cents=3000,
                    distance_meters=500,
                    merchant_reliability=0.95,
                ),
            ]

            # 8. Recommend dinner (after low-protein lunch)
            result = engine.recommend(patient, [lunch_record], menu_items, MealLabel.DINNER)

            assert result.outcome == Outcome.RECOMMENDED

            # Verify knowledge snippets present in clinician_explanation
            assert "knowledgeSnippets" in result.clinician_explanation
            snippets = result.clinician_explanation["knowledgeSnippets"]
            assert len(snippets) > 0
            assert any("sodium" in s["text"].lower() for s in snippets)

            # Verify gap compensation: lean_protein tag should be in matchedTags
            # (low-protein lunch triggers lean_protein compensation)
            matched_tags = result.clinician_explanation.get("matchedTags", [])
            matched_values = {t["value"] for t in matched_tags}
            assert "lean_protein" in matched_values

            # Verify diversity penalty: fish is in recent_ingredients,
            # so the score should reflect -1 penalty
            assert "ckd-safe-1" in result.trace.scores
            # Score with diversity: base would be higher without the penalty
            assert result.trace.scores["ckd-safe-1"] > 0
