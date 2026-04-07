"""Full file ingestion pipeline — parse, chunk, embed, index (Section 11).

Supports PDF, DOCX, TXT, MD. Structure-aware chunking with section
preservation. Dual-indexes into ChromaDB (dense) and FTS5 (lexical).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile, HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.llm_factory import get_embedding_model
from app.core import database as db
from app.retrieval.dense import chroma_add, get_or_create_collection
from app.retrieval.lexical import index_chunks as lexical_index_chunks
from app.retrieval.document_map import (
    extract_sections,
    store_document_map,
    DocumentMapEntry,
    SectionInfo,
)

logger = get_logger("services.ingestion")

# ---------------------------------------------------------------------------
# File validation (Section 13.3)
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


async def validate_upload(filename: str, content: bytes) -> bytes:
    """Validate file extension, size, and MIME type."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"File type {ext} is not allowed. Supported: {ALLOWED_EXTENSIONS}")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_SIZE_BYTES // (1024*1024)}MB limit")

    # MIME type validation
    try:
        import magic
        mime = magic.from_buffer(content[:2048], mime=True)
        allowed_mimes = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/x-markdown",
            "application/octet-stream",  # fallback for some systems
        }
        if mime not in allowed_mimes:
            raise HTTPException(status_code=415, detail=f"MIME type {mime} is not allowed")
    except ImportError:
        logger.warning("python-magic not installed; skipping MIME validation")

    return content


# ---------------------------------------------------------------------------
# File parsers (Section 11.2)
# ---------------------------------------------------------------------------

def parse_pdf(content: bytes) -> str:
    """Extract text from a PDF using pdfplumber."""
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    if not text_parts:
        raise HTTPException(status_code=422, detail="PDF contains no extractable text (image-only PDFs not supported)")

    return "\n\n".join(text_parts)


def parse_docx(content: bytes) -> str:
    """Extract text from a DOCX using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise HTTPException(status_code=422, detail="DOCX contains no extractable text")
    return "\n\n".join(paragraphs)


def parse_text(content: bytes) -> str:
    """Decode plain text / markdown content."""
    return content.decode("utf-8", errors="replace")


async def parse_file(filename: str, content: bytes) -> str:
    """Route to the correct parser based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(content)
    elif ext == ".docx":
        return parse_docx(content)
    elif ext in (".txt", ".md"):
        return parse_text(content)
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")


# ---------------------------------------------------------------------------
# Structure-aware chunking (Section 6.3)
# ---------------------------------------------------------------------------

def chunk_document(
    raw_text: str,
    source_file: str,
    collection_id: str,
) -> tuple[list[dict[str, Any]], list[SectionInfo]]:
    """Chunk a document with structure awareness.

    Returns (chunks_with_metadata, sections).
    Each chunk dict has: chunk_id, content, metadata dict.
    """
    sections = extract_sections(raw_text, source_file=source_file)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1100,
        chunk_overlap=160,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
        length_function=len,
    )

    all_chunks: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for section in sections:
        if not section.text.strip():
            continue

        # Build section path from heading hierarchy
        section_path = section.heading

        splits = splitter.split_text(section.text)
        for i, text in enumerate(splits):
            chunk_id = str(uuid4())
            all_chunks.append({
                "chunk_id": chunk_id,
                "content": text,
                "metadata": {
                    "chunk_id": chunk_id,
                    "source_file": source_file,
                    "section_path": section_path,
                    "page_number": section.page_number,
                    "chunk_index": len(all_chunks),
                    "collection_id": collection_id,
                    "ingested_at": now,
                },
            })

    return all_chunks, sections


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def _chunk_list(lst: list, size: int = 50) -> list[list]:
    """Split a list into batches of the given size."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


# ---------------------------------------------------------------------------
# Main ingestion flow (Section 11.1)
# ---------------------------------------------------------------------------

async def ingest_files(
    files: list[tuple[str, bytes]],
    session_id: str,
    collection_id: str | None = None,
) -> dict[str, Any]:
    """Ingest one or more files: parse → chunk → embed → store.

    Args:
        files: List of (filename, content_bytes) tuples.
        session_id: Session this ingestion belongs to.
        collection_id: Optional override; defaults to sop_{session_id}.

    Returns:
        Dict with session_id, collection_id, total_chunks, files_processed.
    """
    collection_id = collection_id or f"sop_{session_id}"
    settings = get_settings()

    session = await db.get_session(session_id)
    if session is None:
        await db.create_session(
            session_id=session_id,
            task_description="Pending task description",
            collection_id=collection_id,
            reasoning_profile=settings.default_reasoning_profile,
            model_provider=settings.model_provider,
            model_name=settings.active_model_name,
        )
    elif session.get("collection_id") != collection_id:
        await db.update_session(
            session_id,
            collection_id=collection_id,
            model_provider=settings.model_provider,
            model_name=settings.active_model_name,
        )

    # Ensure collection exists
    get_or_create_collection(collection_id)
    embedding_model = get_embedding_model()

    total_chunks = 0
    files_processed: list[str] = []

    for filename, content in files:
        # Validate
        await validate_upload(filename, content)
        checksum = hashlib.sha256(content).hexdigest()

        # Parse
        raw_text = await parse_file(filename, content)
        logger.info("Parsed %s: %d chars", filename, len(raw_text))

        # Chunk with structure awareness
        chunks, sections = chunk_document(raw_text, filename, collection_id)
        if not chunks:
            logger.warning("No chunks produced from %s", filename)
            continue

        # Build document map entry
        doc_entry = DocumentMapEntry(
            source_file=filename,
            sections=[SectionInfo(
                heading=s.heading,
                level=s.level,
                text=s.text[:200] + "..." if len(s.text) > 200 else s.text,
                page_number=s.page_number,
                metadata=s.metadata,
            ) for s in sections],
            total_chars=len(raw_text),
        )
        store_document_map(collection_id, doc_entry)

        # Batch embed and store in ChromaDB
        for batch in _chunk_list(chunks, size=50):
            texts = [c["content"] for c in batch]
            metadatas = [c["metadata"] for c in batch]
            ids = [c["chunk_id"] for c in batch]

            embeddings = embedding_model.embed_documents(texts)
            chroma_add(
                collection_id=collection_id,
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            await asyncio.sleep(0.3)  # Rate-limit buffer

        # Index in lexical FTS5
        lexical_data = [
            {
                "chunk_id": c["chunk_id"],
                "content": c["content"],
                "source_file": c["metadata"]["source_file"],
                "section_path": c["metadata"].get("section_path"),
                "page_number": c["metadata"].get("page_number"),
            }
            for c in chunks
        ]
        await lexical_index_chunks(collection_id, lexical_data)

        # Record in SQLite
        await db.record_ingestion(
            session_id=session_id,
            filename=filename,
            file_size_bytes=len(content),
            checksum_sha256=checksum,
            chunk_count=len(chunks),
        )

        total_chunks += len(chunks)
        files_processed.append(filename)
        logger.info("Ingested %s: %d chunks", filename, len(chunks))

    return {
        "session_id": session_id,
        "collection_id": collection_id,
        "collection_version": 1,
        "total_chunks": total_chunks,
        "files_processed": files_processed,
        "status": "ready",
    }
