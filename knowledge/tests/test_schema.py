import pytest
from datetime import datetime, timezone
from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import (
    KnowledgeDocument,
    DocumentChunk,
    ExtractedConditionRule,
    VerificationResult,
    VerificationIssue,
    SuggestedConcept,
)

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


class TestKnowledgeDocument:
    def test_valid_document(self):
        doc = KnowledgeDocument(
            doc_id="doc-001",
            title="CKD Dietary Guidelines 2024",
            source="https://example.org/ckd-2024.pdf",
            source_type="guideline",
            content_raw="Full text here...",
            chunks=[],
            metadata={"year": "2024", "institution": "NKF"},
            ingested_at=NOW,
        )
        assert doc.doc_id == "doc-001"
        assert doc.source_type == "guideline"

    def test_rejects_invalid_source_type(self):
        with pytest.raises(ValueError, match="source_type"):
            KnowledgeDocument(
                doc_id="doc-001",
                title="Bad",
                source="test.md",
                source_type="invalid_type",
                content_raw="...",
                chunks=[],
                metadata={},
                ingested_at=NOW,
            )

    def test_document_default_metadata(self):
        doc = KnowledgeDocument(
            doc_id="doc-002",
            title="Test",
            source="test.md",
            source_type="paper",
            content_raw="...",
            chunks=[],
            metadata={},
            ingested_at=NOW,
        )
        assert doc.metadata == {}


class TestDocumentChunk:
    def test_valid_chunk(self):
        chunk = DocumentChunk(
            chunk_id="chunk-001",
            doc_id="doc-001",
            text="Patients with CKD should limit sodium intake to under 2000mg per day.",
            chunk_index=0,
            embedding=None,
            metadata={"section": "Sodium Management"},
        )
        assert chunk.chunk_id == "chunk-001"
        assert chunk.chunk_index == 0
        assert chunk.embedding is None

    def test_rejects_negative_chunk_index(self):
        with pytest.raises(ValueError, match="chunk_index"):
            DocumentChunk(
                chunk_id="chunk-001",
                doc_id="doc-001",
                text="text",
                chunk_index=-1,
            )

    def test_chunk_default_metadata(self):
        chunk = DocumentChunk(
            chunk_id="chunk-002",
            doc_id="doc-001",
            text="Some text",
            chunk_index=1,
        )
        assert chunk.metadata == {}


class TestExtractedConditionRule:
    def test_valid_draft_rule(self):
        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001", "chunk-002"],
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
            confidence=0.85,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=NOW,
            verification_result=None,
        )
        assert rule.candidate_id == "cand-001"
        assert rule.status == "draft"
        assert len(rule.hard_exclusions) == 1

    def test_rejects_invalid_confidence(self):
        with pytest.raises(ValueError, match="confidence"):
            ExtractedConditionRule(
                candidate_id="cand-001",
                source_doc_ids=["doc-001"],
                source_chunk_ids=["chunk-001"],
                condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
                hard_exclusions=set(),
                preferred_tags=set(),
                nutrition_limits=set(),
                confidence=1.5,
                extraction_method="manual",
                reviewed_by=None,
                status="draft",
                created_at=NOW,
            )

    def test_rejects_invalid_extraction_method(self):
        with pytest.raises(ValueError, match="extraction_method"):
            ExtractedConditionRule(
                candidate_id="cand-001",
                source_doc_ids=["doc-001"],
                source_chunk_ids=["chunk-001"],
                condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
                hard_exclusions=set(),
                preferred_tags=set(),
                nutrition_limits=set(),
                confidence=0.9,
                extraction_method="invalid_method",
                reviewed_by=None,
                status="draft",
                created_at=NOW,
            )

    def test_rejects_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            ExtractedConditionRule(
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
                status="invalid_status",
                created_at=NOW,
            )

    def test_rule_with_verification_result(self):
        vr = VerificationResult(
            verdict="pass",
            confidence=0.9,
            consistency_score=0.95,
            logic_score=0.88,
            completeness_score=0.82,
            issues=[],
            missing_items=None,
            revised_rule=None,
            evidence_quotes={
                "sodium_limit": "Sodium intake should be limited to under 2000mg per day."
            },
        )
        rule = ExtractedConditionRule(
            candidate_id="cand-002",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-003"],
            condition=ConceptCode(CodeKind.CONDITION, "diabetes"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.75,
            extraction_method="llm+review",
            reviewed_by=None,
            status="pending_review",
            created_at=NOW,
            verification_result=vr,
        )
        assert rule.verification_result is not None
        assert rule.verification_result.verdict == "pass"


class TestVerificationResult:
    def test_pass_result(self):
        vr = VerificationResult(
            verdict="pass",
            confidence=0.9,
            consistency_score=0.95,
            logic_score=0.9,
            completeness_score=0.85,
            issues=[],
        )
        assert vr.verdict == "pass"
        assert vr.issues == []

    def test_rejects_invalid_verdict(self):
        with pytest.raises(ValueError, match="verdict"):
            VerificationResult(
                verdict="invalid",
                confidence=0.5,
                consistency_score=0.5,
                logic_score=0.5,
                completeness_score=0.5,
            )

    def test_rejects_invalid_consistency_score(self):
        with pytest.raises(ValueError, match="consistency_score"):
            VerificationResult(
                verdict="pass",
                confidence=0.5,
                consistency_score=1.5,
                logic_score=0.5,
                completeness_score=0.5,
            )

    def test_revision_needed_result(self):
        issue = VerificationIssue(
            severity="warning",
            dimension="completeness",
            description="Missing phosphorus limit for CKD patients",
            related_field="nutrition_limits",
            suggested_fix="Add phosphorus per-meal limit of 800mg",
        )
        vr = VerificationResult(
            verdict="revision_needed",
            confidence=0.5,
            consistency_score=0.8,
            logic_score=0.6,
            completeness_score=0.3,
            issues=[issue],
            missing_items=["phosphorus_limit"],
        )
        assert vr.verdict == "revision_needed"
        assert len(vr.issues) == 1
        assert vr.missing_items == ["phosphorus_limit"]

    def test_rejected_result(self):
        vr = VerificationResult(
            verdict="rejected",
            confidence=0.1,
            consistency_score=0.2,
            logic_score=0.3,
            completeness_score=0.1,
            issues=[
                VerificationIssue(
                    severity="critical",
                    dimension="consistency",
                    description="No source evidence found for claimed sodium limit",
                    related_field="nutrition_limits",
                )
            ],
        )
        assert vr.verdict == "rejected"


class TestVerificationIssue:
    def test_rejects_invalid_severity(self):
        with pytest.raises(ValueError, match="severity"):
            VerificationIssue(
                severity="invalid",
                dimension="logic",
                description="Test",
            )

    def test_rejects_invalid_dimension(self):
        with pytest.raises(ValueError, match="dimension"):
            VerificationIssue(
                severity="warning",
                dimension="invalid",
                description="Test",
            )

    def test_all_severities(self):
        for severity in ("critical", "warning", "info"):
            issue = VerificationIssue(
                severity=severity,
                dimension="logic",
                description=f"A {severity} issue",
            )
            assert issue.severity == severity


class TestSuggestedConcept:
    def test_valid_suggestion(self):
        sc = SuggestedConcept(
            suggest_id="sug-001",
            candidate_rule_id="cand-001",
            suggested_code=ConceptCode(CodeKind.NUTRITION_TAG, "low_purine"),
            definition="Foods low in purines for gout management",
            source_chunk_ids=["chunk-010", "chunk-011"],
            display_name="低嘌呤",
        )
        assert sc.suggest_id == "sug-001"
        assert sc.suggested_code.value == "low_purine"
