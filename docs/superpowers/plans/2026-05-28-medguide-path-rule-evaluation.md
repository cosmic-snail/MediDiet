# MedGUIDE Path-Rule Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a MedGUIDE-compatible benchmark path that evaluates deterministic rule matching from extracted facts and path rules.

**Architecture:** Add standalone path-rule schema/evaluator and a MedGUIDE runner beside the existing nutrition rule pipeline. Keep `ExtractedConditionRule`, nutrition evaluators, and source-card dataset behavior unchanged.

**Tech Stack:** Python dataclasses, pytest, HuggingFace datasets-server JSON API, JSON reports.

---

### Task 1: PathRule Schema And Metrics

**Files:**
- Create: `knowledge/src/knowledge/path_rule_evaluation.py`
- Test: `knowledge/tests/test_medguide_path_rules.py`

- [x] **Step 1: Write failing tests**

Add tests for MedGUIDE row conversion, deterministic matching, answer correctness, path precision/recall, ordered path matching, missing nodes, and unsupported nodes.

- [x] **Step 2: Run tests and confirm red**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_medguide_path_rules.py -q --rootdir=.
```

Expected: import failure for `knowledge.path_rule_evaluation`.

- [x] **Step 3: Implement minimal module**

Define `PathRule`, `PathRulePrediction`, `path_rule_from_medguide_row`, `match_path_rules`, and `evaluate_path_rule_prediction`.

- [x] **Step 4: Verify green**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_medguide_path_rules.py -q --rootdir=.
```

Expected: path-rule unit tests pass.

### Task 2: MedGUIDE Benchmark Runner

**Files:**
- Create: `knowledge/src/knowledge/medguide_path_rule_benchmark.py`
- Modify: `knowledge/tests/test_medguide_path_rules.py`

- [x] **Step 1: Write failing tests**

Add tests for report writing with `autonomous_llm_answering=false` and for retrying interrupted HuggingFace reads.

- [x] **Step 2: Run tests and confirm red**

Expected: import failure for `knowledge.medguide_path_rule_benchmark`, then retry failure before implementation.

- [x] **Step 3: Implement runner**

Add `fetch_medguide_rows`, `load_facts_jsonl`, `write_medguide_path_rule_report`, and CLI `main`.

- [x] **Step 4: Verify green**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_medguide_path_rules.py -q --rootdir=.
```

Expected: all MedGUIDE tests pass.

### Task 3: Live Smoke And Compatibility Check

**Files:**
- Create: `reports/medguide-path-rule-benchmark-smoke.json`

- [x] **Step 1: Run live MedGUIDE smoke**

Run:

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.medguide_path_rule_benchmark \
  --offset 0 \
  --limit 5 \
  --output reports/medguide-path-rule-benchmark-smoke.json
```

Expected: report writes with `row_count=5`, `mode=oracle_path_facts`, and `autonomous_llm_answering=false`.

- [x] **Step 2: Run regression tests**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest \
  knowledge/tests/test_medguide_path_rules.py \
  knowledge/tests/test_rule_evaluation.py \
  knowledge/tests/test_rule_extraction_dataset.py \
  knowledge/tests/test_rule_extraction_dataset_smoke_reports.py \
  knowledge/tests/test_epfl_guidelines_smoke_dataset.py \
  -q --rootdir=.
```

Expected: existing nutrition-rule tests still pass.

### Task 4: Profile Facts Mode

**Files:**
- Create: `knowledge/src/knowledge/profile_fact_extraction.py`
- Modify: `knowledge/src/knowledge/medguide_path_rule_benchmark.py`
- Modify: `knowledge/tests/test_medguide_path_rules.py`
- Create: `reports/medguide-path-rule-profile-facts-smoke.json`

- [x] **Step 1: Write failing tests**

Add tests proving `extract_profile_facts` can match profile text to candidate path nodes without seeing options, and proving the runner can build profile facts and report `profile_lexical_facts` mode.

- [x] **Step 2: Run tests and confirm red**

Run:

```bash
PYTHONPATH=src:knowledge/src pytest knowledge/tests/test_medguide_path_rules.py -q --rootdir=.
```

Expected: import failure for `knowledge.profile_fact_extraction` or missing `build_profile_facts_for_medguide_rows`.

- [x] **Step 3: Implement lexical fact extractor**

Add deterministic token-overlap matching with small clinical abbreviation normalization such as `BM -> bone marrow` and `HCT -> transplant`. Keep fact extraction independent of answer options.

- [x] **Step 4: Run profile-facts live smoke**

Run:

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.medguide_path_rule_benchmark \
  --offset 0 \
  --limit 20 \
  --profile-facts \
  --output reports/medguide-path-rule-profile-facts-smoke.json
```

Expected: report writes with `mode=profile_lexical_facts` and `autonomous_llm_answering=false`.
