# Rule Extraction Layered Evaluation Summary

## Run

- dataset: `rule_extraction_v1`
- run type: `real_llm`
- provider: `openai_compatible`
- model: `deepseek-v4-flash`
- observations: 2
- operational failures: 0

## Golden Eval

- precision: 0.000
- recall: 0.000
- f1: 0.000
- accuracy chart: `reports/layered-judge-validation-20260528/rule-extraction-v1-golden-eval-accuracy-chart.png`

## Layer 0 Plausibility

- pass: 2
- warn: 0
- fail: 0

## Layer 1 Grounding

- evaluated observations: 2
- average score: 1.000
- unsupported rate: 0.000

## Layer 2 Judge

- evaluated rules: 2
- accept rate: 1.000
- uncertain rate: 0.000
- reject rate: 0.000
- average confidence: 0.900
- calibrated records: 1
- agreement rate: 0.000
- Gwet AC1: -1.000

## Judge Cases

| Experiment | Arm | Doc | Verdict | Confidence | Reason |
| --- | --- | --- | --- | ---: | --- |
| E1 | C2 | zh_guideline_hypertension_food_therapy_2023 | accept | 0.90 | The source text emphasizes a balanced diet with salt reduction and attention to high-sodium foods, directly supporting the condition 'hypertension', hard exclusion 'high_sodium', and preferred tags 'balanced' and 'low_sodium'. No nutrition limits are mentioned, which is consistent. |
| E1 | C2 | zh_guideline_diabetes_food_therapy_2023 | accept | 0.90 | The source text explicitly supports the condition 'diabetes' and the preferred tags 'balanced' (balanced food selection) and 'controlled_carbs' (carbohydrate quality). No hard exclusions or nutrition limits are mentioned, so empty lists are acceptable. |
