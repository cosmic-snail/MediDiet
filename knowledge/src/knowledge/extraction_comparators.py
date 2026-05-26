from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol


COMPARATOR_STRATEGIES = {
    "C0": "clean_synthetic_two_stage",
    "C1": "raw_card_current_two_stage",
    "C2": "extractable_content_current_two_stage",
    "C3": "source_notes_plus_extractable_current_two_stage",
    "C4": "one_shot_json",
    "C5": "two_stage_no_rejection",
    "C6": "two_stage_with_judge_observation",
    "C7": "self_consistency_aggregate",
    "C8": "manifest_free_directory_scan",
}


@dataclass(frozen=True)
class ComparatorInput:
    experiment_id: str
    arm_id: str
    dataset_id: str
    doc_id: str
    input_variant: str
    text: str
    source_card_hash: str
    chunk_hashes: tuple[str, ...]


class ExtractorProvider(Protocol):
    name: str

    def extract(self, text: str, arm_id: str) -> dict[str, Any]:
        ...


class FakeExtractorProvider:
    name = "fake"

    def __init__(self, response: dict[str, Any] | None = None):
        self.response = response or _fake_response_for_text("")

    def extract(self, text: str, arm_id: str) -> dict[str, Any]:
        return self.response if self.response != {} else {}


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fake_response_for_text(text: str) -> dict[str, Any]:
    lower = text.lower()
    if "sodium" in lower:
        return {"rules": [{"condition": "hypertension", "hard_exclusions": [], "preferred_tags": ["low_sodium"], "nutrition_limits": [{"metric": "sodium_mg", "scope": "daily", "max_value": 2000, "window_hours": 24}], "evidence_quote": "Adults should reduce sodium intake to less than 2 g/day."}], "suggested_concepts": []}
    if "sugar" in lower or "diabetes" in lower:
        return {"rules": [{"condition": "diabetes", "hard_exclusions": [], "preferred_tags": ["low_sugar"], "nutrition_limits": [{"metric": "sugar_g", "scope": "daily", "max_value": 25, "window_hours": 24}], "evidence_quote": "Limit added sugar to 25 g per day."}], "suggested_concepts": []}
    return {"rules": [], "suggested_concepts": []}


def run_comparator_arm(comparator_input: ComparatorInput, provider: ExtractorProvider | None = None) -> dict[str, Any]:
    provider = provider or FakeExtractorProvider(_fake_response_for_text(comparator_input.text))
    started = time.perf_counter()
    raw_response = provider.extract(comparator_input.text, comparator_input.arm_id)
    latency_ms = int((time.perf_counter() - started) * 1000)
    parsed_rules = raw_response.get("rules", []) if isinstance(raw_response, dict) else []
    suggested_concepts = raw_response.get("suggested_concepts", []) if isinstance(raw_response, dict) else []
    input_hash = _sha256_text(comparator_input.text)
    raw_output_hash = _sha256_json(raw_response)
    return {
        "run_id": _sha256_json({"experiment_id": comparator_input.experiment_id, "arm_id": comparator_input.arm_id, "doc_id": comparator_input.doc_id, "input_hash": input_hash, "raw_response": raw_response}),
        "experiment_id": comparator_input.experiment_id,
        "arm_id": comparator_input.arm_id,
        "dataset_id": comparator_input.dataset_id,
        "doc_id": comparator_input.doc_id,
        "expected_id": None,
        "gold_id": None,
        "input_variant": comparator_input.input_variant,
        "extractor_name": provider.name,
        "model": provider.name,
        "provider": provider.name,
        "temperature": 0.0,
        "prompt_version": f"{comparator_input.arm_id.lower()}-dry-run-v1",
        "prompt_hash": _sha256_text(comparator_input.arm_id),
        "input_hash": input_hash,
        "source_card_hash": comparator_input.source_card_hash,
        "chunk_hashes": list(comparator_input.chunk_hashes),
        "latency_ms": latency_ms,
        "retry_count": 0,
        "finish_reason": "stop",
        "raw_output_hash": raw_output_hash,
        "raw_output_path": "",
        "parse_status": "parsed",
        "parsed_rules": parsed_rules,
        "suggested_concepts": suggested_concepts,
        "observation_points": {
            "O5": {"arm_id": comparator_input.arm_id, "input_variant": comparator_input.input_variant, "input_hash": input_hash, "strategy": COMPARATOR_STRATEGIES.get(comparator_input.arm_id, "unknown")},
            "O6": {"provider": provider.name, "latency_ms": latency_ms, "retry_count": 0, "empty_output": not bool(raw_response)},
            "O8": {"parsed_rule_count": len(parsed_rules), "suggested_concept_count": len(suggested_concepts)},
        },
        "evaluator": {},
        "failures": [] if parsed_rules else ["no_rule_extracted"],
    }
