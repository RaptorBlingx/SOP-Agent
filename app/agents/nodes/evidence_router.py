"""Node 3: evidence_router_node — hybrid retrieval per step (Section 5.2, 6.5).

Retrieves step-specific evidence using hybrid (dense + lexical) retrieval.
Decides if retrieval is sufficient or if broader context is needed.
"""

from __future__ import annotations

from app.agents.state import AgentState, EvidenceRef
from app.core.llm_factory import get_embedding_model
from app.core.logging import get_logger
from app.retrieval.dense import chroma_search
from app.retrieval.lexical import lexical_search
from app.retrieval.rerank import retrieve_evidence_pack
from app.retrieval.graph_memory import query_graph_memory
from app.core import database as db

logger = get_logger("agents.nodes.evidence_router")


async def evidence_router_node(state: AgentState) -> dict:
    """Retrieve evidence for the current step using hybrid retrieval."""
    if state.current_step_index >= len(state.steps):
        logger.info("No more steps to retrieve evidence for")
        return {"status": "executing"}

    step = state.steps[state.current_step_index]
    query = f"{step.title}: {step.objective}"
    logger.info("Retrieving evidence for step %d: %s", step.order, step.title)

    # Layer 2: Hybrid candidate generation
    embedding_model = get_embedding_model()

    # Dense retrieval
    try:
        query_embedding = embedding_model.embed_query(query)
        dense_hits = chroma_search(
            query_embedding=query_embedding,
            collection_id=state.collection_id,
            k=8,
        )
    except Exception as exc:
        logger.warning("Dense retrieval failed: %s", exc)
        dense_hits = []

    # Lexical retrieval
    try:
        lexical_hits = await lexical_search(
            query=query,
            collection_id=state.collection_id,
            k=8,
        )
    except Exception as exc:
        logger.warning("Lexical retrieval failed: %s", exc)
        lexical_hits = []

    # Layer 3: Fuse, deduplicate, diversify
    evidence_pack = retrieve_evidence_pack(dense_hits, lexical_hits, max_items=5)

    # Layer 4: Optional graph memory
    graph_hits = await query_graph_memory(query, state.collection_id)
    if graph_hits:
        evidence_pack.extend(graph_hits[:2])

    # Convert to EvidenceRef objects
    evidence_refs: list[EvidenceRef] = []
    for hit in evidence_pack:
        metadata = hit.get("metadata", {})
        evidence_refs.append(EvidenceRef(
            chunk_id=hit.get("chunk_id", ""),
            source_file=metadata.get("source_file", hit.get("source_file", "unknown")),
            section_path=metadata.get("section_path", hit.get("section_path")),
            page_number=metadata.get("page_number", hit.get("page_number")),
            quote=hit.get("content", "")[:500],
            score=hit.get("rrf_score", hit.get("score", 0.0)),
        ))

    # Store evidence in DB
    for ref in evidence_refs:
        await db.add_evidence(
            session_id=state.session_id,
            step_id=step.step_id,
            chunk_id=ref.chunk_id,
            source_file=ref.source_file,
            quote=ref.quote,
            score=ref.score,
            section_path=ref.section_path,
            page_number=ref.page_number,
        )

    # Update the step's evidence
    updated_steps = list(state.steps)
    updated_steps[state.current_step_index] = step.model_copy(
        update={"evidence": evidence_refs, "status": "executing"}
    )

    await db.update_step(step.step_id, status="executing")
    await db.add_run_event(
        state.session_id, "evidence_loaded",
        {"step_id": step.step_id, "evidence_count": len(evidence_refs)}
    )

    logger.info("Loaded %d evidence items for step %d", len(evidence_refs), step.order)

    return {
        "steps": updated_steps,
        "active_evidence_pack": evidence_refs,
        "run_events": state.run_events + [
            {"event_type": "evidence_loaded", "detail": f"{len(evidence_refs)} items for step {step.order}"}
        ],
    }
