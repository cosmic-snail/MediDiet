from __future__ import annotations

from knowledge.evaluation_taxonomy import (
    AuditStatus,
    EvaluationTrack,
    EvidenceLevel,
    RecommendedAction,
    clean_headline_filter,
    normalize_audit_status,
    normalize_evaluation_track,
    normalize_evidence_level,
    normalize_recommended_action,
)


def test_normalizers_accept_known_values():
    assert normalize_evidence_level("source_card_direct") is EvidenceLevel.SOURCE_CARD_DIRECT
    assert normalize_audit_status("keep") is AuditStatus.KEEP
    assert normalize_recommended_action("replace_umbrella_concept") is RecommendedAction.REPLACE_UMBRELLA_CONCEPT
    assert normalize_evaluation_track("concept_discovery") is EvaluationTrack.CONCEPT_DISCOVERY


def test_clean_headline_filter_keeps_direct_and_trusted_negative_rows():
    assert clean_headline_filter(
        evidence_level=EvidenceLevel.SOURCE_CARD_DIRECT,
        audit_status=AuditStatus.KEEP,
    )
    assert clean_headline_filter(
        evidence_level=EvidenceLevel.CONTEXTUAL_NEGATIVE,
        audit_status=AuditStatus.KEEP,
    )
    assert not clean_headline_filter(
        evidence_level=EvidenceLevel.DERIVED_CONVERSION,
        audit_status=AuditStatus.REVISE_GOLD,
    )
    assert not clean_headline_filter(
        evidence_level=EvidenceLevel.SCHEMA_GAP,
        audit_status=AuditStatus.REVISE_SCHEMA_OR_GOLD,
    )


def test_normalizers_reject_unknown_values():
    try:
        normalize_evaluation_track("one_big_f1")
    except ValueError as exc:
        assert "unknown evaluation track" in str(exc)
    else:
        raise AssertionError("unknown evaluation track should fail")
