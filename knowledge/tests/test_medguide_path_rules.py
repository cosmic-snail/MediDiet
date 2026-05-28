from __future__ import annotations

import http.client
import json

from knowledge import medguide_path_rule_benchmark
from knowledge.medguide_path_rule_benchmark import fetch_medguide_rows, write_medguide_path_rule_report
from knowledge.path_rule_evaluation import (
    PathRulePrediction,
    evaluate_medguide_rows,
    evaluate_path_rule_prediction,
    match_path_rules,
    path_rule_from_medguide_row,
)


MEDGUIDE_ROW = {
    "disease": "aml_7",
    "path": [
        "First relapse (morphologic or molecular)",
        "Early relapse (<6 mo) after ATRA and arsenic trioxide (no anthracycline)",
        "Anthracycline-based regimen as per APL-3 or gemtuzumab ozogamicin",
        "Second remission (morphologic)",
        "PCR negative (by BM)",
        "Transplant candidate",
        "Autologous HCT",
    ],
    "profile": "The patient had a first relapse four months after ATRA and arsenic trioxide, reached a second remission, is PCR negative by bone marrow, and is a transplant candidate.",
    "options": [
        "Clinical trial",
        "Arsenic trioxide consolidation (total of 6 cycles)",
        "Clinical trial or Matched sibling or alternative donor HCT",
        "Matched sibling or alternative donor HCT",
        "Autologous HCT",
    ],
    "answer": "E",
    "answer_text": "Autologous HCT",
}


def test_medguide_row_converts_to_path_rule_with_action_leaf() -> None:
    rule = path_rule_from_medguide_row("medguide-0", MEDGUIDE_ROW)

    assert rule.rule_id == "medguide-0"
    assert rule.disease == "aml_7"
    assert rule.conditions == MEDGUIDE_ROW["path"][:-1]
    assert rule.action == "Autologous HCT"
    assert rule.answer == "E"
    assert rule.answer_text == "Autologous HCT"


def test_matcher_selects_answer_from_extracted_facts_without_llm_answering() -> None:
    rule = path_rule_from_medguide_row("medguide-0", MEDGUIDE_ROW)
    facts = [
        "First relapse (morphologic or molecular)",
        "Early relapse (<6 mo) after ATRA and arsenic trioxide (no anthracycline)",
        "Second remission (morphologic)",
        "PCR negative (by BM)",
        "Transplant candidate",
    ]

    prediction = match_path_rules(
        facts=facts,
        options=MEDGUIDE_ROW["options"],
        candidate_rules=[rule],
    )

    assert prediction.selected_rule_id == "medguide-0"
    assert prediction.selected_answer == "E"
    assert prediction.selected_answer_text == "Autologous HCT"
    assert prediction.matched_path == facts


def test_path_evaluation_reports_answer_and_process_metrics() -> None:
    rule = path_rule_from_medguide_row("medguide-0", MEDGUIDE_ROW)
    prediction = PathRulePrediction(
        selected_rule_id="medguide-0",
        selected_answer="E",
        selected_answer_text="Autologous HCT",
        matched_path=[
            "First relapse (morphologic or molecular)",
            "Second remission (morphologic)",
            "PCR negative (by BM)",
            "Transplant candidate",
            "Unsupported shortcut",
        ],
    )

    evaluation = evaluate_path_rule_prediction(rule, prediction)

    assert evaluation["answer_correct"] is True
    assert evaluation["path_node_precision"] == 0.8
    assert evaluation["path_node_recall"] == 4 / 6
    assert evaluation["path_order_match"] is True
    assert evaluation["missing_path_nodes"] == [
        "Early relapse (<6 mo) after ATRA and arsenic trioxide (no anthracycline)",
        "Anthracycline-based regimen as per APL-3 or gemtuzumab ozogamicin",
    ]
    assert evaluation["unsupported_path_nodes"] == ["Unsupported shortcut"]


def test_medguide_rows_evaluate_rule_matching_with_external_facts() -> None:
    second_row = {
        **MEDGUIDE_ROW,
        "path": [
            "First relapse (morphologic or molecular)",
            "Late relapse (>=6 mo) after ATRA and arsenic trioxide",
            "Arsenic trioxide consolidation",
        ],
        "options": [
            "Clinical trial",
            "Arsenic trioxide consolidation",
            "Autologous HCT",
        ],
        "answer": "B",
        "answer_text": "Arsenic trioxide consolidation",
    }
    rows = [
        {"row_idx": 0, "row": MEDGUIDE_ROW},
        {"row_idx": 1, "row": second_row},
    ]

    report = evaluate_medguide_rows(
        rows,
        facts_by_sample_id={
            "medguide-0": MEDGUIDE_ROW["path"][:-1],
            "medguide-1": MEDGUIDE_ROW["path"][:-1],
        },
    )

    assert report["row_count"] == 2
    assert report["answer_accuracy"] == 0.5
    assert report["average_path_node_recall"] == (1.0 + 0.5) / 2
    assert report["rows"][0]["answer_correct"] is True
    assert report["rows"][1]["answer_correct"] is False


def test_medguide_benchmark_writes_report_without_autonomous_llm_answering(tmp_path) -> None:
    output_path = tmp_path / "medguide-report.json"
    rows = [{"row_idx": 0, "row": MEDGUIDE_ROW}]

    report = write_medguide_path_rule_report(
        rows=rows,
        output_path=output_path,
        facts_by_sample_id={"medguide-0": MEDGUIDE_ROW["path"][:-1]},
    )

    assert report["mode"] == "external_facts"
    assert report["answer_accuracy"] == 1.0
    assert report["autonomous_llm_answering"] is False
    assert output_path.exists()
    assert '"answer_accuracy": 1.0' in output_path.read_text(encoding="utf-8")


def test_fetch_medguide_rows_retries_incomplete_reads(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps({"rows": [{"row_idx": 0, "row": MEDGUIDE_ROW}]}).encode("utf-8")

    def fake_urlopen(url, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise http.client.IncompleteRead(b"{", 4)
        return FakeResponse()

    monkeypatch.setattr(medguide_path_rule_benchmark.urllib.request, "urlopen", fake_urlopen)

    rows = fetch_medguide_rows(offset=0, limit=1)

    assert calls["count"] == 2
    assert rows[0]["row"]["answer_text"] == "Autologous HCT"
