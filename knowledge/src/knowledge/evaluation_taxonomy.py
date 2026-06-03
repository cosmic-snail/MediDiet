from __future__ import annotations

from enum import Enum


class EvidenceLevel(str, Enum):
    SOURCE_CARD_DIRECT = "source_card_direct"
    ORIGINAL_SOURCE_DIRECT = "original_source_direct"
    DERIVED_CONVERSION = "derived_conversion"
    SCHEMA_GAP = "schema_gap"
    CONTEXTUAL_NEGATIVE = "contextual_negative"


class AuditStatus(str, Enum):
    KEEP = "keep"
    BORDERLINE = "borderline"
    REVISE_GOLD = "revise_gold"
    REVISE_SCHEMA_OR_GOLD = "revise_schema_or_gold"
    REVIEW_NEGATIVE = "review_negative"


class RecommendedAction(str, Enum):
    KEEP = "keep"
    REVIEW_CONDITION_SCOPE = "review_condition_scope"
    REMOVE_NUMERIC_LIMIT = "remove_numeric_limit"
    ADD_PERCENT_ENERGY_SCHEMA = "add_percent_energy_schema"
    REPLACE_UMBRELLA_CONCEPT = "replace_umbrella_concept"
    MARK_CONTEXTUAL = "mark_contextual"
    FIX_NEGATIVE_FAILURE_LABEL = "fix_negative_failure_label"


class EvaluationTrack(str, Enum):
    CLEAN_EXTRACTION = "clean_extraction"
    CONTEXTUAL_HANDLING = "contextual_handling"
    CONVERSION = "conversion"
    CONCEPT_DISCOVERY = "concept_discovery"
    MIXED_LEGACY = "mixed_legacy"


CLEAN_HEADLINE_EVIDENCE_LEVELS = {
    EvidenceLevel.SOURCE_CARD_DIRECT,
    EvidenceLevel.ORIGINAL_SOURCE_DIRECT,
    EvidenceLevel.CONTEXTUAL_NEGATIVE,
}
CLEAN_HEADLINE_AUDIT_STATUSES = {AuditStatus.KEEP}


def normalize_evidence_level(value: EvidenceLevel | str) -> EvidenceLevel:
    try:
        return value if isinstance(value, EvidenceLevel) else EvidenceLevel(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown evidence level: {value}") from exc


def normalize_audit_status(value: AuditStatus | str) -> AuditStatus:
    try:
        return value if isinstance(value, AuditStatus) else AuditStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown audit status: {value}") from exc


def normalize_recommended_action(value: RecommendedAction | str) -> RecommendedAction:
    try:
        return value if isinstance(value, RecommendedAction) else RecommendedAction(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown recommended action: {value}") from exc


def normalize_evaluation_track(value: EvaluationTrack | str) -> EvaluationTrack:
    try:
        return value if isinstance(value, EvaluationTrack) else EvaluationTrack(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown evaluation track: {value}") from exc


def clean_headline_filter(*, evidence_level: EvidenceLevel | str, audit_status: AuditStatus | str) -> bool:
    return (
        normalize_evidence_level(evidence_level) in CLEAN_HEADLINE_EVIDENCE_LEVELS
        and normalize_audit_status(audit_status) in CLEAN_HEADLINE_AUDIT_STATUSES
    )
