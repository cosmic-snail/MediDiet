# DocRule-Agent Real LLM Run Summary

## Run Scope

This run was executed after the research harness was implemented, using `.env` for local provider configuration. No credential values are stored in the repository.

- Dataset: `rule_extraction_v1`
- Experiments: `E1`, `E2`
- Comparator arms: `C1`, `C2`
- Documents: `en_guideline_who_sodium_2012`, `en_manual_diabetes_sugar_case`
- Research observation count: 5
- Operational failure count: 3
- Report: `reports/rule-extraction-v1-real-llm-report.json`
- Append-only observations: `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`

## Provider

The run report records:

- provider: `openai_compatible`
- model: `deepseek-v4-flash`

## High-Level Results

The run produced useful successful extractions and separate operational failure records.

Successful examples included:

- Sodium source card under `C2 extractable_content`: extracted `hypertension` with a daily `sodium_mg <= 2000` numeric limit.
- Diabetes sugar source card under both raw-card and extractable-content variants: extracted `diabetes` with a daily `sugar_g <= 25` numeric limit in multiple runs.

Operational failures excluded from research observations included:

- one extraction call failure on the sodium raw-card run: `IncompleteRead(0 bytes read)`.
- verification failures on sodium runs where extraction succeeded but validation hit provider/request errors.
Research observations also included one diabetes extractable-content E2 run with a `revision_needed` verification verdict. This remains in scope because the provider returned a valid model response.

API/transport failures are not part of the research scope for extraction quality. They are recorded separately as run hygiene information and excluded from field-level scoring, stability, and architecture comparisons. Model-level outcomes such as `revision_needed` remain relevant when the provider returned a valid response.

## Interpretation

The strongest early signal is that `extractable_content` gives cleaner sodium extraction than `raw_card` in this tiny run. That aligns with hypothesis H1, but the sample is too small to claim evidence. The right interpretation is that the system can now record the comparison in a repeatable way.

The run also shows why separating research observations from operational failures matters. A pass/fail-only smoke test would collapse provider instability, partial extraction, and numeric success into one coarse result. The new report keeps operational reliability out of extraction-quality metrics.

## Caveats

- This was a small smoke run, not a statistical experiment.
- Provider instability affected some calls, and those calls are excluded from research observations.
- The report currently records normalized parsed rules, not full raw provider responses.
- Some tags are absent because the current baseline concept registry does not include every research concept, such as `low_sugar`.
- Machine-extracted candidates remain research-only and are not approved clinical rules.

## Reproduction Command

```bash
PYTHONPATH=src:knowledge/src python -m knowledge.rule_extraction_dataset_smoke \
  --dataset rule_extraction_v1 \
  --benchmark-portfolio doc_rule_agent_lifecycle_v1 \
  --experiment-matrix doc_rule_agent_v1 \
  --benchmark-experiments B1,B2,B3,B4,B5 \
  --experiments E1,E2 \
  --arms C1,C2 \
  --chunk-strategies raw_card,extractable_content \
  --real-llm \
  --append-observations \
  --write-reports
```

For the focused E1 chunking/input-selection runbook and latest C1/C2/C3 results, see `docs/research/doc-rule-agent-e1-experiment-runbook.md`.
