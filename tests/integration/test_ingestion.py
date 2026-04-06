"""Integration tests for the ingestion pipeline."""

import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_validate_upload_valid_txt(tmp_data_dir):
    from app.services.ingestion import validate_upload

    content = b"Hello world content"
    result = await validate_upload("test.txt", content)
    assert result == content


@pytest.mark.asyncio
async def test_validate_upload_invalid_extension(tmp_data_dir):
    from fastapi import HTTPException
    from app.services.ingestion import validate_upload

    with pytest.raises(HTTPException) as exc_info:
        await validate_upload("test.exe", b"\x00" * 100)
    assert exc_info.value.status_code == 415


def test_chunk_document(sample_sop_text):
    from app.services.ingestion import chunk_document

    chunks, sections = chunk_document(sample_sop_text, "test.md", "col-test")
    assert len(chunks) > 0
    for chunk in chunks:
        assert "content" in chunk
        assert "metadata" in chunk
        assert len(chunk["content"]) > 0


def test_parse_text():
    from app.services.ingestion import parse_text

    content = b"Line 1\nLine 2\nLine 3"
    result = parse_text(content)
    assert "Line 1" in result
    assert "Line 3" in result
