from __future__ import annotations

from medidiet.domain import CodeKind, ConceptCode, Outcome
from medidiet.matcher import MatchRejection
from medidiet.planner import MealInstruction
from medidiet.rules import RulePack
from medidiet.safety import SafetyEvent


class ExplanationBuilder:
    def __init__(self, rule_pack: RulePack):
        self.rule_pack = rule_pack

    def patient_explanation(
        self,
        outcome: Outcome,
        tags: tuple[ConceptCode, ...] = (),
        instructions: tuple[MealInstruction, ...] = (),
    ) -> str:
        if outcome is Outcome.HUMAN_REVIEW_REQUIRED:
            return "当前信息需要营养师确认后再推荐餐食。"
        if outcome is Outcome.REFUSED:
            return "当前候选餐食不满足安全和营养要求，暂不建议自动推荐。"

        parts = ["这份餐食符合当前营养规则"]
        tag_text = [self._tag_label(tag) for tag in tags if tag.kind is CodeKind.NUTRITION_TAG]
        if tag_text:
            parts.append("重点考虑" + "、".join(tag_text))
        instruction_text = [self._instruction_label(instruction) for instruction in instructions]
        if instruction_text:
            parts.append("建议" + "、".join(instruction_text))
        return "，".join(parts) + "。"

    def clinician_explanation(
        self,
        rule_version: str,
        safety_events: tuple[SafetyEvent, ...],
        exclusions: dict[str, MatchRejection],
        scores: dict[str, float],
        matched_tags: tuple[ConceptCode, ...],
    ) -> dict[str, object]:
        return {
            "ruleVersion": rule_version,
            "safetyEvents": [_safety_event_payload(event) for event in safety_events],
            "exclusions": {item_id: _match_rejection_payload(rejection) for item_id, rejection in exclusions.items()},
            "scores": scores,
            "matchedTags": [_concept_payload(tag) for tag in matched_tags],
            "llmBoundary": "Explanation is generated only from rule hits, nutrition facts, and scored candidates.",
        }

    def _tag_label(self, tag: ConceptCode) -> str:
        labels = {
            "low_sodium": "低钠",
            "controlled_carbs": "控主食",
            "vegetable_rich": "蔬菜丰富",
            "high_fiber": "高纤维",
            "lean_protein": "优质蛋白",
            "balanced": "均衡搭配",
        }
        return labels.get(tag.value, tag.value)

    def _instruction_label(self, instruction: MealInstruction) -> str:
        labels = {
            MealInstruction.AVOID_EXTRA_SAUCE: "少放酱汁",
            MealInstruction.CONTROL_ADDED_SUGAR: "控制加糖饮品和甜口配料",
            MealInstruction.AVOID_DEEP_FRIED: "避免油炸做法",
            MealInstruction.CONTROL_PORTION_SIZE: "控制份量",
        }
        return labels[instruction]


def _safety_event_payload(event: SafetyEvent) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": event.code.value,
        "codeName": event.code.name,
        "severity": event.severity.name.lower(),
        "patientId": event.patient_id,
    }
    if event.entity_id is not None:
        payload["entityId"] = event.entity_id
    if event.concept is not None:
        payload["concept"] = _concept_payload(event.concept)
    if event.metric is not None:
        payload["metric"] = event.metric.value
    if event.scope is not None:
        payload["scope"] = event.scope.value
    if event.measured_value is not None:
        payload["measuredValue"] = event.measured_value
    if event.limit_value is not None:
        payload["limitValue"] = event.limit_value
    return payload


def _match_rejection_payload(rejection: MatchRejection) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": rejection.code.value,
        "codeName": rejection.code.name,
        "itemId": rejection.item_id,
    }
    if rejection.concept is not None:
        payload["concept"] = _concept_payload(rejection.concept)
    if rejection.metric is not None:
        payload["metric"] = rejection.metric.value
    if rejection.scope is not None:
        payload["scope"] = rejection.scope.value
    if rejection.measured_value is not None:
        payload["measuredValue"] = rejection.measured_value
    if rejection.limit_value is not None:
        payload["limitValue"] = rejection.limit_value
    return payload


def _concept_payload(concept: ConceptCode) -> dict[str, str]:
    return {"kind": concept.kind.value, "value": concept.value}
