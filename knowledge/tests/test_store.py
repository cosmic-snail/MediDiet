import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import ExtractedConditionRule, VerificationResult
from knowledge.store import RuleStore

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

    def test_list_versions(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.publish_version("v1.0", notes="First")
        temp_store.publish_version("v2.0", notes="Second")
        versions = temp_store.list_versions()
        assert "v1.0" in versions
        assert "v2.0" in versions
        assert len(versions) == 2

    def test_load_version(self, temp_store):
        temp_store.create(
            _make_rule("cand-001", "hypertension", status="approved")
        )
        temp_store.publish_version("v1.0", notes="Test")
        loaded = temp_store.load_version("v1.0")
        assert len(loaded) == 1
        assert loaded[0].condition.value == "hypertension"
