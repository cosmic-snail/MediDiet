from __future__ import annotations

from knowledge.dataset_manifest import diff_source_snapshots


def test_diff_source_snapshots_marks_stale_rule_identity():
    previous = {"doc-1": {"source_card_hash": "sha256:a", "extractable_content_hash": "sha256:b", "rule_identities": ["sha256:rule"]}}
    current = {"doc-1": {"source_card_hash": "sha256:a", "extractable_content_hash": "sha256:c", "rule_identities": []}}
    diff = diff_source_snapshots(previous, current)
    assert diff["changed_doc_ids"] == ["doc-1"]
    assert diff["stale_rule_identities"] == ["sha256:rule"]
