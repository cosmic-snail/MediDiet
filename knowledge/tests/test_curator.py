"""Tests for KnowledgeCurator — manual curation API."""

import tempfile

import pytest

from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import ExtractedConditionRule
from knowledge.store import RuleStore
from knowledge.curator import KnowledgeCurator


@pytest.fixture
def curator_and_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RuleStore(data_dir=tmpdir)
        curator = KnowledgeCurator(store)
        yield curator, store


class TestCreateRule:
    def test_create_rule_manual(self, curator_and_store):
        curator, store = curator_and_store
        rule = curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions={ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium")},
            preferred_tags={ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium")},
        )
        assert rule.status == "draft"
        assert rule.extraction_method == "manual"
        assert rule.candidate_id == "cand-001"

        stored = store.get("cand-001")
        assert stored is not None
        assert stored.status == "draft"

    def test_create_rule_rejects_invalid_confidence(self, curator_and_store):
        curator, _ = curator_and_store
        with pytest.raises(ValueError, match="confidence"):
            curator.create_rule(
                candidate_id="cand-001",
                condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
                confidence=1.5,
            )

    def test_create_rule_rejects_wrong_code_kind(self, curator_and_store):
        curator, _ = curator_and_store
        with pytest.raises(ValueError, match="CodeKind.CONDITION"):
            curator.create_rule(
                candidate_id="cand-001",
                condition=ConceptCode(CodeKind.ALLERGEN, "peanut"),
            )

    def test_create_rule_duplicate_raises(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        with pytest.raises(ValueError, match="already exists"):
            curator.create_rule(
                candidate_id="cand-001",
                condition=ConceptCode(CodeKind.CONDITION, "diabetes"),
            )


class TestReviewRule:
    def test_review_rule_approve(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        rule = curator.review_rule("cand-001", "approved", "dr-smith")
        assert rule.status == "approved"
        assert rule.reviewed_by == "dr-smith"
        assert rule.extraction_method == "manual"  # was manual, stays manual

    def test_review_rule_reject(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        rule = curator.review_rule("cand-001", "rejected", "dr-smith")
        assert rule.status == "rejected"
        assert rule.reviewed_by == "dr-smith"

    def test_review_rule_invalid_decision(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        with pytest.raises(ValueError, match="decision"):
            curator.review_rule("cand-001", "maybe", "dr-smith")

    def test_review_rule_nonexistent(self, curator_and_store):
        curator, _ = curator_and_store
        with pytest.raises(ValueError, match="not found"):
            curator.review_rule("nonexistent", "approved", "dr-smith")

    def test_review_llm_rule_marks_llm_plus_review(self, curator_and_store):
        curator, store = curator_and_store
        # Create a rule that looks like LLM-extracted
        from datetime import datetime, timezone

        rule = ExtractedConditionRule(
            candidate_id="cand-llm",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.9,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=datetime.now(timezone.utc),
        )
        store.create(rule)

        reviewed = curator.review_rule("cand-llm", "approved", "dr-jones")
        assert reviewed.extraction_method == "llm+review"


class TestRejectRule:
    def test_reject_rule_with_reason(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        rule = curator.reject_rule("cand-001", "Insufficient clinical evidence")
        assert rule.status == "rejected"
        assert rule.verification_result is not None
        assert len(rule.verification_result.issues) == 1
        assert "Insufficient clinical evidence" in rule.verification_result.issues[0].description

    def test_reject_rule_appends_to_existing_verification(self, curator_and_store):
        curator, store = curator_and_store
        from knowledge.schema import VerificationResult, VerificationIssue
        from datetime import datetime, timezone

        existing_vr = VerificationResult(
            verdict="revision_needed",
            confidence=0.5,
            consistency_score=0.6,
            logic_score=0.7,
            completeness_score=0.5,
            issues=[
                VerificationIssue(
                    severity="warning",
                    dimension="consistency",
                    description="Missing sodium limit",
                )
            ],
            missing_items=None,
            evidence_quotes={},
            revised_rule=None,
        )
        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.9,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=datetime.now(timezone.utc),
            verification_result=existing_vr,
        )
        store.create(rule)

        rejected = curator.reject_rule("cand-001", "No clinical consensus")
        assert rejected.status == "rejected"
        assert len(rejected.verification_result.issues) == 2
        assert "No clinical consensus" in rejected.verification_result.issues[1].description

    def test_reject_nonexistent_raises(self, curator_and_store):
        curator, _ = curator_and_store
        with pytest.raises(ValueError, match="not found"):
            curator.reject_rule("nonexistent", "reason")


class TestPublish:
    def test_publish_approved_rules(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        curator.review_rule("cand-001", "approved", "dr-smith")

        path = curator.publish("v1.0", "First hypertension rule")
        import os
        assert os.path.exists(path)

    def test_publish_no_approved_rules(self, curator_and_store):
        curator, _ = curator_and_store
        # No rules at all
        path = curator.publish("v1.0", "Empty version")
        import os
        assert os.path.exists(path)


class TestQuery:
    def test_get_candidate(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        rule = curator.get_candidate("cand-001")
        assert rule is not None
        assert rule.candidate_id == "cand-001"

    def test_get_candidate_nonexistent(self, curator_and_store):
        curator, _ = curator_and_store
        assert curator.get_candidate("nonexistent") is None

    def test_list_candidates_all(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        curator.create_rule(
            candidate_id="cand-002",
            condition=ConceptCode(CodeKind.CONDITION, "diabetes"),
        )
        assert len(curator.list_candidates()) == 2

    def test_list_candidates_by_status(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        curator.create_rule(
            candidate_id="cand-002",
            condition=ConceptCode(CodeKind.CONDITION, "diabetes"),
        )
        curator.review_rule("cand-001", "approved", "dr-smith")
        assert len(curator.list_candidates("approved")) == 1
        assert len(curator.list_candidates("draft")) == 1

    def test_list_versions(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        curator.review_rule("cand-001", "approved", "dr-smith")
        curator.publish("v1.0", "First")
        versions = curator.list_versions()
        assert "1.0" in versions

    def test_load_version(self, curator_and_store):
        curator, _ = curator_and_store
        curator.create_rule(
            candidate_id="cand-001",
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
        )
        curator.review_rule("cand-001", "approved", "dr-smith")
        curator.publish("v1.0", "First")
        rules = curator.load_version("v1.0")
        assert len(rules) == 1
        assert rules[0].condition.value == "hypertension"
