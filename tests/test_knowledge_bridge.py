import tempfile
from datetime import datetime, timezone

import pytest

from medidiet.domain import CodeKind, ConceptCode, MealLabel, PatientProfile, Preference, DataSource
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from medidiet.ports import KnowledgeSnippet, KnowledgeContext, RuleProviderPort, KnowledgePort
from knowledge.schema import ExtractedConditionRule
from knowledge.store import RuleStore
from knowledge.vectordb import KnowledgeVectorDB
from medidiet.knowledge_bridge import KnowledgeRuleProvider, KnowledgeRetriever

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RuleStore(data_dir=tmpdir)
        yield store


@pytest.fixture
def temp_vectordb():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = KnowledgeVectorDB(persist_dir=tmpdir)
        yield db


class TestKnowledgeRuleProvider:
    def test_load_rule_pack_from_store(self, temp_store):
        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions={ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium")},
            preferred_tags={ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium")},
            nutrition_limits={
                NutrientLimit(
                    metric=NutrientMetric.SODIUM_MG,
                    scope=LimitScope.PER_MEAL,
                    max_value=700,
                )
            },
            confidence=0.9,
            extraction_method="manual",
            reviewed_by="dietitian-01",
            status="approved",
            created_at=NOW,
        )
        temp_store.create(rule)
        temp_store.publish_version("v1.0", notes="Test")

        provider = KnowledgeRuleProvider(store=temp_store, version="v1.0")
        pack = provider.load_rule_pack()

        assert pack.version == "v1.0"
        rule_from_pack = pack.for_condition(ConceptCode(CodeKind.CONDITION, "hypertension"))
        assert ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium") in rule_from_pack.hard_exclusions

    def test_list_versions(self, temp_store):
        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.9,
            extraction_method="manual",
            reviewed_by=None,
            status="approved",
            created_at=NOW,
        )
        temp_store.create(rule)
        temp_store.publish_version("v1.0", notes="First")
        temp_store.publish_version("v2.0", notes="Second")

        provider = KnowledgeRuleProvider(store=temp_store)
        versions = provider.list_versions()
        assert "v1.0" in versions
        assert "v2.0" in versions

    def test_load_latest_when_no_version_specified(self, temp_store):
        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.9,
            extraction_method="manual",
            reviewed_by=None,
            status="approved",
            created_at=NOW,
        )
        temp_store.create(rule)
        temp_store.publish_version("v1.0", notes="First")
        temp_store.publish_version("v2.0", notes="Second")

        provider = KnowledgeRuleProvider(store=temp_store)
        pack = provider.load_rule_pack()
        assert pack.version == "v2.0"

    def test_implements_rule_provider_port(self, temp_store):
        provider = KnowledgeRuleProvider(store=temp_store)
        assert isinstance(provider, RuleProviderPort)


class TestKnowledgeRetriever:
    def test_search_delegates_to_vectordb(self, temp_vectordb):
        from knowledge.schema import KnowledgeDocument, DocumentChunk
        doc = KnowledgeDocument(
            doc_id="doc-001",
            title="Sodium Guidelines",
            source="https://example.org",
            source_type="guideline",
            content_raw="Limit sodium to 2000mg per day.",
            chunks=[
                DocumentChunk(
                    chunk_id="doc-001-chunk-0000",
                    doc_id="doc-001",
                    text="Limit sodium to under 2000mg per day for hypertensive patients.",
                    chunk_index=0,
                )
            ],
            metadata={},
            ingested_at=NOW,
        )
        temp_vectordb.index_document(doc)

        retriever = KnowledgeRetriever(vectordb=temp_vectordb)
        results = retriever.search("sodium intake", top_k=3)
        assert len(results) > 0
        assert isinstance(results[0], KnowledgeSnippet)
        assert "sodium" in results[0].text.lower()

    def test_retrieve_context(self, temp_vectordb):
        from knowledge.schema import KnowledgeDocument, DocumentChunk
        doc = KnowledgeDocument(
            doc_id="doc-001",
            title="Diabetes Guide",
            source="https://example.org",
            source_type="guideline",
            content_raw="Diabetes patients should control sugar intake.",
            chunks=[
                DocumentChunk(
                    chunk_id="doc-001-chunk-0000",
                    doc_id="doc-001",
                    text="Diabetes patients should limit sugar to under 25g per day.",
                    chunk_index=0,
                )
            ],
            metadata={},
            ingested_at=NOW,
        )

        temp_vectordb.index_document(doc)

        patient = PatientProfile(
            patient_id="p-001",
            age=55,
            height_cm=170,
            weight_kg=75,
            conditions={ConceptCode(CodeKind.CONDITION, "diabetes")},
            allergens=set(),
            contraindications=set(),
            preferences=Preference(),
            key_risk_fields_confirmed=True,
            source=DataSource.CLINICIAN_ENTERED,
        )

        retriever = KnowledgeRetriever(vectordb=temp_vectordb)
        ctx = retriever.retrieve_context(patient, MealLabel.LUNCH)
        assert isinstance(ctx, KnowledgeContext)
        assert len(ctx.snippets) > 0

    def test_implements_knowledge_port(self, temp_vectordb):
        retriever = KnowledgeRetriever(vectordb=temp_vectordb)
        assert isinstance(retriever, KnowledgePort)

    def test_explain_rule_returns_source_info(self, temp_vectordb):
        from knowledge.schema import KnowledgeDocument, DocumentChunk
        doc = KnowledgeDocument(
            doc_id="doc-001",
            title="Hypertension Manual",
            source="https://example.org/ht.pdf",
            source_type="guideline",
            content_raw="Sodium should be limited for hypertension.",
            chunks=[
                DocumentChunk(
                    chunk_id="doc-001-chunk-0000",
                    doc_id="doc-001",
                    text="Hypertension patients: limit sodium to 700mg per meal.",
                    chunk_index=0,
                )
            ],
            metadata={},
            ingested_at=NOW,
        )
        temp_vectordb.index_document(doc)

        retriever = KnowledgeRetriever(vectordb=temp_vectordb)
        explanation = retriever.explain_rule(
            ConceptCode(CodeKind.CONDITION, "hypertension")
        )
        assert isinstance(explanation, str)
        assert len(explanation) > 0
