from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.documents import DocumentImporter
from knowledge.extractor import RuleExtractor
from knowledge.schema import DocumentChunk, ExtractedConditionRule, SuggestedConcept
from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry
from medidiet.llm import LLMConfig, OpenAICompatibleLLMProvider
from medidiet.rules import LimitScope, NutrientMetric


def build_chunking_report(
    *,
    repo_root: Path,
    dataset_dir: Path,
    report_path: Path,
) -> dict[str, Any]:
    manifest = _manifest_by_doc_id(dataset_dir)
    gold_rows = _read_jsonl(dataset_dir / "gold_evaluation_set.jsonl")
    documents = []

    for gold in gold_rows:
        manifest_row = manifest[gold["doc_id"]]
        document = _load_manifest_document(repo_root, manifest_row)
        documents.append(
            {
                "gold_id": gold["gold_id"],
                "doc_id": gold["doc_id"],
                "gold_behavior": gold["gold_behavior"],
                "source_path": manifest_row["path"],
                "source_url": manifest_row["source_url"],
                "chunk_count": len(document.chunks),
                "chunks": [_serialize_chunk(chunk) for chunk in document.chunks],
            }
        )

    report = {
        "dataset": "rule_extraction_v1",
        "mode": "chunking_observation",
        "generated_at": _utc_now(),
        "gold_record_count": len(gold_rows),
        "document_count": len(documents),
        "documents": documents,
    }
    _write_json(report_path, report)
    return report


def run_real_llm_dataset_smoke(
    *,
    repo_root: Path,
    dataset_dir: Path,
    report_path: Path,
    limit: int = 5,
) -> dict[str, Any]:
    manifest = _manifest_by_doc_id(dataset_dir)
    gold_rows = _select_gold_rows(_read_jsonl(dataset_dir / "gold_evaluation_set.jsonl"), limit)
    registry = _registry_for_gold_rows(gold_rows)
    observations = []

    for gold in gold_rows:
        manifest_row = manifest[gold["doc_id"]]
        document = _load_manifest_document(repo_root, manifest_row)
        provider = _RecordingProvider(LLMConfig.from_env())
        extractor = RuleExtractor(provider, registry)
        try:
            rules, suggestions = extractor.extract(
                document.chunks,
                candidate_id_prefix=f"dataset-{gold['doc_id']}",
            )
            error = None
        except Exception as exc:  # pragma: no cover - exercised only in opt-in real LLM runs
            rules = []
            suggestions = []
            error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "raw_response": getattr(exc, "raw_response", None),
            }

        observations.append(
            {
                "gold_id": gold["gold_id"],
                "doc_id": gold["doc_id"],
                "gold_behavior": gold["gold_behavior"],
                "source_path": manifest_row["path"],
                "source_url": manifest_row["source_url"],
                "chunks": [_serialize_chunk(chunk) for chunk in document.chunks],
                "llm_responses": provider.responses,
                "rules": [_serialize_rule(rule) for rule in rules],
                "suggested_concepts": [_serialize_suggestion(suggestion) for suggestion in suggestions],
                "field_match": _field_match(gold, rules, suggestions),
                "error": error,
            }
        )

    report = {
        "dataset": "rule_extraction_v1",
        "mode": "real_llm_dataset_smoke",
        "generated_at": _utc_now(),
        "model": _safe_model_snapshot(),
        "observation_count": len(observations),
        "observations": observations,
    }
    _write_json(report_path, report)
    return report


class _RecordingProvider(OpenAICompatibleLLMProvider):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.responses: list[dict[str, Any]] = []

    def complete(self, request):
        response = super().complete(request)
        self.responses.append(
            {
                "task": request.task.value,
                "content_char_count": len(response.content),
                "content": response.content,
            }
        )
        return response


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _manifest_by_doc_id(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    return {row["doc_id"]: row for row in _read_jsonl(dataset_dir / "manifest.jsonl")}


def _load_manifest_document(repo_root: Path, manifest_row: dict[str, Any]):
    source_path = repo_root / manifest_row["path"]
    return DocumentImporter().import_from_file(
        doc_id=manifest_row["doc_id"],
        title=manifest_row["title"],
        file_path=str(source_path),
        source_type=manifest_row["source_type"],
        metadata={
            "dataset": "rule_extraction_v1",
            "source_url": manifest_row["source_url"],
        },
    )


def _serialize_chunk(chunk: DocumentChunk) -> dict[str, Any]:
    text = chunk.text
    return {
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "char_count": len(text),
        "text_preview": text[:1200],
        "contains_frontmatter": text.lstrip().startswith("---"),
        "contains_source_notes": "## Source Notes" in text,
        "contains_extractable_source_content": "## Extractable Source Content" in text,
        "contains_copyright_handling": "## Copyright Handling" in text,
    }


def _serialize_rule(rule: ExtractedConditionRule) -> dict[str, Any]:
    return {
        "candidate_id": rule.candidate_id,
        "source_doc_ids": rule.source_doc_ids,
        "source_chunk_ids": rule.source_chunk_ids,
        "condition": _code_to_dict(rule.condition),
        "hard_exclusions": [_code_to_dict(code) for code in sorted(rule.hard_exclusions, key=_code_sort_key)],
        "preferred_tags": [_code_to_dict(code) for code in sorted(rule.preferred_tags, key=_code_sort_key)],
        "nutrition_limits": [
            {
                "metric": limit.metric.value,
                "scope": limit.scope.value,
                "max_value": limit.max_value,
                "window_hours": limit.window_hours,
            }
            for limit in sorted(rule.nutrition_limits, key=lambda item: (item.metric.value, item.scope.value, item.max_value))
        ],
        "confidence": rule.confidence,
        "status": rule.status,
        "verification_result": _serialize_verification(rule),
    }


def _serialize_verification(rule: ExtractedConditionRule) -> dict[str, Any] | None:
    result = rule.verification_result
    if result is None:
        return None
    return {
        "verdict": result.verdict,
        "confidence": result.confidence,
        "consistency_score": result.consistency_score,
        "logic_score": result.logic_score,
        "completeness_score": result.completeness_score,
        "issues": [
            {
                "severity": issue.severity,
                "dimension": issue.dimension,
                "description": issue.description,
                "related_field": issue.related_field,
                "suggested_fix": issue.suggested_fix,
            }
            for issue in result.issues
        ],
        "missing_items": result.missing_items,
        "evidence_quotes": result.evidence_quotes,
    }


def _serialize_suggestion(suggestion: SuggestedConcept) -> dict[str, Any]:
    return {
        "suggest_id": suggestion.suggest_id,
        "candidate_rule_id": suggestion.candidate_rule_id,
        "suggested_code": _code_to_dict(suggestion.suggested_code),
        "definition": suggestion.definition,
        "source_chunk_ids": suggestion.source_chunk_ids,
        "display_name": suggestion.display_name,
    }


def _field_match(
    gold: dict[str, Any],
    rules: list[ExtractedConditionRule],
    suggestions: list[SuggestedConcept],
) -> dict[str, Any]:
    if gold["gold_behavior"] == "negative":
        return {
            "behavior_match": not rules and not suggestions,
            "rule_count": len(rules),
            "suggested_concept_count": len(suggestions),
        }
    if gold["gold_behavior"] == "suggested_concept":
        expected = set(gold.get("suggested_concepts", []))
        found = {suggestion.suggested_code.value for suggestion in suggestions}
        return {
            "behavior_match": bool(expected & found),
            "expected_suggested_concepts": sorted(expected),
            "found_suggested_concepts": sorted(found),
            "missing_suggested_concepts": sorted(expected - found),
        }

    expected_condition = gold.get("condition", {}).get("value")
    matching_rules = [rule for rule in rules if rule.condition.value == expected_condition]
    best_rule = matching_rules[0] if matching_rules else None
    expected_exclusions = {item["value"] for item in gold.get("hard_exclusions", [])}
    expected_tags = {item["value"] for item in gold.get("preferred_tags", [])}
    expected_limits = {_limit_key(item) for item in gold.get("nutrition_limits", [])}

    found_exclusions = {code.value for rule in matching_rules for code in rule.hard_exclusions}
    found_tags = {code.value for rule in matching_rules for code in rule.preferred_tags}
    found_limits = {_rule_limit_key(limit) for rule in matching_rules for limit in rule.nutrition_limits}

    return {
        "behavior_match": best_rule is not None,
        "condition_match": best_rule is not None,
        "expected_condition": expected_condition,
        "matched_rule_ids": [rule.candidate_id for rule in matching_rules],
        "hard_exclusions": _set_match(expected_exclusions, found_exclusions),
        "preferred_tags": _set_match(expected_tags, found_tags),
        "nutrition_limits": _set_match(expected_limits, found_limits),
    }


def _set_match(expected: set[Any], found: set[Any]) -> dict[str, Any]:
    return {
        "expected": sorted(expected),
        "found": sorted(found),
        "matched": sorted(expected & found),
        "missing": sorted(expected - found),
        "extra": sorted(found - expected),
        "all_expected_matched": expected <= found,
    }


def _limit_key(item: dict[str, Any]) -> str:
    return f"{item.get('metric')}|{item.get('scope')}|{_format_limit_value(item.get('max_value', 0))}|{item.get('window_hours')}"


def _rule_limit_key(limit) -> str:
    return f"{limit.metric.value}|{limit.scope.value}|{_format_limit_value(limit.max_value)}|{limit.window_hours}"


def _format_limit_value(value: Any) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _registry_for_gold_rows(gold_rows: list[dict[str, Any]]) -> ConceptRegistry:
    definitions: dict[tuple[CodeKind, str], ConceptDefinition] = {}

    def add(kind: CodeKind, value: str) -> None:
        if value:
            code = ConceptCode(kind, value)
            definitions[(kind, value)] = ConceptDefinition(code, value.replace("_", " ").title())

    for row in gold_rows:
        if condition := row.get("condition"):
            add(CodeKind.CONDITION, condition.get("value", ""))
        for item in row.get("hard_exclusions", []):
            add(CodeKind.CONTRAINDICATION, item.get("value", ""))
        for item in row.get("preferred_tags", []):
            add(CodeKind.NUTRITION_TAG, item.get("value", ""))
        for concept in row.get("suggested_concepts", []):
            add(CodeKind.NUTRITION_TAG, concept)

    return ConceptRegistry(list(definitions.values()))


def _select_gold_rows(gold_rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return gold_rows
    preferred = [row for row in gold_rows if row["gold_behavior"] == "rule"]
    concepts = [row for row in gold_rows if row["gold_behavior"] == "suggested_concept"]
    negatives = [row for row in gold_rows if row["gold_behavior"] == "negative"]
    selected = [*preferred[: max(0, limit - 2)], *concepts[:1], *negatives[:1]]
    return selected[:limit]


def _code_to_dict(code: ConceptCode) -> dict[str, str]:
    return {"kind": code.kind.value, "value": code.value}


def _code_sort_key(code: ConceptCode) -> tuple[str, str]:
    return (code.kind.value, code.value)


def _safe_model_snapshot() -> dict[str, str | None]:
    config = LLMConfig.from_env()
    return {
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "timeout_seconds": str(config.timeout_seconds),
        "retry_attempts": str(config.retry_attempts),
        "retry_backoff_seconds": str(config.retry_backoff_seconds),
        "api_key": "<set>" if config.api_key else "<unset>",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
