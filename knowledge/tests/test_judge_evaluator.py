from __future__ import annotations

import json

from medidiet.llm import LLMResponse, LLMTask
from knowledge.judge_evaluator import (
    JudgeLLMEvaluator,
    build_layer_2_judge_summary,
    calibrate_judge_against_gold,
    gwet_ac1,
)


class RecordingJudgeProvider:
    def __init__(self, payloads: list[dict]):
        self.payloads = list(payloads)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return LLMResponse(
            content=json.dumps(self.payloads.pop(0), ensure_ascii=False),
            provider_name="recording",
            model="judge-model",
        )


def test_judge_evaluator_parses_accept_verdict():
    provider = RecordingJudgeProvider(
        [
            {
                "verdict": "accept",
                "confidence": 0.82,
                "field_verdicts": {"condition": "accept", "nutrition_limits": "accept"},
                "reason": "The rule is supported by the source card.",
            }
        ]
    )
    evaluator = JudgeLLMEvaluator(provider)

    result = evaluator.evaluate_rule(
        source_text="Hypertension guidance recommends sodium below 2000 mg per day.",
        extracted_rule={"condition": "hypertension", "nutrition_limits": [{"metric": "sodium_mg", "max_value": 2000}]},
        evaluation_context={"gold_id": "gold_001"},
    )

    assert provider.requests[0].task is LLMTask.RULE_VALIDATION
    assert result["verdict"] == "accept"
    assert result["confidence"] == 0.82
    assert result["field_verdicts"]["condition"] == "accept"


def test_gwet_ac1_handles_binary_agreement():
    assert gwet_ac1(["accept", "reject", "accept"], ["accept", "reject", "reject"]) == 0.3333


def test_calibrate_judge_against_gold_reports_agreement_and_ac1():
    judge_results = [
        {"gold_id": "gold-1", "verdict": "accept"},
        {"gold_id": "gold-2", "verdict": "reject"},
        {"gold_id": "gold-3", "verdict": "accept"},
    ]
    gold_evaluations = [
        {"gold_id": "gold-1", "overall": "match"},
        {"gold_id": "gold-2", "overall": "miss"},
        {"gold_id": "gold-3", "overall": "miss"},
    ]

    result = calibrate_judge_against_gold(judge_results, gold_evaluations)

    assert result["calibrated_record_count"] == 3
    assert result["agreement_rate"] == 2 / 3
    assert result["gwet_ac1"] == 0.3333


def test_build_layer_2_judge_summary_counts_verdicts_and_calibration():
    judge_results = [
        {"gold_id": "gold-1", "verdict": "accept", "confidence": 0.9},
        {"gold_id": "gold-2", "verdict": "uncertain", "confidence": 0.4},
        {"gold_id": "gold-3", "verdict": "reject", "confidence": 0.8},
    ]
    gold_evaluations = [
        {"gold_id": "gold-1", "overall": "match"},
        {"gold_id": "gold-2", "overall": "partial_match"},
        {"gold_id": "gold-3", "overall": "miss"},
    ]

    summary = build_layer_2_judge_summary(judge_results, gold_evaluations)

    assert summary["evaluated_rule_count"] == 3
    assert summary["accept_rate"] == 1 / 3
    assert summary["uncertain_rate"] == 1 / 3
    assert summary["reject_rate"] == 1 / 3
    assert summary["avg_confidence"] == 0.7
    assert summary["calibration"]["agreement_rate"] == 2 / 3
