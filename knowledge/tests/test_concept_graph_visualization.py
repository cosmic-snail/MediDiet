from __future__ import annotations

import json
from pathlib import Path

from knowledge.concept_graph_visualization import (
    build_evaluation_concept_graph,
    build_extracted_concept_graph,
    write_concept_graph_artifacts,
)


def _sample_expectation() -> dict:
    return {
        "gold_id": "gold-gout",
        "doc_id": "gout-doc",
        "expected_atomic_concepts": [
            {
                "kind": "nutrition_tag",
                "value": "low_purine",
                "aliases": ["limit high-purine foods"],
            },
            {
                "kind": "contraindication",
                "value": "alcohol",
                "aliases": ["limit alcohol"],
            },
        ],
        "semantic_groups": [
            {
                "canonical": {"kind": "nutrition_tag", "value": "low_purine"},
                "equivalent_values": ["purine_restriction", "low_purine_diet"],
            }
        ],
        "umbrella_mappings": [
            {
                "umbrella_value": "purine_and_alcohol_limits",
                "maps_to": [
                    {"kind": "nutrition_tag", "value": "low_purine"},
                    {"kind": "contraindication", "value": "alcohol"},
                ],
            }
        ],
    }


def test_extracted_concept_graph_links_aliases_and_umbrella_children():
    extracted_rules = [
        {
            "doc_id": "gout-doc",
            "suggested_concepts": [
                {"kind": "nutrition_tag", "suggested_code": "purine_restriction"},
                {"kind": "nutrition_tag", "suggested_code": "purine_and_alcohol_limits"},
            ],
        }
    ]

    graph = build_extracted_concept_graph(
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        extracted_rules=extracted_rules,
        concept_expectations=[_sample_expectation()],
    )

    edge_pairs = {(edge["source"], edge["target"], edge["edge_type"]) for edge in graph["edges"]}
    assert ("alias:purine_restriction", "nutrition_tag:low_purine", "same_as") in edge_pairs
    assert ("umbrella:purine_and_alcohol_limits", "nutrition_tag:low_purine", "contains") in edge_pairs
    assert ("umbrella:purine_and_alcohol_limits", "contraindication:alcohol", "contains") in edge_pairs


def test_evaluation_concept_graph_marks_matched_and_missing_atomic_concepts():
    concept_evaluations = [
        {
            "gold_id": "gold-gout",
            "matched_concepts": [{"kind": "nutrition_tag", "value": "low_purine"}],
            "missing_concepts": [{"kind": "contraindication", "value": "alcohol"}],
            "forbidden_umbrella_matches": ["purine_and_alcohol_limits"],
        }
    ]

    graph = build_evaluation_concept_graph(
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        concept_expectations=[_sample_expectation()],
        concept_evaluations=concept_evaluations,
    )

    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    edge_pairs = {(edge["source"], edge["target"], edge["edge_type"]) for edge in graph["edges"]}
    assert nodes_by_id["nutrition_tag:low_purine"]["status"] == "matched"
    assert nodes_by_id["contraindication:alcohol"]["status"] == "missing"
    assert ("alias:limit_high_purine_foods", "nutrition_tag:low_purine", "same_as") in edge_pairs
    assert ("umbrella:purine_and_alcohol_limits", "contraindication:alcohol", "contains") in edge_pairs


def test_write_concept_graph_artifacts_writes_json_and_png(tmp_path: Path):
    extracted_graph = {
        "dataset_id": "rule_extraction_v1",
        "run_type": "real_llm",
        "graph_type": "extracted_concept_graph",
        "nodes": [
            {
                "id": "nutrition_tag:low_purine",
                "label": "low_purine",
                "node_type": "atomic_concept",
                "status": "matched",
            }
        ],
        "edges": [],
    }
    evaluation_graph = {
        "dataset_id": "rule_extraction_v1",
        "run_type": "real_llm",
        "graph_type": "evaluation_concept_graph",
        "nodes": [
            {
                "id": "nutrition_tag:low_purine",
                "label": "low_purine",
                "node_type": "atomic_concept",
                "status": "matched",
            }
        ],
        "edges": [],
    }

    artifact_paths = write_concept_graph_artifacts(
        output_dir=tmp_path,
        extracted_graph=extracted_graph,
        evaluation_graph=evaluation_graph,
    )

    assert Path(artifact_paths["extracted_concept_graph_json"]).exists()
    assert Path(artifact_paths["extracted_concept_graph_png"]).exists()
    assert Path(artifact_paths["evaluation_concept_graph_json"]).exists()
    assert Path(artifact_paths["evaluation_concept_graph_png"]).exists()
    saved_graph = json.loads(Path(artifact_paths["evaluation_concept_graph_json"]).read_text(encoding="utf-8"))
    assert saved_graph["graph_type"] == "evaluation_concept_graph"
