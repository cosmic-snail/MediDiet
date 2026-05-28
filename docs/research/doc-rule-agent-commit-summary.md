# DocRule-Agent Research Harness Commit Summary

## Commit

- Commit: `b3ad039 implement doc-rule-agent research harness`
- Branch: `codex/doc-rule-agent-research-program`
- PR: `https://github.com/cosmic-snail/MediDiet/pull/8`
- Date: 2026-05-26

## Purpose

This commit turns the earlier document-to-rule extraction prototype into a reproducible DocRule-Agent research harness. The main change is the addition of a research plane beside the existing clinical rule publication flow. The research plane can compare extraction designs, record observations, evaluate field-level quality, study stability, and preserve machine registry snapshots without weakening the existing human-reviewed `approved` rule semantics.

## What Changed

### Research Protocol And Benchmark Planning

The commit adds research documentation under `docs/research/`:

- `doc-rule-agent-research-protocol.md` defines research questions, hypotheses, comparator arms C0-C8, observation points O1-O13, benchmark experiments B1-B7, and transfer experiments E1-E7.
- `public-benchmark-selection.md` explains why the evaluation uses lifecycle-specific public benchmarks instead of forcing every dataset into `ExtractedConditionRule`.
- `target-nutrition-gold-protocol.md` defines the planned KDOQI/KDIGO/ADA/dialysis nutrition gold set scope, target size, fields, split policy, and clinical boundary.

### Rule Extraction Dataset Scaffold

The commit creates `knowledge/datasets/rule_extraction_v1/` with:

- manifest rows for sodium and diabetes sugar source cards.
- frozen gold evaluation rows.
- a challenge row for schema-gap analysis.
- append-only `extraction_observations.jsonl`.
- a Chinese README linking the dataset to the research protocol.

It also adds two short source cards under `knowledge/source_documents/guidelines/`. These are source-card summaries and short excerpts, not full copyrighted guideline copies.

### Core Research Modules

The implementation adds small, testable modules:

- `dataset_manifest.py`: manifest-driven ingestion, source-card hashing, extractable-content hashing, frontmatter agreement checks, and source snapshot diffing.
- `extraction_experiments.py`: comparator arms, observation points, benchmark matrix, and transfer experiment matrix.
- `public_benchmarks.py`: L0-L8 lifecycle benchmark registry and bridge-schema mapping.
- `extraction_comparators.py`: shared dry-run comparator contract for C0-C8.
- `extraction_observations.py`: append-only observation dataclass and JSONL writer.
- `extraction_stability.py`: repeated-run stability summaries.
- `rule_evaluation.py`: field-level evaluator and concept-gap reporting aliases.
- `rule_identity.py`: canonical rule identity and rule-set diff helpers.
- `source_governance.py`: authority metadata and numeric conflict detection.
- `research_registry.py`: research-only machine snapshots and registry report export.
- `rule_extraction_dataset_smoke.py`: deterministic dry-run report command and opt-in real LLM report command.

### Document Chunking Instrumentation

`DocumentImporter` now supports explicit chunk strategies while preserving the production default:

- `raw_card`
- `extractable_content`
- `source_notes_plus_extractable`

Generated chunks now expose metadata needed by the research protocol: strategy, index, start/end character offsets, chunk hash, overlap prefix, mid-word-start flag, frontmatter flag, and copyright-handling flag.

## Generated Reports

The commit includes deterministic reports under `reports/`:

- benchmark portfolio report.
- transfer-gap report.
- experiment matrix report.
- observation coverage report.
- field evaluation report.
- stability report.
- chunking report.
- research registry JSONL and Markdown report.
- paper-oriented error taxonomy and experiment summary.
- real LLM report from the opt-in run.

These reports are intentionally machine-readable where possible, so future analysis scripts can compare dry-run, real-run, and repeated-run outputs.

## Real LLM Run

The real LLM run used the local `.env` configuration without committing any credentials. After excluding API-level operational failures from research metrics, it produced five research observations and three operational failure records from:

- experiments: `E1`, `E2`
- arms: `C1`, `C2`
- documents: sodium source card and diabetes sugar source card
- provider/model recorded in the report: `openai_compatible / deepseek-v4-flash`

The run successfully extracted several numeric rules. API and transport failures are treated as operational run failures, not research observations; they do not affect field-level scoring, stability, or extraction architecture comparisons.

## Safety Boundary

This commit does not publish machine-extracted rules into patient-facing `RulePack` output. Machine outputs are marked as research-only observations or registry snapshots. Clinical publication still requires separate explicit review through the existing approval path.

## Validation

The branch was verified with:

```bash
PYTHONPATH=src:knowledge/src pytest -q --rootdir=.
```

Observed result before PR creation:

```text
280 passed, 12 skipped, 142 warnings, 16 subtests passed
```

The deterministic dry-run report command was also executed successfully:

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --benchmark-portfolio doc_rule_agent_lifecycle_v1 \
  --experiment-matrix doc_rule_agent_v1 \
  --benchmark-experiments B1,B2,B3,B4,B5,B6,B7 \
  --experiments E1,E2,E3,E4,E5,E6,E7 \
  --arms C0,C1,C2,C3,C4,C5,C6,C7,C8 \
  --chunk-strategies raw_card,extractable_content \
  --dry-run \
  --write-reports
```

## Follow-Up Work

Useful next steps:

- Expand `rule_extraction_v1` from two source cards toward the planned 100-200 target nutrition gold records.
- Add retry-count and raw-response-path recording for real LLM calls.
- Add a richer real-run evaluator that joins observations back to frozen gold rows.
- Separate large generated JSON reports if PR size becomes noisy.
- Run stability experiments with more repeats once provider reliability and cost are acceptable.
