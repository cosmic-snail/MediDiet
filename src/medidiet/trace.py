from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from medidiet.domain import Outcome, RiskLevel
from medidiet.explainer import _match_rejection_payload, _safety_event_payload
from medidiet.matcher import MatchRejection
from medidiet.safety import SafetyEvent


@dataclass(frozen=True)
class RecommendationTrace:
    trace_id: str
    patient_id: str
    rule_version: str
    outcome: Outcome
    risk_level: RiskLevel
    safety_events: tuple[SafetyEvent, ...] = field(default_factory=tuple)
    exclusions: dict[str, MatchRejection] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    patient_explanation: str = ""
    clinician_explanation: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, Outcome):
            raise TypeError("outcome must be an Outcome")
        if not isinstance(self.risk_level, RiskLevel):
            raise TypeError("risk_level must be a RiskLevel")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    def to_dict(self) -> dict[str, object]:
        return {
            "traceId": self.trace_id,
            "patientId": self.patient_id,
            "ruleVersion": self.rule_version,
            "outcome": self.outcome.value,
            "riskLevel": self.risk_level.value,
            "createdAt": self.created_at.isoformat(),
            "safetyEvents": [_safety_event_payload(event) for event in self.safety_events],
            "exclusions": {item_id: _match_rejection_payload(rejection) for item_id, rejection in self.exclusions.items()},
            "scores": self.scores,
            "patientExplanation": self.patient_explanation,
            "clinicianExplanation": self.clinician_explanation,
        }
