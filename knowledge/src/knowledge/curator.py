"""Manual curation API — human-in-the-loop rule review and publishing."""

from datetime import datetime, timezone

from medidiet.domain import CodeKind, ConceptCode
from medidiet.rules import NutrientLimit
from knowledge.schema import ExtractedConditionRule, VerificationIssue
from knowledge.store import RuleStore


class KnowledgeCurator:
    """Manual curation interface for health condition dietary rules.

    Provides human-in-the-loop operations: create rules manually, review
    LLM-extracted candidates, reject with reasons, and publish approved
    rules as versioned RulePacks (via RuleStore).
    """

    def __init__(self, store: RuleStore):
        self._store = store

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_rule(
        self,
        candidate_id: str,
        condition: ConceptCode,
        hard_exclusions: set[ConceptCode] | None = None,
        preferred_tags: set[ConceptCode] | None = None,
        nutrition_limits: set[NutrientLimit] | None = None,
        source_doc_ids: list[str] | None = None,
        source_chunk_ids: list[str] | None = None,
        confidence: float = 1.0,
        reviewer: str | None = None,
    ) -> ExtractedConditionRule:
        """Manually create a draft rule candidate."""
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        if condition.kind != CodeKind.CONDITION:
            raise ValueError(f"condition must be CodeKind.CONDITION, got {condition.kind}")

        rule = ExtractedConditionRule(
            candidate_id=candidate_id,
            source_doc_ids=source_doc_ids or [],
            source_chunk_ids=source_chunk_ids or [],
            condition=condition,
            hard_exclusions=hard_exclusions or set(),
            preferred_tags=preferred_tags or set(),
            nutrition_limits=nutrition_limits or set(),
            confidence=confidence,
            extraction_method="manual",
            reviewed_by=reviewer,
            status="draft",
            created_at=datetime.now(timezone.utc),
            verification_result=None,
        )
        self._store.create(rule)
        return rule

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------

    def review_rule(
        self, candidate_id: str, decision: str, reviewer: str
    ) -> ExtractedConditionRule:
        """Approve or reject a candidate rule.

        Args:
            candidate_id: The rule to review.
            decision: "approved" or "rejected".
            reviewer: Name or ID of the human reviewer.

        Returns:
            The updated rule.
        """
        if decision not in ("approved", "rejected"):
            raise ValueError(
                f"decision must be 'approved' or 'rejected', got '{decision}'"
            )

        rule = self._store.get(candidate_id)
        if rule is None:
            raise ValueError(f"rule not found: {candidate_id}")

        rule.reviewed_by = reviewer
        rule.status = decision

        # If previously LLM-extracted, mark as LLM+review
        if rule.extraction_method == "llm":
            rule.extraction_method = "llm+review"

        self._store.update(rule)
        return rule

    def reject_rule(self, candidate_id: str, reason: str) -> ExtractedConditionRule:
        """Reject a rule with a specific reason.

        The reason is recorded in the rule's verification_result if one
        exists, otherwise it's attached to the rule's status only.
        """
        rule = self._store.get(candidate_id)
        if rule is None:
            raise ValueError(f"rule not found: {candidate_id}")

        rule.reviewed_by = "system"
        rule.status = "rejected"

        issue = VerificationIssue(
            severity="critical",
            dimension="completeness",
            description=reason,
            related_field=None,
            suggested_fix=None,
        )

        if rule.verification_result is not None:
            rule.verification_result.issues.append(issue)
        else:
            from knowledge.schema import VerificationResult

            rule.verification_result = VerificationResult(
                verdict="rejected",
                confidence=0.0,
                consistency_score=0.0,
                logic_score=0.0,
                completeness_score=0.0,
                issues=[issue],
                missing_items=None,
                evidence_quotes={},
                revised_rule=None,
            )

        self._store.update(rule)
        return rule

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, version: str, notes: str) -> str:
        """Publish all approved rules as a versioned RulePack.

        Returns the file path to the published version.
        """
        return self._store.publish_version(version, notes)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_candidate(self, candidate_id: str) -> ExtractedConditionRule | None:
        """Get a candidate rule by ID."""
        return self._store.get(candidate_id)

    def list_candidates(
        self, status: str | None = None
    ) -> list[ExtractedConditionRule]:
        """List all candidates, optionally filtered by status."""
        if status is not None:
            return self._store.list_by_status(status)
        return self._store.list_all()

    def list_versions(self) -> list[str]:
        """List published version names."""
        return self._store.list_versions()

    def load_version(self, version: str) -> list[ExtractedConditionRule]:
        """Load rules from a published version."""
        return self._store.load_version(version)
