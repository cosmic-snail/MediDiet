from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from medidiet.domain import ConceptCode
from medidiet.rules import NutrientLimit


@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    source: str
    source_type: str  # "guideline" | "paper" | "food_db" | "manual"
    content_raw: str
    chunks: list[DocumentChunk]
    metadata: dict[str, str]
    ingested_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.source_type, str) or self.source_type not in (
            "guideline", "paper", "food_db", "manual",
        ):
            raise ValueError(
                f"source_type must be one of: guideline, paper, food_db, manual; "
                f"got {self.source_type!r}"
            )


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be non-negative")


@dataclass
class ExtractedConditionRule:
    candidate_id: str
    source_doc_ids: list[str]
    source_chunk_ids: list[str]
    condition: ConceptCode
    hard_exclusions: set[ConceptCode]
    preferred_tags: set[ConceptCode]
    nutrition_limits: set[NutrientLimit]
    confidence: float
    extraction_method: str  # "llm" | "manual" | "llm+review"
    reviewed_by: str | None
    status: str  # "draft" | "pending_review" | "approved" | "rejected"
    created_at: datetime
    verification_result: VerificationResult | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.extraction_method not in ("llm", "manual", "llm+review"):
            raise ValueError(
                f"extraction_method must be llm, manual, or llm+review; "
                f"got {self.extraction_method!r}"
            )
        if self.status not in ("draft", "pending_review", "approved", "rejected"):
            raise ValueError(
                f"status must be draft, pending_review, approved, or rejected; "
                f"got {self.status!r}"
            )


@dataclass
class VerificationResult:
    verdict: str  # "pass" | "revision_needed" | "rejected"
    confidence: float
    consistency_score: float  # 0-1
    logic_score: float  # 0-1
    completeness_score: float  # 0-1
    issues: list[VerificationIssue] = field(default_factory=list)
    missing_items: list[str] | None = None
    revised_rule: ExtractedConditionRule | None = None
    evidence_quotes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in ("pass", "revision_needed", "rejected"):
            raise ValueError(
                f"verdict must be pass, revision_needed, or rejected; "
                f"got {self.verdict!r}"
            )
        for score_name in ("consistency_score", "logic_score", "completeness_score"):
            score = getattr(self, score_name)
            if not 0 <= score <= 1:
                raise ValueError(f"{score_name} must be between 0 and 1")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class VerificationIssue:
    severity: str  # "critical" | "warning" | "info"
    dimension: str  # "consistency" | "logic" | "completeness"
    description: str
    related_field: str | None = None
    suggested_fix: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("critical", "warning", "info"):
            raise ValueError(
                f"severity must be critical, warning, or info; "
                f"got {self.severity!r}"
            )
        if self.dimension not in ("consistency", "logic", "completeness"):
            raise ValueError(
                f"dimension must be consistency, logic, or completeness; "
                f"got {self.dimension!r}"
            )


@dataclass
class SuggestedConcept:
    suggest_id: str
    candidate_rule_id: str
    suggested_code: ConceptCode
    definition: str
    source_chunk_ids: list[str]
    display_name: str
