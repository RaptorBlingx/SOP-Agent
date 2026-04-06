"""Document map for section-level retrieval (Section 6.5 Layer 1).

Stores file/section-level summaries for the planner to quickly identify
the most relevant files and sections for a given task.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger("retrieval.document_map")


@dataclass
class SectionInfo:
    """A section extracted from a document."""
    heading: str
    level: int
    text: str
    page_number: int | None = None
    char_start: int = 0
    char_end: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentMapEntry:
    """Summary of a single ingested document."""
    source_file: str
    sections: list[SectionInfo] = field(default_factory=list)
    total_chars: int = 0

    @property
    def section_headings(self) -> list[str]:
        return [s.heading for s in self.sections]

    def to_summary_text(self) -> str:
        """Produce a compact text summary for the planner."""
        lines = [f"File: {self.source_file} ({self.total_chars} chars, {len(self.sections)} sections)"]
        for s in self.sections:
            prefix = "  " * s.level
            lines.append(f"{prefix}- {s.heading}")
        return "\n".join(lines)


# In-memory document map per collection
_document_maps: dict[str, list[DocumentMapEntry]] = {}


def store_document_map(collection_id: str, entry: DocumentMapEntry) -> None:
    """Store a document map entry for a collection."""
    _document_maps.setdefault(collection_id, []).append(entry)


def get_document_map(collection_id: str) -> list[DocumentMapEntry]:
    """Retrieve all document map entries for a collection."""
    return _document_maps.get(collection_id, [])


def get_document_map_summary(collection_id: str) -> str:
    """Get a text summary of all documents in a collection for the planner."""
    entries = get_document_map(collection_id)
    if not entries:
        return "No documents indexed."
    return "\n\n".join(e.to_summary_text() for e in entries)


def clear_document_map(collection_id: str) -> None:
    """Clear the document map for a collection."""
    _document_maps.pop(collection_id, None)


def extract_sections(raw_text: str, source_file: str = "") -> list[SectionInfo]:
    """Extract structured sections from raw document text.

    Recognizes markdown-style headings (# ## ###) and numbered sections
    (1. 2. 1.1 etc). Preserves heading hierarchy for the document map.
    """
    lines = raw_text.split("\n")
    sections: list[SectionInfo] = []
    current_heading = "Introduction"
    current_level = 0
    current_lines: list[str] = []
    char_pos = 0

    heading_patterns = [
        (re.compile(r"^(#{1,6})\s+(.+)"), "markdown"),
        (re.compile(r"^(\d+)\.\s+([A-Z].{2,})"), "numbered"),
    ]

    for line in lines:
        matched = False
        for pattern, style in heading_patterns:
            m = pattern.match(line.strip())
            if m:
                # Save previous section
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        sections.append(SectionInfo(
                            heading=current_heading,
                            level=current_level,
                            text=text,
                            char_start=char_pos - len(text),
                            char_end=char_pos,
                            metadata={"source_file": source_file},
                        ))

                # Start new section
                if style == "markdown":
                    current_level = len(m.group(1))
                    current_heading = m.group(2).strip()
                else:
                    current_level = m.group(1).count(".") + 1
                    current_heading = m.group(2).strip()

                current_lines = []
                matched = True
                break

        if not matched:
            current_lines.append(line)

        char_pos += len(line) + 1  # +1 for newline

    # Final section
    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append(SectionInfo(
                heading=current_heading,
                level=current_level,
                text=text,
                char_start=char_pos - len(text),
                char_end=char_pos,
                metadata={"source_file": source_file},
            ))

    # If no sections were detected, treat entire text as one section
    if not sections and raw_text.strip():
        sections.append(SectionInfo(
            heading="Document",
            level=0,
            text=raw_text.strip(),
            char_start=0,
            char_end=len(raw_text),
            metadata={"source_file": source_file},
        ))

    return sections
