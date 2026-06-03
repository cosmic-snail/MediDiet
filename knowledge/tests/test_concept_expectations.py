from __future__ import annotations

import json
from pathlib import Path

from medidiet.domain import CodeKind, ConceptCode


DATASET_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "datasets" / "rule_extraction_v1"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_concept_expectations_cover_schema_gap_gold_rows():
    audit_rows = _read_jsonl(DATASET_DIR / "gold_audit.jsonl")
    expectation_rows = _read_jsonl(DATASET_DIR / "concept_expectations.jsonl")
    schema_gap_gold_ids = {
        audit_row["gold_id"]
        for audit_row in audit_rows
        if audit_row["evidence_level"] == "schema_gap"
        and audit_row["audit_status"] == "revise_schema_or_gold"
    }
    expectation_gold_ids = {expectation_row["gold_id"] for expectation_row in expectation_rows}

    assert expectation_gold_ids == schema_gap_gold_ids


def test_concept_expectations_use_atomic_product_concepts():
    expectation_rows = _read_jsonl(DATASET_DIR / "concept_expectations.jsonl")
    for expectation_row in expectation_rows:
        assert expectation_row["track"] == "concept_discovery"
        assert expectation_row["expected_atomic_concepts"]
        seen_concept_codes: set[tuple[str, str]] = set()
        for concept_record in expectation_row["expected_atomic_concepts"]:
            kind = CodeKind(concept_record["kind"])
            code = ConceptCode(kind, concept_record["value"])
            concept_key = (code.kind.value, code.value)
            assert concept_key not in seen_concept_codes
            seen_concept_codes.add(concept_key)
            assert concept_record["aliases"]
        for umbrella_code in expectation_row.get("do_not_score_as", []):
            assert umbrella_code not in {value for _, value in seen_concept_codes}


def test_concept_expectations_define_linking_and_umbrella_layers():
    expectation_rows = _read_jsonl(DATASET_DIR / "concept_expectations.jsonl")
    for expectation_row in expectation_rows:
        atomic_concept_keys = {
            (concept_record["kind"], concept_record["value"])
            for concept_record in expectation_row["expected_atomic_concepts"]
        }
        assert expectation_row["semantic_groups"]
        for semantic_group in expectation_row["semantic_groups"]:
            canonical = semantic_group["canonical"]
            assert (canonical["kind"], canonical["value"]) in atomic_concept_keys
            assert semantic_group["equivalent_values"]
        assert expectation_row["umbrella_mappings"]
        for umbrella_mapping in expectation_row["umbrella_mappings"]:
            assert umbrella_mapping["umbrella_value"]
            mapped_atomic_keys = {
                (concept_record["kind"], concept_record["value"])
                for concept_record in umbrella_mapping["maps_to"]
            }
            assert mapped_atomic_keys <= atomic_concept_keys
            assert mapped_atomic_keys
