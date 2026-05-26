from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.documents import DocumentImporter
from knowledge.schema import KnowledgeDocument


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""
    after = text.split(marker, 1)[1]
    return after.split("\n## ", 1)[0].strip()


def load_manifest_rows(dataset_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest_path = dataset_dir / "manifest.jsonl"
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_dataset_documents(dataset_dir: Path, source_root: Path) -> list[KnowledgeDocument]:
    importer = DocumentImporter()
    docs: list[KnowledgeDocument] = []
    for row in load_manifest_rows(dataset_dir):
        source_card_path = row.get("source_card_path") or row.get("path")
        if not source_card_path:
            raise ValueError(f"manifest row {row.get('doc_id', '<unknown>')} is missing source_card_path/path")
        raw_path = Path(source_card_path)
        if raw_path.is_absolute():
            card_path = raw_path
        elif source_card_path.startswith("knowledge/source_documents/"):
            card_path = source_root.parent.parent / raw_path
        else:
            card_path = source_root / raw_path
        source_text = card_path.read_text(encoding="utf-8")
        frontmatter = extract_frontmatter(source_text)
        if frontmatter.get("doc_id") and frontmatter["doc_id"] != row["doc_id"]:
            raise ValueError(
                f"manifest doc_id {row['doc_id']} disagrees with source card {frontmatter['doc_id']}"
            )
        extractable = extract_section(source_text, "Extractable Source Content") or source_text
        metadata = {k: v for k, v in row.items() if k not in {"source_card_path", "path"}}
        metadata.update(
            {
                "dataset_id": dataset_dir.name,
                "source_card_path": source_card_path,
                "source_card_hash": sha256_text(source_text),
                "extractable_content_hash": sha256_text(extractable),
                "manifest_row_hash": sha256_text(json.dumps(row, ensure_ascii=False, sort_keys=True)),
                "frontmatter_doc_id": frontmatter.get("doc_id", ""),
                "frontmatter_agrees": str(frontmatter.get("doc_id", row["doc_id"]) == row["doc_id"]).lower(),
            }
        )
        docs.append(
            importer.import_from_text(
                doc_id=row["doc_id"],
                title=row.get("title", row["doc_id"]),
                source=str(card_path),
                source_type=row.get("source_type", "guideline"),
                content=source_text,
                metadata=metadata,
                ingested_at=datetime.now(timezone.utc),
            )
        )
    return docs


def snapshot_source_hashes(docs: list[KnowledgeDocument], rule_identities_by_doc: dict[str, list[str]] | None = None) -> dict:
    return {
        doc.doc_id: {
            "source_card_hash": doc.metadata.get("source_card_hash", ""),
            "extractable_content_hash": doc.metadata.get("extractable_content_hash", ""),
            "rule_identities": list((rule_identities_by_doc or {}).get(doc.doc_id, [])),
        }
        for doc in docs
    }


def diff_source_snapshots(previous: dict, current: dict) -> dict:
    previous_ids = set(previous)
    current_ids = set(current)
    changed = {
        doc_id
        for doc_id in previous_ids & current_ids
        if previous[doc_id].get("extractable_content_hash") != current[doc_id].get("extractable_content_hash")
        or previous[doc_id].get("source_card_hash") != current[doc_id].get("source_card_hash")
    }
    stale: list[str] = []
    for doc_id in changed | (previous_ids - current_ids):
        stale.extend(previous.get(doc_id, {}).get("rule_identities", []))
    return {
        "added_doc_ids": sorted(current_ids - previous_ids),
        "removed_doc_ids": sorted(previous_ids - current_ids),
        "changed_doc_ids": sorted(changed),
        "unchanged_doc_ids": sorted((previous_ids & current_ids) - changed),
        "stale_rule_identities": sorted(set(stale)),
    }
