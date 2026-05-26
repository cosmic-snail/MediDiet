# Nutrition Rule Extraction Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `rule_extraction_v1`, a 60-source bilingual no-human-in-loop nutrition rule extraction dataset with weak labels, extraction observations, a frozen offline gold subset, and a challenge set.

**Architecture:** Keep the dataset inside the existing `knowledge/` package so the current `KnowledgeLoader` can import Markdown source cards without code changes. Use JSONL files for manifest, machine-generated expected rules, run observations, gold evaluation records, and challenge records. Add focused validation tests to make the dataset auditable and prevent distribution drift, schema drift, and gold leakage.

**Tech Stack:** Python standard library, pytest, existing `knowledge.loader.KnowledgeLoader`, Markdown source cards, JSONL metadata files.

---

## File Structure

Create or modify these files:

- Create: `knowledge/source_documents/manual/.gitkeep`
- Create: `knowledge/datasets/rule_extraction_v1/README.zh.md`
- Create: `knowledge/datasets/rule_extraction_v1/manifest.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/expected_rules.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/challenge_set.jsonl`
- Create: `knowledge/tests/test_rule_extraction_dataset.py`
- Create: 24 Markdown source cards under `knowledge/source_documents/guidelines/`
- Create: 18 Markdown source cards under `knowledge/source_documents/papers/`
- Create: 18 Markdown source cards under `knowledge/source_documents/manual/`

Do not change extraction logic in `knowledge/src/knowledge/extractor.py` during dataset construction. CKD, gout, protein, potassium, phosphorus, purine, alcohol, and hydration are expected to expose concept or metric gaps.

## Source Card Template

Every Markdown source card must use this shape:

```markdown
---
doc_id: en_guideline_who_sodium_2012
title: "WHO Guideline: Sodium Intake for Adults and Children"
language: en
source_type: guideline
source_url: "https://www.who.int/publications/i/item/9789241504836"
publisher: "World Health Organization"
year: "2012"
disease_focus: ["hypertension", "cardiovascular_risk"]
nutrition_focus: ["sodium_mg"]
evaluation_labels: ["should_extract"]
annotation_method: llm_generated
label_model: "deepseek-v4-flash"
label_prompt_version: "metadata-labeling-v1"
review_status: unreviewed
label_confidence: 0.72
failure_is_valid_observation: true
---

# WHO Guideline: Sodium Intake for Adults and Children

## Source Notes

This source card is included to test extraction of explicit sodium limits.

## Extractable Source Content

Use short source excerpts only where necessary for evidence quotes. Otherwise use faithful summaries and keep the source URL traceable.
```

## Task 1: Dataset Skeleton And Basic Validation

**Files:**
- Create: `knowledge/source_documents/manual/.gitkeep`
- Create: `knowledge/datasets/rule_extraction_v1/README.zh.md`
- Create: `knowledge/datasets/rule_extraction_v1/manifest.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/expected_rules.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl`
- Create: `knowledge/datasets/rule_extraction_v1/challenge_set.jsonl`
- Create: `knowledge/tests/test_rule_extraction_dataset.py`

- [ ] **Step 1: Write the failing skeleton validation test**

Create `knowledge/tests/test_rule_extraction_dataset.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from knowledge.loader import KnowledgeLoader


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "knowledge" / "source_documents"
DATASET_DIR = REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1"


DATASET_FILES = {
    "README.zh.md",
    "manifest.jsonl",
    "expected_rules.jsonl",
    "extraction_observations.jsonl",
    "gold_evaluation_set.jsonl",
    "challenge_set.jsonl",
}


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{path}:{line_number} is invalid JSONL: {exc}") from exc
        assert isinstance(row, dict), f"{path}:{line_number} must contain a JSON object"
        rows.append(row)
    return rows


def test_dataset_skeleton_files_exist_and_jsonl_is_parseable():
    assert (SOURCE_ROOT / "manual").exists()
    assert DATASET_DIR.exists()
    for filename in DATASET_FILES:
        path = DATASET_DIR / filename
        assert path.exists(), f"missing dataset file: {path}"
        if path.suffix == ".jsonl":
            _read_jsonl(path)


def test_knowledge_loader_can_load_all_dataset_source_directories():
    loader = KnowledgeLoader()
    source_types = {
        "guidelines": "guideline",
        "papers": "paper",
        "manual": "manual",
    }
    for directory_name, source_type in source_types.items():
        docs = loader.load_from_directory(
            str(SOURCE_ROOT / directory_name),
            source_type=source_type,
        )
        assert isinstance(docs, list)
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: FAIL because `knowledge/source_documents/manual/` and `knowledge/datasets/rule_extraction_v1/` do not exist.

- [ ] **Step 3: Create the dataset skeleton**

Create the directories with `mkdir`, then add empty JSONL files and the README with `apply_patch`:

```bash
mkdir -p knowledge/source_documents/manual
mkdir -p knowledge/datasets/rule_extraction_v1
```

Add the files with this patch:

```patch
*** Begin Patch
*** Add File: knowledge/source_documents/manual/.gitkeep
+
*** Add File: knowledge/datasets/rule_extraction_v1/manifest.jsonl
+
*** Add File: knowledge/datasets/rule_extraction_v1/expected_rules.jsonl
+
*** Add File: knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl
+
*** Add File: knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl
+
*** Add File: knowledge/datasets/rule_extraction_v1/challenge_set.jsonl
+
*** Add File: knowledge/datasets/rule_extraction_v1/README.zh.md
+# rule_extraction_v1
+
+这是一个用于营养与疾病规则抽取研究的数据集。系统构建链路保持 no-human-in-loop：`manifest.jsonl` 和 `expected_rules.jsonl` 中的标签是机器生成弱标签，不代表临床金标准。
+
+## 文件
+
+- `manifest.jsonl`：60 个真实来源 source card 的元数据和弱标签。
+- `expected_rules.jsonl`：机器生成的预期抽取假设。
+- `extraction_observations.jsonl`：无人闭环抽取运行后的观察结果。
+- `gold_evaluation_set.jsonl`：冻结的离线评测真值子集，只用于计算指标，不用于更新 prompt、标签或规则。
+- `challenge_set.jsonl`：上下文复杂或当前 schema 不支持的样本，用于失败分析，不强制纳入 F1。
+
+## 评测边界
+
+本数据集用于研究系统行为、可追溯性、稳定性和失败类型。任何规则候选都不是已审核临床建议。
*** End Patch
```

- [ ] **Step 4: Run the skeleton test and verify it passes**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  knowledge/source_documents/manual/.gitkeep \
  knowledge/datasets/rule_extraction_v1/README.zh.md \
  knowledge/datasets/rule_extraction_v1/manifest.jsonl \
  knowledge/datasets/rule_extraction_v1/expected_rules.jsonl \
  knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl \
  knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl \
  knowledge/datasets/rule_extraction_v1/challenge_set.jsonl \
  knowledge/tests/test_rule_extraction_dataset.py
git commit -m "test: add rule extraction dataset skeleton"
```

## Task 2: Guideline Source Cards And Manifest Records

**Files:**
- Modify: `knowledge/datasets/rule_extraction_v1/manifest.jsonl`
- Modify: `knowledge/tests/test_rule_extraction_dataset.py`
- Create: 24 Markdown files under `knowledge/source_documents/guidelines/`

- [ ] **Step 1: Extend validation tests for manifest schema and guideline distribution**

Append these tests to `knowledge/tests/test_rule_extraction_dataset.py`:

```python
REQUIRED_MANIFEST_FIELDS = {
    "doc_id",
    "path",
    "title",
    "language",
    "source_type",
    "source_url",
    "publisher",
    "year",
    "disease_focus",
    "nutrition_focus",
    "evaluation_labels",
    "annotation_method",
    "label_model",
    "label_prompt_version",
    "label_confidence",
    "review_status",
    "failure_is_valid_observation",
    "copyright_mode",
}

ALLOWED_SOURCE_TYPES = {"guideline", "paper", "manual"}
ALLOWED_LANGUAGES = {"zh", "en"}
ALLOWED_EVALUATION_LABELS = {
    "should_extract",
    "concept_gap",
    "negative",
    "contextual",
    "conflict",
    "cross_language",
    "patient_education",
}


def _manifest_rows() -> list[dict]:
    return _read_jsonl(DATASET_DIR / "manifest.jsonl")


def test_guideline_manifest_subset_has_required_distribution():
    rows = _manifest_rows()
    guideline_rows = [row for row in rows if row.get("source_type") == "guideline"]
    assert len(guideline_rows) == 24
    assert sum(1 for row in guideline_rows if row["language"] == "zh") == 12
    assert sum(1 for row in guideline_rows if row["language"] == "en") == 12


def test_manifest_records_have_required_fields_and_existing_markdown_paths():
    rows = _manifest_rows()
    seen_doc_ids: set[str] = set()
    for row in rows:
        missing = REQUIRED_MANIFEST_FIELDS - set(row)
        assert not missing, f"{row.get('doc_id', 'unknown_doc')} missing fields: {sorted(missing)}"
        assert row["doc_id"] not in seen_doc_ids
        seen_doc_ids.add(row["doc_id"])
        assert row["language"] in ALLOWED_LANGUAGES
        assert row["source_type"] in ALLOWED_SOURCE_TYPES
        assert row["annotation_method"] == "llm_generated"
        assert row["review_status"] == "unreviewed"
        assert row["failure_is_valid_observation"] is True
        assert isinstance(row["label_confidence"], int | float)
        assert 0 <= row["label_confidence"] <= 1
        assert row["copyright_mode"] == "short_excerpt_or_summary"
        assert set(row["evaluation_labels"]).issubset(ALLOWED_EVALUATION_LABELS)
        path = REPO_ROOT / row["path"]
        assert path.exists(), f"source card path does not exist: {path}"
        assert path.suffix == ".md"
        text = path.read_text(encoding="utf-8")
        assert f"doc_id: {row['doc_id']}" in text
        assert f"source_url: \"{row['source_url']}\"" in text
```

- [ ] **Step 2: Run the guideline tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_rule_extraction_dataset.py::test_guideline_manifest_subset_has_required_distribution \
  knowledge/tests/test_rule_extraction_dataset.py::test_manifest_records_have_required_fields_and_existing_markdown_paths \
  -q --rootdir=.
```

Expected: FAIL because no guideline manifest records exist yet.

- [ ] **Step 3: Add 24 guideline cards**

Create 12 Chinese and 12 English guideline/standard cards. Use official source URLs whenever possible. Keep each source card focused on 1 to 3 claims.

Required Chinese guideline coverage:

```text
zh_guideline_hypertension_food_therapy_2023
zh_guideline_diabetes_food_therapy_2023
zh_guideline_hyperlipidemia_food_therapy_2023
zh_guideline_obesity_food_therapy_2024
zh_guideline_gout_food_therapy_2024
zh_guideline_chronic_disease_nutrition_exercise_2024
zh_guideline_chinese_dietary_guidelines_2022
zh_guideline_salt_reduction_public_health
zh_guideline_sugar_reduction_public_health
zh_guideline_cardiovascular_dietary_pattern
zh_guideline_ckd_nutrition_china
zh_guideline_general_adult_dietary_balance
```

Required English guideline coverage:

```text
en_guideline_who_sodium_2012
en_guideline_who_sugars_2015
en_guideline_who_saturated_trans_fat_2023
en_guideline_who_carbohydrate_2023
en_guideline_ada_standards_nutrition_2026
en_guideline_kdigo_ckd_2024
en_guideline_kdoqi_ckd_nutrition_2020
en_guideline_aha_dietary_guidance_2021
en_guideline_acr_gout_2020
en_guideline_nice_type2_diabetes
en_guideline_nice_obesity
en_guideline_nice_hypertension
```

Each corresponding `manifest.jsonl` row must use the exact `doc_id`, `path`, `source_type`, `language`, `source_url`, `publisher`, `year`, `disease_focus`, `nutrition_focus`, and `evaluation_labels` from the source card header.

- [ ] **Step 4: Run the guideline tests and verify they pass**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS for skeleton tests, guideline distribution test, and manifest schema/path test.

- [ ] **Step 5: Commit**

```bash
git add knowledge/source_documents/guidelines knowledge/datasets/rule_extraction_v1/manifest.jsonl knowledge/tests/test_rule_extraction_dataset.py
git commit -m "data: add guideline source cards for rule extraction dataset"
```

## Task 3: Paper And Review Source Cards

**Files:**
- Modify: `knowledge/datasets/rule_extraction_v1/manifest.jsonl`
- Modify: `knowledge/tests/test_rule_extraction_dataset.py`
- Create: 18 Markdown files under `knowledge/source_documents/papers/`

- [ ] **Step 1: Add paper distribution tests**

Append this test to `knowledge/tests/test_rule_extraction_dataset.py`:

```python
def test_paper_manifest_subset_has_required_distribution():
    rows = _manifest_rows()
    paper_rows = [row for row in rows if row.get("source_type") == "paper"]
    assert len(paper_rows) == 18
    assert sum(1 for row in paper_rows if row["language"] == "zh") == 9
    assert sum(1 for row in paper_rows if row["language"] == "en") == 9
```

- [ ] **Step 2: Run the paper distribution test and verify it fails**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_rule_extraction_dataset.py::test_paper_manifest_subset_has_required_distribution \
  -q --rootdir=.
```

Expected: FAIL because no paper manifest records exist yet.

- [ ] **Step 3: Add 18 paper/review cards**

Create 9 Chinese and 9 English paper/review cards. Prefer open-access full text, PubMed Central, official journal abstracts, or publisher pages with stable metadata.

Required English paper coverage:

```text
en_paper_diabetes_nutrition_consensus_2019
en_paper_dash_sodium_trial
en_paper_mediterranean_diet_cardiovascular_prevention
en_paper_ckd_nutrition_kdoqi_review
en_paper_gout_diet_purine_alcohol_fructose_review
en_paper_weight_loss_obesity_diet_review
en_paper_low_sodium_blood_pressure_meta_analysis
en_paper_saturated_fat_cardiovascular_review
en_paper_fiber_diabetes_glycemic_control_review
```

Required Chinese paper/review coverage:

```text
zh_paper_hypertension_salt_reduction_review
zh_paper_diabetes_medical_nutrition_review
zh_paper_hyperlipidemia_dietary_intervention_review
zh_paper_obesity_energy_control_review
zh_paper_gout_hyperuricemia_diet_review
zh_paper_ckd_dietary_management_review
zh_paper_chinese_dietary_pattern_chronic_disease_review
zh_paper_sugar_sweetened_beverage_metabolic_risk_review
zh_paper_salt_intake_blood_pressure_china_review
```

For every paper card:

- Use `source_type: paper`.
- Use `evaluation_labels` to identify `should_extract`, `concept_gap`, `contextual`, or `negative`.
- Avoid full article reproduction; use bibliographic metadata plus short abstract-level summary or short excerpt.

- [ ] **Step 4: Run the dataset tests and verify they pass**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS for skeleton, guideline, paper, and manifest schema/path tests.

- [ ] **Step 5: Commit**

```bash
git add knowledge/source_documents/papers knowledge/datasets/rule_extraction_v1/manifest.jsonl knowledge/tests/test_rule_extraction_dataset.py
git commit -m "data: add paper source cards for rule extraction dataset"
```

## Task 4: Manual Web And Patient Education Source Cards

**Files:**
- Modify: `knowledge/datasets/rule_extraction_v1/manifest.jsonl`
- Modify: `knowledge/tests/test_rule_extraction_dataset.py`
- Create: 18 Markdown files under `knowledge/source_documents/manual/`

- [ ] **Step 1: Add full distribution tests**

Append these tests to `knowledge/tests/test_rule_extraction_dataset.py`:

```python
def test_manual_manifest_subset_has_required_distribution():
    rows = _manifest_rows()
    manual_rows = [row for row in rows if row.get("source_type") == "manual"]
    assert len(manual_rows) == 18
    assert sum(1 for row in manual_rows if row["language"] == "zh") == 9
    assert sum(1 for row in manual_rows if row["language"] == "en") == 9


def test_manifest_has_exact_rule_extraction_v1_distribution():
    rows = _manifest_rows()
    assert len(rows) == 60
    assert sum(1 for row in rows if row["language"] == "zh") == 30
    assert sum(1 for row in rows if row["language"] == "en") == 30
    assert sum(1 for row in rows if row["source_type"] == "guideline") == 24
    assert sum(1 for row in rows if row["source_type"] == "paper") == 18
    assert sum(1 for row in rows if row["source_type"] == "manual") == 18
    assert sum(1 for row in rows if "should_extract" in row["evaluation_labels"]) >= 20
    assert sum(1 for row in rows if "concept_gap" in row["evaluation_labels"]) >= 12
    hard_cases = [
        row for row in rows
        if {"negative", "contextual", "conflict"} & set(row["evaluation_labels"])
    ]
    assert len(hard_cases) >= 8
```

- [ ] **Step 2: Run the full distribution tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_rule_extraction_dataset.py::test_manual_manifest_subset_has_required_distribution \
  knowledge/tests/test_rule_extraction_dataset.py::test_manifest_has_exact_rule_extraction_v1_distribution \
  -q --rootdir=.
```

Expected: FAIL because manual records are not present and total distribution is incomplete.

- [ ] **Step 3: Add 18 manual/web cards**

Create 9 Chinese and 9 English web or patient-education cards.

Required English manual coverage:

```text
en_manual_cdc_diabetes_meal_planning
en_manual_niddk_diabetes_diet_physical_activity
en_manual_niddk_ckd_eating_right
en_manual_niddk_weight_management
en_manual_mayo_gout_diet
en_manual_cleveland_clinic_renal_diet
en_manual_heart_org_sodium_reduction
en_manual_harvard_diabetes_diet
en_manual_medlineplus_low_sodium_diet
```

Required Chinese manual coverage:

```text
zh_manual_nhc_hypertension_food_therapy_qa
zh_manual_nhc_diabetes_food_therapy_qa
zh_manual_nhc_gout_food_therapy_qa
zh_manual_nhc_obesity_food_therapy_qa
zh_manual_chinese_nutrition_society_dietary_guidelines_public
zh_manual_health_china_salt_reduction
zh_manual_health_china_sugar_reduction
zh_manual_health_china_weight_control
zh_manual_health_china_chronic_disease_diet
```

Manual cards must use `source_type: manual` and include `patient_education` in `evaluation_labels` unless the page is a professional policy Q&A.

- [ ] **Step 4: Run all dataset tests and verify they pass**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS and manifest has exactly 60 records.

- [ ] **Step 5: Commit**

```bash
git add knowledge/source_documents/manual knowledge/datasets/rule_extraction_v1/manifest.jsonl knowledge/tests/test_rule_extraction_dataset.py
git commit -m "data: add manual source cards for rule extraction dataset"
```

## Task 5: Expected Rules, Gold Evaluation Set, Challenge Set, And Observations

**Files:**
- Modify: `knowledge/datasets/rule_extraction_v1/expected_rules.jsonl`
- Modify: `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`
- Modify: `knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl`
- Modify: `knowledge/datasets/rule_extraction_v1/challenge_set.jsonl`
- Modify: `knowledge/tests/test_rule_extraction_dataset.py`

- [ ] **Step 1: Add schema tests for expected, gold, challenge, and observation files**

Append these tests to `knowledge/tests/test_rule_extraction_dataset.py`:

```python
ALLOWED_EXPECTED_BEHAVIORS = {"rule", "suggested_concept", "negative", "contextual", "conflict"}
ALLOWED_GOLD_BEHAVIORS = {"rule", "suggested_concept", "negative"}
ALLOWED_FAILURE_TYPES = {
    "unsupported_nutrient_metric",
    "unknown_condition",
    "unknown_contraindication",
    "unknown_nutrition_tag",
    "contextual_ambiguity",
    "insufficient_evidence",
    "malformed_output",
    "contradictory_source",
    "cross_language_instability",
    "no_relevant_rule",
    "other",
}
ALLOWED_CHALLENGE_TYPES = ALLOWED_FAILURE_TYPES | {"multi_condition_context"}


def _doc_ids_from_manifest() -> set[str]:
    return {row["doc_id"] for row in _manifest_rows()}


def test_expected_rules_are_machine_generated_and_reference_manifest_docs():
    expected_rows = _read_jsonl(DATASET_DIR / "expected_rules.jsonl")
    doc_ids = _doc_ids_from_manifest()
    assert len(expected_rows) >= 20
    for row in expected_rows:
        assert row["expected_id"].startswith("expected_")
        assert row["doc_id"] in doc_ids
        assert row["expected_behavior"] in ALLOWED_EXPECTED_BEHAVIORS
        assert row["annotation_method"] == "llm_generated"
        assert row["review_status"] == "unreviewed"
        assert "label_model" in row
        assert "label_prompt_version" in row
        if row["expected_behavior"] == "rule":
            assert "condition" in row
            assert "nutrition_limits" in row or "hard_exclusions" in row or "preferred_tags" in row


def test_gold_evaluation_set_is_small_frozen_and_offline_only():
    gold_rows = _read_jsonl(DATASET_DIR / "gold_evaluation_set.jsonl")
    doc_ids = _doc_ids_from_manifest()
    assert 12 <= len(gold_rows) <= 15
    assert sum(1 for row in gold_rows if row["gold_behavior"] == "negative") >= 2
    for row in gold_rows:
        assert row["gold_id"].startswith("gold_")
        assert row["doc_id"] in doc_ids
        assert row["gold_behavior"] in ALLOWED_GOLD_BEHAVIORS
        assert row["created_for"] == "offline_evaluation_only"
        assert row["frozen"] is True
        assert "evidence_requirement" in row


def test_challenge_set_references_manifest_docs_and_uses_known_failure_taxonomy():
    challenge_rows = _read_jsonl(DATASET_DIR / "challenge_set.jsonl")
    doc_ids = _doc_ids_from_manifest()
    assert len(challenge_rows) >= 8
    for row in challenge_rows:
        assert row["challenge_id"].startswith("challenge_")
        assert row["doc_id"] in doc_ids
        assert row["challenge_type"] in ALLOWED_CHALLENGE_TYPES
        assert row["reason"]
        assert row["recommended_analysis"]


def test_extraction_observations_file_is_parseable_and_references_known_records_when_populated():
    observation_rows = _read_jsonl(DATASET_DIR / "extraction_observations.jsonl")
    doc_ids = _doc_ids_from_manifest()
    expected_ids = {
        row["expected_id"]
        for row in _read_jsonl(DATASET_DIR / "expected_rules.jsonl")
    }
    for row in observation_rows:
        assert row["run_id"]
        assert row["doc_id"] in doc_ids
        if row.get("expected_id") is not None:
            assert row["expected_id"] in expected_ids
        if row.get("failure_type") is not None:
            assert row["failure_type"] in ALLOWED_FAILURE_TYPES
```

- [ ] **Step 2: Run the schema tests and verify they fail**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_rule_extraction_dataset.py::test_expected_rules_are_machine_generated_and_reference_manifest_docs \
  knowledge/tests/test_rule_extraction_dataset.py::test_gold_evaluation_set_is_small_frozen_and_offline_only \
  knowledge/tests/test_rule_extraction_dataset.py::test_challenge_set_references_manifest_docs_and_uses_known_failure_taxonomy \
  knowledge/tests/test_rule_extraction_dataset.py::test_extraction_observations_file_is_parseable_and_references_known_records_when_populated \
  -q --rootdir=.
```

Expected: FAIL because expected, gold, and challenge records are not present.

- [ ] **Step 3: Add `expected_rules.jsonl`**

Add at least 20 machine-generated expected records. Include these behavior groups:

```text
rule: sodium, sugar, fat, carbohydrate, energy examples supported by current schema
suggested_concept: CKD, gout, purine, protein, potassium, phosphorus, hydration
negative: source cards with no actionable nutrition rule
contextual: dialysis/non-dialysis, acute gout flare, individualized care
conflict: conflicting source statements or stage-dependent recommendations
```

Use this JSONL shape for rule records:

```json
{"expected_id":"expected_en_guideline_who_sodium_2012_001","doc_id":"en_guideline_who_sodium_2012","expected_behavior":"rule","condition":{"kind":"condition","value":"hypertension"},"hard_exclusions":[{"kind":"contraindication","value":"high_sodium"}],"preferred_tags":[{"kind":"nutrition_tag","value":"low_sodium"}],"nutrition_limits":[{"metric":"sodium_mg","scope":"daily","max_value":2000,"window_hours":null}],"evidence_hint":"daily sodium threshold","expected_confidence":0.75,"annotation_method":"llm_generated","label_model":"deepseek-v4-flash","label_prompt_version":"expected-rule-generation-v1","review_status":"unreviewed"}
```

- [ ] **Step 4: Add `gold_evaluation_set.jsonl`**

Add 12 to 15 frozen offline records. Include at least two negative examples. Select low-ambiguity records only. Do not include gold records for hard contextual CKD/gout cases unless the behavior is `suggested_concept` or `negative`.

Use this JSONL shape:

```json
{"gold_id":"gold_en_guideline_who_sodium_2012_001","doc_id":"en_guideline_who_sodium_2012","gold_behavior":"rule","condition":{"kind":"condition","value":"hypertension"},"hard_exclusions":[{"kind":"contraindication","value":"high_sodium"}],"preferred_tags":[{"kind":"nutrition_tag","value":"low_sodium"}],"nutrition_limits":[{"metric":"sodium_mg","scope":"daily","max_value":2000,"window_hours":null}],"evidence_requirement":"The output must cite source text supporting a daily sodium limit.","created_for":"offline_evaluation_only","frozen":true}
```

- [ ] **Step 5: Add `challenge_set.jsonl`**

Add at least 8 challenge records for failure analysis. Include these challenge types:

```text
unsupported_nutrient_metric
unknown_condition
contextual_ambiguity
contradictory_source
cross_language_instability
multi_condition_context
```

Use this JSONL shape:

```json
{"challenge_id":"challenge_zh_guideline_gout_food_therapy_2024_001","doc_id":"zh_guideline_gout_food_therapy_2024","challenge_type":"unsupported_nutrient_metric","reason":"Purine and alcohol recommendations are clinically relevant but not directly represented by the current nutrient metric schema.","recommended_analysis":"Record suggested concepts and verifier behavior; do not count as false negative in rule F1."}
```

- [ ] **Step 6: Leave `extraction_observations.jsonl` empty until a real extraction run**

Confirm the file exists and is valid as an empty JSONL file:

```bash
test -f knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl
```

Expected: command exits with status 0.

- [ ] **Step 7: Run all dataset validation tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  knowledge/datasets/rule_extraction_v1/expected_rules.jsonl \
  knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl \
  knowledge/datasets/rule_extraction_v1/gold_evaluation_set.jsonl \
  knowledge/datasets/rule_extraction_v1/challenge_set.jsonl \
  knowledge/tests/test_rule_extraction_dataset.py
git commit -m "data: add weak labels and evaluation sets"
```

## Task 6: Final Loader And Regression Verification

**Files:**
- Modify: `knowledge/datasets/rule_extraction_v1/README.zh.md`

- [ ] **Step 1: Update README with validation and experiment commands**

Append this section to `knowledge/datasets/rule_extraction_v1/README.zh.md`:

````markdown
## 本地校验

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

## 默认回归

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_loader.py knowledge/tests/test_documents.py knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

## 真实 LLM smoke

真实 LLM smoke 需要显式环境变量。该测试只用于观察无人闭环抽取行为，不会修改 `gold_evaluation_set.jsonl`。

```bash
MEDIDIET_LLM_SMOKE_TEST=1 \
MEDIDIET_LLM_RULE_SMOKE_TEST=1 \
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_real_llm_extraction_smoke.py -q --rootdir=.
```
````

- [ ] **Step 2: Run dataset validation**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 3: Run loader and document regression tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_loader.py \
  knowledge/tests/test_documents.py \
  knowledge/tests/test_rule_extraction_dataset.py \
  -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 4: Confirm source card counts from the filesystem**

Run:

```bash
find knowledge/source_documents/guidelines -maxdepth 1 -name '*.md' | wc -l
find knowledge/source_documents/papers -maxdepth 1 -name '*.md' | wc -l
find knowledge/source_documents/manual -maxdepth 1 -name '*.md' | wc -l
```

Expected:

```text
24
18
18
```

- [ ] **Step 5: Commit**

```bash
git add knowledge/datasets/rule_extraction_v1/README.zh.md
git commit -m "docs: document rule extraction dataset validation"
```

## Task 7: Optional Real LLM Observation Run

**Files:**
- Modify: `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`
- Optional create: `reports/rule-extraction-v1-observation-report.md`

- [ ] **Step 1: Run existing real LLM smoke tests only if environment variables are available**

Run:

```bash
MEDIDIET_LLM_SMOKE_TEST=1 \
MEDIDIET_LLM_RULE_SMOKE_TEST=1 \
MEDIDIET_LLM_CONFLICT_SMOKE_TEST=1 \
MEDIDIET_LLM_NOISY_SMOKE_TEST=1 \
PYTHONPATH=src:knowledge/src python scripts/run_real_llm_smoke_tests.py
```

Expected: a report is written under `reports/` and default CI behavior remains unchanged.

- [ ] **Step 2: If performing a dataset-specific run, append observations only**

Append JSONL rows to `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl` using this shape:

```json
{"run_id":"rule_extraction_v1_2026_05_22_001","doc_id":"en_guideline_who_sodium_2012","expected_id":"expected_en_guideline_who_sodium_2012_001","observed_behavior":"rule","verifier_verdict":"pass","traceability_score":0.86,"consistency_score":0.81,"failure_type":null,"extraction_model":"deepseek-v4-flash","verification_model":"deepseek-v4-flash","prompt_versions":{"extraction":"current","verification":"current"}}
```

Do not edit `gold_evaluation_set.jsonl` during this task.

- [ ] **Step 3: Run dataset validation after observations are appended**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_rule_extraction_dataset.py -q --rootdir=.
```

Expected: PASS.

- [ ] **Step 4: Commit observations if a dataset-specific run was performed**

```bash
git add knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl reports/
git commit -m "test: record rule extraction dataset observations"
```

Skip this commit if no dataset-specific observation run was performed.

## Self-Review Checklist

- Spec coverage: plan covers source cards, manifest, weak expected rules, extraction observations, frozen gold evaluation set, challenge set, quality gates, and leakage prevention.
- No-human-in-loop boundary: system generation uses weak labels and observations; gold records are offline-only and frozen.
- Validation coverage: tests enforce 60 records, 30/30 language split, 24/18/18 source type split, provenance fields, label counts, schema references, gold subset size, and challenge taxonomy.
- Current code alignment: plan uses existing Markdown loader and valid `source_type` values only.
- Known implementation risk: source acquisition needs browsing and copyright care during execution; source cards must use summaries or short excerpts rather than full article text.
