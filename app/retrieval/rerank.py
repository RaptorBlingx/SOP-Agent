"""Reciprocal-rank fusion, reranking, and evidence pack builder (Section 6.5 Layer 3)."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("retrieval.rerank")


def reciprocal_rank_fusion(
    *hit_lists: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank_i)) across all lists the document appears in.
    Higher score = more relevant.
    """
    rrf_scores: dict[str, float] = {}
    hit_map: dict[str, dict[str, Any]] = {}

    for hit_list in hit_lists:
        for rank, hit in enumerate(hit_list):
            chunk_id = hit["chunk_id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
            if chunk_id not in hit_map:
                hit_map[chunk_id] = hit

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)
    merged = []
    for cid in sorted_ids:
        entry = dict(hit_map[cid])
        entry["rrf_score"] = rrf_scores[cid]
        merged.append(entry)

    return merged


def deduplicate_hits(hits: list[dict[str, Any]], threshold: float = 0.9) -> list[dict[str, Any]]:
    """Remove near-duplicate chunks based on content overlap.

    Uses a simple Jaccard-like set overlap on word tokens.
    """
    seen_sets: list[set[str]] = []
    unique: list[dict[str, Any]] = []

    for hit in hits:
        words = set(hit.get("content", "").lower().split())
        is_dup = False
        for seen in seen_sets:
            if not words or not seen:
                continue
            overlap = len(words & seen) / max(len(words | seen), 1)
            if overlap >= threshold:
                is_dup = True
                break
        if not is_dup:
            seen_sets.append(words)
            unique.append(hit)

    return unique


def build_evidence_pack(
    hits: list[dict[str, Any]],
    max_items: int = 5,
) -> list[dict[str, Any]]:
    """Build a compact, diverse evidence pack from ranked hits.

    Prefers diversity across source files and sections.
    """
    deduped = deduplicate_hits(hits)

    # Diversify across source files
    by_source: dict[str, list[dict[str, Any]]] = {}
    for hit in deduped:
        src = hit.get("source_file", hit.get("metadata", {}).get("source_file", "unknown"))
        by_source.setdefault(src, []).append(hit)

    pack: list[dict[str, Any]] = []
    # Round-robin across sources
    source_keys = list(by_source.keys())
    idx = 0
    while len(pack) < max_items and any(by_source.values()):
        key = source_keys[idx % len(source_keys)]
        if by_source[key]:
            pack.append(by_source[key].pop(0))
        idx += 1
        # Remove exhausted sources
        source_keys = [k for k in source_keys if by_source[k]]
        if not source_keys:
            break

    return pack


def retrieve_evidence_pack(
    dense_hits: list[dict[str, Any]],
    lexical_hits: list[dict[str, Any]],
    max_items: int = 5,
) -> list[dict[str, Any]]:
    """Full evidence retrieval pipeline: fuse → deduplicate → diversify → pack."""
    merged = reciprocal_rank_fusion(dense_hits, lexical_hits)
    return build_evidence_pack(merged, max_items=max_items)
