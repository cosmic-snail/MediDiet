from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


EXACT_MATCH_OUTCOMES = {"match"}
USABLE_MATCH_OUTCOMES = {"match", "partial_match"}


def build_golden_eval_accuracy_report(
    dataset_id: str,
    run_type: str,
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    scored_evaluations = [
        evaluation
        for evaluation in evaluations
        if not evaluation.get("excluded_from_f1")
    ]
    grouped_evaluations: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for evaluation in scored_evaluations:
        experiment_id = str(evaluation.get("experiment_id") or "")
        arm_id = str(evaluation.get("arm_id") or "")
        grouped_evaluations[(experiment_id, arm_id)].append(evaluation)

    rows = [
        _summarize_group(experiment_id, arm_id, group_evaluations)
        for (experiment_id, arm_id), group_evaluations in sorted(grouped_evaluations.items())
    ]
    best_arm = max(rows, key=lambda row: (row["usable_accuracy"], row["exact_accuracy"], row["evaluated_record_count"]), default=None)
    return {
        "dataset_id": dataset_id,
        "run_type": run_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "evaluated_record_count": len(scored_evaluations),
            "comparison_count": len(rows),
            "best_arm": best_arm,
        },
        "rows": rows,
    }


def write_golden_eval_accuracy_artifacts(
    *,
    output_dir: Path,
    dataset_id: str,
    run_type: str,
    evaluations: list[dict[str, Any]],
    layer_summaries: dict[str, Any] | None = None,
    report_filename: str = "rule-extraction-v1-golden-eval-accuracy-report.json",
    chart_filename: str = "rule-extraction-v1-golden-eval-accuracy-chart.png",
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_golden_eval_accuracy_report(dataset_id, run_type, evaluations)
    if layer_summaries:
        report.update(layer_summaries)
    report_path = output_dir / report_filename
    chart_path = output_dir / chart_filename
    report["chart_path"] = str(chart_path)
    _write_accuracy_chart(chart_path, report["rows"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"report_path": str(report_path), "chart_path": str(chart_path)}


def _summarize_group(
    experiment_id: str,
    arm_id: str,
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated_record_count = len(evaluations)
    exact_match_count = sum(1 for evaluation in evaluations if evaluation.get("overall") in EXACT_MATCH_OUTCOMES)
    usable_match_count = sum(1 for evaluation in evaluations if evaluation.get("overall") in USABLE_MATCH_OUTCOMES)
    return {
        "experiment_id": experiment_id,
        "arm_id": arm_id,
        "evaluated_record_count": evaluated_record_count,
        "exact_match_count": exact_match_count,
        "usable_match_count": usable_match_count,
        "miss_count": evaluated_record_count - usable_match_count,
        "exact_accuracy": exact_match_count / evaluated_record_count if evaluated_record_count else 0.0,
        "usable_accuracy": usable_match_count / evaluated_record_count if evaluated_record_count else 0.0,
    }


def _write_accuracy_chart(path: Path, rows: list[dict[str, Any]]) -> None:
    width = 980
    height = max(360, 170 + len(rows) * 58)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(size=24)
    label_font = _font(size=15)
    small_font = _font(size=13)

    draw.text((32, 24), "Golden Evaluation Accuracy by Experiment Arm", fill="#111827", font=title_font)
    draw.text((32, 58), "Exact match and usable match rates against frozen golden eval records", fill="#4b5563", font=small_font)

    plot_left = 260
    plot_right = width - 80
    plot_top = 110
    row_height = 58
    bar_height = 18
    usable_color = "#2563eb"
    exact_color = "#16a34a"
    axis_color = "#d1d5db"

    for tick in range(0, 101, 25):
        x = plot_left + int((plot_right - plot_left) * tick / 100)
        draw.line((x, plot_top - 8, x, height - 60), fill=axis_color)
        draw.text((x - 12, height - 48), f"{tick}%", fill="#6b7280", font=small_font)

    draw.rectangle((32, height - 36, 48, height - 20), fill=usable_color)
    draw.text((56, height - 38), "usable match", fill="#374151", font=small_font)
    draw.rectangle((170, height - 36, 186, height - 20), fill=exact_color)
    draw.text((194, height - 38), "exact match", fill="#374151", font=small_font)

    if not rows:
        draw.text((32, 130), "No golden eval records were scored.", fill="#991b1b", font=label_font)
        image.save(path, format="PNG")
        return

    for index, row in enumerate(rows):
        y = plot_top + index * row_height
        label = f"{row['experiment_id']} / {row['arm_id']} ({row['evaluated_record_count']})"
        draw.text((32, y), label, fill="#111827", font=label_font)
        usable_width = int((plot_right - plot_left) * float(row["usable_accuracy"]))
        exact_width = int((plot_right - plot_left) * float(row["exact_accuracy"]))
        draw.rounded_rectangle((plot_left, y + 2, plot_left + usable_width, y + 2 + bar_height), radius=4, fill=usable_color)
        draw.rounded_rectangle((plot_left, y + 28, plot_left + exact_width, y + 28 + bar_height), radius=4, fill=exact_color)
        draw.text((plot_right + 10, y + 1), f"{row['usable_accuracy']:.0%}", fill="#111827", font=small_font)
        draw.text((plot_right + 10, y + 27), f"{row['exact_accuracy']:.0%}", fill="#111827", font=small_font)

    image.save(path, format="PNG")


def _font(size: int) -> ImageFont.ImageFont:
    for font_path in _font_candidate_paths():
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def _font_candidate_paths() -> tuple[Path, ...]:
    return (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
