# DocRule-Agent E1 Experiment Runbook And Results

## Run Date

2026-05-26

## Purpose

This document records how to run the current experiment framework and how to interpret the first E1 real-LLM run. The goal is to confirm that the pipeline is operational, then compare how three source-card input variants affect numeric rule extraction.

## Commands Run

### Dry-Run Full Matrix

Dry-run verifies that the research pipeline can generate all matrix reports without network calls.

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --benchmark-portfolio doc_rule_agent_lifecycle_v1 \
  --experiment-matrix doc_rule_agent_v1 \
  --benchmark-experiments B1,B2,B3,B4,B5,B6,B7 \
  --experiments E1,E2,E3,E4,E5,E6,E7 \
  --arms C0,C1,C2,C3,C4,C5,C6,C7,C8 \
  --chunk-strategies raw_card,extractable_content,source_notes_plus_extractable \
  --dry-run \
  --write-reports
```

### Real LLM E1 Run

This run executes E1 once per document and per input arm.

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --benchmark-portfolio doc_rule_agent_lifecycle_v1 \
  --experiment-matrix doc_rule_agent_v1 \
  --benchmark-experiments B1 \
  --experiments E1 \
  --arms C1,C2,C3 \
  --chunk-strategies raw_card,extractable_content,source_notes_plus_extractable \
  --real-llm \
  --append-observations \
  --write-reports
```

## Test Documents

The current dataset has two source cards.

| doc_id | Source | Focus | Gold Rule |
| --- | --- | --- | --- |
| `en_guideline_who_sodium_2012` | WHO sodium guideline source card | hypertension / sodium | `hypertension`, `sodium_mg daily <= 2000` |
| `en_manual_diabetes_sugar_case` | diabetes sugar stability fixture | diabetes / added sugar | `diabetes`, `sugar_g daily <= 25` |

These source cards are summaries or short excerpts. They are not full copyrighted guideline documents.

## E1 Arms

E1 is the chunking/input-selection ablation.

| Arm | Input Variant | Meaning |
| --- | --- | --- |
| `C1` | `raw_card` | LLM sees the full source card, including frontmatter, source notes, and copyright handling text. |
| `C2` | `extractable_content` | LLM sees only the material after `## Extractable Source Content`. |
| `C3` | `source_notes_plus_extractable` | LLM sees source notes plus extractable content, but not frontmatter or copyright handling blocks. |

## Evaluation Standard

The current E1 evaluation asks whether the extracted candidate matches the frozen gold rule at field level.

Primary fields:

- condition: expected condition code, such as `hypertension` or `diabetes`.
- preferred tags: expected diet tag, such as `low_sodium` or `low_sugar`.
- nutrition limits: metric, scope, max value, and time window.
- verification verdict: whether the verifier accepted, rejected, or requested revision.

For this smoke-scale dataset, the most important signal is numeric-limit recovery:

- Sodium card should recover `sodium_mg daily <= 2000`.
- Diabetes card should recover `sugar_g daily <= 25`.

Current implementation note: daily limits from parsed rules currently store `window_hours: null`, while the gold rows use `window_hours: 24`. When reading reports manually, treat this as a normalization issue to fix before formal scoring. The underlying metric/scope/value can still be inspected directly.

## What To Observe

### 1. Chunking Quality

Report:

```text
reports/rule-extraction-v1-chunking-report.json
```

Observe:

- total chunks per strategy.
- `chunks_with_frontmatter`.
- `chunks_with_copyright_handling`.
- `chunks_starting_mid_word`.
- representative previews.

Meaning:

- If `extractable_content` still contains frontmatter or copyright text, the preprocessing strategy is leaking non-source material.
- If chunks start mid-word, overlap behavior may distort prompts.

### 2. Real LLM Extraction Output

Report:

```text
reports/rule-extraction-v1-real-llm-report.json
```

Observe:

- `observation_count`.
- `operational_failure_count`.
- each observation's `arm_id`, `input_variant`, `doc_id`.
- `parsed_rules`.
- `nutrition_limits`.
- `verification_verdict`.
- `failures`.

Meaning:

- `operational_failures` are API/transport issues and are excluded from research metrics.
- `observations` are valid research rows.
- A parsed rule with the correct condition but no numeric limit is a partial extraction failure.
- A `rejected` verifier result means the extraction should not be treated as a reliable candidate.

### 3. Append-Only Observation Log

Dataset log:

```text
knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl
```

Observe:

- one JSON object per valid research observation.
- `experiment_id`, `arm_id`, `input_variant`, `doc_id`.
- `observation_points.O5`, `O6`, `O8`.

Meaning:

- This file is the machine history for valid research observations.
- API failures should not appear here.

## Current Real LLM E1 Results

This run produced:

- research observations: 6
- operational failures: 0

| doc_id | Arm | Input Variant | Parsed Rule Summary | Verifier |
| --- | --- | --- | --- | --- |
| `en_guideline_who_sodium_2012` | `C1` | `raw_card` | `hypertension`, `sodium_mg daily <= 2000` | pass |
| `en_guideline_who_sodium_2012` | `C2` | `extractable_content` | `hypertension`, `sodium_mg daily <= 2000` | pass |
| `en_guideline_who_sodium_2012` | `C3` | `source_notes_plus_extractable` | `hypertension`, `sodium_mg daily <= 2000` | pass |
| `en_manual_diabetes_sugar_case` | `C1` | `raw_card` | `diabetes`, no numeric limit | rejected |
| `en_manual_diabetes_sugar_case` | `C2` | `extractable_content` | `diabetes`, no numeric limit | rejected |
| `en_manual_diabetes_sugar_case` | `C3` | `source_notes_plus_extractable` | `diabetes`, `sugar_g daily <= 25` | pass |

## Interpretation

The sodium card is easy for the current extractor: all three input variants recover the numeric sodium threshold.

The diabetes card is more sensitive to input selection. In this run, `source_notes_plus_extractable` recovered the numeric sugar limit and passed verification, while raw-card and extractable-content variants missed the numeric limit and were rejected. This is not yet a statistical conclusion, but it is a useful observation: adding source notes may help the model ground short fixture-like source cards.

The next useful step is to repeat E1 for the same two documents several times, then check whether the diabetes `C3` advantage persists or was a one-run stochastic result.

## Practical Reading Checklist

When reviewing a run, check in this order:

1. `operational_failure_count`: if nonzero, those calls should be ignored for research scoring.
2. `observation_count`: confirms how many valid research rows remain.
3. `input_variant`: confirms the intended arm was actually used.
4. `parsed_rules[].nutrition_limits`: verifies numeric recovery.
5. `verification_verdict`: separates accepted candidates from rejected or revision-needed candidates.
6. `extraction_observations.jsonl`: confirms valid observations were appended.
