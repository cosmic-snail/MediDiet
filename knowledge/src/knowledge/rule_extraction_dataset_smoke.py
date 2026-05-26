from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medidiet.llm import LLMConfig, OpenAICompatibleLLMProvider
from medidiet.rules import load_baseline_rule_pack
from knowledge.dataset_manifest import load_dataset_documents, snapshot_source_hashes
from knowledge.documents import DocumentImporter, select_document_content
from knowledge.extraction_comparators import ComparatorInput, run_comparator_arm
from knowledge.extraction_experiments import BENCHMARK_EXPERIMENT_MATRIX, COMPARATOR_ARMS, EXPERIMENT_MATRIX, OBSERVATION_POINTS
from knowledge.extraction_observations import append_observation
from knowledge.extraction_stability import summarize_stability
from knowledge.extractor import RuleExtractor
from knowledge.public_benchmarks import BENCHMARK_PORTFOLIO
from knowledge.research_registry import ResearchRegistry
from knowledge.rule_evaluation import evaluate_rule, precision_recall_f1
from knowledge.rule_identity import canonical_rule_identity
from knowledge.source_governance import detect_conflicts


REPO_ROOT = Path(__file__).resolve().parents[3]

ARM_INPUT_VARIANTS = {
    "C1": "raw_card",
    "C2": "extractable_content",
    "C3": "source_notes_plus_extractable",
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


def build_chunking_report(dataset_dir: Path, source_root: Path, strategies: list[str] | None = None) -> dict[str, Any]:
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
    arms: list[str] | None = None,
    experiments: list[str] | None = None,
    max_docs: int | None = None,
    append_observations: bool = False,
) -> dict[str, Any]:
    _load_default_dotenv()
    dataset_dir = _dataset_dir(dataset)
    docs = load_dataset_documents(dataset_dir, _source_root())
    if max_docs is not None:
        docs = docs[:max_docs]
    output_dir.mkdir(parents=True, exist_ok=True)
    arms = arms or ["C1", "C2"]
    experiments = experiments or ["E1"]
    if llm_provider is None:
        llm_provider = OpenAICompatibleLLMProvider(LLMConfig.from_env())
    extractor = RuleExtractor(llm_provider, load_baseline_rule_pack().concepts)

    observations: list[dict[str, Any]] = []
    operational_failures: list[dict[str, Any]] = []
    observation_path = dataset_dir / "extraction_observations.jsonl"
    for experiment_id in experiments:
        for arm_id in arms:
            input_variant = ARM_INPUT_VARIANTS.get(arm_id, "extractable_content")
            importer = DocumentImporter()
            for doc in docs:
                raw_text = Path(doc.source).read_text(encoding="utf-8")
                selected = select_document_content(raw_text, input_variant)
                selected_doc = importer.import_from_text(
                    doc.doc_id,
                    doc.title,
                    doc.source,
                    doc.source_type,
                    selected,
                    doc.metadata,
                    doc.ingested_at,
                    chunk_strategy=input_variant,
                )
                started = datetime.now(timezone.utc)
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
                except Exception as exc:
                    parsed_rules = []
                    suggested = []
                    failures = [f"provider_error:{type(exc).__name__}"]
                    parse_status = "provider_error"
                    finish_reason = "error"
                latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
                raw_payload = {"parsed_rules": parsed_rules, "suggested_concepts": suggested, "failures": failures}
                comparator_input = ComparatorInput(
                    experiment_id=experiment_id,
                    arm_id=arm_id,
                    dataset_id=dataset,
                    doc_id=doc.doc_id,
                    input_variant=input_variant,
                    text=selected,
                    source_card_hash=doc.metadata.get("source_card_hash", ""),
                    chunk_hashes=tuple(chunk.metadata.get("chunk_hash", "") for chunk in selected_doc.chunks),
                )
                if _is_operational_llm_failure(failures, parsed_rules, suggested):
                    operational_failures.append(
                        {
                            "experiment_id": experiment_id,
                            "arm_id": arm_id,
                            "dataset_id": dataset,
                            "doc_id": doc.doc_id,
                            "input_variant": input_variant,
                            "latency_ms": latency_ms,
                            "failures": failures,
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
                    "finish_reason": finish_reason,
                    "parse_status": parse_status,
                    "parsed_rules": parsed_rules,
                    "suggested_concepts": suggested,
                    "raw_output_hash": run_comparator_arm(comparator_input, provider=None)["raw_output_hash"],
                    "observation_points": {
                        **base["observation_points"],
                        "O6": {**base["observation_points"]["O6"], "provider": "real_llm", "latency_ms": latency_ms, "empty_output": not bool(parsed_rules or suggested)},
                        "O8": {"parsed_rule_count": len(parsed_rules), "suggested_concept_count": len(suggested)},
                    },
                    "failures": failures if failures else ([] if parsed_rules else ["no_rule_extracted"]),
                }
                observation["raw_output_hash"] = "sha256:" + __import__("hashlib").sha256(json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                observations.append(observation)
                if append_observations:
                    append_observation(observation_path, observation)

    stability = summarize_stability(observations)
    report = {
        "dataset_id": dataset,
        "run_type": "real_llm",
        "model": observations[0]["model"] if observations else "",
        "provider": observations[0]["provider"] if observations else "",
        "observation_count": len(observations),
        "operational_failure_count": len(operational_failures),
        "observations": observations,
        "operational_failures": operational_failures,
        "stability": stability,
        "rows": observations,
    }
    (output_dir / "rule-extraction-v1-real-llm-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "dataset_id": dataset,
        "observation_count": len(observations),
        "operational_failure_count": len(operational_failures),
        "report_path": str(output_dir / "rule-extraction-v1-real-llm-report.json"),
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
    parser.add_argument("--append-observations", action="store_true")
    parser.add_argument("--write-reports", action="store_true")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "reports"))
    args = parser.parse_args(argv)
    arms = [item for item in args.arms.split(",") if item] or None
    experiments = [item for item in args.experiments.split(",") if item] or None
    strategies = [item for item in args.chunk_strategies.split(",") if item] or None
    if args.real_llm:
        run_research_real_run(
            args.dataset,
            Path(args.output_dir),
            arms=arms,
            experiments=experiments,
            max_docs=2,
            append_observations=args.append_observations,
        )
    else:
        run_research_dry_run(args.dataset, Path(args.output_dir), arms=arms, experiments=experiments, chunk_strategies=strategies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
