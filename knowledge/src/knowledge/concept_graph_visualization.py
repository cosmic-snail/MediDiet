from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any


def build_extracted_concept_graph(
    *,
    dataset_id: str,
    run_type: str,
    extracted_rules: list[dict[str, Any]],
    concept_expectations: list[dict[str, Any]],
) -> dict[str, Any]:
    graph = _empty_graph(dataset_id, run_type, "extracted_concept_graph")
    canonical_by_surface_form = _build_canonical_surface_map(concept_expectations)
    umbrella_mappings = _build_umbrella_mappings(concept_expectations)
    for extracted_rule in extracted_rules:
        for concept_record in extracted_rule.get("suggested_concepts", []) or []:
            kind, raw_value = _concept_kind_and_value(concept_record)
            normalized_value = _normalize_surface_value(raw_value)
            canonical_key = canonical_by_surface_form.get((kind, normalized_value))
            if canonical_key is not None:
                alias_node_id = f"alias:{normalized_value}"
                atomic_node_id = _concept_node_id(*canonical_key)
                _add_node(graph, alias_node_id, raw_value, "alias")
                _add_node(
                    graph,
                    atomic_node_id,
                    canonical_key[1],
                    "atomic_concept",
                    kind=canonical_key[0],
                    status="matched",
                )
                _add_edge(graph, alias_node_id, atomic_node_id, "same_as")
                continue
            if normalized_value in umbrella_mappings:
                umbrella_node_id = f"umbrella:{normalized_value}"
                _add_node(graph, umbrella_node_id, normalized_value, "umbrella_concept", status="decomposed")
                for child_key in sorted(umbrella_mappings[normalized_value]):
                    child_node_id = _concept_node_id(*child_key)
                    _add_node(
                        graph,
                        child_node_id,
                        child_key[1],
                        "atomic_concept",
                        kind=child_key[0],
                        status="mapped_from_umbrella",
                    )
                    _add_edge(graph, umbrella_node_id, child_node_id, "contains")
                continue
            candidate_node_id = f"candidate:{kind}:{normalized_value}"
            _add_node(graph, candidate_node_id, raw_value, "extracted_candidate", kind=kind, status="unmatched")
    return _dedupe_graph(graph)


def build_evaluation_concept_graph(
    *,
    dataset_id: str,
    run_type: str,
    concept_expectations: list[dict[str, Any]],
    concept_evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    graph = _empty_graph(dataset_id, run_type, "evaluation_concept_graph")
    matched_keys = {
        (str(concept_record["kind"]), str(concept_record["value"]))
        for concept_evaluation in concept_evaluations
        for concept_record in concept_evaluation.get("matched_concepts", []) or []
    }
    missing_keys = {
        (str(concept_record["kind"]), str(concept_record["value"]))
        for concept_evaluation in concept_evaluations
        for concept_record in concept_evaluation.get("missing_concepts", []) or []
    }
    for concept_expectation in concept_expectations:
        for concept_record in concept_expectation.get("expected_atomic_concepts", []) or []:
            key = (str(concept_record["kind"]), str(concept_record["value"]))
            status = "matched" if key in matched_keys else "missing" if key in missing_keys else "expected"
            _add_node(graph, _concept_node_id(*key), key[1], "atomic_concept", kind=key[0], status=status)
            if status == "missing":
                missing_node_id = f"missing:{key[0]}:{key[1]}"
                _add_node(graph, missing_node_id, f"missing {key[1]}", "missing_marker", status="missing")
                _add_edge(graph, _concept_node_id(*key), missing_node_id, "missing_expected")
            for alias in concept_record.get("aliases", []) or []:
                alias_node_id = f"alias:{_normalize_surface_value(alias)}"
                _add_node(graph, alias_node_id, str(alias), "alias")
                _add_edge(graph, alias_node_id, _concept_node_id(*key), "same_as")
        for semantic_group in concept_expectation.get("semantic_groups", []) or []:
            canonical = semantic_group["canonical"]
            canonical_key = (str(canonical["kind"]), str(canonical["value"]))
            for equivalent_value in semantic_group.get("equivalent_values", []) or []:
                alias_node_id = f"alias:{_normalize_surface_value(equivalent_value)}"
                _add_node(graph, alias_node_id, str(equivalent_value), "alias")
                _add_edge(graph, alias_node_id, _concept_node_id(*canonical_key), "same_as")
        for umbrella_mapping in concept_expectation.get("umbrella_mappings", []) or []:
            umbrella_value = _normalize_surface_value(umbrella_mapping["umbrella_value"])
            umbrella_node_id = f"umbrella:{umbrella_value}"
            _add_node(graph, umbrella_node_id, umbrella_value, "umbrella_concept", status="decomposed")
            for concept_record in umbrella_mapping.get("maps_to", []) or []:
                child_key = (str(concept_record["kind"]), str(concept_record["value"]))
                _add_edge(graph, umbrella_node_id, _concept_node_id(*child_key), "contains")
    return _dedupe_graph(graph)


def write_concept_graph_artifacts(
    *,
    output_dir: Path,
    extracted_graph: dict[str, Any],
    evaluation_graph: dict[str, Any],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_json_path = output_dir / "rule-extraction-v1-extracted-concept-graph.json"
    extracted_png_path = output_dir / "rule-extraction-v1-extracted-concept-graph.png"
    evaluation_json_path = output_dir / "rule-extraction-v1-evaluation-concept-graph.json"
    evaluation_png_path = output_dir / "rule-extraction-v1-evaluation-concept-graph.png"
    _write_graph_json(extracted_json_path, extracted_graph)
    _write_graph_json(evaluation_json_path, evaluation_graph)
    _render_graph_png(extracted_png_path, extracted_graph)
    _render_graph_png(evaluation_png_path, evaluation_graph)
    return {
        "extracted_concept_graph_json": str(extracted_json_path),
        "extracted_concept_graph_png": str(extracted_png_path),
        "evaluation_concept_graph_json": str(evaluation_json_path),
        "evaluation_concept_graph_png": str(evaluation_png_path),
    }


def _empty_graph(dataset_id: str, run_type: str, graph_type: str) -> dict[str, Any]:
    return {"dataset_id": dataset_id, "run_type": run_type, "graph_type": graph_type, "nodes": [], "edges": []}


def _concept_kind_and_value(concept_record: Any) -> tuple[str, str]:
    if isinstance(concept_record, dict):
        kind = str(concept_record.get("kind") or concept_record.get("suggested_kind") or "nutrition_tag")
        raw_value = str(concept_record.get("suggested_code") or concept_record.get("value") or "")
        return kind, raw_value
    return "nutrition_tag", str(concept_record)


def _concept_node_id(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def _add_node(graph: dict[str, Any], node_id: str, label: str, node_type: str, **extra: Any) -> None:
    graph["nodes"].append({"id": node_id, "label": label, "node_type": node_type, **extra})


def _add_edge(graph: dict[str, Any], source: str, target: str, edge_type: str) -> None:
    graph["edges"].append({"source": source, "target": target, "edge_type": edge_type})


def _dedupe_graph(graph: dict[str, Any]) -> dict[str, Any]:
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    edge_keys = {(edge["source"], edge["target"], edge["edge_type"]) for edge in graph["edges"]}
    return {
        **graph,
        "nodes": sorted(nodes_by_id.values(), key=lambda node: node["id"]),
        "edges": [
            {"source": source, "target": target, "edge_type": edge_type}
            for source, target, edge_type in sorted(edge_keys)
        ],
    }


def _write_graph_json(path: Path, graph: dict[str, Any]) -> None:
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_graph_png(path: Path, graph: dict[str, Any]) -> None:
    if _render_graph_with_matplotlib(path, graph):
        return
    _render_graph_with_pillow(path, graph)


def _render_graph_with_matplotlib(path: Path, graph: dict[str, Any]) -> bool:
    try:
        os.environ.setdefault("MPLCONFIGDIR", str(path.parent / ".matplotlib"))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
    except Exception:
        return False

    network = nx.DiGraph()
    for node in graph["nodes"]:
        network.add_node(node["id"], **node)
    for edge in graph["edges"]:
        network.add_edge(edge["source"], edge["target"], edge_type=edge["edge_type"])
    plt.figure(figsize=(max(8, len(network.nodes) * 0.55), 6))
    if network.nodes:
        positions = nx.spring_layout(network, seed=17)
        node_colors = [_node_color(network.nodes[node]) for node in network.nodes]
        nx.draw_networkx_nodes(network, positions, node_color=node_colors, node_size=1600)
        nx.draw_networkx_edges(network, positions, arrows=True, arrowstyle="-|>", width=1.4)
        nx.draw_networkx_labels(
            network,
            positions,
            labels={node: network.nodes[node].get("label", node) for node in network.nodes},
            font_size=8,
        )
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()
    return True


def _render_graph_with_pillow(path: Path, graph: dict[str, Any]) -> None:
    from PIL import Image, ImageDraw

    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    node_width = 420
    node_height = 38
    width = 1200
    height = max(360, 120 + len(nodes) * 52 + len(edges) * 26)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 20), f"{graph.get('graph_type', 'concept_graph')} ({graph.get('run_type', '')})", fill="#222222")

    node_boxes: dict[str, tuple[int, int, int, int]] = {}
    for index, node in enumerate(nodes):
        x = 48 + (index % 2) * 520
        y = 72 + (index // 2) * 82
        node_boxes[str(node["id"])] = (x, y, x + node_width, y + node_height)

    for edge in edges:
        source_box = node_boxes.get(str(edge["source"]))
        target_box = node_boxes.get(str(edge["target"]))
        if source_box is None or target_box is None:
            continue
        _draw_pillow_edge(draw, source_box, target_box, str(edge["edge_type"]))

    for node in nodes:
        x, y, right, bottom = node_boxes[str(node["id"])]
        color = _node_color(node)
        draw.rounded_rectangle((x, y, right, bottom), radius=8, fill=color, outline="#555555")
        label = str(node.get("label") or node["id"])[:46]
        draw.text((x + 12, y + 10), label, fill="#111111")

    edge_start_y = 72 + ((len(nodes) + 1) // 2) * 82 + 24
    for index, edge in enumerate(edges):
        y = edge_start_y + index * 24
        edge_label = f"{edge['source']} --{edge['edge_type']}--> {edge['target']}"
        draw.text((48, y), edge_label[:150], fill="#333333")

    image.save(path, format="PNG")


def _draw_pillow_edge(
    draw: Any,
    source_box: tuple[int, int, int, int],
    target_box: tuple[int, int, int, int],
    edge_type: str,
) -> None:
    source_center = ((source_box[0] + source_box[2]) // 2, (source_box[1] + source_box[3]) // 2)
    target_center = ((target_box[0] + target_box[2]) // 2, (target_box[1] + target_box[3]) // 2)
    start = _edge_endpoint(source_center, target_center, source_box)
    end = _edge_endpoint(target_center, source_center, target_box)
    color = "#555555" if edge_type == "same_as" else "#8a5a16"
    draw.line((start, end), fill=color, width=3)
    _draw_arrowhead(draw, start, end, color)
    midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
    draw.text((midpoint[0] - 24, midpoint[1] - 14), edge_type, fill=color)


def _edge_endpoint(
    from_center: tuple[int, int],
    to_center: tuple[int, int],
    box: tuple[int, int, int, int],
) -> tuple[int, int]:
    x0, y0 = from_center
    x1, y1 = to_center
    dx = x1 - x0
    dy = y1 - y0
    if dx == 0 and dy == 0:
        return from_center
    half_width = (box[2] - box[0]) / 2
    half_height = (box[3] - box[1]) / 2
    scale = min(half_width / abs(dx) if dx else float("inf"), half_height / abs(dy) if dy else float("inf"))
    return (int(x0 + dx * scale), int(y0 + dy * scale))


def _draw_arrowhead(
    draw: Any,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
) -> None:
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    arrow_length = 12
    arrow_angle = math.pi / 7
    points = [end]
    for direction in (angle + math.pi - arrow_angle, angle + math.pi + arrow_angle):
        points.append(
            (
                int(end[0] + arrow_length * math.cos(direction)),
                int(end[1] + arrow_length * math.sin(direction)),
            )
        )
    draw.polygon(points, fill=color)


def _node_color(node: dict[str, Any]) -> str:
    if node.get("status") == "matched":
        return "#94d3a2"
    if node.get("status") == "missing":
        return "#f2a0a0"
    if node.get("node_type") == "alias":
        return "#9cc9f5"
    if node.get("node_type") == "umbrella_concept":
        return "#f0bd74"
    return "#c8c8c8"


def _build_canonical_surface_map(
    concept_expectations: list[dict[str, Any]],
) -> dict[tuple[str, str], tuple[str, str]]:
    mapping: dict[tuple[str, str], tuple[str, str]] = {}
    for concept_expectation in concept_expectations:
        for concept_record in concept_expectation.get("expected_atomic_concepts", []) or []:
            key = (str(concept_record["kind"]), str(concept_record["value"]))
            mapping[(key[0], _normalize_surface_value(key[1]))] = key
            for alias in concept_record.get("aliases", []) or []:
                mapping[(key[0], _normalize_surface_value(alias))] = key
        for semantic_group in concept_expectation.get("semantic_groups", []) or []:
            canonical = semantic_group["canonical"]
            key = (str(canonical["kind"]), str(canonical["value"]))
            for equivalent_value in semantic_group.get("equivalent_values", []) or []:
                mapping[(key[0], _normalize_surface_value(equivalent_value))] = key
    return mapping


def _build_umbrella_mappings(concept_expectations: list[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    mappings: dict[str, set[tuple[str, str]]] = {}
    for concept_expectation in concept_expectations:
        for umbrella_mapping in concept_expectation.get("umbrella_mappings", []) or []:
            mappings[_normalize_surface_value(umbrella_mapping["umbrella_value"])] = {
                (str(concept_record["kind"]), str(concept_record["value"]))
                for concept_record in umbrella_mapping.get("maps_to", []) or []
            }
    return mappings


def _normalize_surface_value(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")
