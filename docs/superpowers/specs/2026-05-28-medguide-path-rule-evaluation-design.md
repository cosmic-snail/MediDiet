# MedGUIDE Path-Rule Evaluation Design

## Goal

Add a MedGUIDE-compatible benchmark path that evaluates deterministic rule matching, not autonomous LLM question answering, while leaving the existing nutrition rule extraction and recommendation path unchanged.

## Scope

This design adds a separate path-rule evaluation layer beside `ExtractedConditionRule`.

In scope:

- Convert a MedGUIDE MCQA row into a `PathRule`.
- Match supplied patient facts against candidate path rules.
- Select an answer through deterministic rule matching.
- Evaluate answer correctness and path-process correctness.
- Fetch a small number of MedGUIDE rows from HuggingFace for smoke testing.

Out of scope for this first version:

- Full clinical decision-tree extraction from guideline source text.
- LLM autonomous answering of MedGUIDE prompts.
- Replacement of nutrition rule schemas or recommendation behavior.

## Architecture

The feature is intentionally additive.

- `knowledge.path_rule_evaluation` contains the path-rule schema, deterministic matcher, and metrics.
- `knowledge.medguide_path_rule_benchmark` contains dataset fetch/report helpers and a small CLI.
- Existing modules such as `knowledge.extractor`, `knowledge.rule_evaluation`, and the nutrition `ExtractedConditionRule` dataclass are not changed.

## Data Flow

```text
MedGUIDE row
  -> path_rule_from_medguide_row
  -> PathRule(conditions, action, answer)

patient facts
  -> match_path_rules
  -> PathRulePrediction(selected answer, matched path)

gold PathRule + prediction
  -> evaluate_path_rule_prediction
  -> answer/path metrics
```

The first implementation accepts facts from outside the benchmark runner. In future work, those facts can come from a patient-profile fact extractor. The final answer is still selected by deterministic rule matching.

## Metrics

- `answer_accuracy`: selected answer matches MedGUIDE gold answer.
- `path_node_precision`: matched path nodes that are in the gold path.
- `path_node_recall`: gold path nodes recovered by the matched path.
- `path_order_match`: matched gold nodes preserve the gold order.
- `missing_path_nodes`: gold path nodes not matched.
- `unsupported_path_nodes`: matched nodes outside the gold path.

## Compatibility

The existing nutrition recommendation capability remains compatible because:

- No existing nutrition rule dataclasses are modified.
- No existing evaluator behavior is changed.
- The new benchmark uses separate modules and tests.
- Existing rule-extraction dataset tests continue to pass.

## MedGUIDE Modes

`external_facts` mode is the intended system-evaluation mode. It evaluates facts extracted by the system from the clinical profile.

`oracle_path_facts` mode uses MedGUIDE gold path nodes as facts. It is only a pipeline smoke test and must not be reported as model or system performance.
