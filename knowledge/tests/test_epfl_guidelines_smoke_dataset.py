from __future__ import annotations

from pathlib import Path

from knowledge.dataset_manifest import load_dataset_documents, load_manifest_rows
from knowledge.documents import select_document_content


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = KNOWLEDGE_ROOT / "datasets" / "rule_extraction_epfl_guidelines_smoke"
SOURCE_ROOT = KNOWLEDGE_ROOT / "source_documents"


def test_epfl_guidelines_smoke_manifest_loads_documents() -> None:
    rows = load_manifest_rows(DATASET_DIR)

    assert len(rows) == 8
    assert {row["source_dataset"] for row in rows} == {"epfl-llm/guidelines"}
    assert all(row["failure_is_valid_observation"] is False for row in rows)

    docs = load_dataset_documents(DATASET_DIR, SOURCE_ROOT)
    assert len(docs) == len(rows)
    assert all(doc.metadata["frontmatter_agrees"] == "true" for doc in docs)
    assert all(doc.metadata["source_card_hash"].startswith("sha256:") for doc in docs)


def test_epfl_guidelines_smoke_extractable_content_is_card_body_only() -> None:
    docs = load_dataset_documents(DATASET_DIR, SOURCE_ROOT)

    for doc in docs:
        extractable = select_document_content(doc.content_raw, "extractable_content")
        assert "## Source Notes" not in extractable
        assert "## Copyright Handling" not in extractable
        assert "Excerpt window" in extractable
