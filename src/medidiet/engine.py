from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from medidiet.domain import ConceptCode, IntakeRecord, MealLabel, MenuItem, Outcome, PatientProfile, RiskLevel
from medidiet.explainer import ExplanationBuilder
from medidiet.matcher import MatchRejection, MenuMatcher
from medidiet.nutrition import DailyNutritionCalculator, NextMealTarget
from medidiet.planner import MealPlan, MealPlanGenerator
from medidiet.ports import KnowledgePort
from medidiet.rules import RulePack
from medidiet.safety import SafetyEvent, SafetyGate
from medidiet.trace import RecommendationTrace

# Previous meal for gap compensation: lunch compensates breakfast, dinner compensates lunch
_PREVIOUS_MEAL: dict[MealLabel, MealLabel] = {
    MealLabel.LUNCH: MealLabel.BREAKFAST,
    MealLabel.DINNER: MealLabel.LUNCH,
}


@dataclass(frozen=True)
class RecommendationResult:
    outcome: Outcome
    recommended_items: tuple[MenuItem, ...]
    patient_explanation: str
    clinician_explanation: dict[str, object]
    trace: RecommendationTrace


class RecommendationEngine:
    def __init__(
        self,
        rule_pack: RulePack,
        now: datetime | None = None,
        knowledge: KnowledgePort | None = None,
        recent_ingredients: frozenset[ConceptCode] = frozenset(),
    ):
        self.rule_pack = rule_pack
        self.knowledge = knowledge
        self.recent_ingredients = recent_ingredients
        self.safety_gate = SafetyGate(rule_pack)
        self.calculator = DailyNutritionCalculator(rule_pack, now=now)
        self.planner = MealPlanGenerator(rule_pack)
        self.matcher = MenuMatcher()
        self.explainer = ExplanationBuilder(rule_pack)

    def recommend(
        self,
        patient: PatientProfile,
        intake_records: list[IntakeRecord],
        candidate_menu_items: list[MenuItem],
        meal_label: MealLabel,
    ) -> RecommendationResult:
        if not isinstance(meal_label, MealLabel):
            raise TypeError("meal_label must be a MealLabel")

        safety = self.safety_gate.evaluate(patient, candidate_menu_items, intake_records)
        if safety.requires_human_review:
            explanation = self.explainer.patient_explanation(Outcome.HUMAN_REVIEW_REQUIRED)
            return self._finalize(
                patient=patient,
                meal_label=meal_label,
                outcome=Outcome.HUMAN_REVIEW_REQUIRED,
                risk_level=RiskLevel.HIGH,
                recommended_items=(),
                patient_explanation=explanation,
                safety_events=safety.hard_blocks + safety.uncertainties,
                exclusions={},
                scores={},
                matched_tags=(),
            )

        target = self.calculator.next_meal_target(patient.conditions, intake_records)

        # Nutrient gap compensation: previous meal deficiencies → preference boost
        previous_label = _PREVIOUS_MEAL.get(meal_label)
        if previous_label is not None:
            today = self.calculator.now.astimezone(timezone.utc).date()
            previous_records = [
                r for r in intake_records
                if r.meal_label is previous_label
                and r.occurred_at.astimezone(timezone.utc).date() == today
            ]
            gap_tags = self.calculator.compensation_tags(previous_records)
            if gap_tags:
                merged_tags = frozenset(target.preferred_tags | gap_tags)
                target = NextMealTarget(limits=target.limits, preferred_tags=merged_tags)

        plan = self.planner.generate(target, meal_label)
        match_result = self.matcher.match(plan, candidate_menu_items, patient.preferences, self.recent_ingredients)

        if not match_result.accepted:
            explanation = self.explainer.patient_explanation(Outcome.REFUSED)
            return self._finalize(
                patient=patient,
                meal_label=meal_label,
                outcome=Outcome.REFUSED,
                risk_level=RiskLevel.HIGH,
                recommended_items=(),
                patient_explanation=explanation,
                safety_events=(),
                exclusions=match_result.excluded,
                scores={},
                matched_tags=tuple(plan.required_tags),
            )

        top_score = match_result.accepted[0]
        scores = {scored.item.item_id: scored.score for scored in match_result.accepted}
        explanation = self.explainer.patient_explanation(
            Outcome.RECOMMENDED,
            tags=tuple(plan.required_tags),
            instructions=plan.instructions,
        )
        return self._finalize(
            patient=patient,
            meal_label=meal_label,
            outcome=Outcome.RECOMMENDED,
            risk_level=RiskLevel.LOW,
            recommended_items=(top_score.item,),
            patient_explanation=explanation,
            safety_events=(),
            exclusions=match_result.excluded,
            scores=scores,
            matched_tags=tuple(top_score.matched_required_tags),
        )

    def _finalize(
        self,
        patient: PatientProfile,
        meal_label: MealLabel,
        outcome: Outcome,
        risk_level: RiskLevel,
        recommended_items: tuple[MenuItem, ...],
        patient_explanation: str,
        safety_events: tuple[SafetyEvent, ...],
        exclusions: dict[str, MatchRejection],
        scores: dict[str, float],
        matched_tags: tuple,
    ) -> RecommendationResult:
        # Online knowledge enrichment (silently degrades on failure)
        knowledge_snippets: list[dict[str, object]] | None = None
        if self.knowledge is not None:
            try:
                context = self.knowledge.retrieve_context(patient, meal_label)
                knowledge_snippets = [
                    {
                        "text": s.text,
                        "sourceTitle": s.source_title,
                        "sourceUrl": s.source_url,
                        "chunkId": s.chunk_id,
                        "relevanceScore": s.relevance_score,
                    }
                    for s in context.snippets
                ]
            except Exception:
                pass
        clinician_explanation = self.explainer.clinician_explanation(
            rule_version=self.rule_pack.version,
            safety_events=safety_events,
            exclusions=exclusions,
            scores=scores,
            matched_tags=matched_tags,
            knowledge_snippets=knowledge_snippets,
        )
        trace = RecommendationTrace(
            trace_id=f"trace-{uuid4()}",
            patient_id=patient.patient_id,
            rule_version=self.rule_pack.version,
            outcome=outcome,
            risk_level=risk_level,
            safety_events=safety_events,
            exclusions=exclusions,
            scores=scores,
            patient_explanation=patient_explanation,
            clinician_explanation=clinician_explanation,
        )
        return RecommendationResult(
            outcome=outcome,
            recommended_items=recommended_items,
            patient_explanation=patient_explanation,
            clinician_explanation=clinician_explanation,
            trace=trace,
        )
