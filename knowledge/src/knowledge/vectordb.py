from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from knowledge.schema import KnowledgeDocument, DocumentChunk


class KnowledgeSnippet:
    """Internal result type for vector search results.

    The bridge adapter converts this to the port-level KnowledgeSnippet
    defined in medidiet.ports.
    """

    def __init__(self, text: str, source_title: str, source_url: str,
                 chunk_id: str, relevance_score: float):
        self.text = text
        self.source_title = source_title
        self.source_url = source_url
        self.chunk_id = chunk_id
        self.relevance_score = relevance_score

    def __repr__(self) -> str:
        return (
            f"KnowledgeSnippet(chunk_id={self.chunk_id!r}, "
            f"relevance_score={self.relevance_score:.4f})"
        )


class KnowledgeVectorDB:
    """ChromaDB-backed vector store for knowledge document chunks.

    Handles indexing, semantic search, and deletion of document chunks.
    """

    def __init__(self, persist_dir: str = "data/chroma"):
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="knowledge_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._doc_metadata: dict[str, dict[str, str]] = {}

    def index_document(self, doc: KnowledgeDocument) -> None:
        """Index all chunks of a KnowledgeDocument into the vector store."""
        if not doc.chunks:
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for chunk in doc.chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            metadatas.append({
                "doc_id": doc.doc_id,
                "source_title": doc.title,
                "source_url": doc.source,
                "source_type": doc.source_type,
                "chunk_index": chunk.chunk_index,
            })

        self._doc_metadata[doc.doc_id] = {
            "title": doc.title,
            "source": doc.source,
        }

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query: str, top_k: int = 5,
               filter_source: str | None = None) -> list[KnowledgeSnippet]:
        """Semantic search over indexed chunks.

        Returns results sorted by relevance (most relevant first).
        """
        if self._collection.count() == 0:
            return []

        where_filter = None
        if filter_source is not None:
            where_filter = {"source_type": filter_source}

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            where=where_filter,
        )

        snippets: list[KnowledgeSnippet] = []
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for i, chunk_id in enumerate(ids):
            meta = metadatas[i]
            distance = distances[i]
            # Convert cosine distance to a 0-1 relevance score
            relevance_score = round(max(0, 1 - distance / 2), 4)

            snippets.append(
                KnowledgeSnippet(
                    text=documents[i],
                    source_title=meta.get("source_title", ""),
                    source_url=meta.get("source_url", ""),
                    chunk_id=chunk_id,
                    relevance_score=relevance_score,
                )
            )

        return snippets

    def search_by_condition(self, condition, top_k: int = 10) -> list[KnowledgeSnippet]:
        """Search using a ConceptCode or string condition as the query."""
        from medidiet.domain import ConceptCode
        if isinstance(condition, ConceptCode):
            query = condition.value.replace("_", " ")
        else:
            query = str(condition)
        return self.search(query, top_k=top_k)

    def delete_document(self, doc_id: str) -> None:
        """Remove all chunks belonging to a document from the index."""
        existing = self._collection.get(
            where={"doc_id": doc_id}
        )
        if existing and existing["ids"]:
            self._collection.delete(ids=existing["ids"])

        self._doc_metadata.pop(doc_id, None)
