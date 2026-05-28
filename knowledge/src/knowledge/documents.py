from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from knowledge.schema import KnowledgeDocument, DocumentChunk

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


class ContentSelectionStrategy(str, Enum):
    RAW_CARD = "raw_card"
    EXTRACTABLE_CONTENT = "extractable_content"
    SOURCE_NOTES_PLUS_EXTRACTABLE = "source_notes_plus_extractable"


RAW_CARD = ContentSelectionStrategy.RAW_CARD.value
EXTRACTABLE_CONTENT = ContentSelectionStrategy.EXTRACTABLE_CONTENT.value
SOURCE_NOTES_PLUS_EXTRACTABLE = ContentSelectionStrategy.SOURCE_NOTES_PLUS_EXTRACTABLE.value
CHUNK_STRATEGIES = {RAW_CARD, EXTRACTABLE_CONTENT, SOURCE_NOTES_PLUS_EXTRACTABLE}


def _normalize_content_strategy(strategy: str | ContentSelectionStrategy) -> ContentSelectionStrategy:
    try:
        return ContentSelectionStrategy(strategy)
    except ValueError as exc:
        raise ValueError(f"unknown chunk strategy: {strategy}") from exc


def select_document_content(content: str, strategy: str | ContentSelectionStrategy = RAW_CARD) -> str:
    """Select the text variant that an extraction experiment should see."""
    content_strategy = _normalize_content_strategy(strategy)
    if content_strategy is ContentSelectionStrategy.RAW_CARD:
        return content

    extract_marker = "## Extractable Source Content"
    notes_marker = "## Source Notes"
    if extract_marker in content:
        extractable = content.split(extract_marker, 1)[1].split("\n## ", 1)[0].strip()
    else:
        extractable = content.strip()
    if content_strategy is ContentSelectionStrategy.EXTRACTABLE_CONTENT:
        return extractable

    notes = ""
    if notes_marker in content:
        after_notes = content.split(notes_marker, 1)[1]
        notes = after_notes.split("## ", 1)[0].strip()
    if notes:
        return f"## Source Notes\n\n{notes}\n\n## Extractable Source Content\n\n{extractable}"
    return extractable


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
        chunk_strategy: str | ContentSelectionStrategy = RAW_CARD,
    ) -> KnowledgeDocument:
        chunk_strategy_value = _normalize_content_strategy(chunk_strategy).value
        selected_content = select_document_content(content, chunk_strategy_value)
        chunks = self._chunk_text(doc_id, selected_content, chunk_strategy=chunk_strategy_value)
        metadata = dict(metadata)
        metadata.setdefault("chunk_strategy", chunk_strategy_value)
        return KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            source=source,
            source_type=source_type,
            content_raw=selected_content,
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
        chunk_strategy: str | ContentSelectionStrategy = RAW_CARD,
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
            chunk_strategy=chunk_strategy,
        )

    def _chunk_text(
        self, doc_id: str, text: str, chunk_strategy: str = RAW_CARD
    ) -> list[DocumentChunk]:
        if not text.strip():
            return []

        chunks: list[DocumentChunk] = []
        paragraphs = text.split("\n\n")
        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_start = text.find(para, current_start if current_chunk else 0)
            if para_start < 0:
                para_start = 0

            if len(current_chunk) + len(para) + 2 <= self.chunk_size or not current_chunk:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                    current_start = para_start
            else:
                chunk_end = current_start + len(current_chunk)
                chunks.append(
                    self._make_chunk(
                        doc_id, current_chunk, chunk_index, current_start, chunk_end, chunk_strategy
                    )
                )
                chunk_index += 1

                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    overlap_prefix = current_chunk[-self.chunk_overlap :]
                    current_chunk = overlap_prefix + "\n\n" + para
                    current_start = max(0, chunk_end - self.chunk_overlap)
                else:
                    current_chunk = para
                    current_start = para_start

        if current_chunk:
            chunk_end = current_start + len(current_chunk)
            chunks.append(
                self._make_chunk(
                    doc_id, current_chunk, chunk_index, current_start, chunk_end, chunk_strategy
                )
            )

        return chunks

    def _make_chunk(
        self,
        doc_id: str,
        text: str,
        chunk_index: int,
        start_char: int,
        end_char: int,
        chunk_strategy: str,
    ) -> DocumentChunk:
        prefix = text[: min(self.chunk_overlap, len(text))]
        starts_mid_word = bool(text and text[0].isalnum() and start_char > 0)
        metadata = {
            "chunk_strategy": chunk_strategy,
            "chunk_index": str(chunk_index),
            "chunk_start_char": str(start_char),
            "chunk_end_char": str(end_char),
            "chunk_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "overlap_prefix": prefix,
            "starts_mid_word": str(starts_mid_word).lower(),
            "contains_frontmatter": str(text.lstrip().startswith("---")).lower(),
            "contains_copyright_handling": str("copyright" in text.lower()).lower(),
        }
        return DocumentChunk(
            chunk_id=f"{doc_id}-chunk-{chunk_index:04d}",
            doc_id=doc_id,
            text=text,
            chunk_index=chunk_index,
            metadata=metadata,
        )
