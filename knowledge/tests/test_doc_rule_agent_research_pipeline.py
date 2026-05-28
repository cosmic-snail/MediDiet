from __future__ import annotations

import json
from pathlib import Path

from knowledge.rule_extraction_dataset_smoke import run_research_dry_run


def test_doc_rule_agent_research_pipeline_dry_run_writes_reports(tmp_path: Path):
    result = run_research_dry_run("rule_extraction_v1", tmp_path, arms=["C0", "C1", "C2"], experiments=["E1", "E2"])
    assert result["observation_count"] > 0
    expected = [
        "rule-extraction-v1-chunking-report.json",
        "doc-rule-agent-benchmark-portfolio-report.json",
        "doc-rule-agent-transfer-gap-report.json",
        "rule-extraction-v1-experiment-matrix-report.json",
        "rule-extraction-v1-observation-coverage-report.json",
        "rule-extraction-v1-field-evaluation-report.json",
        "rule-extraction-v1-stability-report.json",
        "rule-extraction-v1-research-registry-report.md",
    ]
    for filename in expected:
        path = tmp_path / filename
        assert path.exists()
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data.get("rows") or data.get("experiments") or data.get("benchmarks")
