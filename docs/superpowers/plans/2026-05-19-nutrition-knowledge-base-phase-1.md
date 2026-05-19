# Nutrition Knowledge Base — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the standalone `knowledge` package with structured rule storage, document chunking, ChromaDB vector search, batch document loading, and port interfaces connecting to the MediDiet engine.

**Architecture:** Independent `knowledge/` top-level package with its own `pyproject.toml`. Defines data models in `schema.py`, rule CRUD in `store.py`, document handling in `documents.py`, ChromaDB wrapper in `vectordb.py`, and batch import in `loader.py`. The MediDiet engine integrates via `RuleProviderPort` and `KnowledgePort` protocols defined in `ports.py`, implemented by `knowledge_bridge.py`.

**Tech Stack:** Python 3.11+, ChromaDB (vector store), httpx (LLM provider calls — deferred to Phase 2), dataclasses, JSON file versioning.

---

### Task 1: Create knowledge package skeleton

**Files:**
- Create: `knowledge/pyproject.toml`
- Create: `knowledge/src/knowledge/__init__.py`
- Create: `knowledge/tests/__init__.py`
- Modify: `MediDiet/pyproject.toml` (add optional dependency)

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p knowledge/src/knowledge knowledge/tests
```

Expected: directories created

- [ ] **Step 2: Write knowledge/pyproject.toml**

```toml
[project]
name = "medidiet-knowledge"
version = "0.1.0"
description = "Nutrition knowledge base for MediDiet — structured rules, document management, vector search"
requires-python = ">=3.11"
dependencies = [
    "chromadb>=0.4,<1.0",
    "httpx>=0.27,<1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Write knowledge/src/knowledge/__init__.py**

```python
"""MediDiet knowledge base — structured rules, document management, vector search."""
```

- [ ] **Step 4: Write knowledge/tests/__init__.py**

```python
"""Tests for the knowledge package."""
```

- [ ] **Step 5: Add knowledge as optional dependency in root pyproject.toml**

Read the existing `pyproject.toml` at the repo root, add under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
knowledge = ["medidiet-knowledge"]
```

And add a `[tool.setuptools.packages.find]` exclude or leave the root config as-is since knowledge is managed separately.

- [ ] **Step 6: Install the knowledge package in development mode**

```bash
cd knowledge && pip install -e .
```

Expected: installs chromadb, httpx and the knowledge package

- [ ] **Step 7: Verify import**

```bash
python -c "import knowledge; print(knowledge.__doc__)"
```

Expected: "MediDiet knowledge base — structured rules, document management, vector search."

- [ ] **Step 8: Commit**

```bash
git add knowledge/pyproject.toml knowledge/src/knowledge/__init__.py knowledge/tests/__init__.py pyproject.toml
git commit -m "feat: add knowledge package skeleton"
```

---

### Task 2: Define data models (schema.py)

**Files:**
- Create: `knowledge/src/knowledge/schema.py`
- Test: `knowledge/tests/test_schema.py`

Base types (`ConceptCode`, `CodeKind`, `NutrientLimit`, `NutrientMetric`, `LimitScope`) are imported from `medidiet.domain` and `medidiet.rules`.

- [ ] **Step 1: Write the failing tests**

Create `knowledge/tests/test_schema.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd knowledge && python -m pytest tests/test_schema.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge.schema'`

- [ ] **Step 3: Write knowledge/src/knowledge/schema.py**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from medidiet.domain import ConceptCode
from medidiet.rules import NutrientLimit


@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    source: str
    source_type: str  # "guideline" | "paper" | "food_db" | "manual"
    content_raw: str
    chunks: list[DocumentChunk]
    metadata: dict[str, str]
    ingested_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.source_type, str) or self.source_type not in (
            "guideline", "paper", "food_db", "manual",
        ):
            raise ValueError(
                f"source_type must be one of: guideline, paper, food_db, manual; "
                f"got {self.source_type!r}"
            )


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be non-negative")


@dataclass
class ExtractedConditionRule:
    candidate_id: str
    source_doc_ids: list[str]
    source_chunk_ids: list[str]
    condition: ConceptCode
    hard_exclusions: set[ConceptCode]
    preferred_tags: set[ConceptCode]
    nutrition_limits: set[NutrientLimit]
    confidence: float
    extraction_method: str  # "llm" | "manual" | "llm+review"
    reviewed_by: str | None
    status: str  # "draft" | "pending_review" | "approved" | "rejected"
    created_at: datetime
    verification_result: VerificationResult | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.extraction_method not in ("llm", "manual", "llm+review"):
            raise ValueError(
                f"extraction_method must be llm, manual, or llm+review; "
                f"got {self.extraction_method!r}"
            )
        if self.status not in ("draft", "pending_review", "approved", "rejected"):
            raise ValueError(
                f"status must be draft, pending_review, approved, or rejected; "
                f"got {self.status!r}"
            )


@dataclass
class VerificationResult:
    verdict: str  # "pass" | "revision_needed" | "rejected"
    confidence: float
    consistency_score: float  # 0-1
    logic_score: float  # 0-1
    completeness_score: float  # 0-1
    issues: list[VerificationIssue] = field(default_factory=list)
    missing_items: list[str] | None = None
    revised_rule: ExtractedConditionRule | None = None
    evidence_quotes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in ("pass", "revision_needed", "rejected"):
            raise ValueError(
                f"verdict must be pass, revision_needed, or rejected; "
                f"got {self.verdict!r}"
            )
        for score_name in ("consistency_score", "logic_score", "completeness_score"):
            score = getattr(self, score_name)
            if not 0 <= score <= 1:
                raise ValueError(f"{score_name} must be between 0 and 1")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class VerificationIssue:
    severity: str  # "critical" | "warning" | "info"
    dimension: str  # "consistency" | "logic" | "completeness"
    description: str
    related_field: str | None = None
    suggested_fix: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("critical", "warning", "info"):
            raise ValueError(
                f"severity must be critical, warning, or info; "
                f"got {self.severity!r}"
            )
        if self.dimension not in ("consistency", "logic", "completeness"):
            raise ValueError(
                f"dimension must be consistency, logic, or completeness; "
                f"got {self.dimension!r}"
            )


@dataclass
class SuggestedConcept:
    suggest_id: str
    candidate_rule_id: str
    suggested_code: ConceptCode
    definition: str
    source_chunk_ids: list[str]
    display_name: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd knowledge && python -m pytest tests/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/src/knowledge/schema.py knowledge/tests/test_schema.py
git commit -m "feat: add knowledge base data models"
```

---

### Task 3: Implement structured rule store (store.py)

**Files:**
- Create: `knowledge/src/knowledge/store.py`
- Test: `knowledge/tests/test_store.py`
- Create: `data/rules/.gitkeep`

The store manages `ExtractedConditionRule` objects with JSON file persistence and versioning.

- [ ] **Step 1: Write the failing tests**

Create `knowledge/tests/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd knowledge && python -m pytest tests/test_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge.store'`

- [ ] **Step 3: Create data/rules/.gitkeep**

```bash
mkdir -p data/rules && touch data/rules/.gitkeep
```

- [ ] **Step 4: Write knowledge/src/knowledge/store.py**

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from medidiet.domain import ConceptCode, CodeKind
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import ExtractedConditionRule, VerificationResult, VerificationIssue


class RuleStore:
    def __init__(self, data_dir: str = "data"):
        self._rules_dir = Path(data_dir) / "rules"
        self._rules_dir.mkdir(parents=True, exist_ok=True)
        self._candidates_file = self._rules_dir / "candidates.json"
        self._versions: dict[str, Path] = {}
        self._cache: dict[str, ExtractedConditionRule] = {}
        self._load()

    def create(self, rule: ExtractedConditionRule) -> None:
        if rule.candidate_id in self._cache:
            raise ValueError(f"rule already exists: {rule.candidate_id}")
        self._cache[rule.candidate_id] = rule
        self._save()

    def get(self, candidate_id: str) -> ExtractedConditionRule | None:
        return self._cache.get(candidate_id)

    def update(self, rule: ExtractedConditionRule) -> None:
        if rule.candidate_id not in self._cache:
            raise ValueError(f"rule not found: {rule.candidate_id}")
        self._cache[rule.candidate_id] = rule
        self._save()

    def delete(self, candidate_id: str) -> None:
        if candidate_id not in self._cache:
            raise ValueError(f"rule not found: {candidate_id}")
        del self._cache[candidate_id]
        self._save()

    def list_all(self) -> list[ExtractedConditionRule]:
        return list(self._cache.values())

    def list_by_status(self, status: str) -> list[ExtractedConditionRule]:
        return [rule for rule in self._cache.values() if rule.status == status]

    def list_by_condition(self, condition: ConceptCode) -> list[ExtractedConditionRule]:
        return [
            rule
            for rule in self._cache.values()
            if rule.condition == condition
        ]

    def publish_version(self, version: str, notes: str) -> str:
        approved = self.list_by_status("approved")
        rules_data = [_serialize_rule(rule) for rule in approved]
        payload = {
            "version": version,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "rules": rules_data,
        }
        version_path = self._rules_dir / f"{version}.json"
        with open(version_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self._versions[version] = version_path
        return str(version_path)

    def list_versions(self) -> list[str]:
        versions = []
        for entry in sorted(self._rules_dir.glob("v*.json")):
            name = entry.stem
            if name not in self._versions:
                self._versions[name] = entry
            versions.append(name)
        return sorted(versions)

    def load_version(self, version: str) -> list[ExtractedConditionRule]:
        version_path = self._rules_dir / f"{version}.json"
        if not version_path.exists():
            raise ValueError(f"version not found: {version}")
        with open(version_path, encoding="utf-8") as f:
            data = json.load(f)
        return [_deserialize_rule(rule_data) for rule_data in data["rules"]]

    def _load(self) -> None:
        if self._candidates_file.exists():
            with open(self._candidates_file, encoding="utf-8") as f:
                data = json.load(f)
            for rule_data in data.get("candidates", []):
                rule = _deserialize_rule(rule_data)
                self._cache[rule.candidate_id] = rule

    def _save(self) -> None:
        candidates = [_serialize_rule(rule) for rule in self._cache.values()]
        with open(self._candidates_file, "w", encoding="utf-8") as f:
            json.dump({"candidates": candidates}, f, ensure_ascii=False, indent=2)


def _serialize_rule(rule: ExtractedConditionRule) -> dict:
    data = {
        "candidate_id": rule.candidate_id,
        "source_doc_ids": rule.source_doc_ids,
        "source_chunk_ids": rule.source_chunk_ids,
        "condition": {"kind": rule.condition.kind.value, "value": rule.condition.value},
        "hard_exclusions": [
            {"kind": c.kind.value, "value": c.value} for c in rule.hard_exclusions
        ],
        "preferred_tags": [
            {"kind": c.kind.value, "value": c.value} for c in rule.preferred_tags
        ],
        "nutrition_limits": [
            {
                "metric": limit.metric.value,
                "scope": limit.scope.value,
                "max_value": limit.max_value,
                "window_hours": limit.window_hours,
            }
            for limit in rule.nutrition_limits
        ],
        "confidence": rule.confidence,
        "extraction_method": rule.extraction_method,
        "reviewed_by": rule.reviewed_by,
        "status": rule.status,
        "created_at": rule.created_at.isoformat(),
    }
    if rule.verification_result is not None:
        vr = rule.verification_result
        data["verification_result"] = {
            "verdict": vr.verdict,
            "confidence": vr.confidence,
            "consistency_score": vr.consistency_score,
            "logic_score": vr.logic_score,
            "completeness_score": vr.completeness_score,
            "issues": [
                {
                    "severity": iss.severity,
                    "dimension": iss.dimension,
                    "description": iss.description,
                    "related_field": iss.related_field,
                    "suggested_fix": iss.suggested_fix,
                }
                for iss in vr.issues
            ],
            "missing_items": vr.missing_items,
            "evidence_quotes": vr.evidence_quotes,
        }
    return data


def _deserialize_rule(data: dict) -> ExtractedConditionRule:
    condition = ConceptCode(
        CodeKind(data["condition"]["kind"]), data["condition"]["value"]
    )
    hard_exclusions = {
        ConceptCode(CodeKind(c["kind"]), c["value"]) for c in data["hard_exclusions"]
    }
    preferred_tags = {
        ConceptCode(CodeKind(c["kind"]), c["value"]) for c in data["preferred_tags"]
    }
    nutrition_limits = set()
    for limit_data in data["nutrition_limits"]:
        window_hours = limit_data.get("window_hours")
        nutrition_limits.add(
            NutrientLimit(
                metric=NutrientMetric(limit_data["metric"]),
                scope=LimitScope(limit_data["scope"]),
                max_value=limit_data["max_value"],
                window_hours=window_hours,
            )
        )

    verification_result = None
    if "verification_result" in data and data["verification_result"] is not None:
        vr_data = data["verification_result"]
        issues = []
        for iss_data in vr_data.get("issues", []):
            issues.append(
                VerificationIssue(
                    severity=iss_data["severity"],
                    dimension=iss_data["dimension"],
                    description=iss_data["description"],
                    related_field=iss_data.get("related_field"),
                    suggested_fix=iss_data.get("suggested_fix"),
                )
            )
        verification_result = VerificationResult(
            verdict=vr_data["verdict"],
            confidence=vr_data["confidence"],
            consistency_score=vr_data["consistency_score"],
            logic_score=vr_data["logic_score"],
            completeness_score=vr_data["completeness_score"],
            issues=issues,
            missing_items=vr_data.get("missing_items"),
            evidence_quotes=vr_data.get("evidence_quotes", {}),
        )

    return ExtractedConditionRule(
        candidate_id=data["candidate_id"],
        source_doc_ids=data["source_doc_ids"],
        source_chunk_ids=data["source_chunk_ids"],
        condition=condition,
        hard_exclusions=hard_exclusions,
        preferred_tags=preferred_tags,
        nutrition_limits=nutrition_limits,
        confidence=data["confidence"],
        extraction_method=data["extraction_method"],
        reviewed_by=data.get("reviewed_by"),
        status=data["status"],
        created_at=datetime.fromisoformat(data["created_at"]),
        verification_result=verification_result,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd knowledge && python -m pytest tests/test_store.py -v
```

Expected: all PASS

- [ ] **Step 6: Add .gitignore entry for data/ directory**

Ensure the repo root `.gitignore` contains `data/chroma/`, `data/knowledge.db`. The `data/rules/v*.json` files should be tracked (versioned rules).

Add to root `.gitignore` if not already present:
```
data/chroma/
data/knowledge.db
```

- [ ] **Step 7: Commit**

```bash
git add knowledge/src/knowledge/store.py knowledge/tests/test_store.py data/rules/.gitkeep
git commit -m "feat: add structured rule store with JSON persistence and versioning"
```

---

### Task 4: Implement document management (documents.py)

**Files:**
- Create: `knowledge/src/knowledge/documents.py`
- Test: `knowledge/tests/test_documents.py`

- [ ] **Step 1: Write the failing tests**

Create `knowledge/tests/test_documents.py`:

```python
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge.schema import KnowledgeDocument, DocumentChunk
from knowledge.documents import DocumentImporter

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)

SAMPLE_MD = """# CKD Dietary Guidelines

## Sodium Management

Patients with chronic kidney disease should limit sodium intake to under 2000mg per day.
This helps manage blood pressure and fluid retention.

## Protein Guidelines

Protein intake should be adjusted based on CKD stage. For stages 1-3, moderate protein
restriction of 0.8g/kg/day is recommended. For stages 4-5, further restriction may apply.

## Potassium Monitoring

Serum potassium levels should be monitored regularly. When levels are elevated,
dietary potassium should be limited to 2000-3000mg per day.
"""


@pytest.fixture
def importer():
    return DocumentImporter()


class TestDocumentImporter:
    def test_import_from_text(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="CKD Dietary Guidelines",
            source="ckd-guidelines.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={"year": "2024"},
            ingested_at=NOW,
        )
        assert doc.doc_id == "doc-001"
        assert doc.title == "CKD Dietary Guidelines"
        assert doc.source_type == "guideline"
        assert doc.content_raw == SAMPLE_MD
        assert len(doc.chunks) > 0

    def test_chunks_preserve_text_content(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        all_text = "".join(chunk.text for chunk in doc.chunks)
        assert "sodium intake to under 2000mg" in all_text
        assert "Protein intake should be adjusted" in all_text

    def test_chunks_have_sequential_indices(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        indices = [chunk.chunk_index for chunk in doc.chunks]
        assert indices == sorted(indices)
        assert indices[0] == 0

    def test_chunks_reference_correct_doc_id(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        for chunk in doc.chunks:
            assert chunk.doc_id == "doc-001"

    def test_chunk_ids_are_unique(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        chunk_ids = [chunk.chunk_id for chunk in doc.chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_import_from_file(self, importer):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_MD)
            tmp_path = f.name

        try:
            doc = importer.import_from_file(
                doc_id="doc-002",
                title="From File",
                file_path=tmp_path,
                source_type="guideline",
                metadata={},
            )
            assert doc.doc_id == "doc-002"
            assert len(doc.chunks) > 0
            assert doc.content_raw == SAMPLE_MD
        finally:
            Path(tmp_path).unlink()

    def test_short_text_produces_single_chunk(self, importer):
        short = "Short text."
        doc = importer.import_from_text(
            doc_id="doc-003",
            title="Short",
            source="short.md",
            source_type="paper",
            content=short,
            metadata={},
            ingested_at=NOW,
        )
        assert len(doc.chunks) == 1
        assert doc.chunks[0].text == short

    def test_empty_text_produces_no_chunks(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-004",
            title="Empty",
            source="empty.md",
            source_type="paper",
            content="",
            metadata={},
            ingested_at=NOW,
        )
        assert len(doc.chunks) == 0

    def test_rejects_invalid_source_type(self, importer):
        with pytest.raises(ValueError, match="source_type"):
            importer.import_from_text(
                doc_id="doc-005",
                title="Bad",
                source="bad.md",
                source_type="invalid_type",
                content="text",
                metadata={},
                ingested_at=NOW,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd knowledge && python -m pytest tests/test_documents.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge.documents'`

- [ ] **Step 3: Write knowledge/src/knowledge/documents.py**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


from knowledge.schema import KnowledgeDocument, DocumentChunk

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


class DocumentImporter:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE,
                 chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def import_from_text(
        self,
        doc_id: str,
        title: str,
        source: str,
        source_type: str,
        content: str,
        metadata: dict[str, str],
        ingested_at: datetime,
    ) -> KnowledgeDocument:
        chunks = self._chunk_text(doc_id, content)
        return KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            source=source,
            source_type=source_type,
            content_raw=content,
            chunks=chunks,
            metadata=metadata,
            ingested_at=ingested_at,
        )

    def import_from_file(
        self,
        doc_id: str,
        title: str,
        file_path: str,
        source_type: str,
        metadata: dict[str, str],
    ) -> KnowledgeDocument:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return self.import_from_text(
            doc_id=doc_id,
            title=title,
            source=str(path),
            source_type=source_type,
            content=content,
            metadata=metadata,
            ingested_at=datetime.now(timezone.utc),
        )

    def _chunk_text(self, doc_id: str, text: str) -> list[DocumentChunk]:
        if not text.strip():
            return []

        chunks: list[DocumentChunk] = []
        paragraphs = text.split("\n\n")
        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{doc_id}-chunk-{chunk_index:04d}",
                            doc_id=doc_id,
                            text=current_chunk,
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1

                    if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                        current_chunk = current_chunk[-self.chunk_overlap:] + "\n\n" + para
                    else:
                        current_chunk = para
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{doc_id}-chunk-{chunk_index:04d}",
                    doc_id=doc_id,
                    text=current_chunk,
                    chunk_index=chunk_index,
                )
            )

        return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd knowledge && python -m pytest tests/test_documents.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/src/knowledge/documents.py knowledge/tests/test_documents.py
git commit -m "feat: add document import and chunking"
```

---

### Task 5: Implement ChromaDB vector store wrapper (vectordb.py)

**Files:**
- Create: `knowledge/src/knowledge/vectordb.py`
- Test: `knowledge/tests/test_vectordb.py`

- [ ] **Step 1: Write the failing tests**

Create `knowledge/tests/test_vectordb.py`:

```python
import tempfile
from datetime import datetime, timezone

import pytest

from knowledge.schema import KnowledgeDocument, DocumentChunk
from knowledge.vectordb import KnowledgeVectorDB

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


def _make_doc(doc_id, title, source_type, content, metadata=None):
    chunks = [
        DocumentChunk(
            chunk_id=f"{doc_id}-chunk-0000",
            doc_id=doc_id,
            text=content,
            chunk_index=0,
        )
    ]
    return KnowledgeDocument(
        doc_id=doc_id,
        title=title,
        source="test-source",
        source_type=source_type,
        content_raw=content,
        chunks=chunks,
        metadata=metadata or {},
        ingested_at=NOW,
    )


@pytest.fixture
def vector_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = KnowledgeVectorDB(persist_dir=tmpdir)
        yield db


class TestKnowledgeVectorDB:
    def test_index_and_search(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "CKD Guidelines",
            "guideline",
            "Patients with CKD should limit sodium intake to under 2000mg per day.",
        )
        vector_db.index_document(doc)

        results = vector_db.search("sodium intake for kidney disease", top_k=3)
        assert len(results) > 0
        assert "sodium" in results[0].text.lower()

    def test_search_returns_relevance_scores(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "CKD Guidelines",
            "guideline",
            "Limit sodium to 2000mg per day for kidney patients.",
        )
        vector_db.index_document(doc)

        results = vector_db.search("sodium restriction", top_k=3)
        for result in results:
            assert 0 <= result.relevance_score <= 1

    def test_search_respects_top_k(self, vector_db):
        for i in range(5):
            doc = _make_doc(
                f"doc-{i:03d}",
                f"Doc {i}",
                "guideline",
                f"Sodium intake guideline number {i} for patients.",
            )
            vector_db.index_document(doc)

        results = vector_db.search("sodium", top_k=3)
        assert len(results) == 3

    def test_delete_document(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "To Delete",
            "paper",
            "This document will be deleted.",
        )
        vector_db.index_document(doc)
        results_before = vector_db.search("deleted", top_k=3)
        assert len(results_before) > 0

        vector_db.delete_document("doc-001")
        results_after = vector_db.search("deleted", top_k=3)
        assert len(results_after) == 0

    def test_search_returns_source_metadata(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "Test Title",
            "guideline",
            "Sodium should be limited.",
            metadata={"year": "2024"},
        )
        vector_db.index_document(doc)

        results = vector_db.search("sodium", top_k=1)
        assert len(results) > 0
        assert results[0].source_title == "Test Title"

    def test_empty_search_returns_empty_list(self, vector_db):
        results = vector_db.search("anything", top_k=5)
        assert results == []

    def test_index_empty_chunks_does_not_crash(self, vector_db):
        doc = KnowledgeDocument(
            doc_id="empty-doc",
            title="Empty",
            source="none",
            source_type="paper",
            content_raw="",
            chunks=[],
            metadata={},
            ingested_at=NOW,
        )
        vector_db.index_document(doc)
        results = vector_db.search("test", top_k=3)
        assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd knowledge && python -m pytest tests/test_vectordb.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge.vectordb'`

- [ ] **Step 3: Write knowledge/src/knowledge/vectordb.py**

```python
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from knowledge.schema import KnowledgeDocument, DocumentChunk


class KnowledgeSnippet:
    def __init__(self, text: str, source_title: str, source_url: str,
                 chunk_id: str, relevance_score: float):
        self.text = text
        self.source_title = source_title
        self.source_url = source_url
        self.chunk_id = chunk_id
        self.relevance_score = relevance_score

    def __repr__(self) -> str:
        return (
            f"KnowledgeSnippet(chunk_id={self.chunk_id!r}, "
            f"relevance_score={self.relevance_score:.4f})"
        )


class KnowledgeVectorDB:
    def __init__(self, persist_dir: str = "data/chroma"):
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="knowledge_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._doc_metadata: dict[str, dict[str, str]] = {}

    def index_document(self, doc: KnowledgeDocument) -> None:
        if not doc.chunks:
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for chunk in doc.chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            metadatas.append({
                "doc_id": doc.doc_id,
                "source_title": doc.title,
                "source_url": doc.source,
                "source_type": doc.source_type,
                "chunk_index": chunk.chunk_index,
            })

        self._doc_metadata[doc.doc_id] = {
            "title": doc.title,
            "source": doc.source,
        }

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query: str, top_k: int = 5,
               filter_source: str | None = None) -> list[KnowledgeSnippet]:
        if self._collection.count() == 0:
            return []

        where_filter = None
        if filter_source is not None:
            where_filter = {"source_type": filter_source}

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            where=where_filter,
        )

        snippets: list[KnowledgeSnippet] = []
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for i, chunk_id in enumerate(ids):
            meta = metadatas[i]
            distance = distances[i]
            relevance_score = round(max(0, 1 - distance / 2), 4)

            snippets.append(
                KnowledgeSnippet(
                    text=documents[i],
                    source_title=meta.get("source_title", ""),
                    source_url=meta.get("source_url", ""),
                    chunk_id=chunk_id,
                    relevance_score=relevance_score,
                )
            )

        return snippets

    def search_by_condition(self, condition, top_k: int = 10) -> list[KnowledgeSnippet]:
        from medidiet.domain import ConceptCode
        if isinstance(condition, ConceptCode):
            query = condition.value.replace("_", " ")
        else:
            query = str(condition)
        return self.search(query, top_k=top_k)

    def delete_document(self, doc_id: str) -> None:
        existing = self._collection.get(
            where={"doc_id": doc_id}
        )
        if existing and existing["ids"]:
            self._collection.delete(ids=existing["ids"])

        self._doc_metadata.pop(doc_id, None)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd knowledge && python -m pytest tests/test_vectordb.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/src/knowledge/vectordb.py knowledge/tests/test_vectordb.py
git commit -m "feat: add ChromaDB vector store wrapper with indexing and search"
```

---

### Task 6: Implement batch document loader (loader.py)

**Files:**
- Create: `knowledge/src/knowledge/loader.py`
- Test: `knowledge/tests/test_loader.py`
- Create: `docs/knowledge/guidelines/.gitkeep`
- Create: `docs/knowledge/papers/.gitkeep`
- Create: `docs/knowledge/food_db/.gitkeep`

- [ ] **Step 1: Write the failing tests**

Create `knowledge/tests/test_loader.py`:

```python
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge.documents import DocumentImporter
from knowledge.loader import KnowledgeLoader

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def loader():
    return KnowledgeLoader(importer=DocumentImporter())


class TestKnowledgeLoader:
    def test_load_from_directory(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "guideline-ckd.md"
            file1.write_text("# CKD Guidelines\n\nLimit sodium to under 2000mg per day.", encoding="utf-8")
            file2 = Path(tmpdir) / "paper-protein.md"
            file2.write_text("# Protein Study\n\nProtein intake of 0.8g/kg is recommended for CKD.", encoding="utf-8")

            docs = loader.load_from_directory(tmpdir, source_type="guideline")
            assert len(docs) == 2
            assert all(doc.source_type == "guideline" for doc in docs)

    def test_load_from_directory_skips_non_md_txt(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc.md").write_text("# MD", encoding="utf-8")
            (Path(tmpdir) / "doc.txt").write_text("TXT", encoding="utf-8")
            (Path(tmpdir) / "doc.pdf").write_text("PDF", encoding="utf-8")
            (Path(tmpdir) / "image.png").write_text("PNG", encoding="utf-8")

            docs = loader.load_from_directory(tmpdir, source_type="paper")
            assert len(docs) == 2

    def test_load_empty_directory(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs = loader.load_from_directory(tmpdir, source_type="guideline")
            assert docs == []

    def test_load_nonexistent_directory(self, loader):
        with pytest.raises(FileNotFoundError):
            loader.load_from_directory("/nonexistent/path", source_type="guideline")

    def test_doc_ids_are_derived_from_filename(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "ckd-guideline-2024.md").write_text("# CKD", encoding="utf-8")

            docs = loader.load_from_directory(tmpdir, source_type="guideline")
            assert len(docs) == 1
            assert docs[0].doc_id.startswith("ckd-guideline-2024")

    def test_doc_metadata_includes_filename(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "study.md").write_text("# Study\n\nContent here.", encoding="utf-8")

            docs = loader.load_from_directory(tmpdir, source_type="paper")
            assert len(docs) == 1
            assert "filename" in docs[0].metadata
            assert docs[0].metadata["filename"] == "study.md"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd knowledge && python -m pytest tests/test_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge.loader'`

- [ ] **Step 3: Create docs/knowledge directory structure**

```bash
mkdir -p docs/knowledge/guidelines docs/knowledge/papers docs/knowledge/food_db
touch docs/knowledge/guidelines/.gitkeep
touch docs/knowledge/papers/.gitkeep
touch docs/knowledge/food_db/.gitkeep
```

- [ ] **Step 4: Write knowledge/src/knowledge/loader.py**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from knowledge.documents import DocumentImporter
from knowledge.schema import KnowledgeDocument

SUPPORTED_SUFFIXES = {".md", ".txt"}


class KnowledgeLoader:
    def __init__(self, importer: DocumentImporter | None = None):
        self.importer = importer or DocumentImporter()

    def load_from_directory(self, directory: str, source_type: str) -> list[KnowledgeDocument]:
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"directory not found: {directory}")

        docs: list[KnowledgeDocument] = []
        for file_path in sorted(dir_path.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue

            stem = file_path.stem
            doc_id = stem.lower().replace(" ", "_").replace("-", "_")

            doc = self.importer.import_from_file(
                doc_id=doc_id,
                title=stem.replace("_", " ").replace("-", " "),
                file_path=str(file_path),
                source_type=source_type,
                metadata={"filename": file_path.name},
            )
            docs.append(doc)

        return docs

    def load_and_index(self, directory: str, source_type: str,
                       vector_db=None) -> list[KnowledgeDocument]:
        docs = self.load_from_directory(directory, source_type)
        if vector_db is not None:
            for doc in docs:
                vector_db.index_document(doc)
        return docs
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd knowledge && python -m pytest tests/test_loader.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add knowledge/src/knowledge/loader.py knowledge/tests/test_loader.py docs/knowledge/
git commit -m "feat: add batch document loader with directory import"
```

---

### Task 7: Extend MediDiet ports (ports.py) and add KnowledgeSnippet/KnowledgeContext models

**Files:**
- Modify: `src/medidiet/ports.py`
- Test: `tests/test_ports.py` (update existing)

- [ ] **Step 1: Read the existing ports.py**

Read `src/medidiet/ports.py` to understand current port definitions before extending.

- [ ] **Step 2: Add KnowledgeSnippet, KnowledgeContext dataclasses, RuleProviderPort, and KnowledgePort protocols**

Append to `src/medidiet/ports.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from medidiet.domain import ConceptCode, MealLabel, PatientProfile
from medidiet.rules import RulePack


@dataclass(frozen=True)
class KnowledgeSnippet:
    text: str
    source_title: str
    source_url: str
    chunk_id: str
    relevance_score: float


@dataclass(frozen=True)
class KnowledgeContext:
    snippets: tuple[KnowledgeSnippet, ...]
    related_conditions: tuple[ConceptCode, ...]
    retrieved_at: datetime


class RuleProviderPort(Protocol):
    def load_rule_pack(self, version: str | None = None) -> RulePack:
        ...

    def list_versions(self) -> list[str]:
        ...

    def publish_version(self, version: str, notes: str) -> RulePack:
        ...


class KnowledgePort(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[KnowledgeSnippet]:
        ...

    def explain_rule(self, condition: ConceptCode) -> str:
        ...

    def retrieve_context(
        self, patient: PatientProfile, meal_label: MealLabel,
    ) -> KnowledgeContext:
        ...
```

- [ ] **Step 3: Write/update tests in tests/test_ports.py**

Read the existing `tests/test_ports.py`, then add these tests:

```python
from datetime import datetime, timezone
from medidiet.domain import ConceptCode, CodeKind, MealLabel, PatientProfile, Preference, DataSource
from medidiet.ports import KnowledgeSnippet, KnowledgeContext, RuleProviderPort, KnowledgePort


class TestKnowledgeSnippet:
    def test_valid_snippet(self):
        snippet = KnowledgeSnippet(
            text="Limit sodium to 2000mg per day.",
            source_title="CKD Guidelines",
            source_url="https://example.org/ckd.pdf",
            chunk_id="doc-001-chunk-0000",
            relevance_score=0.85,
        )
        assert snippet.text == "Limit sodium to 2000mg per day."
        assert snippet.relevance_score == 0.85


class TestKnowledgeContext:
    def test_valid_context(self):
        snippets = (
            KnowledgeSnippet(
                text="Sodium restriction.",
                source_title="Guide",
                source_url="https://example.org",
                chunk_id="chunk-001",
                relevance_score=0.9,
            ),
        )
        ctx = KnowledgeContext(
            snippets=snippets,
            related_conditions=(ConceptCode(CodeKind.CONDITION, "hypertension"),),
            retrieved_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
        assert len(ctx.snippets) == 1
        assert len(ctx.related_conditions) == 1


class TestRuleProviderPortProtocol:
    def test_protocol_is_usable_for_type_checking(self):
        class FakeProvider:
            def load_rule_pack(self, version=None):
                pass

            def list_versions(self):
                return []

            def publish_version(self, version, notes):
                pass

        provider = FakeProvider()
        assert isinstance(provider, RuleProviderPort)


class TestKnowledgePortProtocol:
    def test_protocol_is_usable_for_type_checking(self):
        class FakeKnowledge:
            def search(self, query, top_k=5):
                return []

            def explain_rule(self, condition):
                return ""

            def retrieve_context(self, patient, meal_label):
                return KnowledgeContext(
                    snippets=(),
                    related_conditions=(),
                    retrieved_at=datetime.now(timezone.utc),
                )

        kp = FakeKnowledge()
        assert isinstance(kp, KnowledgePort)
```

- [ ] **Step 4: Run the existing port tests + new tests to verify**

```bash
PYTHONPATH=src python -m pytest tests/test_ports.py -v
```

Expected: all tests PASS (old + new)

- [ ] **Step 5: Commit**

```bash
git add src/medidiet/ports.py tests/test_ports.py
git commit -m "feat: add KnowledgePort, RuleProviderPort, and knowledge DTOs to ports"
```

---

### Task 8: Implement knowledge bridge adapter (knowledge_bridge.py)

**Files:**
- Create: `src/medidiet/knowledge_bridge.py`
- Test: `tests/test_knowledge_bridge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_knowledge_bridge.py`:

```python
import tempfile
from datetime import datetime, timezone

import pytest

from medidiet.domain import CodeKind, ConceptCode, MealLabel, PatientProfile, Preference, DataSource
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from medidiet.ports import KnowledgeSnippet, KnowledgeContext, RuleProviderPort, KnowledgePort
from knowledge.schema import ExtractedConditionRule
from knowledge.store import RuleStore
from knowledge.vectordb import KnowledgeVectorDB
from knowledge.documents import DocumentImporter
from knowledge.loader import KnowledgeLoader
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src python -m pytest tests/test_knowledge_bridge.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'medidiet.knowledge_bridge'`

- [ ] **Step 3: Write src/medidiet/knowledge_bridge.py**

```python
from __future__ import annotations

from datetime import datetime, timezone

from medidiet.domain import ConceptCode, CodeKind, MealLabel, PatientProfile
from medidiet.rules import RulePack, ConditionRule, NutrientLimit, RuleSource, ConceptRegistry, ConceptDefinition
from medidiet.ports import KnowledgeSnippet, KnowledgeContext

from knowledge.store import RuleStore
from knowledge.vectordb import KnowledgeVectorDB
from knowledge.schema import ExtractedConditionRule


class KnowledgeRuleProvider:
    def __init__(self, store: RuleStore, version: str | None = None):
        self._store = store
        self._version = version

    def load_rule_pack(self, version: str | None = None) -> RulePack:
        target = version or self._version
        if target is None:
            versions = self._store.list_versions()
            if not versions:
                raise ValueError("no published versions available")
            target = versions[-1]

        extracted_rules = self._store.load_version(target)

        concepts = self._build_concept_registry(extracted_rules)
        rules_by_condition: dict[ConceptCode, ConditionRule] = {}
        for er in extracted_rules:
            rules_by_condition[er.condition] = ConditionRule(
                condition=er.condition,
                hard_exclusions=er.hard_exclusions,
                preferred_tags=er.preferred_tags,
                nutrition_limits=er.nutrition_limits,
            )

        return RulePack(
            version=target,
            sources=(
                RuleSource(
                    title="Knowledge Base",
                    url="",
                    version=target,
                    note="Generated from knowledge base",
                ),
            ),
            concepts=concepts,
            rules_by_condition=rules_by_condition,
        )

    def list_versions(self) -> list[str]:
        return self._store.list_versions()

    def publish_version(self, version: str, notes: str) -> RulePack:
        self._store.publish_version(version, notes)
        return self.load_rule_pack(version)

    def _build_concept_registry(
        self, rules: list[ExtractedConditionRule],
    ) -> ConceptRegistry:
        definitions: list[ConceptDefinition] = []
        seen: set[tuple[CodeKind, str]] = set()

        for rule in rules:
            key = (rule.condition.kind, rule.condition.value)
            if key not in seen:
                seen.add(key)
                definitions.append(
                    ConceptDefinition(
                        code=rule.condition,
                        display_name=rule.condition.value.replace("_", " ").title(),
                    )
                )

            for code in rule.hard_exclusions | rule.preferred_tags:
                key = (code.kind, code.value)
                if key not in seen:
                    seen.add(key)
                    definitions.append(
                        ConceptDefinition(
                            code=code,
                            display_name=code.value.replace("_", " ").title(),
                        )
                    )

        return ConceptRegistry(definitions)


class KnowledgeRetriever:
    def __init__(self, vectordb: KnowledgeVectorDB):
        self._vectordb = vectordb

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeSnippet]:
        results = self._vectordb.search(query, top_k=top_k)
        return [
            KnowledgeSnippet(
                text=r.text,
                source_title=r.source_title,
                source_url=r.source_url,
                chunk_id=r.chunk_id,
                relevance_score=r.relevance_score,
            )
            for r in results
        ]

    def explain_rule(self, condition: ConceptCode) -> str:
        results = self._vectordb.search(
            condition.value.replace("_", " "), top_k=3
        )
        if not results:
            return f"No source documentation found for {condition.value}."

        lines = [f"Sources for {condition.value}:"]
        for r in results:
            lines.append(
                f"- [{r.source_title}] {r.text[:200]}"
                f"{'...' if len(r.text) > 200 else ''}"
            )
        return "\n".join(lines)

    def retrieve_context(
        self, patient: PatientProfile, meal_label: MealLabel,
    ) -> KnowledgeContext:
        queries = [c.value.replace("_", " ") for c in patient.conditions]
        if not queries:
            return KnowledgeContext(
                snippets=(),
                related_conditions=(),
                retrieved_at=datetime.now(timezone.utc),
            )

        all_snippets: list[KnowledgeSnippet] = []
        for query in queries:
            results = self._vectordb.search(query, top_k=3)
            for r in results:
                all_snippets.append(
                    KnowledgeSnippet(
                        text=r.text,
                        source_title=r.source_title,
                        source_url=r.source_url,
                        chunk_id=r.chunk_id,
                        relevance_score=r.relevance_score,
                    )
                )

        all_snippets.sort(key=lambda s: s.relevance_score, reverse=True)
        unique_snippets = list({s.chunk_id: s for s in all_snippets}.values())
        top = unique_snippets[:5]

        return KnowledgeContext(
            snippets=tuple(top),
            related_conditions=tuple(patient.conditions),
            retrieved_at=datetime.now(timezone.utc),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=src python -m pytest tests/test_knowledge_bridge.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/medidiet/knowledge_bridge.py tests/test_knowledge_bridge.py
git commit -m "feat: add knowledge bridge adapter implementing ports"
```

---

### Task 9: Integration test — end-to-end Phase 1 workflow

**Files:**
- Create: `tests/test_knowledge_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_knowledge_integration.py`:

```python
import tempfile
from datetime import datetime, timezone

from knowledge.schema import ExtractedConditionRule, KnowledgeDocument, DocumentChunk
from knowledge.store import RuleStore
from knowledge.documents import DocumentImporter
from knowledge.vectordb import KnowledgeVectorDB
from knowledge.loader import KnowledgeLoader
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
            assert "v1.0" in store.list_versions()

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
```

- [ ] **Step 2: Run integration test**

```bash
PYTHONPATH=src python -m pytest tests/test_knowledge_integration.py -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_knowledge_integration.py
git commit -m "test: add Phase 1 end-to-end integration test"
```

---

### Task 10: Run full test suite and verify no regressions

- [ ] **Step 1: Run all existing MediDiet tests**

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: all existing tests PASS with zero failures

- [ ] **Step 2: Run all new knowledge package tests**

```bash
cd knowledge && python -m pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 3: Run knowledge bridge integration test**

```bash
PYTHONPATH=src python -m pytest tests/test_knowledge_bridge.py tests/test_knowledge_integration.py -v
```

Expected: all PASS

- [ ] **Step 4: Verify port type checking (optional)**

```bash
PYTHONPATH=src python -m pytest tests/test_ports.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit if any final adjustments were needed**

```bash
git add -A
git commit -m "chore: finalize Phase 1 with all tests passing"
```
