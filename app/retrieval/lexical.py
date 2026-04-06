"""SQLite FTS5 lexical (BM25) search layer (Section 6.5 Layer 2)."""

from __future__ import annotations

from typing import Any

from app.core.database import store_lexical_chunk, lexical_fts_search, delete_lexical_chunks
from app.core.logging import get_logger

logger = get_logger("retrieval.lexical")


async def index_chunks(
    collection_id: str,
    chunks: list[dict[str, Any]],
) -> int:
    """Index a batch of chunks into the FTS5 lexical index."""
    count = 0
    for chunk in chunks:
        await store_lexical_chunk(
            collection_id=collection_id,
            chunk_id=chunk["chunk_id"],
            source_file=chunk.get("source_file", ""),
            content=chunk["content"],
            section_path=chunk.get("section_path"),
            page_number=chunk.get("page_number"),
        )
        count += 1
    logger.info("Indexed %d chunks in lexical index for %s", count, collection_id)
    return count


async def lexical_search(
    query: str,
    collection_id: str,
    k: int = 8,
) -> list[dict[str, Any]]:
    """BM25 search via SQLite FTS5.

    Returns results with keys: chunk_id, content, source_file, section_path,
    page_number, score (negated rank, higher is better).
    """
    # FTS5 MATCH requires sanitized input
    sanitized = _sanitize_fts_query(query)
    if not sanitized:
        return []

    try:
        rows = await lexical_fts_search(sanitized, collection_id, k)
    except Exception as exc:
        logger.warning("Lexical search failed for query '%s': %s", query, exc)
        return []

    hits = []
    for row in rows:
        hits.append({
            "chunk_id": row.get("chunk_id", ""),
            "content": row.get("content", ""),
            "source_file": row.get("source_file", ""),
            "section_path": row.get("section_path"),
            "page_number": row.get("page_number"),
            "score": -row.get("rank", 0),  # FTS5 rank is negative; negate for consistency
        })
    return hits


async def clear_lexical_index(collection_id: str) -> None:
    """Remove all lexical chunks for a collection."""
    await delete_lexical_chunks(collection_id)
    logger.info("Cleared lexical index for %s", collection_id)


def _sanitize_fts_query(query: str) -> str:
    """Sanitize a query for FTS5 MATCH syntax.

    Wraps each word in quotes to prevent syntax errors from special chars.
    """
    words = query.strip().split()
    if not words:
        return ""
    # Quote each term and join with OR for broad matching
    return " OR ".join(f'"{w}"' for w in words[:20])
