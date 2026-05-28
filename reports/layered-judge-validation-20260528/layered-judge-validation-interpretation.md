# Layered Judge Validation Interpretation

## Run Scope

- Dataset: `rule_extraction_v1`
- Experiment: `E1`
- Arm: `C2`
- Documents: first 2 manifest source cards
- Judge setting: `--judge-llm --judge-max-rules 4`
- Provider/model: `openai_compatible / deepseek-v4-flash`

## Outputs

- Real LLM report: `reports/layered-judge-validation-20260528/rule-extraction-v1-real-llm-report.json`
- Golden eval accuracy report: `reports/layered-judge-validation-20260528/rule-extraction-v1-golden-eval-accuracy-report.json`
- Golden eval accuracy chart: `reports/layered-judge-validation-20260528/rule-extraction-v1-golden-eval-accuracy-chart.png`
- Layered summary: `reports/layered-judge-validation-20260528/rule-extraction-v1-layered-evaluation-summary.md`

## Layer Results

Layer 0 plausibility passed both observations: `pass=2`, `warn=0`, `fail=0`.

Layer 1 grounding also passed cleanly: average grounding score was `1.000`, and unsupported observation rate was `0.000`.

Layer 2 Judge evaluated 2 extracted rules. It accepted both rules with average confidence `0.900`.

## Golden Eval Comparison

Only one of the two observed documents currently maps to a frozen golden eval row in this run:

- `zh_guideline_hypertension_food_therapy_2023`

Golden eval marked this extraction as `miss` because the extracted rule omitted the required numeric sodium limit:

- condition: match
- hard exclusions: match
- preferred tags: partial
- nutrition limits: missing
- failure: `missing_numeric_limit`

The Judge LLM accepted the same rule because the source supports hypertension salt reduction and high-sodium avoidance. This creates a Judge-vs-gold disagreement:

- calibrated records: `1`
- agreement rate: `0.000`
- Gwet AC1: `-1.000`

## Interpretation

The deterministic layers are working as intended: L0 and L1 confirm that the extracted rules are plausible and grounded in the source text. The failure is not hallucination; it is under-extraction relative to the frozen gold requirement.

The Judge prompt is currently too permissive for numeric-threshold gold cases. It accepts a general sodium-reduction rule even when the golden eval expects an explicit `sodium_mg <= 2000` daily limit. The next Judge prompt should explicitly reject or mark uncertain when a frozen gold numeric requirement is absent from the extracted rule.

## Recommended Next Fix

Tighten the Judge prompt and calibration context:

- Include the golden eval expectation when judging calibration records.
- Tell Judge that a missing required numeric threshold is not acceptable even if the broader dietary direction is supported.
- Distinguish `source-supported but incomplete` from `accept`.

After that, rerun the same command and expect the hypertension case to move from Judge `accept` to `reject` or `uncertain`, improving alignment with golden eval.
