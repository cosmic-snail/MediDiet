# Rule Extraction Stratified Gold Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace one mixed rule-extraction F1 with a verifiable, product-aligned evaluation stack that separates clean extraction, contextual handling, unit conversion, and atomic concept discovery.

**Architecture:** Keep the frozen `gold_evaluation_set.jsonl` unchanged while adding explicit per-track expectation files and centralized taxonomy enums. Evaluate each track with a focused scorer, then publish one stratified report that preserves the old mixed score for continuity and makes `clean_extraction_f1` the headline regression guard. Concept evaluation reuses the existing product `ConceptRegistry` JSONL schema so manually entered and LLM-proposed concepts share the same registration path.

**Tech Stack:** Python standard library, pytest, JSONL dataset metadata, existing `medidiet.concept_registry`, existing `knowledge.rule_evaluation`, existing `knowledge.gold_audit`, existing real-LLM report pipeline in `knowledge.rule_extraction_dataset_smoke`.

---

## Current State

The current PR already added a gold audit layer:

- Frozen gold file: `knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl`
- Audit metadata file: `knowledge/datasets/rule_extraction_v1/gold_audit.jsonl`
- Audit report module: `knowledge/src/knowledge/gold_audit.py`
- Manual audit report: `reports/rule-extraction-v1-gold-audit-20260602.md`

The audit split is:

| audit_status | count | meaning |
|---|---:|---|
| `keep` | 7 | can be used in the clean headline score |
| `borderline` | 1 | source supports a signal, but the disease/rule binding is contextual |
| `revise_gold` | 2 | current gold asks for a field not directly supported by current source-card input |
| `revise_schema_or_gold` | 3 | source supports concepts that should be atomic or registry-driven rather than umbrella ids |
| `review_negative` | 1 | current negative label is too coarse for a dietary-pattern source |

The evidence split is:

| evidence_level | count | intended track |
|---|---:|---|
| `source_card_direct` | 6 | clean extraction or contextual rule, depending on audit status |
| `contextual_negative` | 3 | clean negative or contextual handling |
| `derived_conversion` | 2 | conversion or gold-revision track |
| `schema_gap` | 3 | concept discovery and product registry track |

The optimization must preserve this principle:

```text
Do not improve metrics by editing source cards to expose frozen gold answers.
If a source does not directly provide the value required by gold, move the case into a separate evaluation track.
```

## Target Evaluation Tracks

| track | input evidence | scorer asks | primary metric |
|---|---|---|---|
| `clean_extraction` | source card directly supports the expected rule, or trusted negative | Did the extractor directly recover a supported structured rule or avoid hallucinating one? | precision / recall / F1 |
| `contextual_handling` | source has nutrition signal but not a fixed disease-specific numeric rule | Did the extractor preserve context without over-claiming a hard rule? | contextual accept rate and overclaim rate |
| `conversion` | source gives a different unit or expression such as percent of energy | Did the system declare the needed conversion, formula, assumptions, and output value correctly? | conversion accuracy |
| `concept_discovery` | source contains concepts not yet represented by supported rule fields | Did the system propose or match product-ready atomic concepts and aliases? | atomic concept recall / precision |
| `mixed_legacy` | all frozen gold rows | Backward-compatible score only; not the main headline | legacy precision / recall / F1 |

The headline number after this plan should be:

```text
clean_extraction_f1
```

The other tracks should be reported beside it, not averaged into it.

## File Structure

Create or modify these files:

- Create: `knowledge/src/knowledge/evaluation_taxonomy.py`
- Create: `knowledge/tests/test_evaluation_taxonomy.py`
- Create: `knowledge/datasets/rule_extraction_v1/concept_expectations.jsonl`
- Create: `knowledge/tests/test_concept_expectations.py`
- Create: `knowledge/src/knowledge/concept_evaluation.py`
- Create: `knowledge/tests/test_concept_evaluation.py`
- Create: `knowledge/datasets/rule_extraction_v1/conversion_expectations.jsonl`
- Create: `knowledge/src/knowledge/conversion_evaluation.py`
- Create: `knowledge/tests/test_conversion_evaluation.py`
- Create: `knowledge/datasets/rule_extraction_v1/contextual_expectations.jsonl`
- Create: `knowledge/src/knowledge/contextual_evaluation.py`
- Create: `knowledge/tests/test_contextual_evaluation.py`
- Create: `knowledge/src/knowledge/stratified_evaluation.py`
- Create: `knowledge/tests/test_stratified_evaluation.py`
- Modify: `knowledge/src/knowledge/gold_audit.py`
- Modify: `knowledge/src/knowledge/rule_evaluation.py`
- Modify: `knowledge/src/knowledge/rule_extraction_dataset_smoke.py`
- Modify: `knowledge/tests/test_gold_audit.py`
- Modify: `knowledge/tests/test_rule_extraction_dataset.py`
- Modify: `knowledge/tests/test_rule_extraction_dataset_smoke_reports.py`
- Modify: `knowledge/datasets/rule_extraction_v1/README.zh.md`
- Modify: `docs/research/doc-rule-agent-research-protocol.md`
- Modify: `reports/rule-extraction-v1-gold-audit-20260602.md`

Do not modify:

- `knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl` during this plan.
- source cards solely to expose a benchmark-required answer.

## Data Contract

### `concept_expectations.jsonl`

Each row describes atomic expected concepts for one schema-gap gold row.

```json
{
  "gold_id": "gold_en_manual_niddk_ckd_eating_right_001",
  "doc_id": "en_manual_niddk_ckd_eating_right",
  "track": "concept_discovery",
  "expected_atomic_concepts": [
    {
      "kind": "nutrition_tag",
      "value": "low_sodium",
      "aliases": ["sodium restriction", "limit sodium", "低钠"]
    },
    {
      "kind": "nutrition_tag",
      "value": "potassium_management",
      "aliases": ["potassium restriction", "limit potassium", "钾管理"]
    },
    {
      "kind": "nutrition_tag",
      "value": "phosphorus_management",
      "aliases": ["phosphorus restriction", "limit phosphorus", "磷管理"]
    },
    {
      "kind": "nutrition_tag",
      "value": "controlled_protein",
      "aliases": ["protein management", "protein control", "蛋白质控制"]
    }
  ],
  "source_support": "Source card states CKD eating plans may require attention to sodium, protein, potassium, and phosphorus.",
  "do_not_score_as": ["potassium_phosphorus_management"]
}
```

Use `kind` values supported by `medidiet.domain.CodeKind`. Keep concept `value` in normalized snake_case.

### `conversion_expectations.jsonl`

Each row describes a conversion that should be evaluated as conversion, not direct extraction.

```json
{
  "gold_id": "gold_en_guideline_who_sugars_2015_001",
  "doc_id": "en_guideline_who_sugars_2015",
  "track": "conversion",
  "source_expression": {
    "metric": "free_sugars_percent_energy",
    "max_value": 10,
    "scope": "daily"
  },
  "target_expression": {
    "metric": "sugar_g",
    "max_value": 50,
    "scope": "daily"
  },
  "required_assumptions": [
    {
      "name": "energy_reference_kcal",
      "value": 2000,
      "source": "benchmark_assumption"
    },
    {
      "name": "sugar_kcal_per_g",
      "value": 4,
      "source": "nutrition_conversion_constant"
    }
  ],
  "formula": "sugar_g = energy_reference_kcal * percent_energy / 100 / sugar_kcal_per_g",
  "conversion_policy": "Report the conversion separately from clean extraction. Do not require the extractor to infer 50 g when the source card only exposes percent-of-energy guidance."
}
```

Rows such as `en_manual_medlineplus_low_sodium_diet` should not be forced into conversion unless the current source input exposes a numeric expression to convert. If no numeric expression is present, keep it as a `revise_gold` case with `recommended_action=remove_numeric_limit`.

### `contextual_expectations.jsonl`

Each row describes a source that has nutrition signal but should not be judged as a plain fixed-limit rule.

```json
{
  "gold_id": "gold_en_paper_mediterranean_diet_cardiovascular_prevention_001",
  "doc_id": "en_paper_mediterranean_diet_cardiovascular_prevention",
  "track": "contextual_handling",
  "expected_context": {
    "condition": "cardiovascular_risk",
    "nutrition_signal": "dietary_pattern",
    "pattern_tags": ["mediterranean_pattern", "plant_foods", "nuts", "olive_oil"]
  },
  "forbidden_overclaims": [
    {
      "type": "numeric_limit",
      "metrics": ["fat_g", "sodium_mg", "sugar_g"]
    }
  ],
  "acceptance_policy": "Accept contextual/pattern extraction or no fixed rule. Reject invented numeric nutrient limits."
}
```

## Task 1: Centralize Evaluation Taxonomy

**Files:**
- Create: `knowledge/src/knowledge/evaluation_taxonomy.py`
- Create: `knowledge/tests/test_evaluation_taxonomy.py`
- Modify: `knowledge/src/knowledge/gold_audit.py`
- Modify: `knowledge/tests/test_rule_extraction_dataset.py`

- [ ] **Step 1: Write the failing taxonomy tests**

Create `knowledge/tests/test_evaluation_taxonomy.py`:

```python
from knowledge.evaluation_taxonomy import (
    AuditStatus,
    EvaluationTrack,
    EvidenceLevel,
    RecommendedAction,
    clean_headline_filter,
    normalize_audit_status,
    normalize_evaluation_track,
    normalize_evidence_level,
    normalize_recommended_action,
)


def test_normalizers_accept_known_values():
    assert normalize_evidence_level("source_card_direct") is EvidenceLevel.SOURCE_CARD_DIRECT
    assert normalize_audit_status("keep") is AuditStatus.KEEP
    assert normalize_recommended_action("replace_umbrella_concept") is RecommendedAction.REPLACE_UMBRELLA_CONCEPT
    assert normalize_evaluation_track("concept_discovery") is EvaluationTrack.CONCEPT_DISCOVERY


def test_clean_headline_filter_keeps_direct_and_trusted_negative_rows():
    assert clean_headline_filter(
        evidence_level=EvidenceLevel.SOURCE_CARD_DIRECT,
        audit_status=AuditStatus.KEEP,
    )
    assert clean_headline_filter(
        evidence_level=EvidenceLevel.CONTEXTUAL_NEGATIVE,
        audit_status=AuditStatus.KEEP,
    )
    assert not clean_headline_filter(
        evidence_level=EvidenceLevel.DERIVED_CONVERSION,
        audit_status=AuditStatus.REVISE_GOLD,
    )
    assert not clean_headline_filter(
        evidence_level=EvidenceLevel.SCHEMA_GAP,
        audit_status=AuditStatus.REVISE_SCHEMA_OR_GOLD,
    )


def test_normalizers_reject_unknown_values():
    try:
        normalize_evaluation_track("one_big_f1")
    except ValueError as exc:
        assert "unknown evaluation track" in str(exc)
    else:
        raise AssertionError("unknown evaluation track should fail")
```

- [ ] **Step 2: Run the taxonomy tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_evaluation_taxonomy.py -q --rootdir=.
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge.evaluation_taxonomy'`.

- [ ] **Step 3: Implement `evaluation_taxonomy.py`**

Create `knowledge/src/knowledge/evaluation_taxonomy.py`:

```python
from __future__ import annotations

from enum import Enum


class EvidenceLevel(str, Enum):
    SOURCE_CARD_DIRECT = "source_card_direct"
    ORIGINAL_SOURCE_DIRECT = "original_source_direct"
    DERIVED_CONVERSION = "derived_conversion"
    SCHEMA_GAP = "schema_gap"
    CONTEXTUAL_NEGATIVE = "contextual_negative"


class AuditStatus(str, Enum):
    KEEP = "keep"
    BORDERLINE = "borderline"
    REVISE_GOLD = "revise_gold"
    REVISE_SCHEMA_OR_GOLD = "revise_schema_or_gold"
    REVIEW_NEGATIVE = "review_negative"


class RecommendedAction(str, Enum):
    KEEP = "keep"
    REVIEW_CONDITION_SCOPE = "review_condition_scope"
    REMOVE_NUMERIC_LIMIT = "remove_numeric_limit"
    ADD_PERCENT_ENERGY_SCHEMA = "add_percent_energy_schema"
    REPLACE_UMBRELLA_CONCEPT = "replace_umbrella_concept"
    MARK_CONTEXTUAL = "mark_contextual"
    FIX_NEGATIVE_FAILURE_LABEL = "fix_negative_failure_label"


class EvaluationTrack(str, Enum):
    CLEAN_EXTRACTION = "clean_extraction"
    CONTEXTUAL_HANDLING = "contextual_handling"
    CONVERSION = "conversion"
    CONCEPT_DISCOVERY = "concept_discovery"
    MIXED_LEGACY = "mixed_legacy"


CLEAN_HEADLINE_EVIDENCE_LEVELS = {
    EvidenceLevel.SOURCE_CARD_DIRECT,
    EvidenceLevel.ORIGINAL_SOURCE_DIRECT,
    EvidenceLevel.CONTEXTUAL_NEGATIVE,
}
CLEAN_HEADLINE_AUDIT_STATUSES = {AuditStatus.KEEP}


def normalize_evidence_level(value: EvidenceLevel | str) -> EvidenceLevel:
    try:
        return value if isinstance(value, EvidenceLevel) else EvidenceLevel(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown evidence level: {value}") from exc


def normalize_audit_status(value: AuditStatus | str) -> AuditStatus:
    try:
        return value if isinstance(value, AuditStatus) else AuditStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown audit status: {value}") from exc


def normalize_recommended_action(value: RecommendedAction | str) -> RecommendedAction:
    try:
        return value if isinstance(value, RecommendedAction) else RecommendedAction(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown recommended action: {value}") from exc


def normalize_evaluation_track(value: EvaluationTrack | str) -> EvaluationTrack:
    try:
        return value if isinstance(value, EvaluationTrack) else EvaluationTrack(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown evaluation track: {value}") from exc


def clean_headline_filter(*, evidence_level: EvidenceLevel | str, audit_status: AuditStatus | str) -> bool:
    return (
        normalize_evidence_level(evidence_level) in CLEAN_HEADLINE_EVIDENCE_LEVELS
        and normalize_audit_status(audit_status) in CLEAN_HEADLINE_AUDIT_STATUSES
    )
```

- [ ] **Step 4: Replace scattered strings in `gold_audit.py`**

Modify `knowledge/src/knowledge/gold_audit.py`:

```python
from knowledge.evaluation_taxonomy import clean_headline_filter
```

Replace the local `CLEAN_HEADLINE_EVIDENCE_LEVELS` and `CLEAN_HEADLINE_AUDIT_STATUSES` sets with calls to `clean_headline_filter(...)`.

For `clean_evaluations`, use:

```python
clean_evaluations = [
    evaluation
    for evaluation in annotated_evaluations
    if evaluation.get("evidence_level") is not None
    and evaluation.get("audit_status") is not None
    and clean_headline_filter(
        evidence_level=str(evaluation["evidence_level"]),
        audit_status=str(evaluation["audit_status"]),
    )
]
```

For `clean_headline_record_count`, use:

```python
"clean_headline_record_count": len(
    [
        gold_audit_row
        for gold_audit_row in audit_rows
        if gold_audit_row.get("evidence_level") is not None
        and gold_audit_row.get("audit_status") is not None
        and clean_headline_filter(
            evidence_level=str(gold_audit_row["evidence_level"]),
            audit_status=str(gold_audit_row["audit_status"]),
        )
    ]
),
```

- [ ] **Step 5: Update dataset validation to use taxonomy enums**

Modify `knowledge/tests/test_rule_extraction_dataset.py` so the allowed sets come from the enums:

```python
from knowledge.evaluation_taxonomy import AuditStatus, EvidenceLevel, RecommendedAction


ALLOWED_GOLD_AUDIT_EVIDENCE_LEVELS = {item.value for item in EvidenceLevel}
ALLOWED_GOLD_AUDIT_STATUSES = {item.value for item in AuditStatus}
ALLOWED_GOLD_AUDIT_ACTIONS = {item.value for item in RecommendedAction}
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_evaluation_taxonomy.py knowledge/tests/test_gold_audit.py knowledge/tests/test_rule_extraction_dataset.py::test_gold_audit_metadata_covers_every_frozen_gold_row -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add knowledge/src/knowledge/evaluation_taxonomy.py knowledge/src/knowledge/gold_audit.py knowledge/tests/test_evaluation_taxonomy.py knowledge/tests/test_rule_extraction_dataset.py
git commit -m "refactor: centralize evaluation taxonomy"
```

## Task 2: Add Atomic Concept Expectations

**Files:**
- Create: `knowledge/datasets/rule_extraction_v1/concept_expectations.jsonl`
- Create: `knowledge/tests/test_concept_expectations.py`
- Modify: `knowledge/datasets/rule_extraction_v1/README.zh.md`

- [ ] **Step 1: Write the failing dataset expectation test**

Create `knowledge/tests/test_concept_expectations.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from medidiet.domain import CodeKind, ConceptCode


DATASET_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "datasets" / "rule_extraction_v1"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_concept_expectations_cover_schema_gap_gold_rows():
    audit_rows = _read_jsonl(DATASET_DIR / "gold_audit.jsonl")
    expectation_rows = _read_jsonl(DATASET_DIR / "concept_expectations.jsonl")
    schema_gap_gold_ids = {
        row["gold_id"]
        for row in audit_rows
        if row["evidence_level"] == "schema_gap"
        and row["audit_status"] == "revise_schema_or_gold"
    }
    expectation_gold_ids = {row["gold_id"] for row in expectation_rows}

    assert expectation_gold_ids == schema_gap_gold_ids


def test_concept_expectations_use_atomic_product_concepts():
    expectation_rows = _read_jsonl(DATASET_DIR / "concept_expectations.jsonl")
    for expectation_row in expectation_rows:
        assert expectation_row["track"] == "concept_discovery"
        assert expectation_row["expected_atomic_concepts"]
        seen_codes: set[tuple[str, str]] = set()
        for concept_record in expectation_row["expected_atomic_concepts"]:
            kind = CodeKind(concept_record["kind"])
            code = ConceptCode(kind, concept_record["value"])
            key = (code.kind.value, code.value)
            assert key not in seen_codes
            seen_codes.add(key)
            assert concept_record["aliases"]
        for umbrella_code in expectation_row.get("do_not_score_as", []):
            assert umbrella_code not in {value for _, value in seen_codes}
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_concept_expectations.py -q --rootdir=.
```

Expected: FAIL because `concept_expectations.jsonl` does not exist.

- [ ] **Step 3: Add `concept_expectations.jsonl`**

Create `knowledge/datasets/rule_extraction_v1/concept_expectations.jsonl` with exactly three rows:

```jsonl
{"gold_id":"gold_en_manual_niddk_ckd_eating_right_001","doc_id":"en_manual_niddk_ckd_eating_right","track":"concept_discovery","expected_atomic_concepts":[{"kind":"nutrition_tag","value":"low_sodium","aliases":["sodium restriction","limit sodium","low-sodium diet","低钠"]},{"kind":"nutrition_tag","value":"potassium_management","aliases":["potassium restriction","limit potassium","potassium control","钾管理"]},{"kind":"nutrition_tag","value":"phosphorus_management","aliases":["phosphorus restriction","limit phosphorus","phosphorus control","磷管理"]},{"kind":"nutrition_tag","value":"controlled_protein","aliases":["protein management","protein control","controlled protein","蛋白质控制"]}],"source_support":"Source card states CKD eating plans may require attention to sodium, protein, potassium, and phosphorus.","do_not_score_as":["potassium_phosphorus_management"]}
{"gold_id":"gold_en_manual_mayo_gout_diet_001","doc_id":"en_manual_mayo_gout_diet","track":"concept_discovery","expected_atomic_concepts":[{"kind":"nutrition_tag","value":"low_purine","aliases":["purine restriction","limit high-purine foods","low purine diet","限制高嘌呤"]},{"kind":"contraindication","value":"alcohol","aliases":["limit alcohol","avoid alcohol","alcohol restriction","限制饮酒"]},{"kind":"contraindication","value":"high_fructose","aliases":["limit fructose","avoid sweetened drinks","high-fructose drinks","限制果糖"]},{"kind":"nutrition_tag","value":"hydration_support","aliases":["adequate hydration","drink enough fluids","fluid intake","充足饮水"]}],"source_support":"Source card discusses high-purine foods, alcohol, sweetened drinks, and hydration in gout diet advice.","do_not_score_as":["purine_alcohol_fructose_hydration"]}
{"gold_id":"gold_zh_guideline_gout_food_therapy_2024_001","doc_id":"zh_guideline_gout_food_therapy_2024","track":"concept_discovery","expected_atomic_concepts":[{"kind":"nutrition_tag","value":"low_purine","aliases":["purine restriction","limit high-purine foods","低嘌呤","限制高嘌呤"]},{"kind":"contraindication","value":"alcohol","aliases":["limit alcohol","avoid alcohol","限制饮酒","戒酒"]},{"kind":"nutrition_tag","value":"hydration_support","aliases":["adequate hydration","drink enough fluids","多饮水","充足饮水"]}],"source_support":"Source card raises purine exposure, alcohol control, and hydration as disease-relevant nutrition concepts.","do_not_score_as":["purine_and_alcohol_limits"]}
```

- [ ] **Step 4: Add README description**

Modify `knowledge/datasets/rule_extraction_v1/README.zh.md` file list:

```markdown
- `concept_expectations.jsonl`：schema-gap gold 的 atomic concept 期望与 alias group，用于产品概念注册和实验概念评估。
```

- [ ] **Step 5: Run dataset tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_concept_expectations.py knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add knowledge/datasets/rule_extraction_v1/concept_expectations.jsonl knowledge/datasets/rule_extraction_v1/README.zh.md knowledge/tests/test_concept_expectations.py
git commit -m "data: add atomic concept expectations"
```

## Task 3: Score Atomic Concept Discovery Against Product Registry Semantics

**Files:**
- Create: `knowledge/src/knowledge/concept_evaluation.py`
- Create: `knowledge/tests/test_concept_evaluation.py`
- Modify: `knowledge/src/knowledge/rule_evaluation.py`
- Modify: `knowledge/tests/test_rule_evaluation.py`

- [ ] **Step 1: Write failing concept evaluation tests**

Create `knowledge/tests/test_concept_evaluation.py`:

```python
from knowledge.concept_evaluation import evaluate_concept_expectation, precision_recall_f1_for_concepts


def test_evaluate_concept_expectation_matches_atomic_values_and_aliases():
    expectation = {
        "gold_id": "gold-gout",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "low_purine", "aliases": ["limit high-purine foods"]},
            {"kind": "contraindication", "value": "alcohol", "aliases": ["limit alcohol"]},
        ],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {"kind": "nutrition_tag", "suggested_code": "limit high-purine foods"},
                {"kind": "contraindication", "suggested_code": "alcohol"},
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["matched_concepts"] == [
        {"kind": "nutrition_tag", "value": "low_purine"},
        {"kind": "contraindication", "value": "alcohol"},
    ]
    assert evaluation["missing_concepts"] == []


def test_evaluate_concept_expectation_penalizes_umbrella_only_match():
    expectation = {
        "gold_id": "gold-ckd",
        "expected_atomic_concepts": [
            {"kind": "nutrition_tag", "value": "potassium_management", "aliases": ["potassium restriction"]},
            {"kind": "nutrition_tag", "value": "phosphorus_management", "aliases": ["phosphorus restriction"]},
        ],
        "do_not_score_as": ["potassium_phosphorus_management"],
    }
    extracted_rules = [
        {
            "suggested_concepts": [
                {"kind": "nutrition_tag", "suggested_code": "potassium_phosphorus_management"}
            ]
        }
    ]

    evaluation = evaluate_concept_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "miss"
    assert evaluation["missing_concepts"] == [
        {"kind": "nutrition_tag", "value": "potassium_management"},
        {"kind": "nutrition_tag", "value": "phosphorus_management"},
    ]


def test_precision_recall_f1_for_concepts_counts_extra_atomic_concepts():
    evaluations = [
        {"true_positive_count": 2, "false_negative_count": 0, "false_positive_count": 1},
        {"true_positive_count": 1, "false_negative_count": 1, "false_positive_count": 0},
    ]

    assert precision_recall_f1_for_concepts(evaluations) == {
        "precision": 0.75,
        "recall": 0.75,
        "f1": 0.75,
    }
```

- [ ] **Step 2: Run the concept evaluation tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_concept_evaluation.py -q --rootdir=.
```

Expected: FAIL because `knowledge.concept_evaluation` does not exist.

- [ ] **Step 3: Implement concept evaluation**

Create `knowledge/src/knowledge/concept_evaluation.py`:

```python
from __future__ import annotations

from typing import Any


def evaluate_concept_expectation(expectation: dict[str, Any], extracted_rules: list[dict[str, Any]]) -> dict[str, Any]:
    expected_records = expectation.get("expected_atomic_concepts", []) or []
    expected_by_alias: dict[tuple[str, str], tuple[str, str]] = {}
    expected_keys: set[tuple[str, str]] = set()
    forbidden_values = {str(value) for value in expectation.get("do_not_score_as", []) or []}

    for expected_record in expected_records:
        kind = str(expected_record["kind"])
        value = str(expected_record["value"])
        expected_key = (kind, value)
        expected_keys.add(expected_key)
        expected_by_alias[(kind, value.lower())] = expected_key
        for alias in expected_record.get("aliases", []) or []:
            expected_by_alias[(kind, str(alias).strip().lower())] = expected_key

    extracted_keys: set[tuple[str, str]] = set()
    forbidden_matches: set[str] = set()
    for extracted_rule in extracted_rules:
        for concept_record in extracted_rule.get("suggested_concepts", []) or []:
            kind = str(concept_record.get("kind") or concept_record.get("suggested_kind") or "nutrition_tag")
            raw_value = str(concept_record.get("suggested_code") or concept_record.get("value") or concept_record)
            normalized_value = raw_value.strip().lower()
            if normalized_value in forbidden_values:
                forbidden_matches.add(normalized_value)
                continue
            matched_key = expected_by_alias.get((kind, normalized_value))
            if matched_key is not None:
                extracted_keys.add(matched_key)
            elif raw_value:
                extracted_keys.add((kind, normalized_value))

    true_positive_keys = expected_keys & extracted_keys
    false_negative_keys = expected_keys - extracted_keys
    false_positive_keys = extracted_keys - expected_keys

    return {
        "gold_id": expectation.get("gold_id"),
        "track": "concept_discovery",
        "overall": "match" if not false_negative_keys else "miss",
        "matched_concepts": _sorted_concepts(true_positive_keys),
        "missing_concepts": _sorted_concepts(false_negative_keys),
        "extra_concepts": _sorted_concepts(false_positive_keys),
        "forbidden_umbrella_matches": sorted(forbidden_matches),
        "true_positive_count": len(true_positive_keys),
        "false_negative_count": len(false_negative_keys),
        "false_positive_count": len(false_positive_keys),
    }


def precision_recall_f1_for_concepts(evaluations: list[dict[str, Any]]) -> dict[str, float]:
    true_positive_count = sum(int(evaluation.get("true_positive_count", 0)) for evaluation in evaluations)
    false_negative_count = sum(int(evaluation.get("false_negative_count", 0)) for evaluation in evaluations)
    false_positive_count = sum(int(evaluation.get("false_positive_count", 0)) for evaluation in evaluations)
    precision = true_positive_count / (true_positive_count + false_positive_count) if true_positive_count + false_positive_count else 0.0
    recall = true_positive_count / (true_positive_count + false_negative_count) if true_positive_count + false_negative_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _sorted_concepts(keys: set[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"kind": kind, "value": value} for kind, value in sorted(keys)]
```

- [ ] **Step 4: Remove reporting-only umbrella alias logic from `rule_evaluation.py`**

Replace `SUGGESTED_CONCEPT_ALIASES` with a comment explaining that umbrella-to-atomic matching now lives in `concept_evaluation.py`.

In `knowledge/tests/test_rule_evaluation.py`, replace the old alias test:

```python
def test_concept_gap_alias_is_reporting_only():
    gold = {"gold_id": "gap", "should_extract": True, "condition": "ckd", "suggested_concepts": ["potassium_phosphorus_management"], "nutrition_limits": []}
    extracted = [{"condition": "ckd", "suggested_concepts": ["potassium_management", "phosphorus_management"], "nutrition_limits": []}]
    assert "suggested_concept_mismatch" not in evaluate_rule(gold, extracted)["failures"]
```

with:

```python
def test_umbrella_concept_is_not_soft_matched_in_clean_rule_evaluation():
    gold = {
        "gold_id": "gap",
        "gold_behavior": "suggested_concept",
        "suggested_concepts": ["potassium_phosphorus_management"],
    }
    extracted = [{"suggested_concepts": ["potassium_management", "phosphorus_management"]}]

    evaluation = evaluate_rule(gold, extracted)

    assert evaluation["overall"] == "miss"
    assert "suggested_concept_mismatch" in evaluation["failures"]
```

This keeps old mixed score behavior explicit while moving fair atomic scoring to the concept track.

- [ ] **Step 5: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_concept_evaluation.py knowledge/tests/test_rule_evaluation.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add knowledge/src/knowledge/concept_evaluation.py knowledge/src/knowledge/rule_evaluation.py knowledge/tests/test_concept_evaluation.py knowledge/tests/test_rule_evaluation.py
git commit -m "feat: score atomic concept discovery"
```

## Task 4: Add Conversion Evaluation

**Files:**
- Create: `knowledge/datasets/rule_extraction_v1/conversion_expectations.jsonl`
- Create: `knowledge/src/knowledge/conversion_evaluation.py`
- Create: `knowledge/tests/test_conversion_evaluation.py`
- Modify: `knowledge/datasets/rule_extraction_v1/README.zh.md`

- [ ] **Step 1: Write failing conversion tests**

Create `knowledge/tests/test_conversion_evaluation.py`:

```python
from knowledge.conversion_evaluation import evaluate_conversion_expectation


def test_evaluate_percent_energy_to_grams_conversion():
    expectation = {
        "gold_id": "gold-sugar",
        "source_expression": {"metric": "free_sugars_percent_energy", "max_value": 10, "scope": "daily"},
        "target_expression": {"metric": "sugar_g", "max_value": 50, "scope": "daily"},
        "required_assumptions": [
            {"name": "energy_reference_kcal", "value": 2000, "source": "benchmark_assumption"},
            {"name": "sugar_kcal_per_g", "value": 4, "source": "nutrition_conversion_constant"},
        ],
    }
    extracted_conversion = {
        "source_metric": "free_sugars_percent_energy",
        "target_metric": "sugar_g",
        "source_value": 10,
        "target_value": 50,
        "assumptions": {"energy_reference_kcal": 2000, "sugar_kcal_per_g": 4},
    }

    evaluation = evaluate_conversion_expectation(expectation, extracted_conversion)

    assert evaluation["overall"] == "match"
    assert evaluation["value_error"] == 0


def test_conversion_requires_explicit_assumptions():
    expectation = {
        "gold_id": "gold-sugar",
        "source_expression": {"metric": "free_sugars_percent_energy", "max_value": 10, "scope": "daily"},
        "target_expression": {"metric": "sugar_g", "max_value": 50, "scope": "daily"},
        "required_assumptions": [
            {"name": "energy_reference_kcal", "value": 2000, "source": "benchmark_assumption"},
            {"name": "sugar_kcal_per_g", "value": 4, "source": "nutrition_conversion_constant"},
        ],
    }
    extracted_conversion = {
        "source_metric": "free_sugars_percent_energy",
        "target_metric": "sugar_g",
        "source_value": 10,
        "target_value": 50,
        "assumptions": {"sugar_kcal_per_g": 4},
    }

    evaluation = evaluate_conversion_expectation(expectation, extracted_conversion)

    assert evaluation["overall"] == "miss"
    assert evaluation["missing_assumptions"] == ["energy_reference_kcal"]
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_conversion_evaluation.py -q --rootdir=.
```

Expected: FAIL because `knowledge.conversion_evaluation` does not exist.

- [ ] **Step 3: Add conversion expectations**

Create `knowledge/datasets/rule_extraction_v1/conversion_expectations.jsonl`:

```jsonl
{"gold_id":"gold_en_guideline_who_sugars_2015_001","doc_id":"en_guideline_who_sugars_2015","track":"conversion","source_expression":{"metric":"free_sugars_percent_energy","max_value":10,"scope":"daily"},"target_expression":{"metric":"sugar_g","max_value":50,"scope":"daily"},"required_assumptions":[{"name":"energy_reference_kcal","value":2000,"source":"benchmark_assumption"},{"name":"sugar_kcal_per_g","value":4,"source":"nutrition_conversion_constant"}],"formula":"sugar_g = energy_reference_kcal * percent_energy / 100 / sugar_kcal_per_g","conversion_policy":"Report this as conversion accuracy, not clean extraction recall."}
```

- [ ] **Step 4: Implement conversion evaluator**

Create `knowledge/src/knowledge/conversion_evaluation.py`:

```python
from __future__ import annotations

from typing import Any


def evaluate_conversion_expectation(
    expectation: dict[str, Any],
    extracted_conversion: dict[str, Any] | None,
    *,
    tolerance: float = 0.001,
) -> dict[str, Any]:
    if extracted_conversion is None:
        return {
            "gold_id": expectation.get("gold_id"),
            "track": "conversion",
            "overall": "miss",
            "missing_assumptions": [str(item["name"]) for item in expectation.get("required_assumptions", []) or []],
            "value_error": None,
            "failures": ["missing_conversion"],
        }

    required_assumptions = expectation.get("required_assumptions", []) or []
    provided_assumptions = extracted_conversion.get("assumptions", {}) or {}
    missing_assumptions = [
        str(assumption["name"])
        for assumption in required_assumptions
        if str(assumption["name"]) not in provided_assumptions
    ]
    expected_value = float(expectation["target_expression"]["max_value"])
    observed_value = float(extracted_conversion.get("target_value", 0))
    value_error = abs(observed_value - expected_value)
    source_metric_matches = extracted_conversion.get("source_metric") == expectation["source_expression"]["metric"]
    target_metric_matches = extracted_conversion.get("target_metric") == expectation["target_expression"]["metric"]

    failures: list[str] = []
    if missing_assumptions:
        failures.append("missing_conversion_assumption")
    if not source_metric_matches or not target_metric_matches:
        failures.append("conversion_metric_mismatch")
    if value_error > tolerance:
        failures.append("conversion_value_mismatch")

    return {
        "gold_id": expectation.get("gold_id"),
        "track": "conversion",
        "overall": "match" if not failures else "miss",
        "missing_assumptions": missing_assumptions,
        "value_error": value_error,
        "failures": failures,
    }
```

- [ ] **Step 5: Add README description**

Modify `knowledge/datasets/rule_extraction_v1/README.zh.md` file list:

```markdown
- `conversion_expectations.jsonl`：百分比、单位、能量口径等转换评估样本；不进入 clean extraction F1。
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_conversion_evaluation.py knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add knowledge/datasets/rule_extraction_v1/conversion_expectations.jsonl knowledge/src/knowledge/conversion_evaluation.py knowledge/tests/test_conversion_evaluation.py knowledge/datasets/rule_extraction_v1/README.zh.md
git commit -m "feat: add conversion evaluation track"
```

## Task 5: Add Contextual Handling Evaluation

**Files:**
- Create: `knowledge/datasets/rule_extraction_v1/contextual_expectations.jsonl`
- Create: `knowledge/src/knowledge/contextual_evaluation.py`
- Create: `knowledge/tests/test_contextual_evaluation.py`
- Modify: `knowledge/src/knowledge/rule_evaluation.py`
- Modify: `knowledge/tests/test_rule_evaluation.py`
- Modify: `knowledge/datasets/rule_extraction_v1/README.zh.md`

- [ ] **Step 1: Write failing contextual tests**

Create `knowledge/tests/test_contextual_evaluation.py`:

```python
from knowledge.contextual_evaluation import evaluate_contextual_expectation


def test_contextual_evaluation_accepts_pattern_rule_without_numeric_overclaim():
    expectation = {
        "gold_id": "gold-pattern",
        "expected_context": {
            "condition": "cardiovascular_risk",
            "nutrition_signal": "dietary_pattern",
            "pattern_tags": ["mediterranean_pattern", "nuts", "olive_oil"],
        },
        "forbidden_overclaims": [{"type": "numeric_limit", "metrics": ["fat_g", "sodium_mg"]}],
    }
    extracted_rules = [
        {
            "condition": "cardiovascular_risk",
            "preferred_tags": ["mediterranean_pattern", "nuts"],
            "nutrition_limits": [],
        }
    ]

    evaluation = evaluate_contextual_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "match"
    assert evaluation["overclaim_failures"] == []


def test_contextual_evaluation_rejects_invented_numeric_limit():
    expectation = {
        "gold_id": "gold-pattern",
        "expected_context": {
            "condition": "cardiovascular_risk",
            "nutrition_signal": "dietary_pattern",
            "pattern_tags": ["mediterranean_pattern"],
        },
        "forbidden_overclaims": [{"type": "numeric_limit", "metrics": ["fat_g", "sodium_mg"]}],
    }
    extracted_rules = [
        {
            "condition": "cardiovascular_risk",
            "preferred_tags": ["mediterranean_pattern"],
            "nutrition_limits": [{"metric": "fat_g", "scope": "daily", "max_value": 30}],
        }
    ]

    evaluation = evaluate_contextual_expectation(expectation, extracted_rules)

    assert evaluation["overall"] == "mismatch"
    assert evaluation["overclaim_failures"] == ["unexpected_numeric_limit:fat_g"]
```

- [ ] **Step 2: Run contextual tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_contextual_evaluation.py -q --rootdir=.
```

Expected: FAIL because `knowledge.contextual_evaluation` does not exist.

- [ ] **Step 3: Add contextual expectations**

Create `knowledge/datasets/rule_extraction_v1/contextual_expectations.jsonl`:

```jsonl
{"gold_id":"gold_zh_manual_health_china_sugar_reduction_001","doc_id":"zh_manual_health_china_sugar_reduction","track":"contextual_handling","expected_context":{"condition":"chronic_disease_prevention","nutrition_signal":"sugar_reduction","pattern_tags":["low_sugar","sugary_drink_reduction"]},"forbidden_overclaims":[{"type":"numeric_limit","metrics":["sugar_g"]}],"acceptance_policy":"Accept sugar-reduction context; reject invented diabetes-specific numeric limits."}
{"gold_id":"gold_en_paper_mediterranean_diet_cardiovascular_prevention_001","doc_id":"en_paper_mediterranean_diet_cardiovascular_prevention","track":"contextual_handling","expected_context":{"condition":"cardiovascular_risk","nutrition_signal":"dietary_pattern","pattern_tags":["mediterranean_pattern","plant_foods","nuts","olive_oil"]},"forbidden_overclaims":[{"type":"numeric_limit","metrics":["fat_g","sodium_mg","sugar_g"]}],"acceptance_policy":"Accept contextual or dietary-pattern extraction; reject invented single-nutrient limits."}
```

- [ ] **Step 4: Implement contextual evaluator**

Create `knowledge/src/knowledge/contextual_evaluation.py`:

```python
from __future__ import annotations

from typing import Any


def evaluate_contextual_expectation(expectation: dict[str, Any], extracted_rules: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden_metrics = {
        str(metric)
        for overclaim_record in expectation.get("forbidden_overclaims", []) or []
        if overclaim_record.get("type") == "numeric_limit"
        for metric in overclaim_record.get("metrics", []) or []
    }
    overclaim_failures: list[str] = []
    matched_context = False
    expected_context = expectation.get("expected_context", {}) or {}
    expected_condition = str(expected_context.get("condition") or "")
    expected_pattern_tags = {str(tag) for tag in expected_context.get("pattern_tags", []) or []}

    for extracted_rule in extracted_rules:
        for nutrition_limit in extracted_rule.get("nutrition_limits", []) or []:
            metric = str(nutrition_limit.get("metric") or "")
            if metric in forbidden_metrics:
                overclaim_failures.append(f"unexpected_numeric_limit:{metric}")
        condition = _code_value(extracted_rule.get("condition"))
        preferred_tags = {_code_value(tag) for tag in extracted_rule.get("preferred_tags", []) or []}
        if condition == expected_condition or expected_pattern_tags & preferred_tags:
            matched_context = True

    failures: list[str] = []
    if overclaim_failures:
        failures.append("contextual_overclaim")
    if extracted_rules and not matched_context:
        failures.append("context_mismatch")

    return {
        "gold_id": expectation.get("gold_id"),
        "track": "contextual_handling",
        "overall": "match" if not failures else "mismatch",
        "matched_context": matched_context,
        "overclaim_failures": sorted(set(overclaim_failures)),
        "failures": failures,
    }


def _code_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")
```

- [ ] **Step 5: Split negative failure labels in `rule_evaluation.py`**

In `evaluate_rule`, replace:

```python
failures = [] if not extracted else ["unexpected_numeric_limit"]
```

with:

```python
failures = [] if not extracted else _unexpected_negative_failures(extracted)
```

Add:

```python
def _unexpected_negative_failures(extracted: list[dict[str, Any]]) -> list[str]:
    failures: set[str] = set()
    for extracted_rule in extracted:
        if extracted_rule.get("nutrition_limits"):
            failures.add("unexpected_numeric_limit")
        if extracted_rule.get("suggested_concepts"):
            failures.add("unexpected_suggested_concept")
        if extracted_rule.get("preferred_tags") and not extracted_rule.get("nutrition_limits"):
            failures.add("unexpected_contextual_rule")
    return sorted(failures) or ["unexpected_rule"]
```

Add a test in `knowledge/tests/test_rule_evaluation.py`:

```python
def test_negative_rule_failure_labels_distinguish_contextual_and_numeric_outputs():
    gold = {"gold_id": "negative", "gold_behavior": "negative", "should_extract": False}

    numeric_evaluation = evaluate_rule(gold, [{"nutrition_limits": [{"metric": "sodium_mg"}]}])
    contextual_evaluation = evaluate_rule(gold, [{"preferred_tags": ["mediterranean_pattern"], "nutrition_limits": []}])
    concept_evaluation = evaluate_rule(gold, [{"suggested_concepts": ["low_purine"]}])

    assert numeric_evaluation["failures"] == ["unexpected_numeric_limit"]
    assert contextual_evaluation["failures"] == ["unexpected_contextual_rule"]
    assert concept_evaluation["failures"] == ["unexpected_suggested_concept"]
```

- [ ] **Step 6: Add README description**

Modify `knowledge/datasets/rule_extraction_v1/README.zh.md` file list:

```markdown
- `contextual_expectations.jsonl`：上下文/膳食模式样本，用于评估模型是否避免过度生成固定数值规则。
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_contextual_evaluation.py knowledge/tests/test_rule_evaluation.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add knowledge/datasets/rule_extraction_v1/contextual_expectations.jsonl knowledge/src/knowledge/contextual_evaluation.py knowledge/src/knowledge/rule_evaluation.py knowledge/tests/test_contextual_evaluation.py knowledge/tests/test_rule_evaluation.py knowledge/datasets/rule_extraction_v1/README.zh.md
git commit -m "feat: add contextual evaluation track"
```

## Task 6: Build Stratified Evaluation Report

**Files:**
- Create: `knowledge/src/knowledge/stratified_evaluation.py`
- Create: `knowledge/tests/test_stratified_evaluation.py`
- Modify: `knowledge/src/knowledge/rule_extraction_dataset_smoke.py`
- Modify: `knowledge/tests/test_rule_extraction_dataset_smoke_reports.py`
- Modify: `knowledge/src/knowledge/gold_audit.py`
- Modify: `knowledge/tests/test_gold_audit.py`

- [ ] **Step 1: Write failing stratified report tests**

Create `knowledge/tests/test_stratified_evaluation.py`:

```python
from knowledge.stratified_evaluation import build_stratified_evaluation_report


def test_stratified_report_exposes_track_summaries_without_averaging_them():
    gold_rows = [
        {"gold_id": "gold-clean", "doc_id": "clean-doc", "gold_behavior": "rule"},
        {"gold_id": "gold-concept", "doc_id": "concept-doc", "gold_behavior": "suggested_concept"},
    ]
    audit_rows = [
        {"gold_id": "gold-clean", "evidence_level": "source_card_direct", "audit_status": "keep"},
        {"gold_id": "gold-concept", "evidence_level": "schema_gap", "audit_status": "revise_schema_or_gold"},
    ]
    rule_evaluations = [
        {"gold_id": "gold-clean", "experiment_id": "E1", "arm_id": "C2", "overall": "match"},
        {"gold_id": "gold-concept", "experiment_id": "E1", "arm_id": "C2", "overall": "miss"},
    ]
    concept_evaluations = [
        {"gold_id": "gold-concept", "overall": "match", "true_positive_count": 2, "false_negative_count": 0, "false_positive_count": 0}
    ]

    report = build_stratified_evaluation_report(
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        gold_rows=gold_rows,
        audit_rows=audit_rows,
        rule_evaluations=rule_evaluations,
        concept_evaluations=concept_evaluations,
        conversion_evaluations=[],
        contextual_evaluations=[],
    )

    assert report["headline_metric"] == "clean_extraction_f1"
    assert report["tracks"]["clean_extraction"]["overall"]["f1"] == 1.0
    assert report["tracks"]["concept_discovery"]["overall"]["f1"] == 1.0
    assert report["tracks"]["mixed_legacy"]["overall"]["recall"] < 1.0
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_stratified_evaluation.py -q --rootdir=.
```

Expected: FAIL because `knowledge.stratified_evaluation` does not exist.

- [ ] **Step 3: Implement stratified report builder**

Create `knowledge/src/knowledge/stratified_evaluation.py`:

```python
from __future__ import annotations

from typing import Any

from knowledge.concept_evaluation import precision_recall_f1_for_concepts
from knowledge.evaluation_taxonomy import EvaluationTrack
from knowledge.gold_audit import annotate_evaluations_with_gold_audit, build_gold_audit_report
from knowledge.rule_evaluation import precision_recall_f1


def build_stratified_evaluation_report(
    *,
    dataset_id: str,
    run_type: str,
    gold_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    rule_evaluations: list[dict[str, Any]],
    concept_evaluations: list[dict[str, Any]],
    conversion_evaluations: list[dict[str, Any]],
    contextual_evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_audit_report = build_gold_audit_report(
        dataset_id=dataset_id,
        run_type=run_type,
        gold_rows=gold_rows,
        evaluations=rule_evaluations,
        audit_rows=audit_rows,
    )
    annotated_rule_evaluations = annotate_evaluations_with_gold_audit(rule_evaluations, audit_rows)
    clean_rule_evaluations = [
        evaluation
        for evaluation in annotated_rule_evaluations
        if evaluation.get("gold_id")
        and evaluation.get("evidence_level") in {"source_card_direct", "original_source_direct", "contextual_negative"}
        and evaluation.get("audit_status") == "keep"
    ]
    return {
        "dataset_id": dataset_id,
        "run_type": run_type,
        "headline_metric": "clean_extraction_f1",
        "tracks": {
            EvaluationTrack.CLEAN_EXTRACTION.value: {
                "evaluated_record_count": len(clean_rule_evaluations),
                "overall": precision_recall_f1(clean_rule_evaluations),
            },
            EvaluationTrack.CONCEPT_DISCOVERY.value: {
                "evaluated_record_count": len(concept_evaluations),
                "overall": precision_recall_f1_for_concepts(concept_evaluations),
            },
            EvaluationTrack.CONVERSION.value: {
                "evaluated_record_count": len(conversion_evaluations),
                "overall": _binary_accuracy(conversion_evaluations),
            },
            EvaluationTrack.CONTEXTUAL_HANDLING.value: {
                "evaluated_record_count": len(contextual_evaluations),
                "overall": _binary_accuracy(contextual_evaluations),
            },
            EvaluationTrack.MIXED_LEGACY.value: gold_audit_report["all_evaluation_summary"],
        },
        "gold_audit": gold_audit_report,
    }


def _binary_accuracy(evaluations: list[dict[str, Any]]) -> dict[str, float]:
    if not evaluations:
        return {"accuracy": 0.0}
    matches = sum(1 for evaluation in evaluations if evaluation.get("overall") == "match")
    return {"accuracy": matches / len(evaluations)}
```

After Task 1 has introduced `clean_headline_filter`, replace the inline clean filter in this module with the centralized helper before committing.

- [ ] **Step 4: Wire stratified report into real-run output**

Modify `knowledge/src/knowledge/rule_extraction_dataset_smoke.py`:

```python
from knowledge.stratified_evaluation import build_stratified_evaluation_report
```

After `gold_audit_report = write_gold_audit_report(...)`, build a stratified report with empty non-rule track lists for the first integration step:

```python
stratified_evaluation = build_stratified_evaluation_report(
    dataset_id=dataset,
    run_type="real_llm",
    gold_rows=gold_rows,
    audit_rows=audit_rows,
    rule_evaluations=evaluations,
    concept_evaluations=[],
    conversion_evaluations=[],
    contextual_evaluations=[],
)
```

Add to the main `report` dict:

```python
"stratified_evaluation": stratified_evaluation,
```

Write a separate JSON artifact:

```python
stratified_evaluation_report_path = output_dir / "rule-extraction-v1-stratified-evaluation-report.json"
stratified_evaluation_report_path.write_text(
    json.dumps(stratified_evaluation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
report["stratified_evaluation_report_path"] = str(stratified_evaluation_report_path)
```

- [ ] **Step 5: Extend smoke report test**

In `knowledge/tests/test_rule_extraction_dataset_smoke_reports.py`, add assertions to `test_real_run_uses_llm_provider_and_writes_observation_report`:

```python
assert report["stratified_evaluation"]["headline_metric"] == "clean_extraction_f1"
assert "clean_extraction" in report["stratified_evaluation"]["tracks"]
assert "mixed_legacy" in report["stratified_evaluation"]["tracks"]
assert Path(report["stratified_evaluation_report_path"]).exists()
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_stratified_evaluation.py knowledge/tests/test_rule_extraction_dataset_smoke_reports.py knowledge/tests/test_gold_audit.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add knowledge/src/knowledge/stratified_evaluation.py knowledge/src/knowledge/rule_extraction_dataset_smoke.py knowledge/src/knowledge/gold_audit.py knowledge/tests/test_stratified_evaluation.py knowledge/tests/test_rule_extraction_dataset_smoke_reports.py knowledge/tests/test_gold_audit.py
git commit -m "feat: report stratified evaluation tracks"
```

## Task 7: Connect Track Expectations To Real Observations

**Files:**
- Modify: `knowledge/src/knowledge/rule_extraction_dataset_smoke.py`
- Modify: `knowledge/src/knowledge/stratified_evaluation.py`
- Modify: `knowledge/tests/test_stratified_evaluation.py`
- Modify: `knowledge/tests/test_rule_extraction_dataset_smoke_reports.py`

- [ ] **Step 1: Add a test for loading track expectation files**

In `knowledge/tests/test_stratified_evaluation.py`, add:

```python
from pathlib import Path

from knowledge.stratified_evaluation import load_track_expectations


def test_load_track_expectations_reads_all_track_files(tmp_path: Path):
    dataset_dir = tmp_path
    (dataset_dir / "concept_expectations.jsonl").write_text('{"gold_id":"gold-concept"}\n', encoding="utf-8")
    (dataset_dir / "conversion_expectations.jsonl").write_text('{"gold_id":"gold-conversion"}\n', encoding="utf-8")
    (dataset_dir / "contextual_expectations.jsonl").write_text('{"gold_id":"gold-contextual"}\n', encoding="utf-8")

    expectations = load_track_expectations(dataset_dir)

    assert expectations["concept_discovery"][0]["gold_id"] == "gold-concept"
    assert expectations["conversion"][0]["gold_id"] == "gold-conversion"
    assert expectations["contextual_handling"][0]["gold_id"] == "gold-contextual"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_stratified_evaluation.py::test_load_track_expectations_reads_all_track_files -q --rootdir=.
```

Expected: FAIL because `load_track_expectations` does not exist.

- [ ] **Step 3: Implement expectation loading**

Add to `knowledge/src/knowledge/stratified_evaluation.py`:

```python
import json
from pathlib import Path


TRACK_EXPECTATION_FILES = {
    "concept_discovery": "concept_expectations.jsonl",
    "conversion": "conversion_expectations.jsonl",
    "contextual_handling": "contextual_expectations.jsonl",
}


def load_track_expectations(dataset_dir: Path) -> dict[str, list[dict[str, Any]]]:
    expectations_by_track: dict[str, list[dict[str, Any]]] = {}
    for evaluation_track, filename in TRACK_EXPECTATION_FILES.items():
        expectation_path = dataset_dir / filename
        expectations_by_track[evaluation_track] = _read_jsonl(expectation_path)
    return expectations_by_track


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
```

- [ ] **Step 4: Map observations to track evaluators**

In `knowledge/src/knowledge/rule_extraction_dataset_smoke.py`, after normal rule evaluation, derive extracted rules by `doc_id`:

```python
rules_by_doc_id = {
    observation["doc_id"]: observation.get("parsed_rules", []) or []
    for observation in observations
}
```

Then call:

```python
track_expectations = load_track_expectations(dataset_dir)
concept_evaluations = [
    evaluate_concept_expectation(expectation, rules_by_doc_id.get(expectation["doc_id"], []))
    for expectation in track_expectations["concept_discovery"]
]
conversion_evaluations = [
    evaluate_conversion_expectation(expectation, None)
    for expectation in track_expectations["conversion"]
]
contextual_evaluations = [
    evaluate_contextual_expectation(expectation, rules_by_doc_id.get(expectation["doc_id"], []))
    for expectation in track_expectations["contextual_handling"]
]
```

Use `None` for `conversion_evaluations` until the extractor emits explicit conversion records. This makes conversion misses visible without pretending ordinary rule extraction should infer hidden benchmark assumptions.

- [ ] **Step 5: Add smoke assertions**

In `knowledge/tests/test_rule_extraction_dataset_smoke_reports.py`, assert that the track sections are present even when counts are zero in small smoke fixtures:

```python
tracks = report["stratified_evaluation"]["tracks"]
assert set(tracks) >= {"clean_extraction", "concept_discovery", "conversion", "contextual_handling", "mixed_legacy"}
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_stratified_evaluation.py knowledge/tests/test_rule_extraction_dataset_smoke_reports.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add knowledge/src/knowledge/stratified_evaluation.py knowledge/src/knowledge/rule_extraction_dataset_smoke.py knowledge/tests/test_stratified_evaluation.py knowledge/tests/test_rule_extraction_dataset_smoke_reports.py
git commit -m "feat: connect stratified tracks to observations"
```

## Task 8: Update Research Protocol And Audit Report

**Files:**
- Modify: `docs/research/doc-rule-agent-research-protocol.md`
- Modify: `reports/rule-extraction-v1-gold-audit-20260602.md`
- Modify: `knowledge/datasets/rule_extraction_v1/README.zh.md`

- [ ] **Step 1: Update primary metrics in research protocol**

In `docs/research/doc-rule-agent-research-protocol.md`, replace the single primary metric sentence:

```markdown
Primary metrics include field-level precision, recall, F1, numeric-limit exact match, numeric tolerance match, parse success, stability, conflict accuracy, and citation completeness.
```

with:

```markdown
Primary metrics are reported by evaluation track. `clean_extraction_f1` is the headline regression metric for source-card-direct and trusted-negative rows. `contextual_handling` reports contextual accept rate and overclaim rate. `conversion` reports conversion accuracy and missing-assumption rate. `concept_discovery` reports atomic concept precision, recall, F1, and duplicate/umbrella rate. The legacy mixed precision/recall/F1 is retained only for continuity and must not be used as the sole headline score after gold audit metadata is available.
```

- [ ] **Step 2: Update manual audit report**

In `reports/rule-extraction-v1-gold-audit-20260602.md`, add a section after `## Proposed Next Steps`:

```markdown
## Planned Evaluation Tracks

- `clean_extraction`: source-card-direct rules and trusted negatives; headline F1.
- `contextual_handling`: sources with nutrition signal but no fixed numeric disease rule; evaluate context preservation and overclaim avoidance.
- `conversion`: sources that require unit or energy-reference conversion; evaluate formula, assumptions, and converted value separately.
- `concept_discovery`: schema-gap sources; evaluate atomic product concepts and aliases instead of umbrella ids.
- `mixed_legacy`: all frozen gold rows; retained only for continuity with earlier reports.
```

- [ ] **Step 3: Update dataset README report list**

In `knowledge/datasets/rule_extraction_v1/README.zh.md`, under real LLM report locations, add:

```markdown
- `reports/rule-extraction-v1-stratified-evaluation-report.json`
```

- [ ] **Step 4: Run documentation diff check**

Run:

```bash
git diff --check docs/research/doc-rule-agent-research-protocol.md reports/rule-extraction-v1-gold-audit-20260602.md knowledge/datasets/rule_extraction_v1/README.zh.md
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add docs/research/doc-rule-agent-research-protocol.md reports/rule-extraction-v1-gold-audit-20260602.md knowledge/datasets/rule_extraction_v1/README.zh.md
git commit -m "docs: define stratified evaluation protocol"
```

## Task 9: Final Verification And Experiment Run

**Files:**
- No new source files.
- Generated experiment reports should go under a new directory such as `reports/rule-extraction-stratified-eval-full-c2-20260602/`.

- [ ] **Step 1: Run focused tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_evaluation_taxonomy.py \
  knowledge/tests/test_gold_audit.py \
  knowledge/tests/test_concept_expectations.py \
  knowledge/tests/test_concept_evaluation.py \
  knowledge/tests/test_conversion_evaluation.py \
  knowledge/tests/test_contextual_evaluation.py \
  knowledge/tests/test_stratified_evaluation.py \
  knowledge/tests/test_rule_extraction_dataset.py \
  knowledge/tests/test_rule_extraction_dataset_smoke_reports.py \
  knowledge/tests/test_rule_evaluation.py \
  -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest -q --rootdir=.
```

Expected: PASS with no failures.

- [ ] **Step 3: Run deterministic dry-run report generation**

Run:

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --dry-run \
  --output-dir reports/rule-extraction-stratified-eval-dry-run-20260602
```

Expected:

- `reports/rule-extraction-stratified-eval-dry-run-20260602/rule-extraction-v1-stratified-evaluation-report.json` exists.
- Report has `headline_metric: clean_extraction_f1`.
- Report has all five track keys.

- [ ] **Step 4: Run full real-LLM C2 experiment**

Run only after the dry-run and tests pass:

```bash
MEDIDIET_LLM_DATASET_SMOKE_TEST=1 \
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --real-llm \
  --experiments E1 \
  --arms C2 \
  --max-docs 0 \
  --output-dir reports/rule-extraction-stratified-eval-full-c2-20260602
```

Expected:

- Real run completes or checkpoint/resume reports operational failures separately.
- `rule-extraction-v1-real-llm-report.json` includes `stratified_evaluation`.
- `rule-extraction-v1-stratified-evaluation-report.json` includes all tracks.

- [ ] **Step 5: Summarize metrics**

Generate the PR comment body from the stratified report so every metric line has a concrete value:

```bash
python -c "import json, pathlib; p=pathlib.Path('reports/rule-extraction-stratified-eval-full-c2-20260602/rule-extraction-v1-stratified-evaluation-report.json'); r=json.loads(p.read_text(encoding='utf-8')); tracks=r['tracks']; clean=tracks['clean_extraction']['overall']; contextual=tracks['contextual_handling']['overall']; conversion=tracks['conversion']['overall']; concept=tracks['concept_discovery']['overall']; legacy=tracks['mixed_legacy']['overall']; print('Stratified evaluation full C2 result:'); print(f'- clean_extraction_f1: {clean.get(\"f1\", 0):.3f}'); print(f'- contextual_handling accuracy: {contextual.get(\"accuracy\", 0):.3f}'); print(f'- conversion accuracy: {conversion.get(\"accuracy\", 0):.3f}'); print(f'- concept_discovery P/R/F1: {concept.get(\"precision\", 0):.3f} / {concept.get(\"recall\", 0):.3f} / {concept.get(\"f1\", 0):.3f}'); print(f'- mixed_legacy P/R/F1: {legacy.get(\"precision\", 0):.3f} / {legacy.get(\"recall\", 0):.3f} / {legacy.get(\"f1\", 0):.3f}'); print('\\nInterpretation: clean extraction is the direct-evidence headline score; conversion, concept discovery, and contextual handling are separate capabilities, not direct-extraction misses.')"
```

Expected: the command prints a complete comment body with numeric values copied from the generated report.

- [ ] **Step 6: Commit any non-generated source/reporting changes**

Do not commit bulky run output directories unless the PR convention requires them. Commit only source, tests, stable metadata, and intentionally curated reports.

```bash
git status --short
git add \
  docs/research/doc-rule-agent-research-protocol.md \
  knowledge/datasets/rule_extraction_v1/README.zh.md \
  knowledge/datasets/rule_extraction_v1/concept_expectations.jsonl \
  knowledge/datasets/rule_extraction_v1/contextual_expectations.jsonl \
  knowledge/datasets/rule_extraction_v1/conversion_expectations.jsonl \
  knowledge/src/knowledge/concept_evaluation.py \
  knowledge/src/knowledge/contextual_evaluation.py \
  knowledge/src/knowledge/conversion_evaluation.py \
  knowledge/src/knowledge/evaluation_taxonomy.py \
  knowledge/src/knowledge/gold_audit.py \
  knowledge/src/knowledge/rule_evaluation.py \
  knowledge/src/knowledge/rule_extraction_dataset_smoke.py \
  knowledge/src/knowledge/stratified_evaluation.py \
  knowledge/tests/test_concept_evaluation.py \
  knowledge/tests/test_concept_expectations.py \
  knowledge/tests/test_contextual_evaluation.py \
  knowledge/tests/test_conversion_evaluation.py \
  knowledge/tests/test_evaluation_taxonomy.py \
  knowledge/tests/test_gold_audit.py \
  knowledge/tests/test_rule_evaluation.py \
  knowledge/tests/test_rule_extraction_dataset.py \
  knowledge/tests/test_rule_extraction_dataset_smoke_reports.py \
  knowledge/tests/test_stratified_evaluation.py \
  reports/rule-extraction-v1-gold-audit-20260602.md
git commit -m "feat: add stratified rule extraction evaluation"
```

## Acceptance Criteria

The plan is complete when:

- `gold_evaluation_set.jsonl` remains unchanged.
- `gold_audit.jsonl` remains a one-to-one audit layer over frozen gold.
- Clean headline rows are selected through centralized taxonomy, not scattered string comparisons.
- Schema-gap rows are evaluated against atomic concepts and aliases, not umbrella ids.
- Conversion rows are evaluated through explicit formulas and assumptions.
- Contextual rows are evaluated for context preservation and overclaim avoidance.
- Real-LLM reports include `stratified_evaluation` and a separate stratified JSON artifact.
- Full pytest passes.
- PR #11 and issue #12 are updated with the plan execution result and latest metrics.

## Risk Controls

- Do not edit source cards to make a frozen gold row easier to pass.
- Do not mutate frozen gold during implementation; add expectation files beside it.
- Do not average track metrics into one score.
- Do not allow LLM-generated concept candidates to become product-approved automatically; they stay `status=candidate` until product review.
- Do not treat MedlinePlus low-sodium numeric gold as a conversion case unless the current source input exposes a numeric expression to convert.
- Keep full generated experiment output unstaged unless explicitly requested.

## Recommended Execution Order

1. Task 1: taxonomy centralization.
2. Task 2: atomic concept expectation data.
3. Task 3: concept discovery scorer.
4. Task 4: conversion scorer.
5. Task 5: contextual scorer and negative failure labels.
6. Task 6: stratified report builder.
7. Task 7: real observation integration.
8. Task 8: protocol/docs update.
9. Task 9: full verification and real-LLM experiment.

This order keeps each step testable and avoids changing product-facing behavior before the evaluation data contract is explicit.
