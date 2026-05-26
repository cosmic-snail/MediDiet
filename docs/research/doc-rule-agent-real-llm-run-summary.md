# DocRule-Agent Real LLM Run Summary

## Run Scope

This run was executed after the research harness was implemented, using `.env` for local provider configuration. No credential values are stored in the repository.

- Dataset: `rule_extraction_v1`
- Experiments: `E1`, `E2`
- Comparator arms: `C1`, `C2`
- Documents: `en_guideline_who_sodium_2012`, `en_manual_diabetes_sugar_case`
- Observation count: 8
- Report: `reports/rule-extraction-v1-real-llm-report.json`
- Append-only observations: `knowledge/datasets/rule_extraction_v1/extraction_observations.jsonl`

## Provider

The run report records:

- provider: `openai_compatible`
- model: `deepseek-v4-flash`

## High-Level Results

The run produced both useful successful extractions and useful failure observations.

Successful examples included:

- Sodium source card under `C2 extractable_content`: extracted `hypertension` with a daily `sodium_mg <= 2000` numeric limit.
- Diabetes sugar source card under both raw-card and extractable-content variants: extracted `diabetes` with a daily `sugar_g <= 25` numeric limit in multiple runs.

Observed failures included:

- one extraction call failure on the sodium raw-card run: `IncompleteRead(0 bytes read)`.
- verification failures on sodium runs where extraction succeeded but validation hit provider/request errors.
- one diabetes extractable-content E2 run with a `revision_needed` verification verdict.

These failures are not treated as noise to erase. They are part of O6 provider-call and O8 structured-parse observations and should inform the stability and reliability sections of the paper.

## Interpretation

The strongest early signal is that `extractable_content` gives cleaner sodium extraction than `raw_card` in this tiny run. That aligns with hypothesis H1, but the sample is too small to claim evidence. The right interpretation is that the system can now record the comparison in a repeatable way.

The run also shows why observation logging matters. A pass/fail-only smoke test would collapse provider instability, verification failure, partial extraction, and numeric success into one coarse result. The new report keeps those states separate.

## Caveats

- This was a small smoke run, not a statistical experiment.
- Provider instability affected some calls.
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
