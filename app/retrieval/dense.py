"""ChromaDB dense vector retrieval wrapper (Section 6.5 Layer 2)."""

from __future__ import annotations

import json
from typing import Any

import chromadb

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("retrieval.dense")

_client: chromadb.ClientAPI | None = None


def _sanitize_metadata_value(value: Any) -> Any:
    """Convert metadata values to Chroma-compatible scalar types."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def _sanitize_metadatas(metadatas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize all metadata dicts before sending them to ChromaDB."""
    return [
        {key: _sanitize_metadata_value(value) for key, value in metadata.items()}
        for metadata in metadatas
    ]


def get_chroma_client() -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client singleton."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = chromadb.PersistentClient(path=settings.chromadb_path)
        logger.info("ChromaDB client initialized at %s", settings.chromadb_path)
    return _client


def get_or_create_collection(collection_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection by ID."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=collection_id,
        metadata={"hnsw:space": "cosine"},
    )


def delete_collection(collection_id: str) -> None:
    """Delete a ChromaDB collection."""
    client = get_chroma_client()
    try:
        client.delete_collection(name=collection_id)
        logger.info("Deleted collection %s", collection_id)
    except ValueError:
        logger.warning("Collection %s not found for deletion", collection_id)


def chroma_add(
    collection_id: str,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """Add documents with embeddings to a ChromaDB collection."""
    collection = get_or_create_collection(collection_id)
    safe_metadatas = _sanitize_metadatas(metadatas)
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=safe_metadatas,
    )


def chroma_search(
    query_embedding: list[float],
    collection_id: str,
    k: int = 8,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Dense similarity search against a ChromaDB collection."""
    collection = get_or_create_collection(collection_id)
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    hits = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            hits.append({
                "chunk_id": doc_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 1.0,
                "score": 1.0 - (results["distances"][0][i] if results["distances"] else 1.0),
            })
    return hits


def chroma_count(collection_id: str) -> int:
    """Return the number of documents in a collection."""
    collection = get_or_create_collection(collection_id)
    return collection.count()
