from pathlib import Path
import tempfile

import pytest

from knowledge.documents import DocumentImporter
from knowledge.loader import KnowledgeLoader


@pytest.fixture
def loader():
    return KnowledgeLoader(importer=DocumentImporter())


class TestKnowledgeLoader:
    def test_load_from_directory(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "guideline-ckd.md"
            file1.write_text(
                "# CKD Guidelines\n\nLimit sodium to under 2000mg per day.",
                encoding="utf-8",
            )
            file2 = Path(tmpdir) / "paper-protein.md"
            file2.write_text(
                "# Protein Study\n\nProtein intake of 0.8g/kg is recommended for CKD.",
                encoding="utf-8",
            )

            docs = loader.load_from_directory(tmpdir, source_type="guideline")
            assert len(docs) == 2
            assert all(doc.source_type == "guideline" for doc in docs)

    def test_load_from_directory_skips_non_md_txt(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc.md").write_text("# MD", encoding="utf-8")
            (Path(tmpdir) / "doc.txt").write_text("TXT", encoding="utf-8")
            (Path(tmpdir) / "doc.pdf").write_text("PDF", encoding="utf-8")
            (Path(tmpdir) / "image.png").write_text("PNG", encoding="utf-8")

            docs = loader.load_from_directory(tmpdir, source_type="paper")
            assert len(docs) == 2

    def test_load_empty_directory(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs = loader.load_from_directory(tmpdir, source_type="guideline")
            assert docs == []

    def test_load_nonexistent_directory(self, loader):
        with pytest.raises(FileNotFoundError):
            loader.load_from_directory("/nonexistent/path", source_type="guideline")

    def test_doc_ids_are_derived_from_filename(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "ckd-guideline-2024.md").write_text(
                "# CKD", encoding="utf-8"
            )

            docs = loader.load_from_directory(tmpdir, source_type="guideline")
            assert len(docs) == 1
            assert docs[0].doc_id.startswith("ckd_guideline_2024")

    def test_doc_metadata_includes_filename(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "study.md").write_text(
                "# Study\n\nContent here.", encoding="utf-8"
            )

            docs = loader.load_from_directory(tmpdir, source_type="paper")
            assert len(docs) == 1
            assert "filename" in docs[0].metadata
            assert docs[0].metadata["filename"] == "study.md"
