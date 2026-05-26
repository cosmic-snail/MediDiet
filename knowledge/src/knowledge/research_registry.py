from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.dataset_manifest import diff_source_snapshots


class ResearchRegistry:
    def __init__(self, path: Path):
        self.path = path

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def create_snapshot(
        self,
        dataset_id: str,
        run_id: str,
        candidates: list[dict[str, Any]],
        source_hashes: dict | None = None,
        observation_ids: list[str] | None = None,
        stability_summary: dict | None = None,
        conflict_summary: dict | None = None,
    ) -> str:
        previous = next((row for row in reversed(self._rows()) if row.get("dataset_id") == dataset_id), None)
        stale = diff_source_snapshots(previous.get("source_hashes", {}) if previous else {}, source_hashes or {})
        payload = {"dataset_id": dataset_id, "run_id": run_id, "candidate_count": len(candidates), "source_hashes": source_hashes or {}}
        snapshot_id = "research-snapshot-" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        row = {
            "snapshot_id": snapshot_id,
            "snapshot_type": "research_only",
            "publication_boundary": "research_only",
            "dataset_id": dataset_id,
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_hashes": source_hashes or {},
            "observation_ids": observation_ids or [],
            "candidates": candidates,
            "candidate_identities": [item.get("rule_identity", "") for item in candidates],
            "stability_summary": stability_summary or {},
            "conflict_summary": conflict_summary or {},
            "stale_candidates": stale,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return snapshot_id

    def load_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        for row in self._rows():
            if row.get("snapshot_id") == snapshot_id:
                return row
        raise KeyError(snapshot_id)

    def export_report(self, path: Path) -> None:
        rows = self._rows()
        latest = rows[-1] if rows else {}
        lines = [
            "# Rule Extraction V1 Research Registry Report",
            "",
            f"- snapshot id: {latest.get('snapshot_id', 'none')}",
            f"- snapshot type: {latest.get('snapshot_type', 'research_only')}",
            f"- candidates: {len(latest.get('candidates', []))}",
            "",
            "## Stable Rules",
            "",
            "Dry-run stable rule identities are listed in the machine JSONL snapshot.",
            "",
            "## Unstable Rules",
            "",
            json.dumps(latest.get("stability_summary", {}), ensure_ascii=False, indent=2),
            "",
            "## Stale Candidates",
            "",
            json.dumps(latest.get("stale_candidates", {}), ensure_ascii=False, indent=2),
            "",
            "## Conflicts",
            "",
            json.dumps(latest.get("conflict_summary", {}), ensure_ascii=False, indent=2),
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
