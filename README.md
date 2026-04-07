# SOP Agent v1.2

> AI-powered Standard Operating Procedure execution engine with human-on-the-loop oversight.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-green.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SOP Agent ingests Standard Operating Procedure documents (PDF, DOCX, TXT, Markdown), builds an execution plan grounded in retrieved evidence, and walks through each step with independent verification — pausing for human approval when policy or uncertainty demands it. The final output is a traceable Markdown report with full evidence citations.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Using the Operator Console (UI)](#using-the-operator-console-ui)
- [API Reference](#api-reference)
- [MCP Integration](#mcp-integration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Architecture Deep Dive](#architecture-deep-dive)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    Streamlit Operator Console                    │
│            Upload → Task → Monitor → Approve → Report           │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTP + SSE
┌──────────────────────▼───────────────────────────────────────────┐
│                    FastAPI Backend (Port 8000)                    │
│  /api/v1/ingest · /execute · /intervene · /report · /sessions   │
│  /mcp/tools · /mcp/call · /mcp/sse · /health                   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────┐
│                 LangGraph 8-Node StateGraph                      │
│                                                                  │
│  ┌─────────┐   ┌─────────┐   ┌──────────────┐   ┌──────────┐  │
│  │ Intake  │──▶│ Planner │──▶│ Evidence     │──▶│ Executor │  │
│  └─────────┘   └─────────┘   │ Router       │   └────┬─────┘  │
│       │                      └──────────────┘        │         │
│       │              ┌───────────────────────────────▼──────┐  │
│       │              │           Verifier                    │  │
│       │              └──┬──────────┬────────────┬───────────┘  │
│       │                 │          │            │               │
│       │        ┌────────▼──┐  ┌───▼─────┐  ┌──▼──────────┐   │
│       │        │ Approval  │  │Replanner│  │  Reporter    │   │
│       │        │ Gate ⏸️   │  └─────────┘  │  (→ END)     │   │
│       │        └───────────┘               └──────────────┘   │
└───────────────────────────────────────────────────────────────────┘
                       │                │
         ┌─────────────┴──┐    ┌───────┴─────────┐
         │  ChromaDB      │    │  SQLite + FTS5   │
         │  (Dense Vectors)│    │  (BM25 Lexical)  │
         └────────────────┘    └─────────────────┘
```

---

## Key Features

| Feature | Description |
|---|---|
| **Multi-Format Ingestion** | PDF, DOCX, TXT, Markdown with structure-aware chunking |
| **Hybrid RAG** | Dense (ChromaDB cosine) + Lexical (SQLite FTS5 BM25) with RRF fusion |
| **8-Node Agent Graph** | LangGraph StateGraph with conditional routing and checkpointing |
| **Human-on-the-Loop** | `interrupt_before` on approval gate; operator approves/overrides/skips/aborts/replans |
| **Policy Engine** | Configurable confidence thresholds, risk-based approval rules |
| **Multi-Provider LLM** | Gemini, OpenAI, Anthropic, Ollama — hot-swappable via env var |
| **Evidence Traceability** | Every action cites source file, section, page, and quote |
| **MCP Server** | 4 Model Context Protocol tools for IDE/agent integration |
| **Operator Console** | Streamlit UI with real-time SSE monitoring |
| **Production Resilience** | Retry with exponential backoff, structured output repair, rate limiting |

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Runtime | Python | 3.12+ |
| Agent Framework | LangGraph | 0.2+ |
| LLM Abstraction | LangChain | 0.3+ |
| Backend API | FastAPI + Uvicorn | 0.115+ |
| Frontend | Streamlit | 1.40+ |
| Vector Store | ChromaDB | 0.5+ |
| Database | SQLite (WAL mode) + aiosqlite | — |
| Full-Text Search | SQLite FTS5 (BM25) | — |
| Document Parsing | pdfplumber, python-docx | — |
| Streaming | SSE (sse-starlette) | 2.0+ |
| Validation | Pydantic v2 | 2.9+ |
| Resilience | tenacity | 9.0+ |

---

## Project Structure

```
SOP-Agent/
├── app/
│   ├── main.py                    # FastAPI app factory & lifespan
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (env-driven)
│   │   ├── database.py            # Async SQLite CRUD (6 tables + FTS5)
│   │   ├── llm_factory.py         # Multi-provider LLM/embedding factory
│   │   └── logging.py             # Structured logging with PII redaction
│   ├── agents/
│   │   ├── state.py               # AgentState + all Pydantic schemas
│   │   ├── graph.py               # StateGraph compilation (8 nodes)
│   │   ├── routing.py             # Conditional edge functions
│   │   └── nodes/
│   │       ├── intake.py          # Node 1: Session validation & resume
│   │       ├── planner.py         # Node 2: Structured plan generation
│   │       ├── evidence_router.py # Node 3: Hybrid retrieval per step
│   │       ├── executor.py        # Node 4: Action recommendation
│   │       ├── verifier.py        # Node 5: Independent verification
│   │       ├── approval_gate.py   # Node 6: Human-on-the-loop interrupt
│   │       ├── replanner.py       # Node 7: Partial plan rewrite
│   │       └── reporter.py        # Node 8: Final report generation
│   ├── retrieval/
│   │   ├── dense.py               # ChromaDB wrapper
│   │   ├── lexical.py             # SQLite FTS5 BM25 search
│   │   ├── rerank.py              # RRF fusion + dedup + diversity
│   │   ├── document_map.py        # Section-level document index
│   │   └── graph_memory.py        # GraphRAG stub (feature-flagged)
│   ├── policy/
│   │   ├── thresholds.py          # Confidence & evidence thresholds
│   │   └── approval_rules.py      # Risk-based approval rules
│   ├── services/
│   │   ├── ingestion.py           # Parse → chunk → embed → index pipeline
│   │   ├── collection_versioning.py
│   │   └── report_export.py       # Markdown export
│   ├── api/
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── routes/
│   │       ├── ingest.py          # POST /api/v1/ingest
│   │       ├── execute.py         # POST /api/v1/execute + SSE stream
│   │       ├── intervene.py       # POST /api/v1/intervene
│   │       ├── report.py          # GET  /api/v1/report/{id}
│   │       └── session.py         # GET/DELETE /api/v1/sessions
│   └── mcp/
│       ├── server.py              # MCP tool server (4 tools)
│       └── sse.py                 # MCP SSE transport router
├── frontend/
│   ├── app.py                     # Streamlit main app
│   ├── components/
│   │   ├── upload.py              # Phase 1: File upload
│   │   ├── task_input.py          # Phase 2: Task description
│   │   ├── execution_monitor.py   # Phase 3: Real-time monitoring
│   │   ├── approval_panel.py      # Approval decision UI
│   │   └── report_viewer.py       # Phase 4: Report viewer
│   └── utils/
│       ├── api_client.py          # HTTP client for backend
│       └── sse_listener.py        # SSE stream consumer
├── tests/
│   ├── conftest.py                # Shared fixtures
│   ├── unit/                      # 42 unit tests
│   └── integration/               # 13 integration tests
├── scripts/
│   └── init_db.py                 # Standalone DB initializer
├── data/                          # Runtime data (gitignored)
├── docs/
│   ├── ARCHITECTURE.md            # Deep architecture guide
│   ├── API.md                     # Full API reference
│   └── DEPLOYMENT.md              # Production deployment guide
├── .env.example                   # Environment template
├── Dockerfile                     # Backend container
├── Dockerfile.frontend            # Frontend container
├── docker-compose.yml             # Full-stack orchestration
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project metadata & tool config
└── SOP_Agent_Full_Specification.md
```

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **An LLM API key** (Gemini, OpenAI, or Anthropic) — or **Ollama** running locally

### 1. Clone & Install

```bash
git clone https://github.com/RaptorBlingx/SOP-Agent.git
cd SOP-Agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API key. For the fastest start with Google Gemini:

```env
MODEL_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_EMBED_MODEL=models/gemini-embedding-2-preview
```

Or use a local Ollama instance (no API key needed):

```env
MODEL_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### 3. Initialize Database

```bash
python scripts/init_db.py
```

### 4. Start the Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the Frontend (separate terminal)

```bash
streamlit run frontend/app.py --server.port 8501
```

### 6. Open the Operator Console

Navigate to **http://localhost:8501** in your browser.

---

## Configuration

All configuration is driven by environment variables (loaded from `.env`):

| Variable | Default | Description |
|---|---|---|
| `MODEL_PROVIDER` | `gemini` | LLM provider: `gemini`, `openai`, `anthropic`, `ollama` |
| `EMBEDDING_PROVIDER` | `gemini` | Embedding provider: `gemini`, `openai`, `ollama` |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Gemini chat model name |
| `GEMINI_EMBED_MODEL` | `models/gemini-embedding-2-preview` | Gemini embedding model name |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-5.4-mini` | OpenAI chat model name |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Anthropic chat model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3:8b` | Ollama chat model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `DATABASE_PATH` | `./data/sop_agent.db` | SQLite database file path |
| `CHROMADB_PATH` | `./data/chromadb` | ChromaDB persistence directory |
| `UPLOAD_PATH` | `./data/uploads` | File upload directory |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `http://localhost:8501,...` | Comma-separated allowed origins |
| `RATE_LIMIT_RPM` | `60` | LLM requests per minute |
| `RATE_LIMIT_TPM` | `100000` | LLM tokens per minute |
| `ENABLE_GRAPH_MEMORY` | `false` | Enable GraphRAG memory layer |
| `ENABLE_LANGSMITH` | `false` | Enable LangSmith tracing |

---

## Running the Application

### Option A: Direct (Development)

```bash
# Terminal 1 — Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
streamlit run frontend/app.py --server.port 8501
```

The backend serves the API at `http://localhost:8000` (Swagger docs at `/docs`).
The frontend operator console runs at `http://localhost:8501`.

### Option B: Docker Compose (Production)

```bash
# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

This starts:
- **Backend** on port `8000`
- **Frontend** on port `8501`
- Persistent data in `./data/` volume mount

---

## Using the Operator Console (UI)

The Streamlit-based Operator Console provides a 4-phase workflow:

### Phase 1: Upload Documents
- Drag & drop SOP files (PDF, DOCX, TXT, MD)
- Files are parsed, chunked, embedded, and indexed
- A new session is created automatically

### Phase 2: Enter Task
- Describe the SOP task in natural language
- Example: *"Execute the employee onboarding procedure for a new software engineer starting Monday"*
- Click **Start Execution**

### Phase 3: Monitor & Approve
- Real-time step-by-step execution progress via SSE
- When a step requires approval, an approval panel appears
- Available actions:
  - **Approve** — accept the recommended action
  - **Override** — provide alternative instructions
  - **Skip** — skip this step
  - **Abort** — stop execution entirely
  - **Request Replan** — regenerate remaining steps

### Phase 4: Review Report
- View the generated Markdown execution report
- Download as `.md` file
- Report includes evidence citations, interventions, and metrics

### Sidebar
- Backend health indicator
- Recent sessions list (click to restore)
- Session ID and current phase

---

## API Reference

Base URL: `http://localhost:8000`

### Health Check
```
GET /health
→ {"status": "ok", "version": "1.2.0"}
```

### Ingest Documents
```
POST /api/v1/ingest
Content-Type: multipart/form-data

files: [file1.pdf, file2.docx]
session_id: (optional)
collection_name: (optional)

→ {
    "session_id": "...",
    "collection_id": "...",
    "collection_version": 1,
    "total_chunks": 42,
    "files_processed": ["file1.pdf", "file2.docx"],
    "status": "ready"
  }
```

### Start/Resume Execution
```
POST /api/v1/execute
{
    "session_id": "...",
    "task_description": "Execute the onboarding SOP for..."
}
→ {"session_id": "...", "status": "executing", "message": "..."}
```

### Stream Execution Events (SSE)
```
GET /api/v1/execute/{session_id}/stream
→ Server-Sent Events: node_update, approval_needed, done, error
```

### Submit Intervention
```
POST /api/v1/intervene
{
    "session_id": "...",
    "action": "approve",        // approve|override|skip|abort|request_replan
    "override_text": null       // required for "override"
}
→ {"session_id": "...", "status": "resumed", "message": "..."}
```

### Get Report
```
GET /api/v1/report/{session_id}
→ {"session_id": "...", "status": "completed", "report": "# SOP Report..."}
```

### Download Report
```
GET /api/v1/report/{session_id}/download
→ {"session_id": "...", "file_path": "./data/reports/report_xxx.md"}
```

### List Sessions
```
GET /api/v1/sessions
→ {"sessions": [{"session_id": "...", "status": "...", ...}]}
```

### Get Session
```
GET /api/v1/sessions/{session_id}
→ {"session_id": "...", "status": "...", "total_steps": 5, ...}
```

### Delete Session
```
DELETE /api/v1/sessions/{session_id}
→ {"status": "deleted", "session_id": "..."}
```

Full interactive docs available at **http://localhost:8000/docs** (Swagger UI) and **http://localhost:8000/redoc**.

---

## MCP Integration

SOP Agent exposes a Model Context Protocol (MCP) server for integration with AI IDEs and agents.

### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/mcp/tools` | GET | List available MCP tools |
| `/mcp/call` | POST | Execute an MCP tool |
| `/mcp/sse` | GET | SSE keepalive stream |

### Available Tools

| Tool | Description |
|---|---|
| `ingest_sop` | Ingest SOP documents from file paths |
| `run_sop` | Execute a task against ingested SOPs |
| `approve_step` | Submit operator intervention |
| `get_report` | Retrieve execution report |

### Example MCP Call

```bash
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name": "ingest_sop", "arguments": {"file_paths": ["/path/to/sop.pdf"]}}'
```

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=html
```

**Test Suite: 55 tests (42 unit + 13 integration)**

| Module | Tests | Coverage |
|---|---|---|
| Config & Settings | 3 | Env loading, validation, defaults |
| Database CRUD | 7 | All 6 tables + FTS5 search |
| Logging & PII | 3 | Redaction patterns, formatters |
| Policy Engine | 7 | Thresholds, approval rules, severity |
| Retrieval Pipeline | 5 | RRF fusion, dedup, diversity, doc map |
| Agent Routing | 10 | All conditional edge functions |
| Agent State | 6 | Schema validation, defaults |
| API Endpoints | 4 | Ingest, sessions, health |
| Graph Compilation | 3 | Node count, edges, interrupt config |
| Ingestion Pipeline | 3 | Parsing, chunking, validation |
| MCP Server | 4 | Tool listing, tool calls |

---

## Deployment

### Docker Compose (Recommended)

```bash
# Create .env file with your API key
cp .env.example .env && nano .env

# Build and start
docker compose up --build -d

# Verify
curl http://localhost:8000/health
```

### Manual Deployment

```bash
# Install system dependencies
apt-get install -y libmagic1

# Install Python dependencies
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py

# Start backend (production)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# Start frontend
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
```

> **Note:** Use `--workers 1` because SQLite WAL mode is designed for single-writer concurrency.

### Environment Requirements

- Python 3.12+
- `libmagic1` system package (for MIME validation)
- 512 MB RAM minimum; 2 GB recommended for embedding operations
- Network access to your chosen LLM provider (or local Ollama)

---

## Architecture Deep Dive

### Agent Graph Flow

1. **Intake** — Validates session, checks for resume state, creates DB session if new
2. **Planner** — LLM generates structured execution plan (`PlanSchema`) grounded in document map
3. **Evidence Router** — Per-step hybrid retrieval: ChromaDB dense + FTS5 lexical → RRF fusion → top-5 diverse pack
4. **Executor** — LLM recommends specific action with confidence score based on evidence
5. **Verifier** — Independent LLM verification at temperature 0.0; policy checks first (no LLM), then evidence grounding
6. **Approval Gate** — `interrupt_before` triggers when policy/uncertainty requires human review
7. **Replanner** — Rewrites only remaining (unfinished) steps, preserving completed history
8. **Reporter** — Generates final Markdown report with step-by-step details and evidence citations

### Retrieval Pipeline (4 Layers)

1. **Layer 1: Document Map** — Section-level index for planner context
2. **Layer 2: Hybrid Candidates** — Dense (ChromaDB cosine, k=8) + Lexical (FTS5 BM25, k=8)
3. **Layer 3: Fusion & Diversity** — RRF fusion → deduplication → round-robin source diversification → top-5 pack
4. **Layer 4: Graph Memory** — Optional relationship-based retrieval (feature-flagged)

### Database Schema (6 Tables + FTS5)

| Table | Purpose |
|---|---|
| `sessions` | Session state, config, status tracking |
| `session_steps` | Execution plan steps with status |
| `step_evidence` | Evidence citations per step |
| `approvals` | Operator intervention audit log |
| `run_events` | Execution event timeline |
| `ingested_files` | File ingestion records |
| `lexical_chunks` + FTS5 | BM25 full-text search index |

### Security

- PII/API key redaction in all log output (regex-based `RedactingFormatter`)
- File upload: extension whitelist + MIME validation + 20 MB size limit
- Path traversal protection on uploads (`Path.name` sanitization)
- Prompt injection defense: evidence wrapped in `<evidence>` tags with explicit instructions to treat as reference material
- CORS configuration via environment variable
- All secrets loaded from environment variables (never hardcoded)

---

## Troubleshooting

### "API key not set" warning on startup

This is expected if you haven't configured the API key for the selected provider. Set the appropriate key in `.env`:
- Gemini: `GEMINI_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Ollama: No key needed, just ensure the server is running

### Backend unreachable from frontend

Check that the backend is running on port 8000 and CORS includes the frontend origin:
```env
CORS_ORIGINS=http://localhost:8501,http://localhost:3000
```

### ChromaDB errors

Ensure the `CHROMADB_PATH` directory exists and is writable:
```bash
mkdir -p data/chromadb
```

### SQLite "database is locked"

Use `--workers 1` with Uvicorn. SQLite WAL supports concurrent reads but single writer.

### Empty search results

Verify documents were ingested properly by checking the session's chunk count through the API:
```bash
curl http://localhost:8000/api/v1/sessions
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`python -m pytest tests/ -v`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Built with the SOP Agent Full Specification v1.2 — April 2026*