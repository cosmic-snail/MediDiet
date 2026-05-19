from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from knowledge.schema import KnowledgeDocument, DocumentChunk

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


class DocumentImporter:
    def __init__(
        self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def import_from_text(
        self,
        doc_id: str,
        title: str,
        source: str,
        source_type: str,
        content: str,
        metadata: dict[str, str],
        ingested_at: datetime,
    ) -> KnowledgeDocument:
        chunks = self._chunk_text(doc_id, content)
        return KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            source=source,
            source_type=source_type,
            content_raw=content,
            chunks=chunks,
            metadata=metadata,
            ingested_at=ingested_at,
        )

    def import_from_file(
        self,
        doc_id: str,
        title: str,
        file_path: str,
        source_type: str,
        metadata: dict[str, str],
    ) -> KnowledgeDocument:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return self.import_from_text(
            doc_id=doc_id,
            title=title,
            source=str(path),
            source_type=source_type,
            content=content,
            metadata=metadata,
            ingested_at=datetime.now(timezone.utc),
        )

    def _chunk_text(self, doc_id: str, text: str) -> list[DocumentChunk]:
        if not text.strip():
            return []

        chunks: list[DocumentChunk] = []
        paragraphs = text.split("\n\n")
        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= self.chunk_size or not current_chunk:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{doc_id}-chunk-{chunk_index:04d}",
                        doc_id=doc_id,
                        text=current_chunk,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    current_chunk = current_chunk[-self.chunk_overlap :] + "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{doc_id}-chunk-{chunk_index:04d}",
                    doc_id=doc_id,
                    text=current_chunk,
                    chunk_index=chunk_index,
                )
            )

        return chunks
