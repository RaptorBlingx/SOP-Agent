"""Unit tests for retrieval modules."""

import pytest


def test_document_map_extraction(sample_sop_text):
    from app.retrieval.document_map import extract_sections

    sections = extract_sections(sample_sop_text, "test.md")
    assert len(sections) > 0
    headings = [s.heading for s in sections]
    assert any("Pre-Arrival" in h for h in headings)
    assert any("Day One" in h for h in headings)


def test_document_map_store_and_get():
    from app.retrieval.document_map import (
        store_document_map, get_document_map, clear_document_map,
        DocumentMapEntry, SectionInfo,
    )

    entry = DocumentMapEntry(
        source_file="test.pdf",
        sections=[
            SectionInfo(heading="Section 1", level=1, text="Content 1"),
            SectionInfo(heading="Section 2", level=1, text="Content 2"),
        ],
        total_chars=1000,
    )

    store_document_map("test-collection", entry)
    result = get_document_map("test-collection")
    assert len(result) >= 1
    assert len(result[-1].sections) == 2

    clear_document_map("test-collection")
    assert len(get_document_map("test-collection")) == 0


def test_rrf_fusion():
    from app.retrieval.rerank import reciprocal_rank_fusion

    hits_a = [
        {"chunk_id": "a", "content": "alpha", "score": 0.9},
        {"chunk_id": "b", "content": "beta", "score": 0.8},
    ]
    hits_b = [
        {"chunk_id": "b", "content": "beta", "score": 0.95},
        {"chunk_id": "c", "content": "gamma", "score": 0.7},
    ]

    fused = reciprocal_rank_fusion(hits_a, hits_b, k=60)
    assert len(fused) == 3
    ids = [h["chunk_id"] for h in fused]
    assert "b" in ids


def test_deduplication():
    from app.retrieval.rerank import deduplicate_hits

    hits = [
        {"chunk_id": "1", "content": "This is the exact same content repeated"},
        {"chunk_id": "2", "content": "This is the exact same content repeated"},
        {"chunk_id": "3", "content": "Completely different text about another topic"},
    ]

    deduped = deduplicate_hits(hits)
    assert len(deduped) == 2


def test_evidence_pack_diversity():
    from app.retrieval.rerank import build_evidence_pack

    hits = [
        {"chunk_id": "1", "content": "A", "score": 0.9, "source_file": "a.pdf"},
        {"chunk_id": "2", "content": "B", "score": 0.85, "source_file": "a.pdf"},
        {"chunk_id": "3", "content": "C", "score": 0.8, "source_file": "b.pdf"},
        {"chunk_id": "4", "content": "D", "score": 0.75, "source_file": "c.pdf"},
    ]

    pack = build_evidence_pack(hits, max_items=3)
    sources = {h.get("source_file") for h in pack}
    assert len(sources) >= 2
