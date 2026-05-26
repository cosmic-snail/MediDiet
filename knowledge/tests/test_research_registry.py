from __future__ import annotations

from pathlib import Path

from knowledge.research_registry import ResearchRegistry


def test_research_registry_snapshot_is_not_clinical_publication(tmp_path: Path):
    registry = ResearchRegistry(tmp_path / "research_registry.jsonl")
    snapshot_id = registry.create_snapshot(dataset_id="rule_extraction_v1", run_id="run-001", candidates=[{"rule_identity": "sha256:abc", "condition": "hypertension", "status": "machine_observed"}])
    loaded = registry.load_snapshot(snapshot_id)
    assert loaded["snapshot_type"] == "research_only"
    assert loaded["candidates"][0]["status"] == "machine_observed"


def test_research_registry_exports_report(tmp_path: Path):
    registry = ResearchRegistry(tmp_path / "research_registry.jsonl")
    registry.create_snapshot(dataset_id="rule_extraction_v1", run_id="run-001", candidates=[])
    report = tmp_path / "report.md"
    registry.export_report(report)
    assert "research_only" in report.read_text(encoding="utf-8")
