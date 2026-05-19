"""Integration test: end-to-end Phase 1 workflow.

Verifies the complete pipeline:
1. Import documents
2. Index into vector DB
3. Verify semantic search works
4. Manually create and approve rules
5. Publish a version
6. Load RulePack via KnowledgeRuleProvider
7. Search via KnowledgeRetriever
8. Verify explain_rule returns source info
"""

import tempfile
from datetime import datetime, timezone

from knowledge.schema import ExtractedConditionRule
from knowledge.store import RuleStore
from knowledge.documents import DocumentImporter
from knowledge.vectordb import KnowledgeVectorDB
from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from medidiet.knowledge_bridge import KnowledgeRuleProvider, KnowledgeRetriever

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


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
