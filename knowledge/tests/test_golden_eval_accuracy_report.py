from __future__ import annotations

import json
from pathlib import Path

from knowledge.golden_eval_accuracy import (
    _font_candidate_paths,
    build_golden_eval_accuracy_report,
    write_golden_eval_accuracy_artifacts,
)


def test_build_golden_eval_accuracy_report_groups_by_experiment_and_arm():
    evaluations = [
        {"experiment_id": "E1", "arm_id": "C1", "overall": "match"},
        {"experiment_id": "E1", "arm_id": "C1", "overall": "miss"},
        {"experiment_id": "E1", "arm_id": "C2", "overall": "partial_match"},
        {"experiment_id": "E1", "arm_id": "C2", "overall": "match"},
        {"experiment_id": "E2", "arm_id": "C2", "excluded_from_f1": True, "overall": "challenge_only"},
    ]

    report = build_golden_eval_accuracy_report("rule_extraction_v1", "real_llm", evaluations)

    assert report["dataset_id"] == "rule_extraction_v1"
    assert report["run_type"] == "real_llm"
    assert report["summary"]["evaluated_record_count"] == 4
    assert report["summary"]["best_arm"]["arm_id"] == "C2"
    assert report["rows"] == [
        {
            "experiment_id": "E1",
            "arm_id": "C1",
            "evaluated_record_count": 2,
            "exact_match_count": 1,
            "usable_match_count": 1,
            "miss_count": 1,
            "exact_accuracy": 0.5,
            "usable_accuracy": 0.5,
        },
        {
            "experiment_id": "E1",
            "arm_id": "C2",
            "evaluated_record_count": 2,
            "exact_match_count": 1,
            "usable_match_count": 2,
            "miss_count": 0,
            "exact_accuracy": 0.5,
            "usable_accuracy": 1.0,
        },
    ]


def test_write_golden_eval_accuracy_artifacts_creates_json_and_png(tmp_path: Path):
    evaluations = [
        {"experiment_id": "E1", "arm_id": "C1", "overall": "miss"},
        {"experiment_id": "E1", "arm_id": "C2", "overall": "match"},
    ]

    result = write_golden_eval_accuracy_artifacts(
        output_dir=tmp_path,
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        evaluations=evaluations,
    )

    report_path = Path(result["report_path"])
    chart_path = Path(result["chart_path"])
    assert report_path.exists()
    assert chart_path.exists()
    assert chart_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["chart_path"] == str(chart_path)
    assert persisted["summary"]["best_arm"]["arm_id"] == "C2"


def test_write_golden_eval_accuracy_artifacts_preserves_layer_summaries(tmp_path: Path):
    result = write_golden_eval_accuracy_artifacts(
        output_dir=tmp_path,
        dataset_id="rule_extraction_v1",
        run_type="real_llm",
        evaluations=[{"experiment_id": "E1", "arm_id": "C2", "overall": "match"}],
        layer_summaries={
            "layer_0_plausibility": {"pass": 1, "warn": 0, "fail": 0},
            "layer_1_grounding": {"evaluated_observation_count": 1, "avg_score": 1.0, "unsupported_rate": 0.0},
        },
    )

    persisted = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    assert persisted["layer_0_plausibility"]["pass"] == 1
    assert persisted["layer_1_grounding"]["avg_score"] == 1.0


def test_font_candidates_include_linux_dejavu_fallback():
    candidates = [str(path) for path in _font_candidate_paths()]

    assert "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" in candidates
