"""
RAGProvider — Protocol for vector-based retrieval augmented generation.

The naive implementation (adapters/chroma_rag_provider.py) wraps
ChromaDB. Future implementations may delegate to a managed KB service.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol


class RAGProvider(Protocol):
    """Contract for a vector search backend."""

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Insert or update documents in a collection."""
        ...

    async def similarity_search(
        self,
        collection: str,
        query: str,
        *,
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Semantic search. Returns [{id, document, metadata, distance}]."""
        ...

    async def delete(self, collection: str, ids: list[str]) -> None:
        """Remove documents by id."""
        ...
