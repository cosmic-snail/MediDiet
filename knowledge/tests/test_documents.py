import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge.schema import KnowledgeDocument, DocumentChunk
from knowledge.documents import DocumentImporter

NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)

SAMPLE_MD = """# CKD Dietary Guidelines

## Sodium Management

Patients with chronic kidney disease should limit sodium intake to under 2000mg per day.
This helps manage blood pressure and fluid retention.

## Protein Guidelines

Protein intake should be adjusted based on CKD stage. For stages 1-3, moderate protein
restriction of 0.8g/kg/day is recommended. For stages 4-5, further restriction may apply.

## Potassium Monitoring

Serum potassium levels should be monitored regularly. When levels are elevated,
dietary potassium should be limited to 2000-3000mg per day.
"""


@pytest.fixture
def importer():
    return DocumentImporter()


class TestDocumentImporter:
    def test_import_from_text(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="CKD Dietary Guidelines",
            source="ckd-guidelines.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={"year": "2024"},
            ingested_at=NOW,
        )
        assert doc.doc_id == "doc-001"
        assert doc.title == "CKD Dietary Guidelines"
        assert doc.source_type == "guideline"
        assert doc.content_raw == SAMPLE_MD
        assert len(doc.chunks) > 0

    def test_chunks_preserve_text_content(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        all_text = "".join(chunk.text for chunk in doc.chunks)
        assert "sodium intake to under 2000mg" in all_text
        assert "Protein intake should be adjusted" in all_text

    def test_chunks_have_sequential_indices(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        indices = [chunk.chunk_index for chunk in doc.chunks]
        assert indices == sorted(indices)
        assert indices[0] == 0

    def test_chunks_reference_correct_doc_id(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        for chunk in doc.chunks:
            assert chunk.doc_id == "doc-001"

    def test_chunk_ids_are_unique(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-001",
            title="Test",
            source="test.md",
            source_type="guideline",
            content=SAMPLE_MD,
            metadata={},
            ingested_at=NOW,
        )
        chunk_ids = [chunk.chunk_id for chunk in doc.chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_import_from_file(self, importer):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_MD)
            tmp_path = f.name

        try:
            doc = importer.import_from_file(
                doc_id="doc-002",
                title="From File",
                file_path=tmp_path,
                source_type="guideline",
                metadata={},
            )
            assert doc.doc_id == "doc-002"
            assert len(doc.chunks) > 0
            assert doc.content_raw == SAMPLE_MD
        finally:
            Path(tmp_path).unlink()

    def test_short_text_produces_single_chunk(self, importer):
        short = "Short text."
        doc = importer.import_from_text(
            doc_id="doc-003",
            title="Short",
            source="short.md",
            source_type="paper",
            content=short,
            metadata={},
            ingested_at=NOW,
        )
        assert len(doc.chunks) == 1
        assert doc.chunks[0].text == short

    def test_empty_text_produces_no_chunks(self, importer):
        doc = importer.import_from_text(
            doc_id="doc-004",
            title="Empty",
            source="empty.md",
            source_type="paper",
            content="",
            metadata={},
            ingested_at=NOW,
        )
        assert len(doc.chunks) == 0

    def test_rejects_invalid_source_type(self, importer):
        with pytest.raises(ValueError, match="source_type"):
            importer.import_from_text(
                doc_id="doc-005",
                title="Bad",
                source="bad.md",
                source_type="invalid_type",
                content="text",
                metadata={},
                ingested_at=NOW,
            )
