import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import ExtractedConditionRule, VerificationResult, VerificationIssue
from knowledge.store import RuleStore, _normalize_version

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


def _make_rule(candidate_id, condition_value, status="draft"):
    return ExtractedConditionRule(
        candidate_id=candidate_id,
        source_doc_ids=["doc-001"],
        source_chunk_ids=["chunk-001"],
        condition=ConceptCode(CodeKind.CONDITION, condition_value),
        hard_exclusions=set(),
        preferred_tags=set(),
        nutrition_limits=set(),
        confidence=0.9,
        extraction_method="manual",
        reviewed_by=None,
        status=status,
        created_at=NOW,
    )


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RuleStore(data_dir=tmpdir)
        yield store


class TestRuleStoreCRUD:
    def test_create_and_get_rule(self, temp_store):
        rule = _make_rule("cand-001", "hypertension")
        temp_store.create(rule)
        retrieved = temp_store.get("cand-001")
        assert retrieved is not None
        assert retrieved.candidate_id == "cand-001"
        assert retrieved.condition.value == "hypertension"

    def test_get_nonexistent_rule_returns_none(self, temp_store):
        assert temp_store.get("nonexistent") is None

    def test_create_duplicate_raises(self, temp_store):
        rule = _make_rule("cand-001", "hypertension")
        temp_store.create(rule)
        with pytest.raises(ValueError, match="already exists"):
            temp_store.create(rule)

    def test_update_rule(self, temp_store):
        rule = _make_rule("cand-001", "hypertension")
        temp_store.create(rule)
        updated = _make_rule("cand-001", "hypertension", status="pending_review")
        temp_store.update(updated)
        retrieved = temp_store.get("cand-001")
        assert retrieved.status == "pending_review"

    def test_update_nonexistent_raises(self, temp_store):
        rule = _make_rule("nonexistent", "hypertension")
        with pytest.raises(ValueError, match="not found"):
            temp_store.update(rule)

    def test_delete_rule(self, temp_store):
        rule = _make_rule("cand-001", "hypertension")
        temp_store.create(rule)
        temp_store.delete("cand-001")
        assert temp_store.get("cand-001") is None

    def test_delete_nonexistent_raises(self, temp_store):
        with pytest.raises(ValueError, match="not found"):
            temp_store.delete("nonexistent")

    def test_list_all_rules(self, temp_store):
        temp_store.create(_make_rule("cand-001", "hypertension"))
        temp_store.create(_make_rule("cand-002", "diabetes"))
        rules = temp_store.list_all()
        assert len(rules) == 2

    def test_list_by_status(self, temp_store):
        temp_store.create(_make_rule("cand-001", "hypertension", status="draft"))
        temp_store.create(_make_rule("cand-002", "diabetes", status="approved"))
        temp_store.create(_make_rule("cand-003", "hyperlipidemia", status="draft"))
        drafts = temp_store.list_by_status("draft")
        assert len(drafts) == 2
        approved = temp_store.list_by_status("approved")
        assert len(approved) == 1

    def test_list_by_condition(self, temp_store):
        temp_store.create(_make_rule("cand-001", "hypertension"))
        temp_store.create(_make_rule("cand-002", "hypertension"))
        temp_store.create(_make_rule("cand-003", "diabetes"))
        ht_rules = temp_store.list_by_condition(
            ConceptCode(CodeKind.CONDITION, "hypertension")
        )
        assert len(ht_rules) == 2


class TestRuleStorePersistence:
    def test_persists_rules_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = RuleStore(data_dir=tmpdir)
            store1.create(_make_rule("cand-001", "hypertension"))

            store2 = RuleStore(data_dir=tmpdir)
            retrieved = store2.get("cand-001")
            assert retrieved is not None
            assert retrieved.candidate_id == "cand-001"

    def test_empty_store_loads_fine(self, temp_store):
        assert temp_store.list_all() == []


class TestNormalizeVersion:
    def test_already_has_v_prefix(self):
        assert _normalize_version("v1.0") == "v1.0"

    def test_adds_v_prefix(self):
        assert _normalize_version("1.0") == "v1.0"

    def test_allows_alphanumeric(self):
        assert _normalize_version("v1.2.3-alpha") == "v1.2.3-alpha"

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="invalid version"):
            _normalize_version("../../etc")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="invalid version"):
            _normalize_version("v1.0!")

    def test_rejects_slash(self):
        with pytest.raises(ValueError, match="invalid version"):
            _normalize_version("v1.0/foo")

    def test_strip_and_add_v_is_idempotent(self):
        assert _normalize_version("v2.0") == "v2.0"


class TestRuleStoreVersioning:
    def test_publish_version(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        version_path = temp_store.publish_version("v1.0", notes="First release")
        assert os.path.exists(version_path)

        with open(version_path) as f:
            data = json.load(f)
        assert data["version"] == "v1.0"
        assert data["notes"] == "First release"
        assert len(data["rules"]) == 1
        assert data["rules"][0]["condition"]["value"] == "hypertension"

    def test_publish_only_approved_rules(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.create(
            _make_rule("cand-002", "diabetes", status="draft")
        )
        version_path = temp_store.publish_version("v1.0", notes="Test")
        with open(version_path) as f:
            data = json.load(f)
        assert len(data["rules"]) == 1

    def test_publish_without_v_prefix(self, temp_store):
        """Publishing with '1.0' should normalize to 'v1.0' internally."""
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        version_path = temp_store.publish_version("1.0", notes="No v prefix")
        assert os.path.basename(version_path) == "v1.0.json"

        with open(version_path) as f:
            data = json.load(f)
        assert data["version"] == "v1.0"

    def test_list_versions(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.publish_version("v1.0", notes="First")
        temp_store.publish_version("v2.0", notes="Second")
        versions = temp_store.list_versions()
        assert "1.0" in versions
        assert "2.0" in versions
        assert len(versions) == 2

    def test_list_versions_normalized(self, temp_store):
        """Publish without 'v' prefix, but list should still return stripped."""
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.publish_version("1.0", notes="No v prefix")
        versions = temp_store.list_versions()
        assert "1.0" in versions

    def test_load_version(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.publish_version("v1.0", notes="Test")
        loaded = temp_store.load_version("v1.0")
        assert len(loaded) == 1
        assert loaded[0].condition.value == "hypertension"

    def test_load_version_without_v_prefix(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.publish_version("v1.0", notes="Test")
        loaded = temp_store.load_version("1.0")
        assert len(loaded) == 1
        assert loaded[0].condition.value == "hypertension"

    def test_load_nonexistent_version_raises(self, temp_store):
        with pytest.raises(ValueError, match="version not found"):
            temp_store.load_version("v-nonexistent")

    def test_publish_invalid_version_rejected(self, temp_store):
        with pytest.raises(ValueError, match="invalid version"):
            temp_store.publish_version("../../etc", notes="bad")

    def test_verification_round_trip(self):
        """Verify VerificationResult including revised_rule survives serialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = RuleStore(data_dir=tmpdir)

            # Create the revised rule first so it's in the cache of store1.
            revised = _make_rule("cand-revised", "diabetes", status="approved")
            store1.create(revised)

            # Create a rule with a fully populated VerificationResult.
            rule = ExtractedConditionRule(
                candidate_id="cand-001",
                source_doc_ids=["doc-001"],
                source_chunk_ids=["chunk-001"],
                condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
                hard_exclusions={
                    ConceptCode(CodeKind.INGREDIENT, "salt"),
                },
                preferred_tags=set(),
                nutrition_limits={
                    NutrientLimit(
                        metric=NutrientMetric.SODIUM_MG,
                        scope=LimitScope.DAILY,
                        max_value=1500.0,
                        window_hours=None,
                    ),
                },
                confidence=0.95,
                extraction_method="llm+review",
                reviewed_by="dr-simon",
                status="approved",
                created_at=NOW,
                verification_result=VerificationResult(
                    verdict="revision_needed",
                    confidence=0.85,
                    consistency_score=0.9,
                    logic_score=0.8,
                    completeness_score=0.75,
                    issues=[
                        VerificationIssue(
                            severity="warning",
                            dimension="consistency",
                            description="Conflicting sodium limits",
                            related_field="nutrition_limits",
                            suggested_fix="Review sodium max_value",
                        ),
                        VerificationIssue(
                            severity="info",
                            dimension="completeness",
                            description="Missing potassium limit",
                            related_field=None,
                            suggested_fix=None,
                        ),
                    ],
                    missing_items=["potassium_limit"],
                    evidence_quotes={
                        "doc-001": "Limit sodium to 1500mg daily",
                    },
                    revised_rule=revised,
                ),
            )
            store1.create(rule)

            # Load into a brand-new store instance (no in-memory cache).
            store2 = RuleStore(data_dir=tmpdir)
            loaded = store2.get("cand-001")
            assert loaded is not None
            assert loaded.verification_result is not None

            vr = loaded.verification_result
            assert vr.verdict == "revision_needed"
            assert vr.confidence == 0.85
            assert vr.consistency_score == 0.9
            assert vr.logic_score == 0.8
            assert vr.completeness_score == 0.75

            # Issues must round-trip fully.
            assert len(vr.issues) == 2
            assert vr.issues[0].severity == "warning"
            assert vr.issues[0].dimension == "consistency"
            assert vr.issues[0].description == "Conflicting sodium limits"
            assert vr.issues[0].related_field == "nutrition_limits"
            assert vr.issues[0].suggested_fix == "Review sodium max_value"

            assert vr.issues[1].severity == "info"
            assert vr.issues[1].dimension == "completeness"
            assert vr.issues[1].description == "Missing potassium limit"
            assert vr.issues[1].related_field is None
            assert vr.issues[1].suggested_fix is None

            # missing_items and evidence_quotes must round-trip.
            assert vr.missing_items == ["potassium_limit"]
            assert vr.evidence_quotes == {
                "doc-001": "Limit sodium to 1500mg daily",
            }

            # revised_rule is serialized as a candidate_id reference only,
            # so after deserialization in a fresh store it is None.
            assert vr.revised_rule is None
