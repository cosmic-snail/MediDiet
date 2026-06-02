"""LLM rule extraction pipeline — two-stage extraction with cross-validation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from medidiet.domain import CodeKind, ConceptCode, ConceptRegistry
from medidiet.llm import LLMProviderPort, LLMRequest, LLMTask, LLMResponse
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.schema import (
    ExtractedConditionRule,
    ExtractionResult,
    SuggestedConcept,
    VerificationIssue,
    VerificationResult,
)
from knowledge.documents import DocumentChunk


class RuleExtractionError(Exception):
    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """\
You are a clinical nutrition knowledge extraction specialist. Your task is to \
read document fragments from medical dietary guidelines and extract structured \
dietary constraint rules for patients with specific health conditions.

Output a JSON object with two fields:

	{
	  "rules": [
	    {
	      "condition": {"kind": "condition", "value": "<snake_case>"},
	      "hard_exclusions": [{"kind": "contraindication", "value": "<snake_case>"}, ...],
	      "preferred_tags": [{"kind": "nutrition_tag", "value": "<snake_case>"}, ...],
	      "nutrition_limits": [
	        {"metric": "<value>", "scope": "<value>", "max_value": <float>, "window_hours": <int|null>}
	      ],
	      "confidence": <float 0-1>,
	      "evidence_quotes": {"<field_name>": "<exact source text>"}
	    }
	  ],
	  "suggested_concepts": [
	    {"kind": "<CodeKind>", "value": "<snake_case>", "definition": "<description>", "display_name": "<Human Name>"}
	  ]
	}

	Rule object fields:
- condition: {"kind": "condition", "value": "<snake_case>"} — the medical condition
- hard_exclusions: [{"kind": "contraindication", "value": "<snake_case>"}, ...]
- preferred_tags: [{"kind": "nutrition_tag", "value": "<snake_case>"}, ...]
- nutrition_limits: [{"metric": "<value>", "scope": "<value>", "max_value": <float>, "window_hours": <int|null>}, ...]
- confidence: <float 0-1> — your confidence in this extraction
- evidence_quotes: {"<field_name>": "<exact source text>"} — must quote the source

Existing concept codes (use these when applicable):
__CONCEPT_REGISTRY__

Important rules:
- ONLY use condition codes listed under CodeKind.CONDITION above
- For hard_exclusions, ONLY use CodeKind.CONTRAINDICATION codes
- For preferred_tags, ONLY use CodeKind.NUTRITION_TAG codes
- For nutrition_limits.metric, use one of: energy_kcal, carbs_g, fat_g, sodium_mg, sugar_g
- For nutrition_limits.scope, use one of: per_meal, daily, rolling_window
- If you need a concept that does not exist in the registry, add it to a separate \
"suggested_concepts" array in the output (NOT in the rules array)
- If a source gives a numeric threshold for supported metrics, extract it in nutrition_limits; do not replace it with only a preferred_tag.
- Treat explicit daily sodium limit statements as nutrition_limits entries. Example: "2000 mg sodium per day" -> {"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": null}.
- Treat an explicit "5 g salt per day" statement as equivalent to about "2000 mg sodium per day" when the source card states that conversion.
- If a numeric threshold is stated as salt rather than sodium, convert only when the source explicitly provides the sodium/salt relationship or the gold metric uses sodium_mg in the dataset context.
- If the source states a percentage threshold but no supported gram metric can be computed from the text, add the concept to suggested_concepts and explain the percentage in evidence_quotes.
- Every claim MUST have an evidence_quote from the provided fragments
- If a fragment does not contain extractable dietary rules, do not fabricate
- Confidence should reflect how explicit and clear the source text is
- Return empty rules array if no rules can be extracted
"""

_EXTRACTION_USER_PROMPT_TEMPLATE = """\
Source document fragments:

{fragments_text}

Extract structured dietary constraint rules from these fragments. \
For each rule found, include exact evidence quotes from the source text.
"""

_VERIFICATION_SYSTEM_PROMPT = """\
You are a clinical nutrition quality assurance reviewer. You cross-validate \
extracted dietary rules against source document fragments to ensure accuracy, \
consistency, and completeness.

Review the extracted rule against the provided source fragments across three dimensions:

1. **Consistency**: Does every claim have a matching source quote? \
Are there contradictions between the rule and the sources?
2. **Logic**: Are the nutrient limits clinically reasonable? \
Do hard_exclusions contradict preferred_tags?
3. **Completeness**: Are there important dietary constraints in the sources \
that the extracted rule missed?

Output a JSON verification object:
{
  "verdict": "pass" | "revision_needed" | "rejected",
  "confidence": <float 0-1>,
  "consistency_score": <float 0-1>,
  "logic_score": <float 0-1>,
  "completeness_score": <float 0-1>,
  "issues": [
    {
      "severity": "critical" | "warning" | "info",
      "dimension": "consistency" | "logic" | "completeness",
      "description": "<detailed issue description>",
      "related_field": "<field name or null>",
      "suggested_fix": "<concrete fix or null>"
    }
  ],
  "missing_items": ["<item1>", ...] or null,
  "evidence_quotes": {"<field_name>": "<source text>"}
}

Verdict criteria:
- "pass": all scores >= 0.7, no critical issues
- "revision_needed": at least one score < 0.7 but the rule is salvageable \
(issues can be addressed with specific fixes)
- "rejected": critical issues present, or consistency_score < 0.3 \
(rule contradicts sources), or the rule is fundamentally unfounded
"""

_VERIFICATION_USER_PROMPT_TEMPLATE = """\
Extracted rule:
{rule_json}

Source document fragments:
{fragments_text}

Cross-validate this extracted rule against the source fragments. \
Check consistency, logic, and completeness. Provide scores and specific issues.
"""


# ---------------------------------------------------------------------------
# Prompt builders (no LLM calls)
# ---------------------------------------------------------------------------

def _serialize_concept_registry_for_prompt(registry: ConceptRegistry) -> str:
    lines: list[str] = []
    by_kind: dict[CodeKind, list[str]] = {}
    for (kind, value) in sorted(registry._definitions):
        by_kind.setdefault(kind, []).append(value)
    for kind in sorted(by_kind, key=lambda k: k.value):
        values = sorted(by_kind[kind])
        lines.append(f"CodeKind.{kind.name} = {kind.value}: {', '.join(values)}")
    return "\n".join(lines)


def _build_extraction_user_prompt(chunks: list[DocumentChunk]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        parts.append(f"[chunk_id: {chunk.chunk_id}]\n{chunk.text}")
    fragments_text = "\n\n---\n\n".join(parts)
    return _EXTRACTION_USER_PROMPT_TEMPLATE.format(fragments_text=fragments_text)


def _build_verification_user_prompt(
    rule: ExtractedConditionRule, chunks: list[DocumentChunk]
) -> str:
    rule_dict = {
        "condition": {"kind": rule.condition.kind.value, "value": rule.condition.value},
        "hard_exclusions": [
            {"kind": c.kind.value, "value": c.value} for c in sorted(rule.hard_exclusions, key=lambda c: c.value)
        ],
        "preferred_tags": [
            {"kind": c.kind.value, "value": c.value} for c in sorted(rule.preferred_tags, key=lambda c: c.value)
        ],
        "nutrition_limits": [
            {
                "metric": nl.metric.value,
                "scope": nl.scope.value,
                "max_value": nl.max_value,
                "window_hours": nl.window_hours,
            }
            for nl in sorted(rule.nutrition_limits, key=lambda nl: nl.metric.value)
        ],
        "confidence": rule.confidence,
    }
    rule_json = json.dumps(rule_dict, ensure_ascii=False, indent=2)
    parts: list[str] = []
    for chunk in chunks:
        parts.append(f"[chunk_id: {chunk.chunk_id}]\n{chunk.text}")
    fragments_text = "\n\n---\n\n".join(parts)
    return _VERIFICATION_USER_PROMPT_TEMPLATE.format(
        rule_json=rule_json, fragments_text=fragments_text
    )


# ---------------------------------------------------------------------------
# Response parsers (no LLM calls)
# ---------------------------------------------------------------------------

def _parse_concept_code(
    kind_str: str, value_str: str, registry: ConceptRegistry
) -> ConceptCode | None:
    """Try to validate a concept code against the registry. Returns None if unknown."""
    try:
        kind = CodeKind(kind_str)
    except ValueError:
        return None
    try:
        code = ConceptCode(kind, value_str)
    except ValueError:
        code = None
    if code is not None and (code.kind, code.value) in registry._definitions:
        return code
    try:
        return registry.resolve_alias(kind, value_str)
    except ValueError:
        return None


def _parse_extraction_response(
    json_str: str,
    registry: ConceptRegistry,
    candidate_id_prefix: str,
    source_chunk_ids: list[str],
    source_doc_ids: list[str],
) -> tuple[list[ExtractedConditionRule], list[SuggestedConcept]]:
    """Parse LLM extraction JSON into rules and suggested concepts."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise RuleExtractionError(f"Invalid JSON: {e}", raw_response=json_str) from e

    rules: list[ExtractedConditionRule] = []
    suggestions: list[SuggestedConcept] = []

    # Defend against bare array (LLM may ignore the object-wrapper instruction)
    if isinstance(data, list):
        data = {"rules": data, "suggested_concepts": []}
    elif not isinstance(data, dict):
        raise RuleExtractionError(
            f"Expected JSON object at top level, got {type(data).__name__}",
            raw_response=json_str,
        )

    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise RuleExtractionError(
            f"Expected 'rules' array, got {type(raw_rules).__name__}",
            raw_response=json_str,
        )

    now = datetime.now(timezone.utc)

    for i, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            continue

        candidate_id = f"{candidate_id_prefix}-{uuid.uuid4().hex[:8]}"

        # Parse condition (required)
        cond_raw = raw.get("condition")
        if not isinstance(cond_raw, dict):
            continue
        cond_code = _parse_concept_code(
            cond_raw.get("kind", ""), cond_raw.get("value", ""), registry
        )
        if cond_code is None or cond_code.kind != CodeKind.CONDITION:
            # Unknown condition → skip (can't create rule without known condition)
            continue

        # Parse hard_exclusions
        hard_exclusions: set[ConceptCode] = set()
        for ex in raw.get("hard_exclusions", []) or []:
            if isinstance(ex, dict):
                code = _parse_concept_code(
                    ex.get("kind", ""), ex.get("value", ""), registry
                )
                if code is not None:
                    hard_exclusions.add(code)

        # Parse preferred_tags
        preferred_tags: set[ConceptCode] = set()
        for tag in raw.get("preferred_tags", []) or []:
            if isinstance(tag, dict):
                code = _parse_concept_code(
                    tag.get("kind", ""), tag.get("value", ""), registry
                )
                if code is not None:
                    preferred_tags.add(code)

        # Parse nutrition_limits
        nutrition_limits: set[NutrientLimit] = set()
        for nl_raw in raw.get("nutrition_limits", []) or []:
            if not isinstance(nl_raw, dict):
                continue
            try:
                metric = NutrientMetric(nl_raw.get("metric", ""))
                scope = LimitScope(nl_raw.get("scope", ""))
                max_value = float(nl_raw.get("max_value", 0))
                if max_value <= 0:
                    continue
                window_hours_raw = nl_raw.get("window_hours")
                window_hours: int | None = None
                if window_hours_raw is not None:
                    window_hours = int(window_hours_raw)
                if scope != LimitScope.ROLLING_WINDOW:
                    window_hours = None
                nutrition_limits.add(
                    NutrientLimit(
                        metric=metric,
                        scope=scope,
                        max_value=max_value,
                        window_hours=window_hours,
                    )
                )
            except (ValueError, TypeError):
                continue

        # Parse confidence
        confidence = float(raw.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        # Parse evidence_quotes
        evidence_quotes: dict[str, str] = {}
        eq = raw.get("evidence_quotes")
        if isinstance(eq, dict):
            for k, v in eq.items():
                if isinstance(v, str):
                    evidence_quotes[k] = v

        rule = ExtractedConditionRule(
            candidate_id=candidate_id,
            source_doc_ids=list(source_doc_ids),
            source_chunk_ids=list(source_chunk_ids),
            condition=cond_code,
            hard_exclusions=hard_exclusions,
            preferred_tags=preferred_tags,
            nutrition_limits=nutrition_limits,
            confidence=confidence,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=now,
            verification_result=None,
        )
        rules.append(rule)

        # Parse evidence_quotes into a basic VerificationResult for traceability
        if evidence_quotes:
            rule.verification_result = VerificationResult(
                verdict="pass",
                confidence=confidence,
                consistency_score=1.0,
                logic_score=1.0,
                completeness_score=1.0,
                issues=[],
                missing_items=None,
                evidence_quotes=evidence_quotes,
                revised_rule=None,
            )

    # Parse suggested_concepts
    for sc in data.get("suggested_concepts", []) or []:
        if not isinstance(sc, dict):
            continue
        try:
            kind = CodeKind(sc.get("kind", ""))
            value = str(sc.get("value", ""))
            definition = str(sc.get("definition", ""))
            display_name = str(sc.get("display_name", value))
            suggest_id = f"suggest-{uuid.uuid4().hex[:8]}"
            suggestions.append(
                SuggestedConcept(
                    suggest_id=suggest_id,
                    candidate_rule_id=rules[0].candidate_id if rules else "",
                    suggested_code=ConceptCode(kind, value),
                    definition=definition,
                    source_chunk_ids=list(source_chunk_ids),
                    display_name=display_name,
                )
            )
        except (ValueError, TypeError):
            continue

    return rules, suggestions


_VALID_VERDICTS = {"pass", "revision_needed", "rejected"}
_VALID_SEVERITIES = {"critical", "warning", "info"}
_VALID_DIMENSIONS = {"consistency", "logic", "completeness"}


def _parse_verification_response(json_str: str) -> VerificationResult:
    """Parse LLM verification JSON into a VerificationResult."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise RuleExtractionError(f"Invalid JSON: {e}", raw_response=json_str) from e
    if not isinstance(data, dict):
        raise RuleExtractionError(
            f"Expected JSON object, got {type(data).__name__}", raw_response=json_str
        )

    verdict = str(data.get("verdict", ""))
    if verdict not in _VALID_VERDICTS:
        verdict = "revision_needed"

    def _clamp_score(val: object) -> float:
        try:
            return max(0.0, min(1.0, float(str(val))))
        except (ValueError, TypeError):
            return 0.5

    confidence = _clamp_score(data.get("confidence", 0.5))
    consistency_score = _clamp_score(data.get("consistency_score", 0.5))
    logic_score = _clamp_score(data.get("logic_score", 0.5))
    completeness_score = _clamp_score(data.get("completeness_score", 0.5))

    issues: list[VerificationIssue] = []
    for iss in data.get("issues", []) or []:
        if not isinstance(iss, dict):
            continue
        severity = str(iss.get("severity", "info"))
        if severity not in _VALID_SEVERITIES:
            severity = "info"
        dimension = str(iss.get("dimension", "completeness"))
        if dimension not in _VALID_DIMENSIONS:
            dimension = "completeness"
        description = str(iss.get("description", ""))
        related_field_raw = iss.get("related_field")
        related_field = str(related_field_raw) if related_field_raw else None
        suggested_fix_raw = iss.get("suggested_fix")
        suggested_fix = str(suggested_fix_raw) if suggested_fix_raw else None
        issues.append(
            VerificationIssue(
                severity=severity,
                dimension=dimension,
                description=description,
                related_field=related_field,
                suggested_fix=suggested_fix,
            )
        )

    missing_raw = data.get("missing_items")
    missing_items: list[str] | None = None
    if isinstance(missing_raw, list):
        missing_items = [str(item) for item in missing_raw if isinstance(item, str)]

    evidence_quotes: dict[str, str] = {}
    eq = data.get("evidence_quotes")
    if isinstance(eq, dict):
        for k, v in eq.items():
            if isinstance(v, str):
                evidence_quotes[k] = v

    # Hard enforcement: LLM may return "pass" verdict alongside low scores or
    # critical issues. Downgrade the verdict to match the actual evidence.
    has_critical = any(i.severity == "critical" for i in issues)
    min_score = min(consistency_score, logic_score, completeness_score)

    if consistency_score < 0.3:
        verdict = "rejected"
    elif has_critical or min_score < 0.7:
        if verdict == "pass":
            verdict = "revision_needed"

    return VerificationResult(
        verdict=verdict,
        confidence=confidence,
        consistency_score=consistency_score,
        logic_score=logic_score,
        completeness_score=completeness_score,
        issues=issues,
        missing_items=missing_items,
        evidence_quotes=evidence_quotes,
        revised_rule=None,
    )


# ---------------------------------------------------------------------------
# RuleExtractor
# ---------------------------------------------------------------------------


class RuleExtractor:
    """Two-stage LLM rule extraction with cross-validation.

    Stage 1: Extract candidate rules from document chunks via LLM.
    Stage 2: Cross-validate each rule with a different LLM persona.
    """

    def __init__(self, llm: LLMProviderPort, registry: ConceptRegistry):
        self._llm = llm
        self._registry = registry

    def extract(
        self,
        chunks: list[DocumentChunk],
        candidate_id_prefix: str = "extracted",
    ) -> tuple[list[ExtractedConditionRule], list[SuggestedConcept]]:
        """Stage 1: Extract candidate rules from document chunks via LLM."""
        source_chunk_ids = [c.chunk_id for c in chunks]
        source_doc_ids = list({c.doc_id for c in chunks})
        registry_text = _serialize_concept_registry_for_prompt(self._registry)
        system_prompt = _EXTRACTION_SYSTEM_PROMPT.replace(
            "__CONCEPT_REGISTRY__", registry_text
        )
        user_prompt = _build_extraction_user_prompt(chunks)

        request = LLMRequest(
            task=LLMTask.RULE_EXTRACTION,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        try:
            response = self._llm.complete(request)
        except Exception as e:
            raise RuleExtractionError(
                f"LLM extraction call failed: {e}",
                raw_response=None,
            ) from e

        try:
            return _parse_extraction_response(
                response.content, self._registry, candidate_id_prefix, source_chunk_ids, source_doc_ids
            )
        except RuleExtractionError:
            raise
        except Exception as e:
            raise RuleExtractionError(
                f"Failed to parse extraction response: {e}",
                raw_response=response.content,
            ) from e

    def cross_validate(
        self,
        rule: ExtractedConditionRule,
        chunks: list[DocumentChunk],
    ) -> VerificationResult:
        """Stage 2: Cross-validate a single rule against source fragments."""
        user_prompt = _build_verification_user_prompt(rule, chunks)

        request = LLMRequest(
            task=LLMTask.RULE_VALIDATION,
            system_prompt=_VERIFICATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        try:
            response = self._llm.complete(request)
        except Exception as e:
            raise RuleExtractionError(
                f"LLM verification call failed: {e}",
                raw_response=None,
            ) from e

        try:
            return _parse_verification_response(response.content)
        except RuleExtractionError:
            raise
        except Exception as e:
            raise RuleExtractionError(
                f"Failed to parse verification response: {e}",
                raw_response=response.content,
            ) from e

    def extract_and_validate(
        self,
        chunks: list[DocumentChunk],
        candidate_id_prefix: str = "extracted",
        max_retries: int = 2,
    ) -> "ExtractionResult":
        """Full pipeline: extract rules, cross-validate, retry on revision_needed.

        Returns an ExtractionResult bundling all extracted rules, suggested
        concepts, and any errors encountered.
        """
        errors: list[str] = []

        # Stage 1: Extract
        try:
            rules, suggestions = self.extract(chunks, candidate_id_prefix)
        except RuleExtractionError as e:
            return ExtractionResult(
                rules=[],
                suggested_concepts=[],
                extraction_errors=[str(e)],
            )

        # Stage 2: Cross-validate each rule
        validated_rules: list[ExtractedConditionRule] = []
        for rule in rules:
            try:
                vr = self._verify_with_retry(rule, chunks, max_retries)
            except RuleExtractionError as e:
                errors.append(f"Verification failed for {rule.candidate_id}: {e}")
                rule.status = "pending_review"
                validated_rules.append(rule)
                continue

            rule.verification_result = vr

            if vr.verdict == "pass":
                rule.status = "draft"
                validated_rules.append(rule)
            elif vr.verdict == "rejected":
                rule.status = "rejected"
                validated_rules.append(rule)
            elif vr.verdict == "revision_needed":
                rule.status = "pending_review"
                validated_rules.append(rule)
            else:
                rule.status = "pending_review"
                validated_rules.append(rule)

        return ExtractionResult(
            rules=validated_rules,
            suggested_concepts=suggestions,
            extraction_errors=errors if errors else [],
        )

    def _verify_with_retry(
        self,
        rule: ExtractedConditionRule,
        chunks: list[DocumentChunk],
        max_retries: int,
    ) -> VerificationResult:
        """Cross-validate with retry on revision_needed."""
        vr = self.cross_validate(rule, chunks)

        retries = 0
        while vr.verdict == "revision_needed" and retries < max_retries:
            # Build a revised extraction prompt incorporating verification issues
            issue_descriptions = "\n".join(
                f"- [{i.dimension}] {i.description}"
                + (f" (suggested fix: {i.suggested_fix})" if i.suggested_fix else "")
                for i in vr.issues
            )
            revision_prompt = (
                f"Previous extraction was flagged with these issues:\n"
                f"{issue_descriptions}\n\n"
                f"Please re-extract the rules addressing these issues.\n\n"
            )
            chunks_context = "\n\n---\n\n".join(
                f"[{c.chunk_id}]\n{c.text}" for c in chunks
            )
            user_prompt = revision_prompt + chunks_context

            registry_text = _serialize_concept_registry_for_prompt(self._registry)
            system_prompt = _EXTRACTION_SYSTEM_PROMPT.replace(
                "__CONCEPT_REGISTRY__", registry_text
            )

            request = LLMRequest(
                task=LLMTask.RULE_EXTRACTION,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            try:
                response = self._llm.complete(request)
            except Exception as e:
                raise RuleExtractionError(
                    f"LLM retry call failed: {e}",
                ) from e

            try:
                revised_rules, _ = _parse_extraction_response(
                    response.content,
                    self._registry,
                    f"{rule.candidate_id}-r{retries + 1}",
                    [c.chunk_id for c in chunks],
                    list({c.doc_id for c in chunks}),
                )
            except RuleExtractionError as e:
                raise RuleExtractionError(
                    f"Failed to parse retry response: {e}",
                    raw_response=response.content,
                ) from e

            if revised_rules:
                # Take the first revised rule and update the original
                revised = revised_rules[0]
                rule.hard_exclusions = revised.hard_exclusions
                rule.preferred_tags = revised.preferred_tags
                rule.nutrition_limits = revised.nutrition_limits
                rule.confidence = revised.confidence

            vr = self.cross_validate(rule, chunks)
            retries += 1

        return vr

    def extract_and_save(
        self,
        chunks: list[DocumentChunk],
        store: "RuleStore",
        candidate_id_prefix: str = "extracted",
        max_retries: int = 2,
    ) -> ExtractionResult:
        """Full pipeline that extracts, validates, and saves rules to the store."""
        result = self.extract_and_validate(chunks, candidate_id_prefix, max_retries)
        if result.rules:
            store.bulk_create(result.rules)
        return result
