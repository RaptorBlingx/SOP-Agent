# SOP Agent — Architecture Guide

## System Architecture

SOP Agent is a modular AI application composed of four main layers:

1. **Presentation Layer** — Streamlit Operator Console + FastAPI REST endpoints
2. **Orchestration Layer** — LangGraph 8-node StateGraph with conditional routing
3. **Intelligence Layer** — Multi-provider LLM abstraction + hybrid RAG retrieval
4. **Persistence Layer** — SQLite (WAL mode) + ChromaDB vector store

---

## Component Diagram

```
                    ┌─────────────────────────┐
                    │   Operator Console      │
                    │   (Streamlit :8501)      │
                    └────────────┬────────────┘
                                 │ HTTP + SSE
                    ┌────────────▼────────────┐
                    │   FastAPI Gateway        │
                    │   (:8000)                │
                    │                          │
                    │  ┌─────────────────────┐ │
                    │  │  Route Handlers      │ │
                    │  │  ingest · execute ·  │ │
                    │  │  intervene · report  │ │
                    │  │  session · MCP       │ │
                    │  └────────┬────────────┘ │
                    │           │              │
                    │  ┌────────▼────────────┐ │
                    │  │  LangGraph Engine   │ │
                    │  │  (8-node graph)      │ │
                    │  └────────┬────────────┘ │
                    └───────────┼──────────────┘
                      ┌─────────┼─────────┐
                ┌─────▼───┐ ┌──▼────┐ ┌──▼──────┐
                │ChromaDB │ │SQLite │ │ LLM API │
                │(vectors)│ │(state)│ │(Gemini/ │
                │         │ │+ FTS5 │ │OpenAI/  │
                └─────────┘ └───────┘ │Anthropic│
                                      └─────────┘
```

---

## LangGraph StateGraph

The agent graph consists of 8 custom nodes plus 2 built-in LangGraph nodes (`__start__`, `__end__`):

### Node Descriptions

| # | Node | File | Responsibility |
|---|---|---|---|
| 1 | `intake` | `nodes/intake.py` | Validate session, load/create DB records, check for resume |
| 2 | `planner` | `nodes/planner.py` | Generate structured execution plan from task + document map |
| 3 | `evidence_router` | `nodes/evidence_router.py` | Run hybrid retrieval for current step, build evidence pack |
| 4 | `executor` | `nodes/executor.py` | Generate action recommendation with confidence score |
| 5 | `verifier` | `nodes/verifier.py` | Independent verification: policy checks + evidence grounding |
| 6 | `approval_gate` | `nodes/approval_gate.py` | Human-on-the-loop interrupt point |
| 7 | `replanner` | `nodes/replanner.py` | Rewrite remaining plan steps (preserves completed) |
| 8 | `reporter` | `nodes/reporter.py` | Generate final Markdown report with full citations |

### Routing Logic

```
__start__ → intake
intake → planner                                (always)
planner → evidence_router                       (always)
evidence_router → executor                      (always)
executor → verifier                             (always)
verifier → {approval_gate, replanner, reporter} (conditional: route_from_verifier)
approval_gate → {evidence_router, replanner, reporter, END} (conditional: route_from_approval_gate)
replanner → evidence_router                     (always)
reporter → __end__                              (always)
```

### Conditional Routing Functions (`routing.py`)

- **`route_from_verifier`**: If step needs approval → `approval_gate`. If current step < total → next step via `evidence_router`. If all done → `reporter`.
- **`route_from_approval_gate`**: Based on `operator_action`: approve/override → `evidence_router` (next step), skip → `evidence_router` (next step), abort → `reporter` (early finish), request_replan → `replanner`.

### State Schema (`AgentState`)

Key fields in the TypedDict state:

```python
class AgentState(TypedDict):
    session_id: str
    collection_id: str
    task_description: str
    document_map: list[SectionInfo]
    plan: list[PlanStep]
    steps: list[ExecutionStep]      # completed/in-progress steps
    current_step_index: int
    active_evidence_pack: list[EvidenceRef]
    needs_approval: bool
    final_report: str
    error: str | None
```

---

## Retrieval Pipeline

### Layer 1: Document Map

On ingestion, the system builds a section-level index of the document structure. The planner uses this to understand SOP organization before generating a plan.

### Layer 2: Hybrid Candidates

For each step during execution:
- **Dense**: ChromaDB cosine similarity search (k=8 candidates)
- **Lexical**: SQLite FTS5 BM25 ranking (k=8 candidates)

### Layer 3: Fusion & Diversity

1. **Reciprocal Rank Fusion (RRF)** — Combines dense and lexical results using score formula: `1 / (k + rank)` with k=60
2. **Deduplication** — Removes exact-match chunks by content hash
3. **Source Diversification** — Round-robin across unique source documents to prevent single-source bias
4. **Top-K Selection** — Final evidence pack: top 5 diverse chunks

### Layer 4: Graph Memory (Optional)

Feature-flagged (`ENABLE_GRAPH_MEMORY=true`). Provides relationship-based retrieval using entity extraction. Currently a structured stub awaiting a graph database backend.

---

## Database Schema

### Tables

```sql
-- Core session tracking
sessions (id TEXT PK, task TEXT, collection_id TEXT, status TEXT,
          config TEXT, created_at TEXT, updated_at TEXT)

-- Execution plan steps
session_steps (id TEXT PK, session_id TEXT FK, step_index INT,
               title TEXT, description TEXT, status TEXT,
               result TEXT, confidence REAL, created_at TEXT)

-- Evidence citations per step
step_evidence (id TEXT PK, step_id TEXT FK, source_file TEXT,
               section TEXT, page INT, quote TEXT, score REAL)

-- Operator intervention audit log
approvals (id TEXT PK, session_id TEXT FK, step_id TEXT,
           action TEXT, reason TEXT, created_at TEXT)

-- Execution event timeline
run_events (id TEXT PK, session_id TEXT FK, event_type TEXT,
            node TEXT, data TEXT, timestamp TEXT)

-- File ingestion records
ingested_files (id TEXT PK, session_id TEXT, collection_id TEXT,
                filename TEXT, chunk_count INT, created_at TEXT)

-- Full-text search (virtual table)
lexical_chunks (id TEXT, collection_id TEXT, content TEXT,
                source_file TEXT, metadata TEXT)
lexical_chunks_fts (FTS5 virtual table indexing content + source_file)
```

### Connection Pattern

All DB operations use an async context manager:

```python
async with get_connection() as conn:
    await conn.execute(...)
    # auto-commits on exit
```

SQLite WAL mode enables concurrent reads with single writer.

---

## Service Layer

### Ingestion Pipeline (`services/ingestion.py`)

1. **File validation** — Extension whitelist + MIME check + size limit (20 MB)
2. **Parsing** — `pdfplumber` (PDF), `python-docx` (DOCX), plain read (TXT/MD)
3. **Chunking** — Recursive character splitting (1000 chars, 200 overlap)
4. **Embedding** — Provider-dependent (Gemini/OpenAI/Ollama embeddings)
5. **Indexing** — Parallel: ChromaDB dense index + SQLite FTS5 lexical index
6. **Document Map** — Section-level structural index for planner context
7. **Versioning** — Collection version tracking for re-ingestion support

### Report Export (`services/report_export.py`)

Generates structured Markdown reports with:
- Session metadata and timing
- Step-by-step execution results
- Evidence citations with source, page, and relevance score
- Operator interventions log
- Confidence metrics summary

---

## Security Architecture

| Concern | Mitigation |
|---|---|
| Secrets | Environment variables only; never logged or returned in API |
| PII in logs | `RedactingFormatter` with regex patterns for emails, API keys, SSNs, phone numbers |
| File uploads | Extension whitelist (`.pdf`, `.docx`, `.txt`, `.md`) + MIME validation + 20 MB limit |
| Path traversal | `Path.name` sanitization strips directory components |
| Prompt injection | Evidence wrapped in `<evidence>` tags with explicit system instructions |
| CORS | Configurable origins via `CORS_ORIGINS` env var |
| LLM rate limiting | Token bucket with configurable RPM/TPM limits |

---

## Error Handling & Resilience

- **LLM calls**: Wrapped with `tenacity` retry (3 attempts, exponential backoff)
- **Structured output**: Primary `with_structured_output()` with fallback regex extraction
- **Graph errors**: Caught per-node, stored in `AgentState.error`, surfaced in report
- **API errors**: FastAPI exception handlers return structured JSON error responses
- **Database**: WAL mode prevents read blocking; `@asynccontextmanager` ensures connections close

---

## Configuration Architecture

`app/core/config.py` uses Pydantic `BaseSettings` with:
- `.env` file loading
- Type validation and defaults
- `@lru_cache` singleton pattern via `get_settings()`
- Nested CORS origins parsing (comma-separated string → list)
