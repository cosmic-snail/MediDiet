import tempfile
from datetime import datetime, timezone

import pytest

from knowledge.schema import KnowledgeDocument, DocumentChunk
from knowledge.vectordb import KnowledgeVectorDB

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


def _make_doc(doc_id, title, source_type, content, metadata=None):
    chunks = [
        DocumentChunk(
            chunk_id=f"{doc_id}-chunk-0000",
            doc_id=doc_id,
            text=content,
            chunk_index=0,
        )
    ]
    return KnowledgeDocument(
        doc_id=doc_id,
        title=title,
        source="test-source",
        source_type=source_type,
        content_raw=content,
        chunks=chunks,
        metadata=metadata or {},
        ingested_at=NOW,
    )


@pytest.fixture
def vector_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = KnowledgeVectorDB(persist_dir=tmpdir)
        yield db


class TestKnowledgeVectorDB:
    def test_index_and_search(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "CKD Guidelines",
            "guideline",
            "Patients with CKD should limit sodium intake to under 2000mg per day.",
        )
        vector_db.index_document(doc)

        results = vector_db.search("sodium intake for kidney disease", top_k=3)
        assert len(results) > 0
        assert "sodium" in results[0].text.lower()

    def test_search_returns_relevance_scores(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "CKD Guidelines",
            "guideline",
            "Limit sodium to 2000mg per day for kidney patients.",
        )
        vector_db.index_document(doc)

        results = vector_db.search("sodium restriction", top_k=3)
        for result in results:
            assert 0 <= result.relevance_score <= 1

    def test_search_respects_top_k(self, vector_db):
        for i in range(5):
            doc = _make_doc(
                f"doc-{i:03d}",
                f"Doc {i}",
                "guideline",
                f"Sodium intake guideline number {i} for patients.",
            )
            vector_db.index_document(doc)

        results = vector_db.search("sodium", top_k=3)
        assert len(results) == 3

    def test_delete_document(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "To Delete",
            "paper",
            "This document will be deleted.",
        )
        vector_db.index_document(doc)
        results_before = vector_db.search("deleted", top_k=3)
        assert len(results_before) > 0

        vector_db.delete_document("doc-001")
        results_after = vector_db.search("deleted", top_k=3)
        assert len(results_after) == 0

    def test_search_returns_source_metadata(self, vector_db):
        doc = _make_doc(
            "doc-001",
            "Test Title",
            "guideline",
            "Sodium should be limited.",
            metadata={"year": "2024"},
        )
        vector_db.index_document(doc)

        results = vector_db.search("sodium", top_k=1)
        assert len(results) > 0
        assert results[0].source_title == "Test Title"

    def test_empty_search_returns_empty_list(self, vector_db):
        results = vector_db.search("anything", top_k=5)
        assert results == []

    def test_index_empty_chunks_does_not_crash(self, vector_db):
        doc = KnowledgeDocument(
            doc_id="empty-doc",
            title="Empty",
            source="none",
            source_type="paper",
            content_raw="",
            chunks=[],
            metadata={},
            ingested_at=NOW,
        )
        vector_db.index_document(doc)
        results = vector_db.search("test", top_k=3)
        assert results == []
