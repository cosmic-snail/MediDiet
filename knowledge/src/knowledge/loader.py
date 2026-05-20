from __future__ import annotations

from pathlib import Path

from knowledge.documents import DocumentImporter
from knowledge.schema import KnowledgeDocument

SUPPORTED_SUFFIXES = {".md", ".txt"}


class KnowledgeLoader:
    def __init__(self, importer: DocumentImporter | None = None):
        self.importer = importer or DocumentImporter()

    def load_from_directory(
        self, directory: str, source_type: str
    ) -> list[KnowledgeDocument]:
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"directory not found: {directory}")

        docs: list[KnowledgeDocument] = []
        for file_path in sorted(dir_path.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue

            stem = file_path.stem
            doc_id = stem.lower().replace(" ", "_").replace("-", "_")

            doc = self.importer.import_from_file(
                doc_id=doc_id,
                title=stem.replace("_", " ").replace("-", " "),
                file_path=str(file_path),
                source_type=source_type,
                metadata={"filename": file_path.name},
            )
            docs.append(doc)

        return docs

    def load_and_index(
        self, directory: str, source_type: str, vector_db=None
    ) -> list[KnowledgeDocument]:
        docs = self.load_from_directory(directory, source_type)
        if vector_db is not None:
            for doc in docs:
                vector_db.index_document(doc)
        return docs
