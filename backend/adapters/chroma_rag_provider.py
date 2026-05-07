"""
ChromaRAGProvider — naive implementation of RAGProvider Protocol.

Wraps `chromadb.PersistentClient`. One ChromaDB collection per
`collection` argument.

ChromaDB is synchronous; async methods use `asyncio.to_thread` to keep
the event loop free.

Future replacement: possibly a managed KB service, but for now Chroma
stays.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaRAGProvider:
    """ChromaDB-backed vector store adapter."""

    def __init__(self, persist_directory: Optional[str] = None) -> None:
        path = persist_directory or os.getenv(
            "CHROMA_DB_PATH", "./chroma_db/exception_agent"
        )
        abs_path = str(Path(path).resolve())
        self._client = chromadb.PersistentClient(
            path=abs_path,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info("ChromaRAGProvider initialized, path=%s", abs_path)

    def _get_or_create(self, collection: str):
        return self._client.get_or_create_collection(name=collection)

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        def _sync() -> None:
            col = self._get_or_create(collection)
            col.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
        await asyncio.to_thread(_sync)

    async def similarity_search(
        self,
        collection: str,
        query: str,
        *,
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        def _sync() -> list[dict[str, Any]]:
            col = self._get_or_create(collection)
            results = col.query(
                query_texts=[query],
                n_results=top_k,
                where=filter,
            )
            # Chroma returns parallel lists; flatten for position 0 (single query)
            out: list[dict[str, Any]] = []
            ids_list = (results.get("ids") or [[]])[0]
            docs_list = (results.get("documents") or [[]])[0]
            metas_list = (results.get("metadatas") or [[]])[0]
            dists_list = (results.get("distances") or [[]])[0]
            for i, _id in enumerate(ids_list):
                out.append({
                    "id": _id,
                    "document": docs_list[i] if i < len(docs_list) else None,
                    "metadata": metas_list[i] if i < len(metas_list) else {},
                    "distance": dists_list[i] if i < len(dists_list) else None,
                })
            return out

        return await asyncio.to_thread(_sync)

    async def delete(self, collection: str, ids: list[str]) -> None:
        def _sync() -> None:
            col = self._get_or_create(collection)
            col.delete(ids=ids)
        await asyncio.to_thread(_sync)

    def collection_count(self, collection: str) -> int:
        """Synchronous helper for the dashboard."""
        return self._get_or_create(collection).count()
