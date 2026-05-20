"""Tests for knowledge extractor — prompts and parse helpers (no LLM calls)."""

import json

import pytest

from medidiet.domain import (
    CodeKind,
    ConceptCode,
    ConceptDefinition,
    ConceptRegistry,
)
from medidiet.rules import NutrientMetric, NutrientLimit, LimitScope
from knowledge.documents import DocumentChunk
from knowledge.extractor import (
    _serialize_concept_registry_for_prompt,
    _build_extraction_user_prompt,
    _build_verification_user_prompt,
    _parse_extraction_response,
    _parse_verification_response,
    _parse_concept_code,
    RuleExtractionError,
)


def _sample_registry() -> ConceptRegistry:
    return ConceptRegistry(
        [
            ConceptDefinition(
                code=ConceptCode(CodeKind.CONDITION, "hypertension"),
                display_name="Hypertension",
                source="baseline",
            ),
            ConceptDefinition(
                code=ConceptCode(CodeKind.CONDITION, "diabetes"),
                display_name="Diabetes",
                source="baseline",
            ),
            ConceptDefinition(
                code=ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium"),
                display_name="High Sodium",
                source="baseline",
            ),
            ConceptDefinition(
                code=ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium"),
                display_name="Low Sodium",
                source="baseline",
            ),
            ConceptDefinition(
                code=ConceptCode(CodeKind.CONTRAINDICATION, "deep_fried"),
                display_name="Deep Fried",
                source="baseline",
            ),
        ]
    )


def _make_chunk(chunk_id: str, text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id="doc-001",
        text=text,
        chunk_index=0,
    )


class TestSerializeConceptRegistry:
    def test_serialize_groups_by_kind(self):
        registry = _sample_registry()
        text = _serialize_concept_registry_for_prompt(registry)
        assert "CodeKind.CONDITION" in text
        assert "CodeKind.CONTRAINDICATION" in text
        assert "CodeKind.NUTRITION_TAG" in text
        assert "hypertension" in text
        assert "high_sodium" in text
        assert "low_sodium" in text


class TestBuildPrompts:
    def test_build_extraction_user_prompt(self):
        chunks = [
            _make_chunk("doc-001-chunk-0000", "Limit sodium to 700mg per meal."),
            _make_chunk("doc-001-chunk-0001", "Avoid deep fried foods."),
        ]
        prompt = _build_extraction_user_prompt(chunks)
        assert "Limit sodium to 700mg per meal." in prompt
        assert "Avoid deep fried foods." in prompt
        assert "doc-001-chunk-0000" in prompt
        assert "doc-001-chunk-0001" in prompt

    def test_build_verification_user_prompt(self):
        from knowledge.schema import ExtractedConditionRule
        from datetime import datetime, timezone

        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["doc-001-chunk-0000"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions={ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium")},
            preferred_tags={ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium")},
            nutrition_limits={
                NutrientLimit(
                    metric=NutrientMetric.SODIUM_MG,
                    scope=LimitScope.PER_MEAL,
                    max_value=700.0,
                    window_hours=None,
                )
            },
            confidence=0.9,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        chunks = [_make_chunk("doc-001-chunk-0000", "Sodium limit: 700mg per meal.")]
        prompt = _build_verification_user_prompt(rule, chunks)
        assert "hypertension" in prompt
        assert "high_sodium" in prompt
        assert "Sodium limit" in prompt
        assert "700.0" in prompt


class TestParseConceptCode:
    def test_known_code_returns_concept_code(self):
        registry = _sample_registry()
        code = _parse_concept_code("condition", "hypertension", registry)
        assert code is not None
        assert code.kind == CodeKind.CONDITION
        assert code.value == "hypertension"

    def test_unknown_code_returns_none(self):
        registry = _sample_registry()
        code = _parse_concept_code("condition", "unknown_disease", registry)
        assert code is None

    def test_invalid_kind_returns_none(self):
        registry = _sample_registry()
        code = _parse_concept_code("invalid_kind", "hypertension", registry)
        assert code is None


class TestParseExtractionResponse:
    def test_parse_valid_json(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [
                        {"kind": "contraindication", "value": "high_sodium"}
                    ],
                    "preferred_tags": [
                        {"kind": "nutrition_tag", "value": "low_sodium"}
                    ],
                    "nutrition_limits": [
                        {
                            "metric": "sodium_mg",
                            "scope": "per_meal",
                            "max_value": 700.0,
                            "window_hours": None,
                        }
                    ],
                    "confidence": 0.9,
                    "evidence_quotes": {
                        "sodium_limit": "Limit sodium to 700mg per meal"
                    },
                }
            ],
            "suggested_concepts": [],
        })
        rules, suggestions = _parse_extraction_response(
            raw, registry, "test", ["chunk-001"]
        )
        assert len(rules) == 1
        assert rules[0].condition.value == "hypertension"
        assert ConceptCode(CodeKind.CONTRAINDICATION, "high_sodium") in rules[0].hard_exclusions
        assert ConceptCode(CodeKind.NUTRITION_TAG, "low_sodium") in rules[0].preferred_tags
        assert len(rules[0].nutrition_limits) == 1
        nl = next(iter(rules[0].nutrition_limits))
        assert nl.metric == NutrientMetric.SODIUM_MG
        assert nl.max_value == 700.0
        assert rules[0].confidence == 0.9
        assert rules[0].extraction_method == "llm"
        assert rules[0].status == "draft"
        assert len(suggestions) == 0

    def test_parse_with_evidence_quotes_creates_verification(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "diabetes"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.8,
                    "evidence_quotes": {
                        "sugar": "Limit sugar to 25g daily"
                    },
                }
            ],
            "suggested_concepts": [],
        })
        rules, _ = _parse_extraction_response(raw, registry, "test", ["chunk-001"])
        assert len(rules) == 1
        assert rules[0].verification_result is not None
        assert rules[0].verification_result.evidence_quotes == {
            "sugar": "Limit sugar to 25g daily"
        }

    def test_unknown_condition_skipped(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "unknown_disease"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.8,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        rules, _ = _parse_extraction_response(
            raw, registry, "test", ["chunk-001"]
        )
        assert len(rules) == 0

    def test_suggested_concepts_parsed(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [
                {
                    "kind": "contraindication",
                    "value": "high_purine",
                    "definition": "Foods high in purines that may trigger gout",
                    "display_name": "High Purine Foods",
                }
            ],
        })
        rules, suggestions = _parse_extraction_response(
            raw, registry, "test", ["chunk-001"]
        )
        assert len(rules) == 1
        assert len(suggestions) == 1
        assert suggestions[0].suggested_code.value == "high_purine"
        assert suggestions[0].definition == "Foods high in purines that may trigger gout"

    def test_empty_rules_array(self):
        registry = _sample_registry()
        raw = json.dumps({"rules": [], "suggested_concepts": []})
        rules, suggestions = _parse_extraction_response(
            raw, registry, "test", ["chunk-001"]
        )
        assert len(rules) == 0
        assert len(suggestions) == 0

    def test_clamps_confidence_to_range(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 2.5,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        rules, _ = _parse_extraction_response(raw, registry, "test", ["chunk-001"])
        assert rules[0].confidence == 1.0

    def test_malformed_json_raises(self):
        registry = _sample_registry()
        with pytest.raises(RuleExtractionError, match="JSON"):
            _parse_extraction_response("not json", registry, "test", ["chunk-001"])

    def test_rules_not_a_list(self):
        registry = _sample_registry()
        raw = json.dumps({"rules": "not a list"})
        with pytest.raises(RuleExtractionError, match="array"):
            _parse_extraction_response(raw, registry, "test", ["chunk-001"])

    def test_candidate_id_is_unique(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                },
                {
                    "condition": {"kind": "condition", "value": "diabetes"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.8,
                    "evidence_quotes": {},
                },
            ],
            "suggested_concepts": [],
        })
        rules, _ = _parse_extraction_response(raw, registry, "pilot", ["chunk-001"])
        assert len(rules) == 2
        assert rules[0].candidate_id != rules[1].candidate_id
        assert rules[0].candidate_id.startswith("pilot-")
        assert rules[1].candidate_id.startswith("pilot-")

    def test_invalid_nutrition_limit_skipped(self):
        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [
                        {"metric": "invalid_metric", "scope": "per_meal", "max_value": 100},
                    ],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        rules, _ = _parse_extraction_response(raw, registry, "test", ["chunk-001"])
        assert len(rules) == 1
        assert len(rules[0].nutrition_limits) == 0


class TestParseVerificationResponse:
    def test_pass_verdict(self):
        raw = json.dumps({
            "verdict": "pass",
            "confidence": 0.95,
            "consistency_score": 0.9,
            "logic_score": 0.85,
            "completeness_score": 0.8,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })
        result = _parse_verification_response(raw)
        assert result.verdict == "pass"
        assert result.confidence == 0.95
        assert result.consistency_score == 0.9
        assert result.logic_score == 0.85
        assert result.completeness_score == 0.8
        assert len(result.issues) == 0

    def test_revision_needed_with_issues(self):
        raw = json.dumps({
            "verdict": "revision_needed",
            "confidence": 0.6,
            "consistency_score": 0.5,
            "logic_score": 0.9,
            "completeness_score": 0.4,
            "issues": [
                {
                    "severity": "warning",
                    "dimension": "consistency",
                    "description": "Sodium limit not found in source",
                    "related_field": "nutrition_limits",
                    "suggested_fix": "Review sodium max_value",
                },
                {
                    "severity": "info",
                    "dimension": "completeness",
                    "description": "Missing potassium guideline",
                    "related_field": None,
                    "suggested_fix": None,
                },
            ],
            "missing_items": ["potassium_limit"],
            "evidence_quotes": {"sodium": "Limit sodium to 1500mg daily"},
        })
        result = _parse_verification_response(raw)
        assert result.verdict == "revision_needed"
        assert len(result.issues) == 2
        assert result.issues[0].severity == "warning"
        assert result.issues[0].dimension == "consistency"
        assert result.issues[0].description == "Sodium limit not found in source"
        assert result.issues[0].related_field == "nutrition_limits"
        assert result.issues[0].suggested_fix == "Review sodium max_value"
        assert result.issues[1].severity == "info"
        assert result.issues[1].related_field is None
        assert result.issues[1].suggested_fix is None
        assert result.missing_items == ["potassium_limit"]
        assert result.evidence_quotes == {"sodium": "Limit sodium to 1500mg daily"}

    def test_rejected_verdict(self):
        raw = json.dumps({
            "verdict": "rejected",
            "confidence": 0.1,
            "consistency_score": 0.2,
            "logic_score": 0.5,
            "completeness_score": 0.3,
            "issues": [
                {
                    "severity": "critical",
                    "dimension": "consistency",
                    "description": "Rule contradicts source",
                    "related_field": None,
                    "suggested_fix": None,
                }
            ],
            "missing_items": None,
            "evidence_quotes": {},
        })
        result = _parse_verification_response(raw)
        assert result.verdict == "rejected"
        assert len(result.issues) == 1
        assert result.issues[0].severity == "critical"

    def test_invalid_verdict_falls_back(self):
        raw = json.dumps({
            "verdict": "maybe",
            "confidence": 0.5,
            "consistency_score": 0.5,
            "logic_score": 0.5,
            "completeness_score": 0.5,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })
        result = _parse_verification_response(raw)
        assert result.verdict == "revision_needed"

    def test_malformed_json_raises(self):
        with pytest.raises(RuleExtractionError):
            _parse_verification_response("not json")

    def test_clamps_scores_to_range(self):
        raw = json.dumps({
            "verdict": "pass",
            "confidence": 1.5,
            "consistency_score": -0.5,
            "logic_score": 2.0,
            "completeness_score": -1.0,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })
        result = _parse_verification_response(raw)
        assert result.confidence == 1.0
        assert result.consistency_score == 0.0
        assert result.logic_score == 1.0
        assert result.completeness_score == 0.0

    def test_invalid_severity_falls_back(self):
        raw = json.dumps({
            "verdict": "pass",
            "confidence": 0.9,
            "consistency_score": 0.9,
            "logic_score": 0.9,
            "completeness_score": 0.9,
            "issues": [
                {"severity": "unknown", "dimension": "logic", "description": "x"}
            ],
            "missing_items": None,
            "evidence_quotes": {},
        })
        result = _parse_verification_response(raw)
        assert result.issues[0].severity == "info"


# ---------------------------------------------------------------------------
# RuleExtractor tests (using MockLLMProvider for deterministic testing)
# ---------------------------------------------------------------------------


class TestRuleExtractorExtract:
    def test_extract_returns_rules_from_valid_llm_json(self):
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor

        registry = _sample_registry()
        raw = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [
                        {"kind": "contraindication", "value": "high_sodium"}
                    ],
                    "preferred_tags": [
                        {"kind": "nutrition_tag", "value": "low_sodium"}
                    ],
                    "nutrition_limits": [
                        {
                            "metric": "sodium_mg",
                            "scope": "per_meal",
                            "max_value": 700.0,
                            "window_hours": None,
                        }
                    ],
                    "confidence": 0.9,
                    "evidence_quotes": {
                        "sodium_limit": "Limit sodium to 700mg per meal"
                    },
                }
            ],
            "suggested_concepts": [],
        })
        mock = MockLLMProvider(raw_content=raw)
        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("ckd-001-0000", "Limit sodium to 700mg per meal.")]

        rules, suggestions = extractor.extract(chunks)
        assert len(rules) == 1
        assert rules[0].condition.value == "hypertension"
        assert len(suggestions) == 0

    def test_extract_uses_correct_task(self):
        from medidiet.llm import MockLLMProvider, LLMTask
        from knowledge.extractor import RuleExtractor

        registry = _sample_registry()
        mock = MockLLMProvider(raw_content=json.dumps({"rules": [], "suggested_concepts": []}))
        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-1", "Some text.")]

        extractor.extract(chunks)
        assert len(mock.requests) == 1
        assert mock.requests[0].task is LLMTask.RULE_EXTRACTION

    def test_extract_llm_error_wraps_in_rule_extraction_error(self):
        import pytest
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor, RuleExtractionError

        registry = _sample_registry()
        mock = MockLLMProvider(error=RuntimeError("LLM down"))
        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-1", "Some text.")]

        with pytest.raises(RuleExtractionError, match="LLM extraction call failed"):
            extractor.extract(chunks)

    def test_extract_malformed_json_wraps_error(self):
        import pytest
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor, RuleExtractionError

        registry = _sample_registry()
        mock = MockLLMProvider(raw_content="not valid json")
        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-1", "Some text.")]

        with pytest.raises(RuleExtractionError, match="Invalid JSON"):
            extractor.extract(chunks)


class TestRuleExtractorCrossValidate:
    def test_cross_validate_pass(self):
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor
        from knowledge.schema import ExtractedConditionRule
        from datetime import datetime, timezone

        registry = _sample_registry()
        raw = json.dumps({
            "verdict": "pass",
            "confidence": 0.95,
            "consistency_score": 0.9,
            "logic_score": 0.85,
            "completeness_score": 0.8,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })
        mock = MockLLMProvider(raw_content=raw)
        extractor = RuleExtractor(mock, registry)

        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.9,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        chunks = [_make_chunk("chunk-001", "Limit sodium to 700mg per meal.")]

        vr = extractor.cross_validate(rule, chunks)
        assert vr.verdict == "pass"

    def test_cross_validate_uses_correct_task(self):
        from medidiet.llm import MockLLMProvider, LLMTask
        from knowledge.extractor import RuleExtractor
        from knowledge.schema import ExtractedConditionRule
        from datetime import datetime, timezone

        registry = _sample_registry()
        mock = MockLLMProvider(raw_content=json.dumps({
            "verdict": "pass", "confidence": 0.9,
            "consistency_score": 0.9, "logic_score": 0.9, "completeness_score": 0.9,
            "issues": [], "missing_items": None, "evidence_quotes": {},
        }))
        extractor = RuleExtractor(mock, registry)

        rule = ExtractedConditionRule(
            candidate_id="cand-001",
            source_doc_ids=["doc-001"],
            source_chunk_ids=["chunk-001"],
            condition=ConceptCode(CodeKind.CONDITION, "hypertension"),
            hard_exclusions=set(),
            preferred_tags=set(),
            nutrition_limits=set(),
            confidence=0.9,
            extraction_method="llm",
            reviewed_by=None,
            status="draft",
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        mock.requests.clear()
        extractor.cross_validate(rule, [_make_chunk("chunk-001", "...")])
        assert len(mock.requests) == 1
        assert mock.requests[0].task is LLMTask.RULE_VALIDATION


class TestExtractAndValidate:
    def test_full_pipeline_pass(self):
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor

        registry = _sample_registry()
        extraction_json = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        verification_json = json.dumps({
            "verdict": "pass",
            "confidence": 0.95,
            "consistency_score": 0.9,
            "logic_score": 0.9,
            "completeness_score": 0.9,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })
        mock = MockLLMProvider(raw_content=None)
        # Will be called twice: extraction then verification
        call_responses = [extraction_json, verification_json]
        # Override complete() to return different responses per call

        original_complete = mock.complete

        def sequenced_complete(request):
            mock.requests.append(request)
            if mock.error is not None:
                raise mock.error
            if mock.raw_content is not None:
                return type("Response", (), {
                    "content": mock.raw_content,
                    "provider_name": "mock",
                    "model": "mock",
                })()
            # Pop first response
            content = call_responses.pop(0) if call_responses else "{}"
            from medidiet.llm import LLMResponse
            return LLMResponse(content=content, provider_name="mock", model="mock")

        mock.complete = sequenced_complete

        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-001", "Limit sodium to 700mg per meal.")]

        result = extractor.extract_and_validate(chunks)
        assert len(result.rules) == 1
        assert result.rules[0].status == "draft"
        assert result.rules[0].verification_result is not None
        assert result.rules[0].verification_result.verdict == "pass"

    def test_pipeline_rejected_rule(self):
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor

        registry = _sample_registry()
        extraction_json = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        rejection_json = json.dumps({
            "verdict": "rejected",
            "confidence": 0.1,
            "consistency_score": 0.2,
            "logic_score": 0.5,
            "completeness_score": 0.3,
            "issues": [
                {
                    "severity": "critical",
                    "dimension": "consistency",
                    "description": "Rule contradicts source",
                    "related_field": None,
                    "suggested_fix": None,
                }
            ],
            "missing_items": None,
            "evidence_quotes": {},
        })
        mock = MockLLMProvider(raw_content=None)

        call_responses = [extraction_json, rejection_json]

        def sequenced_complete(request):
            mock.requests.append(request)
            if mock.error is not None:
                raise mock.error
            content = call_responses.pop(0) if call_responses else "{}"
            from medidiet.llm import LLMResponse
            return LLMResponse(content=content, provider_name="mock", model="mock")

        mock.complete = sequenced_complete

        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-001", "Some text.")]

        result = extractor.extract_and_validate(chunks)
        assert len(result.rules) == 1
        assert result.rules[0].status == "rejected"

    def test_pipeline_retry_on_revision_needed(self):
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor

        registry = _sample_registry()
        extraction_json = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        revision_json = json.dumps({
            "verdict": "revision_needed",
            "confidence": 0.5,
            "consistency_score": 0.6,
            "logic_score": 0.9,
            "completeness_score": 0.5,
            "issues": [
                {
                    "severity": "warning",
                    "dimension": "consistency",
                    "description": "Missing sodium limit",
                    "related_field": "nutrition_limits",
                    "suggested_fix": "Add sodium restriction",
                }
            ],
            "missing_items": ["sodium_limit"],
            "evidence_quotes": {},
        })
        pass_json = json.dumps({
            "verdict": "pass",
            "confidence": 0.9,
            "consistency_score": 0.9,
            "logic_score": 0.9,
            "completeness_score": 0.9,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })
        # Response sequence: extract, verify(revision), retry-extract, verify(pass)
        call_responses = [extraction_json, revision_json, extraction_json, pass_json]
        mock = MockLLMProvider(raw_content=None)

        def sequenced_complete(request):
            mock.requests.append(request)
            content = call_responses.pop(0) if call_responses else "{}"
            from medidiet.llm import LLMResponse
            return LLMResponse(content=content, provider_name="mock", model="mock")

        mock.complete = sequenced_complete

        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-001", "Limit sodium.")]

        result = extractor.extract_and_validate(chunks, max_retries=1)
        assert len(result.rules) == 1
        assert result.rules[0].verification_result.verdict == "pass"
        # Should have 4 LLM calls: extract, verify, retry-extract, verify
        assert len(mock.requests) == 4

    def test_pipeline_llm_error_returns_error_result(self):
        from medidiet.llm import MockLLMProvider
        from knowledge.extractor import RuleExtractor

        registry = _sample_registry()
        mock = MockLLMProvider(error=RuntimeError("LLM unavailable"))
        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-001", "Some text.")]

        result = extractor.extract_and_validate(chunks)
        assert len(result.rules) == 0
        assert len(result.extraction_errors) == 1


class TestExtractAndSave:
    def test_extract_and_save_persists_rules(self, tmp_path):
        from medidiet.llm import MockLLMProvider, LLMResponse
        from knowledge.extractor import RuleExtractor
        from knowledge.store import RuleStore

        registry = _sample_registry()
        extraction_json = json.dumps({
            "rules": [
                {
                    "condition": {"kind": "condition", "value": "hypertension"},
                    "hard_exclusions": [],
                    "preferred_tags": [],
                    "nutrition_limits": [],
                    "confidence": 0.9,
                    "evidence_quotes": {},
                }
            ],
            "suggested_concepts": [],
        })
        verification_json = json.dumps({
            "verdict": "pass",
            "confidence": 0.95,
            "consistency_score": 0.9,
            "logic_score": 0.9,
            "completeness_score": 0.9,
            "issues": [],
            "missing_items": None,
            "evidence_quotes": {},
        })

        call_responses = [extraction_json, verification_json]
        mock = MockLLMProvider(raw_content=None)

        def sequenced_complete(request):
            mock.requests.append(request)
            content = call_responses.pop(0) if call_responses else "{}"
            return LLMResponse(content=content, provider_name="mock", model="mock")

        mock.complete = sequenced_complete

        store = RuleStore(data_dir=str(tmp_path))
        extractor = RuleExtractor(mock, registry)
        chunks = [_make_chunk("chunk-001", "Limit sodium to 700mg per meal.")]

        result = extractor.extract_and_save(chunks, store)
        assert len(result.rules) == 1
        assert len(store.list_all()) == 1
        stored = store.get(result.rules[0].candidate_id)
        assert stored is not None
        assert stored.condition.value == "hypertension"
