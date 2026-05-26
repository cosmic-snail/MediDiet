from __future__ import annotations

from pathlib import Path

from knowledge.rule_extraction_dataset_smoke import build_chunking_report


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_extractable_content_chunking_removes_source_card_noise():
    report = build_chunking_report(REPO_ROOT / "knowledge" / "datasets" / "rule_extraction_v1", REPO_ROOT / "knowledge" / "source_documents", ["raw_card", "extractable_content"])
    raw_report = report["strategies"]["raw_card"]
    extractable_report = report["strategies"]["extractable_content"]
    assert raw_report["summary"]["total_chunks"] >= extractable_report["summary"]["total_chunks"]
    assert extractable_report["summary"]["chunks_with_frontmatter"] == 0
    assert extractable_report["summary"]["chunks_with_copyright_handling"] == 0
