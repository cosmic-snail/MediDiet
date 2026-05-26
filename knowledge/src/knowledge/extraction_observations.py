from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "experiment_id",
    "arm_id",
    "input_variant",
    "extractor_name",
    "provider",
    "temperature",
    "prompt_hash",
    "input_hash",
    "latency_ms",
    "finish_reason",
    "raw_output_hash",
    "parse_status",
    "observation_points",
}

FAILURE_LABELS = {
    "json_parse_error",
    "no_rule_extracted",
    "missing_numeric_limit",
    "unexpected_numeric_limit",
    "condition_mismatch",
    "suggested_concept_mismatch",
    "unstable_across_runs",
    "unsupported_metric_or_concept",
}


@dataclass(frozen=True)
class ExtractionObservation:
    run_id: str
    experiment_id: str
    arm_id: str
    dataset_id: str
    doc_id: str
    expected_id: str | None
    gold_id: str | None
    input_variant: str
    extractor_name: str
    model: str
    provider: str
    temperature: float
    prompt_version: str
    prompt_hash: str
    input_hash: str
    source_card_hash: str
    chunk_hashes: list[str]
    latency_ms: int
    retry_count: int
    finish_reason: str
    raw_output_hash: str
    raw_output_path: str
    parse_status: str
    parsed_rules: list[dict[str, Any]]
    suggested_concepts: list[dict[str, Any]]
    observation_points: dict[str, Any]
    evaluator: dict[str, Any]
    failures: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        missing = [field_name for field_name in REQUIRED_FIELDS if getattr(self, field_name) in (None, "")]
        if missing:
            raise ValueError(f"missing required observation fields: {', '.join(sorted(missing))}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_observation(path: Path, observation: ExtractionObservation | dict[str, Any]) -> None:
    row = observation.to_dict() if isinstance(observation, ExtractionObservation) else dict(observation)
    missing = [field_name for field_name in REQUIRED_FIELDS if row.get(field_name) in (None, "")]
    if missing:
        raise ValueError(f"missing required observation fields: {', '.join(sorted(missing))}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
