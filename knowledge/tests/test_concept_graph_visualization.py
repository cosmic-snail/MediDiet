from __future__ import annotations

import json
from pathlib import Path

from knowledge.concept_graph_visualization import (
    _build_graphviz_dot,
    _layout_pillow_node_boxes,
    _render_graph_with_pillow,
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


def test_pillow_fallback_draws_edge_lines_between_nodes(tmp_path: Path):
    graph = {
        "dataset_id": "rule_extraction_v1",
        "run_type": "real_llm",
        "graph_type": "extracted_concept_graph",
        "nodes": [
            {"id": "alias:low_purine", "label": "low_purine", "node_type": "alias"},
            {
                "id": "nutrition_tag:low_purine",
                "label": "low_purine",
                "node_type": "atomic_concept",
                "status": "matched",
            },
        ],
        "edges": [
            {
                "source": "alias:low_purine",
                "target": "nutrition_tag:low_purine",
                "edge_type": "same_as",
            }
        ],
    }
    output_path = tmp_path / "fallback-graph.png"

    _render_graph_with_pillow(output_path, graph)

    from PIL import Image

    image = Image.open(output_path)
    node_boxes = _layout_pillow_node_boxes(graph["nodes"], graph["edges"])
    source_box = node_boxes["alias:low_purine"]
    line_sample_x = source_box[2] + 24
    line_sample_y = (source_box[1] + source_box[3]) // 2
    assert image.getpixel((line_sample_x, line_sample_y)) != (251, 251, 248)


def test_graphviz_dot_uses_layered_knowledge_graph_styling():
    graph = {
        "dataset_id": "rule_extraction_v1",
        "run_type": "real_llm",
        "graph_type": "extracted_concept_graph",
        "nodes": [
            {"id": "alias:low_purine", "label": "low_purine", "node_type": "alias"},
            {"id": "umbrella:diet_limits", "label": "diet_limits", "node_type": "umbrella_concept"},
            {
                "id": "nutrition_tag:low_purine",
                "label": "low_purine",
                "node_type": "atomic_concept",
                "status": "matched",
            },
        ],
        "edges": [
            {
                "source": "alias:low_purine",
                "target": "nutrition_tag:low_purine",
                "edge_type": "same_as",
            },
            {
                "source": "umbrella:diet_limits",
                "target": "nutrition_tag:low_purine",
                "edge_type": "contains",
            },
        ],
    }

    dot_source = _build_graphviz_dot(graph)

    assert "rankdir=LR" in dot_source
    assert "splines=ortho" in dot_source
    assert '"alias:low_purine"' in dot_source
    assert 'label=""' in dot_source
    assert 'color="#9b6418"' in dot_source


def test_pillow_layout_places_graph_roles_in_columns_without_overlaps():
    nodes = [
        {"id": "alias:low_purine", "label": "low_purine", "node_type": "alias"},
        {"id": "umbrella:diet_limits", "label": "diet_limits", "node_type": "umbrella_concept"},
        {
            "id": "nutrition_tag:low_purine",
            "label": "low_purine",
            "node_type": "atomic_concept",
            "status": "matched",
        },
        {"id": "missing:nutrition_tag:sodium_limit", "label": "missing sodium_limit", "node_type": "missing_marker"},
    ]
    edges = [
        {"source": "alias:low_purine", "target": "nutrition_tag:low_purine", "edge_type": "same_as"},
        {"source": "umbrella:diet_limits", "target": "nutrition_tag:low_purine", "edge_type": "contains"},
        {
            "source": "nutrition_tag:low_purine",
            "target": "missing:nutrition_tag:sodium_limit",
            "edge_type": "missing_expected",
        },
    ]

    node_boxes = _layout_pillow_node_boxes(nodes, edges)

    assert node_boxes["alias:low_purine"][0] < node_boxes["umbrella:diet_limits"][0]
    assert node_boxes["umbrella:diet_limits"][0] < node_boxes["nutrition_tag:low_purine"][0]
    assert node_boxes["nutrition_tag:low_purine"][0] < node_boxes["missing:nutrition_tag:sodium_limit"][0]
    for node_id, node_box in node_boxes.items():
        other_boxes = {key: box for key, box in node_boxes.items() if key != node_id}
        assert all(not _boxes_overlap(node_box, other_box) for other_box in other_boxes.values())


def _boxes_overlap(first_box: tuple[int, int, int, int], second_box: tuple[int, int, int, int]) -> bool:
    return not (
        first_box[2] <= second_box[0]
        or second_box[2] <= first_box[0]
        or first_box[3] <= second_box[1]
        or second_box[3] <= first_box[1]
    )
