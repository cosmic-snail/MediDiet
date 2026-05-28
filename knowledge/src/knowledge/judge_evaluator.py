from __future__ import annotations

import json
from collections import Counter
from typing import Any

from medidiet.llm import LLMProviderPort, LLMRequest, LLMTask


VALID_JUDGE_VERDICTS = {"accept", "reject", "uncertain"}
POSITIVE_GOLD_OUTCOMES = {"match", "partial_match"}


class JudgeLLMEvaluator:
    def __init__(self, llm_provider: LLMProviderPort):
        self.llm_provider = llm_provider

    def evaluate_rule(
        self,
        *,
        source_text: str,
        extracted_rule: dict[str, Any],
        evaluation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.llm_provider.complete(
            LLMRequest(
                task=LLMTask.RULE_VALIDATION,
                system_prompt=_judge_system_prompt(),
                user_prompt=_judge_user_prompt(source_text, extracted_rule, evaluation_context or {}),
                response_format="json",
            )
        )
        return _parse_judge_response(response.content)


def calibrate_judge_against_gold(
    judge_results: list[dict[str, Any]],
    gold_evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_label_by_id = {
        str(gold_evaluation.get("gold_id")): _gold_label(gold_evaluation)
        for gold_evaluation in gold_evaluations
        if gold_evaluation.get("gold_id")
    }
    judge_labels: list[str] = []
    gold_labels: list[str] = []
    rows: list[dict[str, Any]] = []
    for judge_result in judge_results:
        gold_id = str(judge_result.get("gold_id") or "")
        if gold_id not in gold_label_by_id:
            continue
        judge_label = _judge_label(judge_result)
        gold_label = gold_label_by_id[gold_id]
        judge_labels.append(judge_label)
        gold_labels.append(gold_label)
        rows.append(
            {
                "gold_id": gold_id,
                "judge_label": judge_label,
                "gold_label": gold_label,
                "agrees": judge_label == gold_label,
            }
        )
    agreement_count = sum(1 for row in rows if row["agrees"])
    return {
        "calibrated_record_count": len(rows),
        "agreement_rate": agreement_count / len(rows) if rows else 0.0,
        "gwet_ac1": gwet_ac1(judge_labels, gold_labels) if rows else 0.0,
        "rows": rows,
    }


def build_layer_2_judge_summary(
    judge_results: list[dict[str, Any]],
    gold_evaluations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    verdict_counts = Counter(str(result.get("verdict") or "uncertain") for result in judge_results)
    evaluated_rule_count = len(judge_results)
    confidences = [float(result.get("confidence", 0.0)) for result in judge_results]
    summary = {
        "evaluated_rule_count": evaluated_rule_count,
        "accept_rate": verdict_counts.get("accept", 0) / evaluated_rule_count if evaluated_rule_count else 0.0,
        "uncertain_rate": verdict_counts.get("uncertain", 0) / evaluated_rule_count if evaluated_rule_count else 0.0,
        "reject_rate": verdict_counts.get("reject", 0) / evaluated_rule_count if evaluated_rule_count else 0.0,
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
    }
    if gold_evaluations is not None:
        summary["calibration"] = calibrate_judge_against_gold(judge_results, gold_evaluations)
    return summary


def gwet_ac1(left_labels: list[str], right_labels: list[str]) -> float:
    if len(left_labels) != len(right_labels):
        raise ValueError("label lists must have the same length")
    if not left_labels:
        return 0.0
    labels = sorted(set(left_labels) | set(right_labels))
    observed_agreement = sum(1 for left, right in zip(left_labels, right_labels) if left == right) / len(left_labels)
    category_probabilities = []
    for label in labels:
        left_count = sum(1 for item in left_labels if item == label)
        right_count = sum(1 for item in right_labels if item == label)
        category_probabilities.append((left_count + right_count) / (2 * len(left_labels)))
    chance_agreement = sum(probability * (1 - probability) for probability in category_probabilities) / (len(labels) - 1) if len(labels) > 1 else 0.0
    if chance_agreement == 1:
        return 1.0
    return round((observed_agreement - chance_agreement) / (1 - chance_agreement), 4)


def _parse_judge_response(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {"verdict": "uncertain", "confidence": 0.0, "field_verdicts": {}, "reason": "invalid_judge_json"}
    verdict = str(payload.get("verdict") or "uncertain")
    if verdict not in VALID_JUDGE_VERDICTS:
        verdict = "uncertain"
    return {
        "verdict": verdict,
        "confidence": _clamp_confidence(payload.get("confidence", 0.0)),
        "field_verdicts": payload.get("field_verdicts", {}) if isinstance(payload.get("field_verdicts"), dict) else {},
        "reason": str(payload.get("reason") or ""),
    }


def _judge_label(judge_result: dict[str, Any]) -> str:
    return "accept" if judge_result.get("verdict") == "accept" else "reject"


def _gold_label(gold_evaluation: dict[str, Any]) -> str:
    return "accept" if gold_evaluation.get("overall") in POSITIVE_GOLD_OUTCOMES else "reject"


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _judge_system_prompt() -> str:
    return (
        "You are evaluating whether a structured nutrition rule is supported by a source card. "
        "Return JSON only with verdict accept, reject, or uncertain; confidence; field_verdicts; and reason. "
        "When evaluation_context.expected_gold_rule is present, judge the extracted rule against those required fields. "
        "A source-supported but incomplete rule is not an accept. If the expected gold rule has nutrition_limits and "
        "the extracted rule is missing required nutrition_limits, return reject or uncertain, not accept. "
        "Use accept only when the key extracted fields are source-supported and satisfy the expected gold requirement."
    )


def _judge_user_prompt(
    source_text: str,
    extracted_rule: dict[str, Any],
    evaluation_context: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "source_text": source_text,
            "extracted_rule": extracted_rule,
            "evaluation_context": evaluation_context,
            "output_schema": {
                "verdict": "accept|reject|uncertain",
                "confidence": "0..1",
                "field_verdicts": {
                    "condition": "accept|reject|uncertain",
                    "hard_exclusions": "accept|reject|uncertain",
                    "preferred_tags": "accept|reject|uncertain",
                    "nutrition_limits": "accept|reject|uncertain",
                },
                "reason": "short rationale",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )
