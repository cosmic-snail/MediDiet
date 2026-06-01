from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medidiet.domain import CodeKind, ConceptCode, ConceptDefinition, ConceptRegistry
from medidiet.concept_registry import (
    EXPERIMENT_CONCEPT_STATUSES,
    load_concept_definitions_from_jsonl,
    merge_concept_definitions,
)
from medidiet.llm import LLMConfig, OpenAICompatibleLLMProvider
from medidiet.rules import load_baseline_rule_pack
from knowledge.dataset_manifest import load_dataset_documents, snapshot_source_hashes
from knowledge.concept_coverage import audit_concept_coverage
from knowledge.concept_discovery import discover_concept_candidates
from knowledge.documents import (
    EXTRACTABLE_CONTENT,
    RAW_CARD,
    SOURCE_NOTES_PLUS_EXTRACTABLE,
    DocumentImporter,
    select_document_content,
)
from knowledge.extraction_comparators import ComparatorInput, run_comparator_arm
from knowledge.extraction_experiments import BENCHMARK_EXPERIMENT_MATRIX, COMPARATOR_ARMS, EXPERIMENT_MATRIX, OBSERVATION_POINTS
from knowledge.extraction_observations import append_observation
from knowledge.extraction_stability import summarize_stability
from knowledge.extractor import RuleExtractor
from knowledge.golden_eval_accuracy import write_golden_eval_accuracy_artifacts
from knowledge.judge_evaluator import JudgeLLMEvaluator, build_layer_2_judge_summary
from knowledge.llm_run_control import CircuitBreaker, RunCheckpoint, classify_provider_failure
from knowledge.public_benchmarks import BENCHMARK_PORTFOLIO
from knowledge.research_registry import ResearchRegistry
from knowledge.rule_plausibility import build_plausibility_context, evaluate_observation_plausibility
from knowledge.rule_evaluation import evaluate_rule, precision_recall_f1
from knowledge.rule_identity import canonical_rule_identity
from knowledge.semantic_grounding import evaluate_observation_grounding
from knowledge.schema import DocumentChunk, ExtractedConditionRule, SuggestedConcept
from knowledge.source_governance import detect_conflicts


REPO_ROOT = Path(__file__).resolve().parents[3]

ARM_SOURCE_CONTENT_STRATEGIES = {
    "C1": RAW_CARD,
    "C2": EXTRACTABLE_CONTENT,
    "C3": SOURCE_NOTES_PLUS_EXTRACTABLE,
}


def _dataset_dir(dataset: str) -> Path:
    return REPO_ROOT / "knowledge" / "datasets" / dataset


def _source_root() -> Path:
    return REPO_ROOT / "knowledge" / "source_documents"


def _reports_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path else REPO_ROOT / "reports"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _load_default_dotenv() -> None:
    candidates = [REPO_ROOT / ".env"]
    if ".worktrees" in REPO_ROOT.parts:
        worktrees_index = REPO_ROOT.parts.index(".worktrees")
        candidates.append(Path(*REPO_ROOT.parts[:worktrees_index]) / ".env")
    for path in candidates:
        _load_dotenv(path)


def _rule_to_dict(rule) -> dict[str, Any]:
    return {
        "condition": rule.condition.value,
        "hard_exclusions": sorted(item.value for item in rule.hard_exclusions),
        "preferred_tags": sorted(item.value for item in rule.preferred_tags),
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
        "verification_verdict": rule.verification_result.verdict if rule.verification_result else None,
    }


def _suggestion_to_dict(suggestion) -> dict[str, Any]:
    return {
        "suggested_code": suggestion.suggested_code.value,
        "kind": suggestion.suggested_code.kind.value,
        "definition": suggestion.definition,
        "display_name": suggestion.display_name,
    }


def _is_operational_llm_failure(
    failures: list[str],
    parsed_rules: list[dict[str, Any]],
    suggested_concepts: list[dict[str, Any]],
) -> bool:
    if not failures:
        return False
    markers = (
        "provider_error",
        "LLM extraction call failed",
        "LLM verification call failed",
        "LLM retry call failed",
        "IncompleteRead",
        "Remote end closed connection",
        "request failed",
        "timeout",
        "timed out",
        "empty provider response",
    )
    if any(any(marker in failure for marker in markers) for failure in failures):
        return True
    return not parsed_rules and not suggested_concepts and any(
        "empty_output" in failure for failure in failures
    )


def build_chunking_report(
    dataset_dir: Path | None = None,
    source_root: Path | None = None,
    strategies: list[str] | None = None,
    *,
    repo_root: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    if repo_root is not None:
        if dataset_dir is None or report_path is None:
            raise TypeError("legacy chunking report requires dataset_dir and report_path")
        return _build_legacy_chunking_report(repo_root=repo_root, dataset_dir=dataset_dir, report_path=report_path)
    if dataset_dir is None or source_root is None:
        raise TypeError("research chunking report requires dataset_dir and source_root")
    return _build_research_chunking_report(dataset_dir, source_root, strategies)


def _build_research_chunking_report(dataset_dir: Path, source_root: Path, strategies: list[str] | None = None) -> dict[str, Any]:
    strategies = strategies or ["raw_card", "extractable_content"]
    docs = load_dataset_documents(dataset_dir, source_root)
    report: dict[str, Any] = {"dataset_id": dataset_dir.name, "strategies": {}, "rows": []}
    for strategy in strategies:
        importer = DocumentImporter()
        total = frontmatter = copyright = mid_word = 0
        per_doc: dict[str, int] = {}
        previews: list[dict[str, Any]] = []
        for doc in docs:
            raw = Path(doc.source).read_text(encoding="utf-8")
            selected = select_document_content(raw, strategy)
            strategy_doc = importer.import_from_text(doc.doc_id, doc.title, doc.source, doc.source_type, selected, doc.metadata, doc.ingested_at, chunk_strategy=strategy)
            per_doc[doc.doc_id] = len(strategy_doc.chunks)
            for chunk in strategy_doc.chunks:
                total += 1
                frontmatter += chunk.metadata.get("contains_frontmatter") == "true"
                copyright += chunk.metadata.get("contains_copyright_handling") == "true"
                mid_word += chunk.metadata.get("starts_mid_word") == "true"
                report["rows"].append({"doc_id": doc.doc_id, "strategy": strategy, "chunk_id": chunk.chunk_id, "chunk_hash": chunk.metadata.get("chunk_hash"), "source_card_hash": doc.metadata.get("source_card_hash"), "flags": {"frontmatter": chunk.metadata.get("contains_frontmatter") == "true", "copyright": chunk.metadata.get("contains_copyright_handling") == "true", "starts_mid_word": chunk.metadata.get("starts_mid_word") == "true"}})
                if len(previews) < 3:
                    previews.append({"doc_id": doc.doc_id, "chunk_id": chunk.chunk_id, "preview": chunk.text[:160]})
        report["strategies"][strategy] = {"summary": {"total_chunks": total, "chunks_with_frontmatter": frontmatter, "chunks_with_copyright_handling": copyright, "chunks_starting_mid_word": mid_word}, "per_doc_chunk_counts": per_doc, "representative_chunk_previews": previews}
    first = strategies[0]
    report["summary"] = report["strategies"][first]["summary"]
    return report


def _load_gold(dataset_dir: Path) -> list[dict[str, Any]]:
    path = dataset_dir / "gold_evaluation_set.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _gold_rows_by_doc_id(gold_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    gold_rows_by_doc_id: dict[str, list[dict[str, Any]]] = {}
    for gold_evaluation_row in gold_rows:
        doc_id = str(gold_evaluation_row.get("doc_id") or "")
        if doc_id:
            gold_rows_by_doc_id.setdefault(doc_id, []).append(gold_evaluation_row)
    return gold_rows_by_doc_id


def _research_failure_labels_for_empty_extraction(
    *,
    doc_id: str,
    gold_rows: list[dict[str, Any]],
) -> list[str]:
    doc_gold_rows = _gold_rows_by_doc_id(gold_rows).get(doc_id, [])
    if doc_gold_rows and all(
        gold_evaluation_row.get("gold_behavior") == "negative"
        for gold_evaluation_row in doc_gold_rows
    ):
        return ["expected_empty_extraction"]
    return ["no_rule_extracted"]


def _evaluation_input_from_observation(observation: dict[str, Any]) -> list[dict[str, Any]]:
    extracted = [dict(rule) for rule in observation.get("parsed_rules", [])]
    suggested_codes = [
        suggestion.get("suggested_code")
        for suggestion in observation.get("suggested_concepts", [])
        if suggestion.get("suggested_code")
    ]
    if suggested_codes:
        extracted.append({"suggested_concepts": suggested_codes})
    return extracted


def _evaluate_observations_against_gold(
    dataset_dir: Path,
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gold_by_doc_id: dict[str, list[dict[str, Any]]] = {}
    for gold_row in _load_gold(dataset_dir):
        gold_by_doc_id.setdefault(gold_row.get("doc_id", ""), []).append(gold_row)

    evaluations: list[dict[str, Any]] = []
    for observation in observations:
        for gold_row in gold_by_doc_id.get(observation.get("doc_id", ""), []):
            evaluation = evaluate_rule(gold_row, _evaluation_input_from_observation(observation))
            evaluations.append(
                {
                    **evaluation,
                    "experiment_id": observation.get("experiment_id"),
                    "arm_id": observation.get("arm_id"),
                    "dataset_id": observation.get("dataset_id"),
                    "doc_id": observation.get("doc_id"),
                    "input_variant": observation.get("input_variant"),
                    "source_content_strategy": observation.get(
                        "source_content_strategy",
                        observation.get("input_variant"),
                    ),
                    "gold_behavior": gold_row.get("gold_behavior"),
                }
            )
    return evaluations


def _summarize_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for evaluation in evaluations:
        key = (str(evaluation.get("experiment_id", "")), str(evaluation.get("arm_id", "")))
        grouped.setdefault(key, []).append(evaluation)

    return {
        "evaluated_record_count": len(evaluations),
        "overall": precision_recall_f1(evaluations),
        "by_experiment_arm": [
            {
                "experiment_id": experiment_id,
                "arm_id": arm_id,
                "evaluated_record_count": len(rows),
                **precision_recall_f1(rows),
            }
            for (experiment_id, arm_id), rows in sorted(grouped.items())
        ],
    }


def _summarize_suggested_concepts(observations: list[dict[str, Any]]) -> dict[str, Any]:
    concept_counts: Counter[str] = Counter()
    concept_sources: dict[str, set[str]] = {}
    for observation in observations:
        doc_id = str(observation.get("doc_id", ""))
        for suggestion in observation.get("suggested_concepts", []):
            code = suggestion.get("suggested_code")
            if not code:
                continue
            concept_counts[str(code)] += 1
            concept_sources.setdefault(str(code), set()).add(doc_id)
    return {
        "suggested_concept_count": sum(concept_counts.values()),
        "unique_suggested_concept_count": len(concept_counts),
        "concepts": [
            {
                "suggested_code": code,
                "count": count,
                "doc_ids": sorted(concept_sources.get(code, set())),
            }
            for code, count in sorted(concept_counts.items())
        ],
    }


def _summarize_operational_failures(operational_failures: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, dict[str, Any]] = {}
    by_failure_type: Counter[str] = Counter()
    for operational_failure in operational_failures:
        arm_id = str(operational_failure.get("arm_id") or "")
        by_arm.setdefault(arm_id, {"count": 0, "doc_ids": []})
        by_arm[arm_id]["count"] += 1
        doc_id = str(operational_failure.get("doc_id") or "")
        if doc_id:
            by_arm[arm_id]["doc_ids"].append(doc_id)
        for failure_label in operational_failure.get("failures", []) or []:
            by_failure_type[str(failure_label)] += 1
    for arm_summary in by_arm.values():
        arm_summary["doc_ids"] = sorted(arm_summary["doc_ids"])
    return {
        "total": len(operational_failures),
        "by_arm": dict(sorted(by_arm.items())),
        "by_failure_type": dict(sorted(by_failure_type.items())),
    }


def _summarize_paired_arm_rule_presence(
    observations: list[dict[str, Any]],
    *,
    left_arm: str,
    right_arm: str,
) -> dict[str, Any]:
    rule_presence_by_doc_id: dict[str, dict[str, bool]] = {}
    for observation_record in observations:
        doc_id = str(observation_record.get("doc_id") or "")
        arm_id = str(observation_record.get("arm_id") or "")
        if not doc_id or arm_id not in {left_arm, right_arm}:
            continue
        rule_presence_by_doc_id.setdefault(doc_id, {})
        rule_presence_by_doc_id[doc_id][arm_id] = bool(observation_record.get("parsed_rules"))

    paired_docs = {
        doc_id: arm_presence
        for doc_id, arm_presence in rule_presence_by_doc_id.items()
        if left_arm in arm_presence and right_arm in arm_presence
    }
    both_present = [
        doc_id
        for doc_id, arm_presence in paired_docs.items()
        if arm_presence[left_arm] and arm_presence[right_arm]
    ]
    left_only = [
        doc_id
        for doc_id, arm_presence in paired_docs.items()
        if arm_presence[left_arm] and not arm_presence[right_arm]
    ]
    right_only = [
        doc_id
        for doc_id, arm_presence in paired_docs.items()
        if arm_presence[right_arm] and not arm_presence[left_arm]
    ]
    neither_present = [
        doc_id
        for doc_id, arm_presence in paired_docs.items()
        if not arm_presence[left_arm] and not arm_presence[right_arm]
    ]
    unpaired_left = [
        doc_id
        for doc_id, arm_presence in rule_presence_by_doc_id.items()
        if left_arm in arm_presence and right_arm not in arm_presence
    ]
    unpaired_right = [
        doc_id
        for doc_id, arm_presence in rule_presence_by_doc_id.items()
        if right_arm in arm_presence and left_arm not in arm_presence
    ]
    return {
        "left_arm": left_arm,
        "right_arm": right_arm,
        "paired_doc_count": len(paired_docs),
        "both_present_doc_count": len(both_present),
        "left_only_doc_count": len(left_only),
        "right_only_doc_count": len(right_only),
        "neither_present_doc_count": len(neither_present),
        "unpaired_left_doc_count": len(unpaired_left),
        "unpaired_right_doc_count": len(unpaired_right),
        "both_present_doc_ids": sorted(both_present),
        "left_only_doc_ids": sorted(left_only),
        "right_only_doc_ids": sorted(right_only),
        "neither_present_doc_ids": sorted(neither_present),
        "unpaired_left_doc_ids": sorted(unpaired_left),
        "unpaired_right_doc_ids": sorted(unpaired_right),
    }


def _summarize_numeric_limit_failures(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    missing_numeric_limit_doc_ids = sorted(
        {
            str(evaluation.get("doc_id") or "")
            for evaluation in evaluations
            if "missing_numeric_limit" in (evaluation.get("failures", []) or [])
            and evaluation.get("doc_id")
        }
    )
    return {
        "missing_numeric_limit_count": len(missing_numeric_limit_doc_ids),
        "missing_numeric_limit_doc_ids": missing_numeric_limit_doc_ids,
    }


def _select_judge_calibration_observations(
    *,
    observations: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    max_cases: int,
) -> list[dict[str, Any]]:
    evaluation_by_doc_id = {
        str(evaluation.get("doc_id")): evaluation
        for evaluation in evaluations
        if evaluation.get("doc_id")
    }
    buckets: dict[str, list[dict[str, Any]]] = {
        "match": [],
        "miss": [],
        "negative": [],
        "other": [],
    }
    for observation_record in observations:
        doc_id = str(observation_record.get("doc_id") or "")
        evaluation = evaluation_by_doc_id.get(doc_id, {})
        if evaluation.get("gold_behavior") == "negative":
            buckets["negative"].append(observation_record)
        elif evaluation.get("overall") == "match":
            buckets["match"].append(observation_record)
        elif evaluation.get("overall") == "miss":
            buckets["miss"].append(observation_record)
        else:
            buckets["other"].append(observation_record)

    selected: list[dict[str, Any]] = []
    while len(selected) < max_cases and any(buckets.values()):
        for bucket_name in ("match", "miss", "negative", "other"):
            if buckets[bucket_name] and len(selected) < max_cases:
                selected.append(buckets[bucket_name].pop(0))
    return selected


def run_concept_discovery_report(
    dataset: str,
    output_dir: Path,
    *,
    provider,
    max_docs: int | None = None,
    source_content_strategy: str = EXTRACTABLE_CONTENT,
) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset)
    docs = load_dataset_documents(dataset_dir, _source_root())
    if max_docs is not None:
        docs = docs[:max_docs]
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_rule_pack = load_baseline_rule_pack()
    concept_registry_path = dataset_dir / "concept_registry.jsonl"
    extra_concept_definitions = load_concept_definitions_from_jsonl(
        concept_registry_path,
        include_statuses=EXPERIMENT_CONCEPT_STATUSES,
    )
    known_registry = merge_concept_definitions(
        baseline_rule_pack.concepts,
        extra_concept_definitions,
    )
    known_condition_values = {
        value
        for (kind, value) in known_registry._definitions
        if kind is CodeKind.CONDITION
    }
    candidates: list[dict[str, Any]] = []
    for doc in docs:
        raw_text = Path(doc.source).read_text(encoding="utf-8")
        selected = select_document_content(raw_text, source_content_strategy)
        candidates.extend(
            discover_concept_candidates(
                provider=provider,
                doc_id=doc.doc_id,
                source_text=selected,
                known_condition_values=known_condition_values,
                source_content_strategy=source_content_strategy,
                source_hash=str(doc.metadata.get("source_card_hash") or ""),
            )
        )

    candidate_path = output_dir / "rule-extraction-v1-concept-candidates.jsonl"
    candidate_path.write_text(
        "".join(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n" for candidate in candidates),
        encoding="utf-8",
    )
    report_path = output_dir / "rule-extraction-v1-concept-candidates-report.md"
    report_lines = [
        "# Concept Candidate Discovery",
        "",
        f"- dataset: {dataset}",
        f"- source content strategy: {source_content_strategy}",
        f"- document count: {len(docs)}",
        f"- candidate count: {len(candidates)}",
        "",
        "| value | kind | status | source_type | docs | confidence |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for candidate in candidates:
        report_lines.append(
            f"| {candidate['value']} | {candidate['kind']} | {candidate['status']} | {candidate['source_type']} | {', '.join(candidate.get('source_doc_ids', []))} | {float(candidate.get('confidence', 0.0)):.2f} |"
        )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return {
        "dataset_id": dataset,
        "document_count": len(docs),
        "candidate_count": len(candidates),
        "candidate_path": str(candidate_path),
        "report_path": str(report_path),
    }


@dataclass(frozen=True)
class SourceTextBundle:
    source_text_by_doc_id: dict[str, str]
    missing_path_doc_ids: list[str]
    missing_file_doc_ids: list[str]

    @property
    def diagnostics(self) -> dict[str, Any]:
        return {
            "loaded_doc_count": len(self.source_text_by_doc_id),
            "missing_path_doc_ids": self.missing_path_doc_ids,
            "missing_file_doc_ids": self.missing_file_doc_ids,
        }


def _attach_layer_0_1_evaluations(
    observations: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
    source_text_bundle: SourceTextBundle,
) -> dict[str, Any]:
    plausibility_context = build_plausibility_context(manifest_rows)
    plausibility_counts: Counter[str] = Counter()
    grounding_scores: list[float] = []
    unsupported_observation_count = 0
    for observation in observations:
        plausibility = evaluate_observation_plausibility(
            observation,
            manifest_rows,
            plausibility_context,
        )
        source_text = source_text_bundle.source_text_by_doc_id.get(str(observation.get("doc_id")), "")
        grounding = evaluate_observation_grounding(observation, source_text)
        observation["evaluator"] = {
            **observation.get("evaluator", {}),
            "plausibility": plausibility,
            "grounding": grounding,
        }
        plausibility_counts[plausibility["plausibility_flag"]] += 1
        grounding_scores.append(float(grounding["avg_score"]))
        if grounding["unsupported_rate"] > 0:
            unsupported_observation_count += 1
    return {
        "layer_0_plausibility": {
            "pass": plausibility_counts.get("pass", 0),
            "warn": plausibility_counts.get("warn", 0),
            "fail": plausibility_counts.get("fail", 0),
        },
        "layer_1_grounding": {
            "evaluated_observation_count": len(observations),
            "avg_score": sum(grounding_scores) / len(grounding_scores) if grounding_scores else 1.0,
            "unsupported_rate": unsupported_observation_count / len(observations) if observations else 0.0,
        },
    }


def _attach_layer_2_judge_evaluations(
    observations: list[dict[str, Any]],
    dataset_dir: Path,
    source_text_bundle: SourceTextBundle,
    judge_provider,
    gold_evaluations: list[dict[str, Any]],
    judge_max_rules: int | None = None,
) -> dict[str, Any]:
    if judge_provider is None or judge_max_rules == 0:
        return build_layer_2_judge_summary([], gold_evaluations)
    gold_rows = _load_gold(dataset_dir)
    gold_row_by_doc_id = {
        str(gold_row.get("doc_id")): gold_row
        for gold_row in gold_rows
        if gold_row.get("doc_id")
    }
    gold_id_by_doc_id = {
        str(gold_evaluation.get("doc_id")): str(gold_evaluation.get("gold_id"))
        for gold_evaluation in gold_evaluations
        if gold_evaluation.get("doc_id") and gold_evaluation.get("gold_id")
    }
    evaluator = JudgeLLMEvaluator(judge_provider)
    judge_results: list[dict[str, Any]] = []
    judged_rule_count = 0
    for observation in observations:
        source_text = source_text_bundle.source_text_by_doc_id.get(str(observation.get("doc_id")), "")
        doc_id = str(observation.get("doc_id") or "")
        gold_id = observation.get("gold_id") or gold_id_by_doc_id.get(doc_id)
        expected_gold_rule = gold_row_by_doc_id.get(doc_id)
        rule_results: list[dict[str, Any]] = []
        for rule_index, extracted_rule in enumerate(observation.get("parsed_rules", []) or []):
            if not isinstance(extracted_rule, dict):
                continue
            if judge_max_rules is not None and judged_rule_count >= judge_max_rules:
                continue
            judge_result = evaluator.evaluate_rule(
                source_text=source_text,
                extracted_rule=extracted_rule,
                evaluation_context={
                    "experiment_id": observation.get("experiment_id"),
                    "arm_id": observation.get("arm_id"),
                    "dataset_id": observation.get("dataset_id"),
                    "doc_id": doc_id,
                    "gold_id": gold_id,
                    "expected_gold_rule": expected_gold_rule,
                    "rule_index": rule_index,
                },
            )
            enriched_result = {
                **judge_result,
                "experiment_id": observation.get("experiment_id"),
                "arm_id": observation.get("arm_id"),
                "dataset_id": observation.get("dataset_id"),
                "doc_id": doc_id,
                "gold_id": gold_id,
                "rule_index": rule_index,
            }
            rule_results.append(enriched_result)
            judge_results.append(enriched_result)
            judged_rule_count += 1
        observation["evaluator"] = {
            **observation.get("evaluator", {}),
            "judge": {"rule_results": rule_results},
        }
    return build_layer_2_judge_summary(judge_results, gold_evaluations)


def _load_source_text_bundle(manifest_rows: list[dict[str, Any]]) -> SourceTextBundle:
    source_text_by_doc_id: dict[str, str] = {}
    missing_path_doc_ids: list[str] = []
    missing_file_doc_ids: list[str] = []
    for manifest_row in manifest_rows:
        doc_id = str(manifest_row.get("doc_id") or "")
        path = manifest_row.get("path") or manifest_row.get("source_card_path")
        if not doc_id:
            continue
        if not path:
            missing_path_doc_ids.append(doc_id)
            continue
        source_path = Path(path)
        if not source_path.is_absolute():
            source_path = REPO_ROOT / source_path
        if not source_path.exists():
            missing_file_doc_ids.append(doc_id)
            continue
        source_text_by_doc_id[doc_id] = source_path.read_text(encoding="utf-8")
    return SourceTextBundle(
        source_text_by_doc_id=source_text_by_doc_id,
        missing_path_doc_ids=missing_path_doc_ids,
        missing_file_doc_ids=missing_file_doc_ids,
    )


def _metric_bar(value: float, width: int = 20) -> str:
    filled = int(round(max(0.0, min(1.0, value)) * width))
    return "#" * filled + "." * (width - filled)


def _write_real_llm_visual_summary(
    output_dir: Path,
    report: dict[str, Any],
    evaluation_summary: dict[str, Any],
) -> Path:
    overall = evaluation_summary.get("overall", {})
    lines = [
        "# Rule Extraction Real LLM Summary",
        "",
        "## Run",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| dataset | {report.get('dataset_id', '')} |",
        f"| provider | {report.get('provider', '')} |",
        f"| model | {report.get('model', '')} |",
        f"| observations | {report.get('observation_count', 0)} |",
        f"| operational failures | {report.get('operational_failure_count', 0)} |",
        f"| unique suggested concepts | {report.get('suggested_concept_summary', {}).get('unique_suggested_concept_count', 0)} |",
        "",
        "## Gold Evaluation",
        "",
        "| Metric | Value | Bar |",
        "| --- | ---: | --- |",
        f"| precision | {overall.get('precision', 0):.3f} | `{_metric_bar(overall.get('precision', 0))}` |",
        f"| recall | {overall.get('recall', 0):.3f} | `{_metric_bar(overall.get('recall', 0))}` |",
        f"| f1 | {overall.get('f1', 0):.3f} | `{_metric_bar(overall.get('f1', 0))}` |",
        "",
        "## By Experiment And Arm",
        "",
        "| Experiment | Arm | Records | Precision | Recall | F1 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in evaluation_summary.get("by_experiment_arm", []):
        lines.append(
            f"| {row['experiment_id']} | {row['arm_id']} | {row['evaluated_record_count']} | "
            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |"
        )
    if not evaluation_summary.get("by_experiment_arm"):
        lines.append("| - | - | 0 | 0.000 | 0.000 | 0.000 |")

    summary_path = output_dir / "rule-extraction-v1-real-llm-summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def _write_layered_evaluation_summary(output_dir: Path, report: dict[str, Any]) -> Path:
    layer_0 = report.get("layer_0_plausibility", {})
    layer_1 = report.get("layer_1_grounding", {})
    layer_2 = report.get("layer_2_judge", {})
    calibration = layer_2.get("calibration", {})
    best_arm = report.get("evaluation_summary", {}).get("overall", {})
    lines = [
        "# Rule Extraction Layered Evaluation Summary",
        "",
        "## Run",
        "",
        f"- dataset: `{report.get('dataset_id', '')}`",
        f"- run type: `{report.get('run_type', '')}`",
        f"- provider: `{report.get('provider', '')}`",
        f"- model: `{report.get('model', '')}`",
        f"- observations: {report.get('observation_count', 0)}",
        f"- operational failures: {report.get('operational_failure_count', 0)}",
        "",
        "## Golden Eval",
        "",
        f"- precision: {best_arm.get('precision', 0):.3f}",
        f"- recall: {best_arm.get('recall', 0):.3f}",
        f"- f1: {best_arm.get('f1', 0):.3f}",
        f"- accuracy chart: `{report.get('golden_eval_accuracy', {}).get('chart_path', '')}`",
        "",
        "## Layer 0 Plausibility",
        "",
        f"- pass: {layer_0.get('pass', 0)}",
        f"- warn: {layer_0.get('warn', 0)}",
        f"- fail: {layer_0.get('fail', 0)}",
        "",
        "## Layer 1 Grounding",
        "",
        f"- evaluated observations: {layer_1.get('evaluated_observation_count', 0)}",
        f"- average score: {layer_1.get('avg_score', 0):.3f}",
        f"- unsupported rate: {layer_1.get('unsupported_rate', 0):.3f}",
        "",
        "## Layer 2 Judge",
        "",
        f"- evaluated rules: {layer_2.get('evaluated_rule_count', 0)}",
        f"- accept rate: {layer_2.get('accept_rate', 0):.3f}",
        f"- uncertain rate: {layer_2.get('uncertain_rate', 0):.3f}",
        f"- reject rate: {layer_2.get('reject_rate', 0):.3f}",
        f"- average confidence: {layer_2.get('avg_confidence', 0):.3f}",
        f"- calibrated records: {calibration.get('calibrated_record_count', 0)}",
        f"- agreement rate: {calibration.get('agreement_rate', 0):.3f}",
        f"- Gwet AC1: {calibration.get('gwet_ac1', 0):.3f}",
        "",
        "## Judge Cases",
        "",
        "| Experiment | Arm | Doc | Verdict | Confidence | Reason |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    judge_rows = []
    for observation in report.get("observations", []):
        for judge_result in observation.get("evaluator", {}).get("judge", {}).get("rule_results", []):
            judge_rows.append(judge_result)
    if judge_rows:
        for judge_result in judge_rows[:20]:
            reason = str(judge_result.get("reason", "")).replace("\n", " ")
            lines.append(
                f"| {judge_result.get('experiment_id', '')} | {judge_result.get('arm_id', '')} | "
                f"{judge_result.get('doc_id', '')} | {judge_result.get('verdict', '')} | "
                f"{float(judge_result.get('confidence', 0)):.2f} | {reason} |"
            )
    else:
        lines.append("| - | - | - | - | 0.00 | Judge LLM was not enabled for this run. |")
    summary_path = output_dir / "rule-extraction-v1-layered-evaluation-summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def run_research_dry_run(dataset: str, output_dir: Path, arms: list[str] | None = None, experiments: list[str] | None = None, chunk_strategies: list[str] | None = None) -> dict[str, Any]:
    dataset_dir = _dataset_dir(dataset)
    docs = load_dataset_documents(dataset_dir, _source_root())
    output_dir.mkdir(parents=True, exist_ok=True)
    arms = arms or list(COMPARATOR_ARMS)
    experiments = experiments or [experiment.experiment_id for experiment in EXPERIMENT_MATRIX]
    chunk_strategies = chunk_strategies or ["raw_card", "extractable_content"]
    chunking_report = build_chunking_report(dataset_dir, _source_root(), chunk_strategies)
    (output_dir / "rule-extraction-v1-chunking-report.json").write_text(json.dumps(chunking_report, ensure_ascii=False, indent=2), encoding="utf-8")

    observations: list[dict[str, Any]] = []
    for experiment_id in experiments:
        for arm_id in arms:
            variant = "extractable_content" if arm_id in {"C2", "C4", "C5", "C6", "C7"} else "raw_card"
            for doc in docs[:2]:
                text = doc.content_raw
                comparator_input = ComparatorInput(experiment_id, arm_id, dataset, doc.doc_id, variant, text, doc.metadata.get("source_card_hash", ""), tuple(chunk.metadata.get("chunk_hash", "") for chunk in doc.chunks))
                observations.append(run_comparator_arm(comparator_input))

    gold = _load_gold(dataset_dir)
    evaluations = []
    for gold_row in gold:
        doc_observations = [row for row in observations if row["doc_id"] == gold_row.get("doc_id")]
        extracted = doc_observations[0]["parsed_rules"] if doc_observations else []
        evaluations.append(evaluate_rule(gold_row, extracted))
    stability = summarize_stability(observations[: min(10, len(observations))])
    candidates = []
    for observation in observations:
        for rule in observation.get("parsed_rules", []):
            rule_identity = canonical_rule_identity(rule)
            candidates.append({**rule, "rule_identity": rule_identity, "status": "machine_observed"})
    conflicts = detect_conflicts(candidates)
    registry = ResearchRegistry(output_dir / "rule-extraction-v1-research-registry.jsonl")
    snapshot_id = registry.create_snapshot(dataset, "dry-run", candidates, source_hashes=snapshot_source_hashes(docs), observation_ids=[row["run_id"] for row in observations], stability_summary=stability, conflict_summary={"conflicts": conflicts})
    registry.export_report(output_dir / "rule-extraction-v1-research-registry-report.md")

    reports = {
        "doc-rule-agent-benchmark-portfolio-report.json": {"dataset_id": dataset, "benchmarks": [item.__dict__ for item in BENCHMARK_PORTFOLIO], "rows": [item.benchmark_id for item in BENCHMARK_PORTFOLIO]},
        "doc-rule-agent-transfer-gap-report.json": {"dataset_id": dataset, "rows": [{"gap": "target_nutrition_numeric_thresholds", "source": "dry_run"}]},
        "rule-extraction-v1-experiment-matrix-report.json": {"dataset_id": dataset, "experiments": [item.__dict__ for item in EXPERIMENT_MATRIX], "benchmark_experiments": [item.__dict__ for item in BENCHMARK_EXPERIMENT_MATRIX], "observations": observations},
        "rule-extraction-v1-observation-coverage-report.json": {"dataset_id": dataset, "observation_points": OBSERVATION_POINTS, "covered": sorted({point for row in observations for point in row.get("observation_points", {})}), "rows": observations[:5]},
        "rule-extraction-v1-field-evaluation-report.json": {"dataset_id": dataset, "evaluations": evaluations, "summary": precision_recall_f1(evaluations), "rows": evaluations},
        "rule-extraction-v1-stability-report.json": {"dataset_id": dataset, "summary": stability, "runs": observations[:10], "rows": observations[:10]},
    }
    for filename, data in reports.items():
        (output_dir / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_reports(output_dir, dataset, snapshot_id, reports, chunking_report)
    return {"dataset_id": dataset, "observation_count": len(observations), "snapshot_id": snapshot_id}


def run_research_real_run(
    dataset: str,
    output_dir: Path,
    llm_provider=None,
    judge_provider=None,
    judge_max_rules: int | None = None,
    arms: list[str] | None = None,
    experiments: list[str] | None = None,
    max_docs: int | None = None,
    max_empty_retries: int = 2,
    inter_doc_delay_seconds: float = 0.0,
    append_observations: bool = False,
    resume: bool = False,
    checkpoint_path: str | Path | None = None,
    circuit_breaker_failures: int = 5,
    circuit_breaker_cooldown_seconds: float = 300.0,
) -> dict[str, Any]:
    _load_default_dotenv()
    dataset_dir = _dataset_dir(dataset)
    gold_rows = _load_gold(dataset_dir)
    manifest_rows = _read_jsonl(dataset_dir / "manifest.jsonl")
    source_text_bundle = _load_source_text_bundle(manifest_rows)
    docs = load_dataset_documents(dataset_dir, _source_root())
    if max_docs is not None:
        docs = docs[:max_docs]
    output_dir.mkdir(parents=True, exist_ok=True)
    arms = arms or ["C1", "C2"]
    experiments = experiments or ["E1"]
    if llm_provider is None:
        llm_provider = _build_default_extraction_provider()
    baseline_rule_pack = load_baseline_rule_pack()
    concept_registry_path = dataset_dir / "concept_registry.jsonl"
    extra_concept_definitions = load_concept_definitions_from_jsonl(
        concept_registry_path,
        include_statuses=EXPERIMENT_CONCEPT_STATUSES,
    )
    extractor_registry = merge_concept_definitions(
        baseline_rule_pack.concepts,
        extra_concept_definitions,
    )
    concept_coverage = audit_concept_coverage(
        manifest_rows=manifest_rows,
        gold_rows=gold_rows,
        registry=extractor_registry,
    )
    extractor = RuleExtractor(llm_provider, extractor_registry)
    checkpoint = (
        RunCheckpoint(Path(checkpoint_path))
        if resume and checkpoint_path
        else None
    )
    circuit_breaker = CircuitBreaker(
        failure_threshold=circuit_breaker_failures,
        cooldown_seconds=circuit_breaker_cooldown_seconds,
    )

    observations: list[dict[str, Any]] = []
    operational_failures: list[dict[str, Any]] = []
    observation_path = dataset_dir / "extraction_observations.jsonl"
    for experiment_id in experiments:
        for arm_id in arms:
            source_content_strategy = ARM_SOURCE_CONTENT_STRATEGIES.get(arm_id, EXTRACTABLE_CONTENT)
            importer = DocumentImporter()
            for doc in docs:
                if checkpoint is not None and checkpoint.is_completed(experiment_id, arm_id, doc.doc_id):
                    continue
                if circuit_breaker.should_pause(now_seconds=time.monotonic()):
                    time.sleep(circuit_breaker_cooldown_seconds)
                raw_text = Path(doc.source).read_text(encoding="utf-8")
                selected = select_document_content(raw_text, source_content_strategy)
                selected_doc = importer.import_from_text(
                    doc.doc_id,
                    doc.title,
                    doc.source,
                    doc.source_type,
                    selected,
                    doc.metadata,
                    doc.ingested_at,
                    chunk_strategy=source_content_strategy,
                )
                started = datetime.now(timezone.utc)
                empty_retries = 0
                while True:
                    try:
                        result = extractor.extract_and_validate(
                            selected_doc.chunks,
                            candidate_id_prefix=f"{experiment_id}-{arm_id}-{doc.doc_id}",
                            max_retries=1,
                        )
                        parsed_rules = [_rule_to_dict(rule) for rule in result.rules]
                        suggested = [_suggestion_to_dict(item) for item in result.suggested_concepts]
                        failures = list(result.extraction_errors)
                        parse_status = "parsed"
                        finish_reason = "stop"
                        circuit_breaker.record_success()
                    except Exception as exc:
                        parsed_rules = []
                        suggested = []
                        failure_label = f"provider_error:{type(exc).__name__}:{exc}"
                        failure_class = classify_provider_failure(failure_label)
                        failures = [failure_label, f"provider_failure_class:{failure_class}"]
                        parse_status = "provider_error"
                        finish_reason = "error"
                        circuit_breaker.record_failure(now_seconds=time.monotonic())
                        break
                    if parsed_rules or suggested or empty_retries >= max_empty_retries:
                        break
                    empty_retries += 1
                latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
                raw_payload = {"parsed_rules": parsed_rules, "suggested_concepts": suggested, "failures": failures}
                comparator_input = ComparatorInput(
                    experiment_id=experiment_id,
                    arm_id=arm_id,
                    dataset_id=dataset,
                    doc_id=doc.doc_id,
                    input_variant=source_content_strategy,
                    text=selected,
                    source_card_hash=doc.metadata.get("source_card_hash", ""),
                    chunk_hashes=tuple(chunk.metadata.get("chunk_hash", "") for chunk in selected_doc.chunks),
                )
                if _is_operational_llm_failure(failures, parsed_rules, suggested):
                    provider_failure_class = next(
                        (
                            failure_label.removeprefix("provider_failure_class:")
                            for failure_label in failures
                            if str(failure_label).startswith("provider_failure_class:")
                        ),
                        classify_provider_failure(str(failures[0])) if failures else "provider_error",
                    )
                    operational_failures.append(
                        {
                            "experiment_id": experiment_id,
                            "arm_id": arm_id,
                            "dataset_id": dataset,
                            "doc_id": doc.doc_id,
                            "input_variant": source_content_strategy,
                            "source_content_strategy": source_content_strategy,
                            "latency_ms": latency_ms,
                            "failures": failures,
                            "provider_failure_class": provider_failure_class,
                            "parse_status": parse_status,
                            "finish_reason": finish_reason,
                            "excluded_from_research": True,
                            "exclusion_reason": "llm_api_operational_failure",
                        }
                    )
                    continue
                base = run_comparator_arm(comparator_input)
                observation = {
                    **base,
                    "extractor_name": "real_two_stage_rule_extractor",
                    "model": getattr(getattr(llm_provider, "config", None), "model", None) or "injected-provider",
                    "provider": getattr(getattr(llm_provider, "config", None), "provider", None) or getattr(llm_provider, "name", "injected"),
                    "latency_ms": latency_ms,
                    "empty_retry_count": empty_retries,
                    "finish_reason": finish_reason,
                    "parse_status": parse_status,
                    "source_content_strategy": source_content_strategy,
                    "parsed_rules": parsed_rules,
                    "suggested_concepts": suggested,
                    "raw_output_hash": run_comparator_arm(comparator_input, provider=None)["raw_output_hash"],
                    "observation_points": {
                        **base["observation_points"],
                        "O6": {**base["observation_points"]["O6"], "provider": "real_llm", "latency_ms": latency_ms, "empty_output": not bool(parsed_rules or suggested), "empty_retries": empty_retries},
                        "O8": {"parsed_rule_count": len(parsed_rules), "suggested_concept_count": len(suggested)},
                    },
                    "failures": failures
                    if failures
                    else (
                        []
                        if parsed_rules or suggested
                        else _research_failure_labels_for_empty_extraction(
                            doc_id=doc.doc_id,
                            gold_rows=gold_rows,
                        )
                    ),
                }
                observation["raw_output_hash"] = "sha256:" + __import__("hashlib").sha256(json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                observations.append(observation)
                if append_observations:
                    append_observation(observation_path, observation)
                if checkpoint is not None:
                    checkpoint.record_completed(experiment_id, arm_id, doc.doc_id)
                if inter_doc_delay_seconds > 0:
                    time.sleep(inter_doc_delay_seconds)

    layer_0_1_summary = _attach_layer_0_1_evaluations(
        observations,
        manifest_rows,
        source_text_bundle,
    )
    stability = summarize_stability(observations)
    evaluations = _evaluate_observations_against_gold(dataset_dir, observations)
    evaluation_summary = _summarize_evaluations(evaluations)
    judge_call_limit = None
    if judge_provider is not None and judge_max_rules == 0:
        judge_observations = []
        judge_call_limit = 0
    elif judge_provider is not None and judge_max_rules is not None:
        judge_observations = _select_judge_calibration_observations(
            observations=observations,
            evaluations=evaluations,
            max_cases=judge_max_rules,
        )
    else:
        judge_observations = observations
    judge_sampling = {
        "strategy": "stratified_by_gold_outcome" if judge_provider is not None and judge_max_rules != 0 else "not_run",
        "requested_max_cases": judge_max_rules,
        "selected_observation_count": len(judge_observations) if judge_provider is not None else 0,
    }
    layer_2_judge = _attach_layer_2_judge_evaluations(
        judge_observations,
        dataset_dir,
        source_text_bundle,
        judge_provider,
        evaluations,
        judge_call_limit,
    )
    golden_eval_accuracy = write_golden_eval_accuracy_artifacts(
        output_dir=output_dir,
        dataset_id=dataset,
        run_type="real_llm",
        evaluations=evaluations,
        layer_summaries={**layer_0_1_summary, "layer_2_judge": layer_2_judge},
    )
    suggested_concept_summary = _summarize_suggested_concepts(observations)
    report = {
        "dataset_id": dataset,
        "run_type": "real_llm",
        "model": observations[0]["model"] if observations else "",
        "provider": observations[0]["provider"] if observations else "",
        "judge_model": getattr(getattr(judge_provider, "config", None), "model", None) if judge_provider else "",
        "judge_provider": getattr(getattr(judge_provider, "config", None), "provider", None) if judge_provider else "",
        "requested_max_docs": max_docs,
        "effective_document_count": len(docs),
        "max_empty_retries": max_empty_retries,
        "inter_doc_delay_seconds": inter_doc_delay_seconds,
        "resume": resume,
        "checkpoint_path": str(checkpoint_path or ""),
        "circuit_breaker_failures": circuit_breaker_failures,
        "circuit_breaker_cooldown_seconds": circuit_breaker_cooldown_seconds,
        "source_text_diagnostics": source_text_bundle.diagnostics,
        "concept_registry_paths": [str(concept_registry_path)] if concept_registry_path.exists() else [],
        "concept_registry_included_statuses": [status.value for status in EXPERIMENT_CONCEPT_STATUSES],
        "concept_registry_extra_count": len(extra_concept_definitions),
        "concept_coverage": concept_coverage,
        "observation_count": len(observations),
        "operational_failure_count": len(operational_failures),
        "operational_failure_summary": _summarize_operational_failures(operational_failures),
        "paired_arm_summary": _summarize_paired_arm_rule_presence(
            observations,
            left_arm="C1",
            right_arm="C2",
        ),
        "numeric_limit_summary": _summarize_numeric_limit_failures(evaluations),
        "judge_sampling": judge_sampling,
        "evaluation_summary": evaluation_summary,
        "golden_eval_accuracy": golden_eval_accuracy,
        **layer_0_1_summary,
        "layer_2_judge": layer_2_judge,
        "evaluations": evaluations,
        "suggested_concept_summary": suggested_concept_summary,
        "observations": observations,
        "operational_failures": operational_failures,
        "stability": stability,
        "rows": observations,
    }
    (output_dir / "rule-extraction-v1-real-llm-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    evaluation_report_path = output_dir / "rule-extraction-v1-real-llm-field-evaluation-report.json"
    evaluation_report_path.write_text(
        json.dumps(
            {
                "dataset_id": dataset,
                "run_type": "real_llm_field_evaluation",
                "summary": evaluation_summary,
                "evaluations": evaluations,
                "rows": evaluations,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    visual_summary_path = _write_real_llm_visual_summary(output_dir, report, evaluation_summary)
    layered_summary_path = _write_layered_evaluation_summary(output_dir, report)
    return {
        "dataset_id": dataset,
        "observation_count": len(observations),
        "operational_failure_count": len(operational_failures),
        "evaluated_record_count": len(evaluations),
        "report_path": str(output_dir / "rule-extraction-v1-real-llm-report.json"),
        "evaluation_report_path": str(evaluation_report_path),
        "golden_eval_accuracy_report_path": golden_eval_accuracy["report_path"],
        "golden_eval_accuracy_chart_path": golden_eval_accuracy["chart_path"],
        "visual_summary_path": str(visual_summary_path),
        "layered_summary_path": str(layered_summary_path),
    }


def _write_markdown_reports(output_dir: Path, dataset: str, snapshot_id: str, reports: dict[str, Any], chunking_report: dict[str, Any]) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    (output_dir / "doc-rule-agent-error-taxonomy.md").write_text(
        "\n".join(["# DocRule-Agent Error Taxonomy", "", f"- run id: dry-run", f"- dataset id: {dataset}", "- model: fake", "- prompt version: dry-run-v1", f"- timestamp: {timestamp}", "", "## Categories", "", "- invalid JSON", "- condition omission", "- exclusion omission", "- tag omission", "- numeric limit omission", "- incorrect numeric threshold", "- unsupported nutrition concept", "- evidence quote drift", "- source-card chunk contamination", "- cross-run instability", "- conflict requiring governance", ""]) ,
        encoding="utf-8",
    )
    summary_lines = [
        "# DocRule-Agent Experiment Summary",
        "",
        f"- run id: dry-run",
        f"- dataset id: {dataset}",
        "- model: fake",
        "- prompt version: dry-run-v1",
        f"- timestamp: {timestamp}",
        f"- registry snapshot: {snapshot_id}",
        "",
        "## Dataset Profile",
        "",
        f"- chunk rows: {len(chunking_report.get('rows', []))}",
        "",
        "## Lifecycle Benchmark Portfolio",
        "",
        f"- benchmarks: {len(BENCHMARK_PORTFOLIO)}",
        "",
        "## Comparator Arms",
        "",
        *[f"- {key}: {value}" for key, value in COMPARATOR_ARMS.items()],
        "",
        "## Observation Coverage",
        "",
        json.dumps(reports["rule-extraction-v1-observation-coverage-report.json"]["covered"], ensure_ascii=False),
        "",
        "## Failure Taxonomy Counts",
        "",
        "Dry-run observations preserve failure labels for later real-provider analysis.",
    ]
    (output_dir / "doc-rule-agent-experiment-summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def _build_legacy_chunking_report(
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
    _load_default_dotenv()
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


def _build_default_extraction_provider() -> OpenAICompatibleLLMProvider:
    return OpenAICompatibleLLMProvider(LLMConfig.from_env(prefix="MEDIDIET_LLM_"))


def _build_default_judge_provider() -> OpenAICompatibleLLMProvider:
    return OpenAICompatibleLLMProvider(
        LLMConfig.from_env(
            prefix="MEDIDIET_JUDGE_LLM_",
            fallback_prefix="MEDIDIET_LLM_",
        )
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="rule_extraction_v1")
    parser.add_argument("--benchmark-portfolio", default="")
    parser.add_argument("--experiment-matrix", default="")
    parser.add_argument("--benchmark-experiments", default="")
    parser.add_argument("--experiments", default="")
    parser.add_argument("--arms", default="")
    parser.add_argument("--chunk-strategies", default="raw_card,extractable_content")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--real-llm", action="store_true")
    parser.add_argument("--discover-concepts", action="store_true")
    parser.add_argument("--judge-llm", action="store_true")
    parser.add_argument(
        "--judge-max-rules",
        type=int,
        default=20,
        help="Maximum extracted rules to evaluate with Judge LLM when --judge-llm is set; use 0 to skip judge calls.",
    )
    parser.add_argument("--append-observations", action="store_true")
    parser.add_argument("--write-reports", action="store_true")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "reports"))
    parser.add_argument(
        "--max-docs",
        type=int,
        default=0,
        help="Maximum source documents to run in real-LLM mode; use 0 for all documents.",
    )
    parser.add_argument(
        "--max-empty-retries",
        type=int,
        default=2,
        help="Retry extraction up to N times when LLM returns empty rules and no suggested concepts.",
    )
    parser.add_argument(
        "--inter-doc-delay-seconds",
        type=float,
        default=5.0,
        help="Seconds to sleep after each successful observation in real-LLM mode.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip completed experiment/arm/doc rows from checkpoint.")
    parser.add_argument("--checkpoint-path", default="", help="JSONL checkpoint path for real-LLM runs.")
    parser.add_argument("--circuit-breaker-failures", type=int, default=5)
    parser.add_argument("--circuit-breaker-cooldown-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    arms = [item for item in args.arms.split(",") if item] or None
    experiments = [item for item in args.experiments.split(",") if item] or None
    strategies = [item for item in args.chunk_strategies.split(",") if item] or None
    max_docs = None if args.max_docs <= 0 else args.max_docs
    if args.discover_concepts:
        _load_default_dotenv()
        run_concept_discovery_report(
            args.dataset,
            Path(args.output_dir),
            provider=_build_default_extraction_provider(),
            max_docs=max_docs,
        )
    elif args.real_llm:
        judge_provider = None
        if args.judge_llm:
            _load_default_dotenv()
            judge_provider = _build_default_judge_provider()
        run_research_real_run(
            args.dataset,
            Path(args.output_dir),
            judge_provider=judge_provider,
            judge_max_rules=args.judge_max_rules if args.judge_llm else None,
            arms=arms,
            experiments=experiments,
            max_docs=max_docs,
            max_empty_retries=args.max_empty_retries,
            inter_doc_delay_seconds=args.inter_doc_delay_seconds,
            append_observations=args.append_observations,
            resume=args.resume,
            checkpoint_path=args.checkpoint_path,
            circuit_breaker_failures=args.circuit_breaker_failures,
            circuit_breaker_cooldown_seconds=args.circuit_breaker_cooldown_seconds,
        )
    else:
        run_research_dry_run(args.dataset, Path(args.output_dir), arms=arms, experiments=experiments, chunk_strategies=strategies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
