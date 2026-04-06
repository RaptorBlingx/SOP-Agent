"""Unit tests for app.core.database."""

import pytest


@pytest.mark.asyncio
async def test_create_and_get_session(initialized_db, mock_settings):
    from app.core import database as db

    result = await db.create_session(
        task_description="Test",
        collection_id="col-001",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3:4b",
        session_id="test-001",
    )
    assert result["session_id"] == "test-001"

    session = await db.get_session("test-001")
    assert session is not None
    assert session["status"] == "planning"
    assert session["collection_id"] == "col-001"


@pytest.mark.asyncio
async def test_update_session(initialized_db, mock_settings):
    from app.core import database as db

    await db.create_session(
        task_description="Test",
        collection_id="col-002",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3:4b",
        session_id="test-002",
    )
    await db.update_session("test-002", status="executing")

    session = await db.get_session("test-002")
    assert session["status"] == "executing"


@pytest.mark.asyncio
async def test_delete_session(initialized_db, mock_settings):
    from app.core import database as db

    await db.create_session(
        task_description="Test",
        collection_id="col-003",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3:4b",
        session_id="test-003",
    )
    await db.delete_session("test-003")
    session = await db.get_session("test-003")
    assert session is None


@pytest.mark.asyncio
async def test_create_and_get_steps(initialized_db, mock_settings):
    from app.core import database as db

    await db.create_session(
        task_description="Test",
        collection_id="col-004",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3:4b",
        session_id="test-004",
    )
    await db.create_step("test-004", step_order=1, title="First step", objective="Do thing")
    await db.create_step("test-004", step_order=2, title="Second step", objective="Do other")

    steps = await db.get_steps("test-004")
    assert len(steps) == 2
    assert steps[0]["title"] == "First step"
    assert steps[1]["step_order"] == 2


@pytest.mark.asyncio
async def test_add_and_get_evidence(initialized_db, mock_settings):
    from app.core import database as db

    await db.create_session(
        task_description="Test",
        collection_id="col-005",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3:4b",
        session_id="test-005",
    )
    step_id = await db.create_step("test-005", step_order=1, title="Step 1", objective="Test")
    await db.add_evidence(
        step_id=step_id,
        session_id="test-005",
        chunk_id="chunk-1",
        source_file="doc.pdf",
        quote="Important text here",
        score=0.95,
    )

    evidence = await db.get_evidence_for_step(step_id)
    assert len(evidence) == 1
    assert evidence[0]["chunk_id"] == "chunk-1"
    assert evidence[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_run_events(initialized_db, mock_settings):
    from app.core import database as db

    await db.create_session(
        task_description="Test",
        collection_id="col-006",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3:4b",
        session_id="test-006",
    )
    await db.add_run_event("test-006", "test_event", {"key": "value"})

    events = await db.get_run_events("test-006")
    assert len(events) == 1
    assert events[0]["event_type"] == "test_event"


@pytest.mark.asyncio
async def test_lexical_store_and_search(initialized_db, mock_settings):
    from app.core import database as db

    await db.store_lexical_chunk(
        chunk_id="lx-1",
        collection_id="col-1",
        content="Employee onboarding procedure step one",
        source_file="onboarding.pdf",
    )
    await db.store_lexical_chunk(
        chunk_id="lx-2",
        collection_id="col-1",
        content="Financial reporting quarterly review",
        source_file="finance.pdf",
    )

    results = await db.lexical_fts_search("onboarding", "col-1", k=5)
    assert len(results) >= 1
