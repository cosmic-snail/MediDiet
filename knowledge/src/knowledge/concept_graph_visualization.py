from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_PILLOW_CANVAS_WIDTH = 1500
_PILLOW_NODE_WIDTH = 280
_PILLOW_NODE_HEIGHT = 38
_PILLOW_TOP_Y = 150
_PILLOW_ROW_GAP = 58
_PILLOW_GROUP_GAP = 34
_PILLOW_COLUMN_X_BY_ROLE = {
    "surface": 48,
    "umbrella": 430,
    "atomic": 810,
    "missing": 1190,
}
_PILLOW_ROLE_ORDER = ("surface", "umbrella", "atomic", "missing")


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
    if _render_graph_with_graphviz(path, graph):
        return
    if _render_graph_with_pillow(path, graph):
        return
    _render_graph_with_matplotlib(path, graph)


def _render_graph_with_graphviz(path: Path, graph: dict[str, Any]) -> bool:
    dot_binary_path = shutil.which("dot")
    if dot_binary_path is None:
        return False
    dot_source = _build_graphviz_dot(graph)
    try:
        subprocess.run(
            [dot_binary_path, "-Tpng", "-o", str(path)],
            input=dot_source,
            text=True,
            check=True,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        return False
    return path.exists() and path.stat().st_size > 0


def _build_graphviz_dot(graph: dict[str, Any]) -> str:
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    lines = [
        "digraph ConceptGraph {",
        '  graph [rankdir=LR, bgcolor="white", pad="0.35", nodesep="0.55", ranksep="1.15", splines=ortho, overlap=false, outputorder=edgesfirst];',
        '  node [shape=box, style="rounded,filled", fontname="Arial Unicode MS", fontsize=11, margin="0.12,0.07", penwidth=1.2];',
        '  edge [fontname="Arial Unicode MS", fontsize=9, arrowsize=0.7, penwidth=1.5];',
        f"  label={_dot_quote(_graph_title(graph, nodes, edges))};",
        "  labelloc=t;",
        '  fontsize=18;',
        '  fontname="Helvetica-Bold";',
    ]
    for node in nodes:
        node_id = str(node["id"])
        node_label = _graphviz_node_label(node)
        fill_color = _node_color(node)
        border_color = _node_border_color(node)
        lines.append(
            f"  {_dot_quote(node_id)} [label={_dot_quote(node_label)}, fillcolor={_dot_quote(fill_color)}, color={_dot_quote(border_color)}];"
        )
    for edge in edges:
        edge_type = str(edge["edge_type"])
        edge_color = _edge_color(edge_type)
        lines.append(
            "  "
            f"{_dot_quote(edge['source'])} -> {_dot_quote(edge['target'])} "
            f"[label={_dot_quote(_edge_label(edge_type))}, color={_dot_quote(edge_color)}, fontcolor={_dot_quote(edge_color)}];"
        )
    nodes_by_role: dict[str, list[str]] = {role: [] for role in _PILLOW_ROLE_ORDER}
    for node in nodes:
        nodes_by_role[_pillow_node_role(node)].append(str(node["id"]))
    for role in _PILLOW_ROLE_ORDER:
        role_node_ids = nodes_by_role[role]
        if role_node_ids:
            ranked_nodes = "; ".join(_dot_quote(node_id) for node_id in sorted(role_node_ids))
            lines.append(f"  {{ rank=same; {ranked_nodes}; }}")
    lines.append("}")
    return "\n".join(lines) + "\n"


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


def _render_graph_with_pillow(path: Path, graph: dict[str, Any]) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    fonts = _load_pillow_fonts(ImageFont)
    node_boxes = _layout_pillow_node_boxes(nodes, edges)
    width = _PILLOW_CANVAS_WIDTH
    height = _pillow_canvas_height(node_boxes)
    image = Image.new("RGB", (width, height), "#fbfbf8")
    draw = ImageDraw.Draw(image)
    draw.text((32, 22), _graph_title(graph, nodes, edges), fill="#222222", font=fonts["title"])
    _draw_pillow_column_headers(draw, fonts["small"])
    _draw_pillow_legend(draw, width, fonts["small"])

    for edge_index, edge in enumerate(edges):
        source_box = node_boxes.get(str(edge["source"]))
        target_box = node_boxes.get(str(edge["target"]))
        if source_box is None or target_box is None:
            continue
        _draw_pillow_edge(
            draw,
            source_box,
            target_box,
            str(edge["edge_type"]),
            edge_index=edge_index,
            font=fonts["small"],
        )

    for node in nodes:
        x, y, right, bottom = node_boxes[str(node["id"])]
        color = _node_color(node)
        draw.rounded_rectangle((x, y, right, bottom), radius=10, fill=color, outline=_node_border_color(node), width=2)
        label = _truncate_label(str(node.get("label") or node["id"]), 32)
        draw.text((x + 12, y + 8), label, fill="#111111", font=fonts["regular"])

    image.save(path, format="PNG")
    return True


def _layout_pillow_node_boxes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]] | None = None,
) -> dict[str, tuple[int, int, int, int]]:
    edges = edges or []
    nodes_by_id = {str(node["id"]): node for node in nodes}
    nodes_by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in _PILLOW_ROLE_ORDER}
    for node in nodes:
        nodes_by_role[_pillow_node_role(node)].append(node)
    atomic_node_ids = {str(node["id"]) for node in nodes_by_role["atomic"]}
    surface_nodes_by_atomic_id: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in atomic_node_ids}
    unlinked_surface_nodes: list[dict[str, Any]] = []
    same_as_atomic_target_by_surface_id = _same_as_atomic_target_by_surface_id(edges, atomic_node_ids)
    for surface_node in sorted(nodes_by_role["surface"], key=_pillow_node_sort_key):
        surface_node_id = str(surface_node["id"])
        atomic_target_id = same_as_atomic_target_by_surface_id.get(surface_node_id)
        if atomic_target_id is None:
            unlinked_surface_nodes.append(surface_node)
        else:
            surface_nodes_by_atomic_id[atomic_target_id].append(surface_node)

    node_boxes: dict[str, tuple[int, int, int, int]] = {}
    atomic_y_by_id: dict[str, int] = {}
    next_group_y = _PILLOW_TOP_Y
    for atomic_node in sorted(nodes_by_role["atomic"], key=_pillow_node_sort_key):
        atomic_node_id = str(atomic_node["id"])
        linked_surface_nodes = surface_nodes_by_atomic_id.get(atomic_node_id, [])
        group_rows = max(1, len(linked_surface_nodes))
        for index, surface_node in enumerate(linked_surface_nodes):
            y = next_group_y + index * _PILLOW_ROW_GAP
            node_boxes[str(surface_node["id"])] = _pillow_node_box("surface", y)
        atomic_y = next_group_y + ((group_rows - 1) * _PILLOW_ROW_GAP) // 2
        atomic_y_by_id[atomic_node_id] = atomic_y
        node_boxes[atomic_node_id] = _pillow_node_box("atomic", atomic_y)
        next_group_y += group_rows * _PILLOW_ROW_GAP + _PILLOW_GROUP_GAP

    if unlinked_surface_nodes:
        if node_boxes:
            next_group_y += _PILLOW_GROUP_GAP
        for index, surface_node in enumerate(unlinked_surface_nodes):
            y = next_group_y + index * _PILLOW_ROW_GAP
            node_boxes[str(surface_node["id"])] = _pillow_node_box("surface", y)

    umbrella_desired_positions = _desired_related_node_positions(
        role_nodes=nodes_by_role["umbrella"],
        edges=edges,
        related_y_by_id=atomic_y_by_id,
        outgoing_edge_type="contains",
        incoming_edge_type=None,
        fallback_y=_PILLOW_TOP_Y,
    )
    for umbrella_node, y in _spread_column_positions(umbrella_desired_positions):
        node_boxes[str(umbrella_node["id"])] = _pillow_node_box("umbrella", y)

    missing_desired_positions = _desired_related_node_positions(
        role_nodes=nodes_by_role["missing"],
        edges=edges,
        related_y_by_id=atomic_y_by_id,
        outgoing_edge_type=None,
        incoming_edge_type="missing_expected",
        fallback_y=_PILLOW_TOP_Y,
    )
    for missing_node, y in _spread_column_positions(missing_desired_positions):
        node_boxes[str(missing_node["id"])] = _pillow_node_box("missing", y)

    for node in nodes:
        node_id = str(node["id"])
        if node_id in node_boxes:
            continue
        role = _pillow_node_role(nodes_by_id[node_id])
        role_boxes = [box for placed_id, box in node_boxes.items() if _pillow_node_role(nodes_by_id[placed_id]) == role]
        y = max((box[3] + _PILLOW_GROUP_GAP for box in role_boxes), default=_PILLOW_TOP_Y)
        node_boxes[node_id] = _pillow_node_box(role, y)
    return node_boxes


def _same_as_atomic_target_by_surface_id(
    edges: list[dict[str, Any]],
    atomic_node_ids: set[str],
) -> dict[str, str]:
    target_by_surface_id: dict[str, str] = {}
    for edge in edges:
        if edge.get("edge_type") != "same_as":
            continue
        source_id = str(edge["source"])
        target_id = str(edge["target"])
        if target_id in atomic_node_ids:
            target_by_surface_id[source_id] = target_id
        elif source_id in atomic_node_ids:
            target_by_surface_id[target_id] = source_id
    return target_by_surface_id


def _desired_related_node_positions(
    *,
    role_nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    related_y_by_id: dict[str, int],
    outgoing_edge_type: str | None,
    incoming_edge_type: str | None,
    fallback_y: int,
) -> list[tuple[dict[str, Any], int]]:
    positions: list[tuple[dict[str, Any], int]] = []
    for index, role_node in enumerate(sorted(role_nodes, key=_pillow_node_sort_key)):
        role_node_id = str(role_node["id"])
        related_positions: list[int] = []
        for edge in edges:
            if outgoing_edge_type and edge.get("edge_type") == outgoing_edge_type and str(edge["source"]) == role_node_id:
                related_y = related_y_by_id.get(str(edge["target"]))
                if related_y is not None:
                    related_positions.append(related_y)
            if incoming_edge_type and edge.get("edge_type") == incoming_edge_type and str(edge["target"]) == role_node_id:
                related_y = related_y_by_id.get(str(edge["source"]))
                if related_y is not None:
                    related_positions.append(related_y)
        desired_y = sum(related_positions) // len(related_positions) if related_positions else fallback_y + index * _PILLOW_ROW_GAP
        positions.append((role_node, desired_y))
    return positions


def _spread_column_positions(
    node_positions: list[tuple[dict[str, Any], int]],
) -> list[tuple[dict[str, Any], int]]:
    placed_positions: list[tuple[dict[str, Any], int]] = []
    next_available_y = _PILLOW_TOP_Y
    for node, desired_y in sorted(node_positions, key=lambda item: (item[1], *_pillow_node_sort_key(item[0]))):
        y = max(desired_y, next_available_y)
        placed_positions.append((node, y))
        next_available_y = y + _PILLOW_ROW_GAP
    return placed_positions


def _pillow_node_box(role: str, y: int) -> tuple[int, int, int, int]:
    x = _PILLOW_COLUMN_X_BY_ROLE[role]
    return (x, y, x + _PILLOW_NODE_WIDTH, y + _PILLOW_NODE_HEIGHT)


def _pillow_node_role(node: dict[str, Any]) -> str:
    node_type = str(node.get("node_type") or "")
    if node_type in {"alias", "extracted_candidate"}:
        return "surface"
    if node_type == "umbrella_concept":
        return "umbrella"
    if node_type == "missing_marker":
        return "missing"
    return "atomic"


def _pillow_node_sort_key(node: dict[str, Any]) -> tuple[str, str, str]:
    return (str(node.get("kind") or ""), str(node.get("label") or ""), str(node.get("id") or ""))


def _pillow_canvas_height(node_boxes: dict[str, tuple[int, int, int, int]]) -> int:
    if not node_boxes:
        return 420
    return max(420, max(box[3] for box in node_boxes.values()) + 96)


def _draw_pillow_column_headers(draw: Any, font: Any) -> None:
    headings = {
        "surface": "Surface forms / candidates",
        "umbrella": "Umbrella concepts",
        "atomic": "Atomic concepts",
        "missing": "Eval outcomes",
    }
    for role in _PILLOW_ROLE_ORDER:
        x = _PILLOW_COLUMN_X_BY_ROLE[role]
        draw.text((x, 116), headings[role], fill="#333333", font=font)


def _draw_pillow_legend(draw: Any, width: int, font: Any) -> None:
    legend_x = width - 316
    legend_y = 20
    legend_items = [
        ("matched", "#94d3a2"),
        ("missing", "#f2a0a0"),
        ("alias", "#9cc9f5"),
        ("umbrella", "#f0bd74"),
    ]
    for index, (label, color) in enumerate(legend_items):
        x = legend_x + (index % 2) * 126
        y = legend_y + (index // 2) * 22
        draw.rounded_rectangle((x, y, x + 16, y + 14), radius=3, fill=color, outline="#777777")
        draw.text((x + 22, y - 1), label, fill="#333333", font=font)
    edge_items = [
        ("same_as", _edge_color("same_as")),
        ("contains", _edge_color("contains")),
        ("missing", _edge_color("missing_expected")),
    ]
    for index, (label, color) in enumerate(edge_items):
        x = legend_x
        y = legend_y + 44 + index * 18
        draw.line((x, y + 8, x + 20, y + 8), fill=color, width=3)
        draw.text((x + 26, y), label, fill="#333333", font=font)


def _draw_pillow_edge(
    draw: Any,
    source_box: tuple[int, int, int, int],
    target_box: tuple[int, int, int, int],
    edge_type: str,
    *,
    edge_index: int = 0,
    font: Any | None = None,
) -> None:
    source_center_y = (source_box[1] + source_box[3]) // 2
    target_center_y = (target_box[1] + target_box[3]) // 2
    if source_box[0] <= target_box[0]:
        start = (source_box[2], source_center_y)
        end = (target_box[0], target_center_y)
        lane_x = max(start[0] + 36, end[0] - 50)
    else:
        start = (source_box[0], source_center_y)
        end = (target_box[2], target_center_y)
        lane_x = min(start[0] - 36, end[0] + 50)
    lane_x += (edge_index % 5 - 2) * 4
    color = _edge_color(edge_type)
    path = [start, (lane_x, start[1]), (lane_x, end[1]), end]
    draw.line(path, fill=color, width=3, joint="curve")
    _draw_arrowhead(draw, path[-2], end, color)
    edge_label = _edge_label(edge_type)
    if edge_label:
        label_x = lane_x + 6
        label_y = (start[1] + end[1]) // 2 - 9
        draw.rectangle((label_x - 3, label_y - 2, label_x + 94, label_y + 16), fill="#fbfbf8")
        draw.text((label_x, label_y), _truncate_label(edge_label, 16), fill=color, font=font)


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


def _node_border_color(node: dict[str, Any]) -> str:
    if node.get("status") == "missing":
        return "#a33a3a"
    if node.get("status") == "matched":
        return "#3f7c4b"
    if node.get("node_type") == "umbrella_concept":
        return "#9a641c"
    if node.get("node_type") == "alias":
        return "#356c9e"
    return "#555555"


def _edge_color(edge_type: str) -> str:
    if edge_type == "same_as":
        return "#4b6f96"
    if edge_type == "contains":
        return "#9b6418"
    if edge_type == "missing_expected":
        return "#a33a3a"
    return "#555555"


def _edge_label(edge_type: str) -> str:
    return ""


def _load_pillow_fonts(image_font: Any) -> dict[str, Any]:
    font_candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path in font_candidates:
        if not Path(font_path).exists():
            continue
        try:
            return {
                "title": image_font.truetype(font_path, 15),
                "regular": image_font.truetype(font_path, 13),
                "small": image_font.truetype(font_path, 11),
            }
        except Exception:
            continue
    fallback_font = image_font.load_default()
    return {"title": fallback_font, "regular": fallback_font, "small": fallback_font}


def _graph_title(graph: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    graph_type = graph.get("graph_type", "concept_graph")
    run_type = graph.get("run_type", "")
    return f"{graph_type} ({run_type}) | nodes={len(nodes)} edges={len(edges)}"


def _graphviz_node_label(node: dict[str, Any]) -> str:
    label = _truncate_label(str(node.get("label") or node["id"]), 34)
    node_type = str(node.get("node_type") or "")
    status = node.get("status")
    detail = f"{node_type}"
    if status:
        detail = f"{detail}\n{status}"
    return f"{label}\n{detail}"


def _truncate_label(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1] + "..."


def _dot_quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


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
