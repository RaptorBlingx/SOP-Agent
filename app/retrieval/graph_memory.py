"""GraphRAG memory overlay — stub behind ENABLE_GRAPH_MEMORY flag (Section 6.7).

Decision from spec: GraphRAG is not a day-one dependency.
This module provides the interface contract so the rest of the system
can be coded against it, but the implementation is a no-op until
the feature flag is enabled and a real graph store is integrated.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("retrieval.graph_memory")


async def query_graph_memory(
    query: str,
    collection_id: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Query the graph memory store for relationship-based evidence.

    Returns an empty list when ENABLE_GRAPH_MEMORY is false.
    """
    settings = get_settings()
    if not settings.enable_graph_memory:
        return []

    logger.info("Graph memory query (stub): %s", query[:80])
    # TODO: Implement graph memory when relationship reasoning is needed
    return []


async def index_graph_relations(
    collection_id: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> int:
    """Index extracted entities and relations into the graph store.

    Returns 0 when ENABLE_GRAPH_MEMORY is false.
    """
    settings = get_settings()
    if not settings.enable_graph_memory:
        return 0

    logger.info("Graph memory indexing (stub): %d entities, %d relations",
                len(entities), len(relations))
    # TODO: Implement graph indexing
    return 0
