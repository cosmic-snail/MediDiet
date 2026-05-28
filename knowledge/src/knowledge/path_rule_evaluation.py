from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PathRule:
    """A deterministic rule extracted from a decision path.

    Conditions are ordered path nodes. The action is the leaf recommendation.
    This sits beside the existing nutrition rule schema instead of replacing it.
    """

    rule_id: str
    disease: str
    conditions: list[str]
    action: str
    answer: str
    answer_text: str


@dataclass(frozen=True)
class PathRulePrediction:
    selected_rule_id: str
    selected_answer: str
    selected_answer_text: str
    matched_path: list[str]


def path_rule_from_medguide_row(rule_id: str, row: dict[str, Any]) -> PathRule:
    path = [str(item) for item in row.get("path", []) if str(item).strip()]
    if len(path) < 2:
        raise ValueError("MedGUIDE row path must contain at least one condition and one action")
    return PathRule(
        rule_id=rule_id,
        disease=str(row.get("disease", "")),
        conditions=path[:-1],
        action=path[-1],
        answer=str(row.get("answer", "")),
        answer_text=str(row.get("answer_text", path[-1])),
    )


def match_path_rules(
    facts: list[str],
    options: list[str],
    candidate_rules: list[PathRule],
) -> PathRulePrediction:
    if not candidate_rules:
        return PathRulePrediction("", "", "", [])

    best_rule = max(
        candidate_rules,
        key=lambda rule: (_path_recall(rule.conditions, facts), len(rule.conditions)),
    )
    selected_answer = _option_letter_for_text(best_rule.answer_text or best_rule.action, options)
    return PathRulePrediction(
        selected_rule_id=best_rule.rule_id,
        selected_answer=selected_answer,
        selected_answer_text=best_rule.answer_text or best_rule.action,
        matched_path=[fact for fact in facts if _contains_equivalent_node(best_rule.conditions, fact)],
    )


def evaluate_path_rule_prediction(
    gold_rule: PathRule,
    prediction: PathRulePrediction,
) -> dict[str, Any]:
    gold_nodes = gold_rule.conditions
    predicted_nodes = prediction.matched_path
    matched_gold = [
        node for node in gold_nodes if _contains_equivalent_node(predicted_nodes, node)
    ]
    unsupported = [
        node for node in predicted_nodes if not _contains_equivalent_node(gold_nodes, node)
    ]
    missing = [
        node for node in gold_nodes if not _contains_equivalent_node(predicted_nodes, node)
    ]
    precision = len(matched_gold) / len(predicted_nodes) if predicted_nodes else 0.0
    recall = len(matched_gold) / len(gold_nodes) if gold_nodes else 0.0
    return {
        "gold_rule_id": gold_rule.rule_id,
        "selected_rule_id": prediction.selected_rule_id,
        "answer_correct": _answer_matches(gold_rule, prediction),
        "path_node_precision": precision,
        "path_node_recall": recall,
        "path_order_match": _is_ordered_subsequence(
            [node for node in predicted_nodes if _contains_equivalent_node(gold_nodes, node)],
            gold_nodes,
        ),
        "missing_path_nodes": missing,
        "unsupported_path_nodes": unsupported,
    }


def evaluate_medguide_rows(
    rows: list[dict[str, Any]],
    facts_by_sample_id: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    rules_by_id = {
        _sample_id(item): path_rule_from_medguide_row(_sample_id(item), item["row"])
        for item in rows
    }
    facts_by_sample_id = facts_by_sample_id or {}
    evaluations: list[dict[str, Any]] = []
    for item in rows:
        sample_id = _sample_id(item)
        row = item["row"]
        gold_rule = rules_by_id[sample_id]
        candidate_rules = [
            rule for rule in rules_by_id.values() if rule.disease == gold_rule.disease
        ]
        facts = facts_by_sample_id.get(sample_id, gold_rule.conditions)
        prediction = match_path_rules(
            facts=facts,
            options=[str(option) for option in row.get("options", [])],
            candidate_rules=candidate_rules,
        )
        evaluation = evaluate_path_rule_prediction(gold_rule, prediction)
        evaluations.append(
            {
                **evaluation,
                "sample_id": sample_id,
                "disease": gold_rule.disease,
                "gold_answer": gold_rule.answer,
                "gold_answer_text": gold_rule.answer_text,
                "selected_answer": prediction.selected_answer,
                "selected_answer_text": prediction.selected_answer_text,
            }
        )
    row_count = len(evaluations)
    return {
        "row_count": row_count,
        "answer_accuracy": _mean(1.0 if item["answer_correct"] else 0.0 for item in evaluations),
        "average_path_node_precision": _mean(item["path_node_precision"] for item in evaluations),
        "average_path_node_recall": _mean(item["path_node_recall"] for item in evaluations),
        "path_order_match_rate": _mean(1.0 if item["path_order_match"] else 0.0 for item in evaluations),
        "rows": evaluations,
    }


def _sample_id(item: dict[str, Any]) -> str:
    return f"medguide-{item['row_idx']}"


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _path_recall(gold_nodes: list[str], predicted_nodes: list[str]) -> float:
    if not gold_nodes:
        return 0.0
    matched = sum(1 for node in gold_nodes if _contains_equivalent_node(predicted_nodes, node))
    return matched / len(gold_nodes)


def _answer_matches(gold_rule: PathRule, prediction: PathRulePrediction) -> bool:
    if prediction.selected_answer and gold_rule.answer:
        return prediction.selected_answer.strip().upper() == gold_rule.answer.strip().upper()
    return _normalize_label(prediction.selected_answer_text) == _normalize_label(gold_rule.answer_text)


def _contains_equivalent_node(nodes: list[str], target: str) -> bool:
    normalized_target = _normalize_label(target)
    return any(_normalize_label(node) == normalized_target for node in nodes)


def _is_ordered_subsequence(predicted_nodes: list[str], gold_nodes: list[str]) -> bool:
    if not predicted_nodes:
        return False
    cursor = 0
    for predicted in predicted_nodes:
        found = False
        while cursor < len(gold_nodes):
            if _normalize_label(predicted) == _normalize_label(gold_nodes[cursor]):
                found = True
                cursor += 1
                break
            cursor += 1
        if not found:
            return False
    return True


def _option_letter_for_text(answer_text: str, options: list[str]) -> str:
    normalized_answer = _normalize_label(answer_text)
    for index, option in enumerate(options):
        if _normalize_label(option) == normalized_answer:
            return chr(ord("A") + index)
    return ""


_FOOTNOTE_TRANSLATION = str.maketrans({
    "ᵃ": "",
    "ᵇ": "",
    "ᶜ": "",
    "ᵈ": "",
    "ᵉ": "",
    "ᶠ": "",
    "ᵍ": "",
    "ʰ": "",
    "ᶦ": "",
    "ʲ": "",
    "ᵏ": "",
    "ˡ": "",
    "ᵐ": "",
    "ⁿ": "",
    "ᵒ": "",
    "ᵖ": "",
    "ᵠ": "",
    "ʳ": "",
    "ˢ": "",
    "ᵗ": "",
    "ᵘ": "",
    "ᵛ": "",
    "ʷ": "",
    "ˣ": "",
    "ʸ": "",
    "ᶻ": "",
})


def _normalize_label(value: str) -> str:
    text = value.translate(_FOOTNOTE_TRANSLATION).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())
