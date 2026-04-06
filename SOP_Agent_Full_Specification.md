# SOP Execution Agent - Full Technical Specification
**Version:** 1.2  
**Date:** April 2026  
**Classification:** Internal Engineering Specification  
**Audience:** Senior AI / Software Engineers  
**Decision Posture:** Stable-first baseline, preview features behind explicit flags

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Goals & Success Criteria](#2-goals--success-criteria)

### 9.1 Product Surface

Streamlit is still acceptable for v1, but the UI must present itself as an **operator console**, not a toy demo.

The console should optimize for:

- current run visibility
- evidence inspection
- safe intervention
- auditability

### 9.2 Layout

Use a three-panel layout.

#### Left Rail: Session and Runtime Controls

- Active session ID
- Provider and model lane
- Reasoning profile
- Retrieval mode flags

### 13.1 Credential Handling

- Never hard-code provider credentials.
- Never emit credentials in logs, traces, frontend state, or exception messages.
- Validate required credentials at startup for the selected provider and embedding lane.
- Keep `.env` out of source control and commit only `.env.example`.

### 13.2 Uploaded Documents Are Untrusted Input

SOP files are not inherently safe just because they are internal documents.

Treat uploaded content as untrusted because it can contain:

- prompt injection attempts
- misleading instructions unrelated to the declared task
- sensitive personal or financial information
- malformed or oversized files

### 13.3 File Upload Validation

```python
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


async def validate_upload(file: UploadFile) -> bytes:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(415, detail=f"File type {ext} is not allowed")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(413, detail="File exceeds size limit")

        import magic

        mime = magic.from_buffer(content[:1024], mime=True)
        allowed_mimes = {
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
                "text/markdown",
        }
        if mime not in allowed_mimes:
                raise HTTPException(415, detail=f"MIME type {mime} is not allowed")

        await file.seek(0)
        return content
```

### 13.4 Prompt Injection and Instruction Isolation

The runtime must distinguish between:

- **operator instructions**
- **system prompts and policy**
- **retrieved SOP content**

Retrieved content may inform execution, but it must never override system policy or API-layer constraints. Required defenses:

- wrap retrieved evidence in clearly delimited context blocks
- instruct models that retrieved text is evidence, not authority over runtime policy
- verify that generated actions are traceable to evidence rather than to injected instructions embedded in documents

### 13.5 Logging, Tracing, and PII

- Log event metadata, not raw secrets.
- Redact or hash sensitive identifiers where feasible.
- Store operator interventions and evidence references, but do not indiscriminately dump full uploaded documents into logs.
- If LangSmith or other observability tooling is enabled, route it through the same redaction policy.

### 13.6 MCP Security Posture

- Expose only an allowlisted set of MCP tools.
- Do not enable arbitrary shell or filesystem write access through MCP in v1.
- Require explicit configuration to expose MCP beyond local trusted environments.

### 13.7 CORS and Network Policy

Development may allow local origins. Production must restrict origins to the deployed operator console.


### 9.5 Streamlit State Management


### 14.1 Test Structure

```text
tests/
├── unit/
│   ├── test_parsers.py
│   ├── test_chunking.py
│   ├── test_llm_factory.py
│   ├── test_routing.py
│   ├── test_policy_thresholds.py
│   └── test_schema_validation.py
├── integration/
│   ├── test_ingestion.py
│   ├── test_hybrid_retrieval.py
│   ├── test_agent_nodes.py
│   ├── test_api_endpoints.py
│   └── test_mcp_tools.py
├── e2e/
│   ├── test_full_workflow.py
│   └── test_resume_after_intervention.py
├── evals/
│   ├── grounding_regression.yaml
│   ├── approval_gate_regression.yaml
│   └── replan_regression.yaml
├── fixtures/
│   ├── sample_sop.pdf
│   ├── sample_sop.docx
│   └── task_cases.json
└── conftest.py
```

### 14.2 Code Coverage Targets

| Area | Target |
|---|---|
| Parsers and validation | 95%+ |
| Routing and policy logic | 95%+ |
| Provider factory | 90%+ |
| API endpoints | 85%+ |
| Node logic with mocked providers | 85%+ |
| Retrieval utilities | 80%+ |

### 14.3 Behavioral Evaluation Targets

Code coverage alone is insufficient. Maintain a regression set for model behavior.

| Metric | Target |
|---|---|
| Plan grounding rate | >= 95% |
| Unsupported step completion rate | <= 1% |
| False approval rate on gated steps | <= 1% |
| Replan success on contradiction cases | >= 90% |

### 14.4 Mocking Strategy

Do not use live provider calls in unit or integration tests. Mock the provider factory and return schema-valid objects.

```python
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_llm():
        with patch("app.core.llm_factory.get_llm") as mock:
                llm = AsyncMock()
                mock.return_value = llm
                yield llm
```

### 14.5 Required Regression Cases

- planner produces grounded steps from multi-document SOPs
- verifier rejects unsupported actions when evidence is weak
- approval gate interrupts correctly on policy-required steps
- operator override is recorded and respected
- replanner updates only the unfinished suffix of the plan
- execution resumes cleanly after restart from checkpoint
- provider fallback does not duplicate work or steps

        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=resolved.model,

### 15.1 Local Development Setup

```bash
git clone https://github.com/[owner]/sop-agent
cd sop-agent

python3.14 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

python scripts/init_db.py
uvicorn app.main:app --reload --port 8000
streamlit run frontend/app.py --server.port 8501
```

### 15.2 Container Baseline

```dockerfile
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
        libmagic1 \
        && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data/chromadb /app/data/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
services:
    backend:
        build: .
        env_file:
            - .env
        volumes:
            - ./data:/app/data
        ports:
            - "8000:8000"
        restart: unless-stopped

    frontend:
        build:
            context: .
            dockerfile: Dockerfile.frontend
        environment:
            - BACKEND_URL=http://backend:8000
        depends_on:
            - backend
        ports:
            - "8501:8501"
        restart: unless-stopped
```

### 15.3 Production Guidance

Recommended production posture:

- keep FastAPI and Streamlit in separate containers
- persist SQLite on durable storage or move to libSQL/Turso
- persist ChromaDB on durable storage or replace with managed vector storage when scale requires it
- keep preview models disabled in production unless explicitly approved

### 15.4 Demo vs Production Targets

- Demo hosting: Railway, Render, or similar low-friction platforms
- Production hosting: container platform with persistent volumes, managed secrets, and stable outbound egress controls

---

## 16. Project Directory Structure

```text
sop-agent/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── agents/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── routing.py
│   │   └── nodes/
│   │       ├── intake.py
│   │       ├── planner.py
│   │       ├── evidence_router.py
│   │       ├── executor.py
│   │       ├── verifier.py
│   │       ├── approval_gate.py
│   │       ├── replanner.py
│   │       └── reporter.py
│   ├── api/
│   │   ├── schemas.py
│   │   └── routes/
│   │       ├── ingest.py
│   │       ├── execute.py
│   │       ├── intervene.py
│   │       ├── report.py
│   │       └── session.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── llm_factory.py
│   │   └── logging.py
│   ├── mcp/
│   │   ├── server.py
│   │   └── tools/
│   │       ├── search_sop_context.py
│   │       ├── get_run_state.py
│   │       ├── submit_intervention.py
│   │       └── render_execution_report.py
│   ├── policy/
│   │   ├── approval_rules.py
│   │   └── thresholds.py
│   ├── retrieval/
│   │   ├── dense.py
│   │   ├── lexical.py
│   │   ├── rerank.py
│   │   ├── graph_memory.py
│   │   └── document_map.py
│   └── services/
│       ├── ingestion.py
│       ├── report_export.py
│       └── collection_versioning.py
├── frontend/
│   ├── app.py
│   ├── components/
│   │   ├── upload_workspace.py
│   │   ├── task_launcher.py
│   │   ├── run_console.py
│   │   ├── evidence_drawer.py
│   │   └── report_workspace.py
│   └── utils/
│       ├── api_client.py
│       └── session_manager.py
├── tests/
├── evals/
├── scripts/
├── data/
├── .env.example
├── Dockerfile
├── Dockerfile.frontend
├── docker-compose.yml
├── requirements.txt
└── README.md
```
            collection_version=collection_version,
        )
async def call_llm_with_retry(llm, messages):
    return await llm.ainvoke(messages)
```

If the third attempt fails:

- record a run event
- set the step to `failed` or `needs_approval`
- optionally use a configured fallback provider if `ENABLE_PROVIDER_FAILOVER=true`

### 12.2 Structured Output Validation Failures

Use schema validation as the first failure boundary.

```python
from pydantic import ValidationError


async def invoke_structured(llm, schema, messages):
    structured_llm = llm.with_structured_output(schema)
    try:
        return await structured_llm.ainvoke(messages)
    except ValidationError:
        strict_retry_messages = add_schema_repair_instruction(messages)
        return await structured_llm.ainvoke(strict_retry_messages)
```

Do not rely on heuristic JSON cleanup as the primary path.

### 12.3 Retrieval Failures

If retrieval yields weak evidence:

1. Retry with a richer query.
2. Expand the search to adjacent sections or exception-handling sections.
3. If confidence remains weak, route to approval or replan.

### 12.4 Checkpoint and Resume Failures

- Resume must be idempotent.
- A duplicate `execute` request must not create duplicate steps.
- A failed resume should preserve the last durable checkpoint and return a retryable error with `trace_id`.

### 12.5 Rate Limiting

Provider rate limits change over time, so they must be configuration-driven rather than hard-coded into the spec.

Required behavior:

- maintain a per-provider request limiter
- maintain a per-provider token budget when supported
- degrade to slower but safe execution rather than failing noisily on burst traffic

### 12.6 Operator-Safe Failure Mode

The final fallback posture is:

- never silently continue on low-confidence unsupported actions
- prefer `needs_approval` over incorrect completion
- preserve full context for the operator to decide quickly
### 3.4 Statefulness and Resume Semantics

- Graph state is checkpointed to SQLite after every node execution.
- Each run has a stable `session_id` and append-only event log.
- The runtime persists step status, evidence packs, verification decisions, operator interventions, and provider/model metadata.
- Resume always restarts from the last durable checkpoint, not from reconstructed UI state.
- A step is only considered complete after verification or an operator decision, never after generation alone.

---

## 4. Technology Stack

### 4.1 Core Stack

| Layer | Technology | April 2026 Baseline | Reason |
|---|---|---|---|
| Language Runtime | Python | `3.14.3` | Current stable baseline with modern async/runtime improvements |
| Agent Runtime | LangGraph | `1.1.6` | Current stateful agent orchestration baseline |
| LLM Abstraction | LangChain | `1.2.15` | Provider adapters and structured-output ergonomics |
| Checkpoint Core | `langgraph-checkpoint` | `4.0.1` | Required explicit dependency in LangGraph 1.x |
| SQLite Checkpointer | `langgraph-checkpoint-sqlite` | `3.0.3` | Durable local graph state persistence |
| Backend API | FastAPI | `0.135.3` | Async API layer with clean SSE support |
| Frontend | Streamlit | `1.56.0` | Fast operator-console delivery in pure Python |
| Vector Store | ChromaDB | `1.5.5` | Local dense vector storage with good developer ergonomics |
| State Database | SQLite + `aiosqlite` | `0.22.1` | Simple, durable, and good enough with WAL mode |
| PDF Parser | `pdfplumber` | `0.11.9` | Reliable extraction for digitally generated PDFs |
| DOCX Parser | `python-docx` | `1.2.0` | Standard Word document extraction |
| Report Export | `markdown2` + `weasyprint` | Latest compatible | Markdown-first reporting pipeline |
| Observability | LangSmith (optional) | Latest compatible | Graph tracing and prompt inspection |
| Test Harness | `pytest` + `pytest-asyncio` | Latest compatible | Standard async Python testing stack |
| Containerization | Docker + Compose | Latest compatible | Reproducible local and CI deployment |

### 4.2 Python Baseline Policy

**Python 3.14.3 is the baseline runtime.**

- Python 3.13 remains an acceptable temporary fallback only if a dependency lags.
- Free-threaded builds are officially supported in 3.14, but this project should not assume free-threading in production until benchmarked against the actual provider SDK mix.
- Experimental JIT features are not part of the production baseline.

### 4.3 Provider and Model Support

The system must support four first-class provider lanes, selected by configuration rather than code changes:

| Lane | Provider | Stable Models Approved for Baseline Use | Recommended Role |
|---|---|---|---|
| Development / low-cost | Gemini | `gemini-2.5-flash` | Fast iteration and low-cost demos |
| Balanced production | Anthropic | `claude-sonnet-4-6` | Recommended default for high-quality operational runs |
| High-reasoning production | OpenAI or Anthropic | `gpt-5.4`, `gpt-5.4-mini`, `claude-opus-4-6` | Harder planning, ambiguous procedures, higher-stakes runs |
| Local / privacy mode | Ollama | `qwen3:4b`, `llama4` | Offline or privacy-constrained environments |

### 4.4 Embedding Policy

| Provider | Stable Embedding Baseline | Notes |
|---|---|---|
| Gemini | `text-embedding-004` | Strong default for cost-sensitive environments |
| OpenAI | `text-embedding-3-small` | Strong general-purpose paid baseline |
| Ollama | `nomic-embed-text` | Local default |

`Gemini Embedding 2` is promising but remains preview-only and must not be the default embedding baseline in this specification.

### 4.5 Preview Feature Policy

Preview models and experimental capabilities may be evaluated, but they are not part of the default path.

- `Gemini 3 Flash`, `Gemini 3.1 Pro`, and `Gemini 3.1 Flash-Lite` are preview-only lanes.
- Preview features must be enabled via explicit flags and excluded from the primary regression suite.
- No preview model may become the default until it passes the same grounding, verification, and approval-gating evaluations as stable models.

---

## 5. LangGraph Agent Design

### 5.1 State Schema

The 2026 runtime needs richer state than a simple list of steps plus a human flag. The graph must track evidence, verification outcomes, operator interventions, and replanning decisions as first-class state.

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class EvidenceRef(BaseModel):
    chunk_id: str
    source_file: str
    section_path: str | None = None
    page_number: int | None = None
    quote: str
    score: float


class ExecutionStep(BaseModel):
    step_id: str
    order: int
    title: str
    objective: str
    branch_condition: str | None = None
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool = False
    status: Literal[
        "pending",
        "ready",
        "executing",
        "completed",
        "needs_approval",
        "replanned",
        "skipped",
        "failed",
    ] = "pending"
    recommended_action: str | None = None
    verification_summary: str | None = None
    confidence: float | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    operator_action: str | None = None


class ApprovalRequest(BaseModel):
    request_id: str
    step_id: str
    severity: Literal["medium", "high", "critical"]
    reason: str
    allowed_actions: list[str]


class AgentState(BaseModel):
    session_id: str
    task_description: str
    collection_id: str
    reasoning_profile: Literal["low_cost", "balanced", "high_reasoning", "local"]
    steps: list[ExecutionStep] = Field(default_factory=list)
    current_step_index: int = 0
    active_evidence_pack: list[EvidenceRef] = Field(default_factory=list)
    pending_approval: ApprovalRequest | None = None
    replan_count: int = 0
    messages: Annotated[list, add_messages]
    run_events: list[dict] = Field(default_factory=list)
    status: Literal[
        "planning",
        "executing",
        "awaiting_operator",
        "replanning",
        "completed",
        "failed",
    ] = "planning"
    final_report: str | None = None
    last_error: str | None = None
```

### 5.2 Node Topology

The runtime should use **8 nodes**. The previous planner -> retriever -> executor -> critic loop is too weak for April 2026 because it lacks explicit replanning and treats verification as a simple afterthought.

#### Node 1: `intake_node`

- Validates session, collection, provider config, and resume state.
- Loads persisted state and decides whether to plan from scratch or continue from a checkpoint.
- Pure control logic. No LLM call.

#### Node 2: `planner_node`

- Builds the initial execution plan from the task and an initial evidence pack.
- Uses structured output, not prompt-only JSON conventions.
- May escalate to a long-context planning pack for large or ambiguous SOP corpora.

#### Node 3: `evidence_router_node`

- Retrieves step-specific evidence using hybrid retrieval.
- Decides whether dense plus lexical retrieval is sufficient or whether the step needs broader context.
- Can call optional graph-memory lookups when enabled and justified.

#### Node 4: `executor_node`

- Produces the recommended next action for the active step.
- Must return prerequisites, proposed completion signal, and an explicit confidence estimate.
- Cannot mark a step complete by itself.

#### Node 5: `verifier_node`

- Independently checks the proposed action against source evidence and policy.
- Decides one of four outcomes: continue, approval required, replan required, or fail.
- This node replaces the older shallow critic pattern.

#### Node 6: `approval_gate_node`

- Interrupts the graph only when policy or uncertainty justifies intervention.
- Supports `approve`, `override`, `skip`, `abort`, and `request_replan`.
- This is the operational expression of human-on-the-loop: the system normally continues, but operators can intervene at defined or ad hoc points.

#### Node 7: `replanner_node`

- Rewrites the remaining plan when evidence, verification, or operator input invalidates the current path.
- Preserves completed-step history and appends a replan event to the run log.

#### Node 8: `reporter_node`

- Produces the final Markdown report and summary metadata.
- Includes completed steps, operator interventions, replans, and unresolved exceptions.

### 5.3 Structured Output Contract

Planner, executor, verifier, and reporter must all use typed schemas.

```python
from pydantic import BaseModel


class PlanSchema(BaseModel):
    steps: list[ExecutionStep]


class ExecutionDecision(BaseModel):
    recommended_action: str
    prerequisites: list[str]
    completion_signal: str
    confidence: float


class VerificationDecision(BaseModel):
    outcome: Literal["continue", "needs_approval", "replan", "fail"]
    rationale: str
    confidence: float
    policy_reason: str | None = None


planner = bind_structured(get_llm(profile="planner"), PlanSchema)
executor = bind_structured(get_llm(profile="executor"), ExecutionDecision)
verifier = bind_structured(get_llm(profile="verifier"), VerificationDecision)
```

The spec explicitly rejects generic `json_repair` as a primary strategy. If a provider fails schema validation twice, the runtime must retry with a stricter structured-output path or fall back to an alternate configured provider.

### 5.4 Graph Compilation and Routing

```python
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver


def build_graph(checkpointer: SqliteSaver):
    workflow = StateGraph(AgentState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("evidence_router", evidence_router_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("approval_gate", approval_gate_node)
    workflow.add_node("replanner", replanner_node)
    workflow.add_node("reporter", reporter_node)

    workflow.set_entry_point("intake")

    workflow.add_conditional_edges(
        "intake",
        route_from_intake,
        {
            "plan": "planner",
            "resume": "evidence_router",
        },
    )

    workflow.add_edge("planner", "evidence_router")
    workflow.add_edge("evidence_router", "executor")
    workflow.add_edge("executor", "verifier")

    workflow.add_conditional_edges(
        "verifier",
        route_from_verifier,
        {
            "continue": "evidence_router",
            "approval": "approval_gate",
            "replan": "replanner",
            "complete": "reporter",
            "fail": "approval_gate",
        },
    )

    workflow.add_conditional_edges(
        "approval_gate",
        route_from_approval_gate,
        {
            "continue": "evidence_router",
            "replan": "replanner",
            "abort": "reporter",
        },
    )

    workflow.add_edge("replanner", "evidence_router")
    workflow.add_edge("reporter", END)

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval_gate"],
    )
```

### 5.5 Routing Semantics

- `continue`: current step is complete, advance to the next step.
- `approval`: verifier or policy engine requires operator input.
- `replan`: evidence contradicts the remaining path or operator requested a new approach.
- `complete`: all steps are complete or intentionally skipped.
- `fail`: runtime could not reach a safe continuation without operator judgment.

### 5.6 Human-on-the-Loop Policy

The runtime should continue automatically for low-risk, well-grounded steps. It should pause only when at least one of the following is true:

- The step implies an irreversible external action.
- The evidence pack is weak or contradictory.
- The confidence score falls below the policy threshold.
- The SOP explicitly requires manager, legal, financial, or compliance approval.
- The operator manually intervenes from the UI.

---

## 6. RAG Pipeline Design

### 6.1 Ingestion Pipeline

The baseline architecture is no longer "chunk everything and search vectors." SOPs are procedural documents with headings, numbered steps, approvals, conditional branches, and references. The ingestion path must preserve that structure.

```text
File Upload
-> Type Detection
-> Parser
-> Structure Extraction
-> Semantic Chunking
-> Dense Embedding
-> Dense Index + Lexical Index + Document Map
```

### 6.2 Supported File Types

| File Type | Extension | Parser |
|---|---|---|
| PDF | `.pdf` | `pdfplumber` primary; reject image-only PDFs for now |
| Word Document | `.docx` | `python-docx` |
| Plain Text | `.txt` | UTF-8 text loader |
| Markdown | `.md` | UTF-8 text loader |

Unsupported types must return HTTP 415 with a precise error message.

### 6.3 Chunking Strategy

The chunker must be **structure-aware**.

- Preserve section headings, numbered steps, and bullet groups when possible.
- Prefer logical sections first, then character splitting only as a fallback.
- Use target chunks of roughly 900 to 1200 characters with 120 to 180 characters of overlap.
- Store heading path and source location in metadata so the UI can cite evidence precisely.

Example implementation pattern:

```python
structured_sections = extract_sections(raw_text)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1100,
    chunk_overlap=160,
    separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
    length_function=len,
)

documents = splitter.create_documents(
    texts=[section.text for section in structured_sections],
    metadatas=[section.metadata for section in structured_sections],
)
```

### 6.4 Required Metadata Per Chunk

Each chunk stored in the dense index must include at least:

```python
{
    "chunk_id": "uuid",
    "source_file": "client_onboarding_sop.pdf",
    "page_number": 7,
    "section_path": "4.1 > Enterprise onboarding > Assign account manager",
    "chunk_index": 12,
    "collection_id": "sop_uuid",
    "collection_version": 1,
    "ingested_at": "2026-04-06T12:30:00Z",
}
```

### 6.5 Retrieval Strategy

Retrieval is a **tiered evidence system**, not a single `similarity_search()` call.

#### Layer 1: Document Map Retrieval

- Quickly identify the most relevant files and sections for the user task.
- Used primarily during planning and replanning.

#### Layer 2: Hybrid Candidate Generation

- Dense retrieval from ChromaDB.
- Lexical retrieval from a sidecar SQLite FTS5 index or equivalent BM25 layer.
- Merge candidates with reciprocal-rank fusion.

#### Layer 3: Evidence Packing and Reranking

- Collapse redundant chunks.
- Prefer diversity across files or sections where the SOP spans multiple documents.
- Construct a compact evidence pack for the executor and verifier.

#### Layer 4: Adaptive Follow-up Retrieval

- If verifier confidence is low, retrieve again with a richer query.
- Expand to prerequisite sections, exception-handling sections, or approval-policy sections.

Illustrative retrieval helper:

```python
def retrieve_evidence_pack(query: str, collection_id: str) -> list[EvidenceRef]:
    dense_hits = chroma_search(query=query, collection_id=collection_id, k=8)
    lexical_hits = lexical_search(query=query, collection_id=collection_id, k=8)
    merged_hits = reciprocal_rank_fusion(dense_hits, lexical_hits)
    reranked_hits = rerank_hits(query=query, hits=merged_hits)
    return build_evidence_pack(reranked_hits[:5])
```

### 6.6 Long-Context Strategy

Large-context models changed the design space in 2026. The planner should not blindly stay in tiny context windows.

- For simple tasks, use the compact evidence pack.
- For ambiguous or cross-document tasks, create a long-context pack with section summaries plus the highest-value raw passages.
- Long context is a supplement to retrieval, not a replacement for retrieval.

### 6.7 GraphRAG Decision

**Decision:** GraphRAG is not a day-one dependency for this product. It is an optional advanced overlay.

Rationale:

- Most SOP execution workflows can be solved with strong structure extraction plus hybrid retrieval.
- Graph memory becomes valuable when the corpus contains many cross-references between people, approvals, forms, systems, and prerequisites.
- Treat graph memory as a feature flag (`ENABLE_GRAPH_MEMORY`) and adopt it only when retrieval evidence shows that relationship reasoning is a real bottleneck.

### 6.8 Retrieval Failure Behavior

- If the evidence pack is empty or contradictory, the verifier must not approve completion.
- The runtime should try one richer retrieval pass before escalating.
- If evidence remains weak, route to `approval_gate_node` or `replanner_node`, depending on the cause.

---

## 7. Backend API Design

### 7.1 Base URL

Development base URL: `http://localhost:8000`  
All application endpoints are under `/api/v1/`.

### 7.2 Public REST and SSE Endpoints

#### `POST /api/v1/ingest`

Uploads and indexes one or more SOP documents.

**Request:** `multipart/form-data`

```text
files: List[UploadFile]
session_id: Optional[str]
```

**Response 200:**

```json
{
  "session_id": "uuid",
  "collection_id": "sop_uuid",
  "collection_version": 1,
  "files_processed": ["client_onboarding.pdf"],
  "total_chunks": 142,
  "status": "ready"
}
```

#### `POST /api/v1/execute`

Starts or resumes a session. Response is an SSE stream.

**Request body:**

```json
{
  "session_id": "uuid",
  "task_description": "Onboard a new enterprise client named Acme Corp.",
  "collection_id": "sop_uuid",
  "reasoning_profile": "balanced"
}
```

**SSE events include:**

```text
planning_started
plan_ready
evidence_loaded
step_executing
verification_passed
awaiting_operator
replanning_started
run_completed
```

#### `GET /api/v1/status/{session_id}`

Returns the latest durable view of run state.

**Response 200:**

```json
{
  "session_id": "uuid",
  "status": "awaiting_operator",
  "current_step_index": 3,
  "total_steps": 8,
  "completed_steps": 3,
  "replan_count": 1,
  "awaiting_operator": true,
  "pending_approval": {
    "step_id": "step_4",
    "reason": "Manager approval required for client assignment"
  }
}
```

#### `POST /api/v1/intervene`

Records operator intervention and resumes the run.

**Request body:**

```json
{
  "session_id": "uuid",
  "step_id": "step_4",
  "action": "override",
  "override_text": "Assign Jordan Patel instead of Sarah Chen",
  "reason": "Sarah is unavailable this week"
}
```

Allowed `action` values:

- `approve`
- `override`
- `skip`
- `abort`
- `request_replan`

#### `POST /api/v1/replan`

Requests an explicit replan without waiting for a verifier-triggered replan.

#### `GET /api/v1/report/{session_id}`

Returns the final Markdown report and run metadata.

#### `GET /api/v1/report/{session_id}/pdf`

Downloads the PDF report.

#### `DELETE /api/v1/session/{session_id}`

Deletes session state, report artifacts, and retrieval collections.

#### `GET /api/v1/health`

Health and readiness endpoint.

**Response 200:**

```json
{
  "status": "healthy",
  "model_provider": "anthropic",
  "embedding_provider": "gemini",
  "sqlite": "connected",
  "chromadb": "connected",
  "mcp_tools": "enabled"
}
```

### 7.3 MCP Tool Surface

FastAPI remains the public application API. MCP is the preferred internal tool boundary and the future external composition boundary.

The service should expose MCP tools such as:

| Tool | Purpose |
|---|---|
| `search_sop_context` | Retrieve evidence for a query or step |
| `get_run_state` | Return current step, status, and pending approval |
| `submit_intervention` | Record operator actions |
| `list_run_events` | Return the append-only event log |
| `render_execution_report` | Return Markdown or PDF report artifacts |

Transport may be `stdio` for local composition and HTTP/SSE for service mode. Public internet exposure of the MCP tool surface is not required for v1.

### 7.4 Error Response Schema

All API errors should follow this shape:

```json
{
  "error": "SHORT_ERROR_CODE",
  "message": "Human readable description",
  "detail": "Technical detail if available",
  "retryable": false,
  "trace_id": "uuid"
}
```

---

## 8. Database Schema

### 8.1 Persistence Strategy

- SQLite stores authoritative run state, event history, interventions, and reports.
- SQLite must run in WAL mode.
- ChromaDB stores dense vectors.
- A lightweight lexical index must exist alongside ChromaDB for hybrid retrieval.

Primary file path: `./data/sop_agent.db`

### 8.2 SQLite Schema

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_description TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    collection_version INTEGER NOT NULL DEFAULT 1,
    reasoning_profile TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step_index INTEGER NOT NULL DEFAULT 0,
    replan_count INTEGER NOT NULL DEFAULT 0,
    awaiting_operator INTEGER NOT NULL DEFAULT 0,
    final_report TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS session_steps (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    branch_condition TEXT,
    risk_level TEXT NOT NULL,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    recommended_action TEXT,
    verification_summary TEXT,
    confidence REAL,
    operator_action TEXT,
    completed_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS step_evidence (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    section_path TEXT,
    page_number INTEGER,
    quote TEXT NOT NULL,
    score REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES session_steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    override_text TEXT,
    actor TEXT NOT NULL DEFAULT 'operator',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES session_steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingested_files (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
```

---

## 9. Frontend UI Specification

### 9.1 Framework

**Streamlit** — all in a single `app.py`. No React, no separate frontend server. The entire UI is Python.

### 9.2 Page Layout

The app has a **single-page layout** with a sidebar and main content area.

#### Sidebar
```
┌──────────────────────────┐
│  🤖 SOP Agent            │
│  ─────────────────────── │
│  Model: [dropdown]       │
│  gemini-2.5-flash ▼        │
│                          │
│  ─────────────────────── │
│  Active Session:         │
│  abc-123-def             │
│                          │
│  SOPs Loaded: 3 files    │
│  142 chunks indexed      │
│                          │
│  [+ Upload New SOPs]     │
│  [🗑 Clear Session]       │
└──────────────────────────┘
```

#### Main Area — 3 Phases

**Phase 1: Upload (shown when no SOPs loaded)**
```
┌────────────────────────────────────────────┐
│  Upload Your SOP Documents                 │
│  ─────────────────────────────────────────│
│  Drag & drop or browse                     │
│  Supports: PDF, DOCX, TXT, MD             │
│  Max 10 files, 20MB each                   │
│                                            │
│  [     Choose Files     ]                  │
│                                            │
│  ✅ client_onboarding.pdf (142 chunks)     │
│  ✅ hr_policy.docx (89 chunks)             │
│                                            │
│  [  ▶ Proceed to Task Input  ]             │
└────────────────────────────────────────────┘
```

**Phase 2: Task Input (shown after SOPs loaded)**
```
┌────────────────────────────────────────────┐
│  What task do you want to execute?         │
│  ─────────────────────────────────────────│
│  ┌──────────────────────────────────────┐ │
│  │ Onboard a new enterprise client      │ │
│  │ named Acme Corp. They have a team    │ │
│  │ of 50 people.                        │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  [  ⚡ Generate Execution Plan  ]          │
└────────────────────────────────────────────┘
```

**Phase 3: Execution Tracker (main phase)**

This is the most important screen. It shows a dynamic checklist:

```
┌────────────────────────────────────────────────────────────────┐
│  Executing: "Onboard a new enterprise client: Acme Corp"       │
│  Progress: ████████░░░░░░░░  3 / 8 steps                       │
│────────────────────────────────────────────────────────────────│
│                                                                │
│  ✅  Step 1: Verify client account type                        │
│      AI: Confirmed as Enterprise tier based on team size >25  │
│                                                                │
│  ✅  Step 2: Send welcome email                                │
│      AI: Draft email generated. Subject: "Welcome to..."      │
│                                                                │
│  ✅  Step 3: Create client profile in CRM                      │
│      AI: Completed. Profile fields per SOP section 3.2.       │
│                                                                │
│  🟡  Step 4: Assign dedicated account manager    ← CURRENT    │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  ⚠️ Human Review Required                               │   │
│  │                                                        │   │
│  │  AI Recommendation:                                    │   │
│  │  Assign Sarah Chen (Senior AM) based on SOP rule:      │   │
│  │  Enterprise clients must have Senior AM with 3+ years. │   │
│  │                                                        │   │
│  │  SOP Reference: Section 4.1, Page 7                    │   │
│  │                                                        │   │
│  │  Critic Note: Cannot auto-assign without confirming    │   │
│  │  availability in scheduling system.                    │   │
│  │                                                        │   │
│  │  ┌─────────────────────────────────────────────────┐  │   │
│  │  │ Override (optional): ______________________     │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  │                                                        │   │
│  │  [✅ Approve]   [✏️ Override]   [⏭ Skip]   [🛑 Abort]   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ⬜  Step 5: Schedule kickoff call  (pending)                  │
│  ⬜  Step 6: Provision system access  (pending)                │
│  ⬜  Step 7: Send SLA documentation  (pending)                 │
│  ⬜  Step 8: Complete onboarding checklist  (pending)          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Phase 4: Completion Screen**

```
┌────────────────────────────────────────────┐
│  ✅ Execution Complete                     │
│  Task: Onboard Acme Corp                   │
│  Duration: 12 minutes                      │
│  Steps: 7 completed, 1 skipped             │
│  Human interventions: 2                    │
│                                            │
│  [📥 Download PDF Report]                  │
│  [📋 Copy Markdown]                        │
│  [🔄 Start New Task]                       │
└────────────────────────────────────────────┘
```

### 9.3 Streamlit State Management

Use `st.session_state` to persist:
- `session_id` — UUID for this session
- `collection_id` — ChromaDB collection
- `phase` — `"upload"` | `"task"` | `"executing"` | `"complete"`
- `steps` — list of step dicts
- `awaiting_human` — bool
- `current_step_index` — int

Use `st.rerun()` after API calls to refresh UI state.

### 9.4 Streaming Display

When `/execute` is called, parse the SSE stream and update `st.session_state.steps` incrementally. Use `st.empty()` containers for live updates without full page reloads.

---

## 10. LLM Model Configuration

### 10.1 LLM Factory Function

This function is the **single source of truth** for LLM initialization. All agent nodes call this function. Never initialize an LLM directly in a node.

```python
# app/core/llm_factory.py

import os
from langchain_core.language_models import BaseChatModel

def get_llm(temperature: float = 0.1) -> BaseChatModel:
    provider = os.getenv("MODEL_PROVIDER", "gemini").lower()

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=temperature,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=temperature,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
        )

    else:
        raise ValueError(f"Unsupported MODEL_PROVIDER: {provider}")


def get_embedding_model():
    provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()

    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )

    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    elif provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    else:
        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")
```

### 10.2 Temperature Settings by Node

| Node | Temperature | Reason |
|---|---|---|
| `planner_node` | 0.2 | Creative enough to plan, but grounded |
| `executor_node` | 0.1 | Precise, deterministic recommendations |
| `critic_node` | 0.0 | Fully deterministic — no creativity in review |
| `reporter_node` | 0.3 | Slightly more fluent report writing |

---

## 11. File Ingestion Pipeline

### 11.1 Full Ingestion Flow

```python
# app/services/ingestion.py

async def ingest_files(
    files: List[UploadFile],
    session_id: str,
) -> IngestResult:

    collection_id = f"sop_{session_id}"
    collection = get_or_create_collection(collection_id)
    embedding_model = get_embedding_model()

    all_chunks = []
    processed_files = []

    for file in files:
        # 1. Parse file based on type
        raw_text = await parse_file(file)

        # 2. Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=150
        )
        chunks = splitter.create_documents(
            texts=[raw_text],
            metadatas=[{
                "source_file": file.filename,
                "session_id": session_id,
            }]
        )

        # 3. Enrich metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["ingested_at"] = datetime.utcnow().isoformat()

        all_chunks.extend(chunks)
        processed_files.append({
            "filename": file.filename,
            "chunk_count": len(chunks)
        })

    # 4. Batch embed and store
    # Batch in groups of 50 to avoid rate limits
    for batch in chunk_list(all_chunks, size=50):
        texts = [c.page_content for c in batch]
        metadatas = [c.metadata for c in batch]
        ids = [str(uuid4()) for _ in batch]
        embeddings = embedding_model.embed_documents(texts)
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )
        await asyncio.sleep(0.5)  # Rate limit buffer

    # 5. Record in SQLite
    await db.record_ingestion(session_id, processed_files)

    return IngestResult(
        session_id=session_id,
        collection_id=collection_id,
        total_chunks=len(all_chunks),
        files_processed=[f["filename"] for f in processed_files],
    )
```

### 11.2 File Parsers

```python
async def parse_file(file: UploadFile) -> str:
    content = await file.read()
    suffix = Path(file.filename).suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(content)
    elif suffix == ".docx":
        return parse_docx(content)
    elif suffix in [".txt", ".md"]:
        return content.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported: {suffix}")


def parse_pdf(content: bytes) -> str:
    import pdfplumber
    import io
    text_parts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


def parse_docx(content: bytes) -> str:
    from docx import Document
    import io
    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
```

---

## 12. Error Handling & Fallback Strategy

### 12.1 LLM Call Failures

All LLM calls must be wrapped in a retry decorator:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def call_llm_with_retry(llm, messages):
    return await llm.ainvoke(messages)
```

On 3rd failure: log the error, set step status to `"flagged"`, route to `human_gate_node` with `exception_reason = "AI failed to process this step after 3 attempts. Manual execution required."`.

### 12.2 JSON Parsing Failures

When an LLM returns malformed JSON:

```python
def parse_llm_json(raw_response: str, repair_attempt: bool = False) -> dict:
    # First: try direct parse
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        pass

    # Second: strip markdown code blocks
    cleaned = re.sub(r"```json|```", "", raw_response).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Third: use json_repair library
    try:
        from json_repair import repair_json
        return json.loads(repair_json(cleaned))
    except Exception:
        raise ValueError(f"Unparseable LLM response: {raw_response[:200]}")
```

Add `json_repair` to requirements: `pip install json-repair`

### 12.3 ChromaDB Query Failures

If ChromaDB returns an error or zero results:
- Log warning
- Set `retrieved_context = "No relevant SOP context found for this step."`
- Flag step for human review

### 12.4 Session Not Found

If a `session_id` is submitted but not in SQLite:
- Return HTTP 404 with: `{"error": "SESSION_NOT_FOUND", "message": "No session with this ID exists."}`

### 12.5 Rate Limiting (Gemini Free Tier)

Gemini free tier: 15 requests/minute, 1M tokens/day. Implement:

```python
import asyncio
from collections import deque
import time

class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()

    async def acquire(self):
        now = time.monotonic()
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            await asyncio.sleep(sleep_time)
        self.calls.append(time.monotonic())

gemini_limiter = RateLimiter(max_calls=14, period=60.0)  # 14/min for safety (gemini-2.5-flash free tier)
```

---

## 13. Security Considerations

### 13.1 API Key Handling

- **Never** include API keys in source code
- **Never** log API keys
- **Never** return API keys in any API response
- All keys loaded exclusively from `.env` via `python-dotenv`
- `.env` is in `.gitignore` — a `.env.example` with placeholder values is committed instead

### 13.2 File Upload Security

```python
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB

async def validate_upload(file: UploadFile):
    # Extension check
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, detail=f"File type {ext} not allowed")

    # Size check (read first chunk)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, detail="File exceeds 20MB limit")

    # MIME type validation (basic)
    import magic
    mime = magic.from_buffer(content[:1024], mime=True)
    ALLOWED_MIMES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }
    if mime not in ALLOWED_MIMES:
        raise HTTPException(415, detail=f"MIME type {mime} not allowed")

    await file.seek(0)  # Reset after reading
    return content
```

### 13.3 Input Sanitization

- Sanitize `task_description` to remove any prompt injection attempts
- Maximum length: 2,000 characters
- Strip HTML tags from all user inputs

### 13.4 CORS Configuration

For development, allow `localhost:*`. For production, restrict to known frontend domain.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit dev port
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
```

---

## 14. Testing Requirements

### 14.1 Test Structure

```
tests/
├── unit/
│   ├── test_parsers.py          # PDF, DOCX, TXT parsing
│   ├── test_splitter.py         # Chunking strategy
│   ├── test_llm_factory.py      # LLM initialization
│   ├── test_json_repair.py      # JSON parsing fallbacks
│   └── test_routing.py          # LangGraph routing functions
├── integration/
│   ├── test_ingestion.py        # Full ingestion pipeline
│   ├── test_agent_nodes.py      # Each node with mocked LLM
│   ├── test_api_endpoints.py    # FastAPI endpoints
│   └── test_rag_retrieval.py    # ChromaDB retrieval quality
├── e2e/
│   └── test_full_workflow.py    # Complete SOP upload → execute → report
├── fixtures/
│   ├── sample_sop.pdf           # A realistic SOP document for testing
│   ├── sample_sop.docx
│   └── test_tasks.json          # Sample task descriptions
└── conftest.py
```

### 14.2 Minimum Test Coverage Requirements

| Area | Coverage Target |
|---|---|
| File parsers | 100% |
| Routing functions | 100% |
| LLM factory | 90% |
| API endpoints | 85% |
| Agent nodes (mocked LLM) | 80% |
| RAG retrieval | 75% |

### 14.3 Mocking Strategy for LLM Calls

**Do not make real LLM calls in tests.** Use `unittest.mock.patch`:

```python
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_llm():
    with patch("app.core.llm_factory.get_llm") as mock:
        llm = MagicMock()
        llm.ainvoke.return_value = MagicMock(
            content='[{"step_number": 1, "title": "Test Step", ...}]'
        )
        mock.return_value = llm
        yield llm
```

### 14.4 Key Test Cases

```python
# test_agent_nodes.py

async def test_planner_generates_valid_steps(mock_llm, sample_sop_collection):
    """Planner must return at least 3 steps grounded in SOP."""

async def test_critic_flags_low_confidence_steps(mock_llm):
    """Critic must route to human_gate when confidence < 0.75."""

async def test_human_gate_pauses_graph(mock_llm):
    """Graph must pause and not proceed until /confirm is called."""

async def test_execution_resumes_after_approve(mock_llm):
    """After approve, next step must be retrieved and executed."""

async def test_execution_terminates_on_abort(mock_llm):
    """Abort must skip all remaining steps and go to reporter."""

async def test_reporter_generates_markdown(mock_llm, completed_steps):
    """Reporter output must contain all required sections."""

async def test_full_workflow_no_human_steps(mock_llm, simple_sop):
    """A simple SOP with no approval steps must complete automatically."""
```

---

## 15. Deployment Guide

### 15.1 Local Development Setup

```bash
# 1. Clone repo
git clone https://github.com/[owner]/sop-agent
cd sop-agent

# 2. Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env file
cp .env.example .env
# Edit .env with your GEMINI_API_KEY

# 5. Initialize database
python scripts/init_db.py

# 6. Start backend
uvicorn app.main:app --reload --port 8000

# 7. Start frontend (new terminal)
streamlit run frontend/app.py --server.port 8501
```

### 15.2 Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p /app/data/chromadb /app/data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "8501:8501"
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped
```

```dockerfile
# Dockerfile.frontend
FROM python:3.13-slim
WORKDIR /app
COPY requirements-frontend.txt .
RUN pip install --no-cache-dir -r requirements-frontend.txt
COPY frontend/ .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

### 15.3 Railway Deployment

1. Push to GitHub
2. Connect Railway to GitHub repo
3. Add environment variables in Railway dashboard (from `.env.example`)
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add a second Railway service for Streamlit frontend
6. Set `BACKEND_URL` in frontend service env to the Railway backend URL

### 15.4 Persistent Storage on Railway

Railway volumes are ephemeral. For production:
- Use **Turso** (hosted SQLite) instead of local SQLite
- Use **Chroma Cloud** or migrate ChromaDB to a persistent Railway volume

For demo/portfolio purposes, local SQLite + ChromaDB on Railway is fine (data resets on redeploy, acceptable for demos).

---

## 16. Project Directory Structure

```
sop-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── llm_factory.py         # LLM + embedding factory
│   │   ├── config.py              # Settings from env vars
│   │   └── database.py            # SQLite connection + queries
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py               # AgentState TypedDict + SOPStep
│   │   ├── graph.py               # LangGraph graph builder
│   │   ├── nodes/
│   │   │   ├── supervisor.py
│   │   │   ├── planner.py
│   │   │   ├── retriever.py
│   │   │   ├── executor.py
│   │   │   ├── critic.py
│   │   │   ├── human_gate.py
│   │   │   └── reporter.py
│   │   └── routing.py             # All routing/conditional edge functions
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion.py           # File upload + chunking + embedding
│   │   ├── retrieval.py           # ChromaDB query wrapper
│   │   └── report_export.py       # Markdown → PDF
│   └── api/
│       ├── __init__.py
│       ├── routes/
│       │   ├── ingest.py
│       │   ├── execute.py
│       │   ├── session.py
│       │   └── report.py
│       └── schemas.py             # Pydantic request/response models
├── frontend/
│   ├── app.py                     # Streamlit entry point
│   ├── components/
│   │   ├── upload_panel.py
│   │   ├── task_input.py
│   │   ├── execution_tracker.py   # The main checklist UI
│   │   ├── human_gate_ui.py       # Approval/override panel
│   │   └── report_viewer.py
│   └── utils/
│       ├── api_client.py          # HTTP client for FastAPI
│       └── session_manager.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── fixtures/
│   └── conftest.py
├── scripts/
│   ├── init_db.py                 # Create SQLite tables
│   └── test_llm.py                # Quick LLM connectivity test
├── data/                          # Gitignored — runtime data
│   ├── chromadb/
│   ├── uploads/
│   └── sop_agent.db
├── .env.example
├── .env                           # Gitignored
├── .gitignore
├── requirements.txt               # Backend
├── requirements-frontend.txt      # Frontend (Streamlit only)
├── Dockerfile
├── Dockerfile.frontend
├── docker-compose.yml
└── README.md
```

---

## 17. Environment Variables Reference

```bash
# .env.example

# Core model behavior
MODEL_PROFILE=balanced
MODEL_PROVIDER=
MODEL_NAME=
ALLOW_PREVIEW_MODELS=false
ENABLE_PROVIDER_FAILOVER=false
FALLBACK_MODEL_PROVIDER=openai
FALLBACK_MODEL_NAME=gpt-5.4-mini

# Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4
OPENAI_EMBED_MODEL=text-embedding-3-small

# Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=models/text-embedding-004

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Embeddings
EMBEDDING_PROVIDER=gemini

# Retrieval and graph memory
ENABLE_GRAPH_MEMORY=false
LEXICAL_INDEX_PATH=./data/lexical.db
TOP_K_DENSE=8
TOP_K_LEXICAL=8
TOP_K_EVIDENCE_PACK=5

# Policy thresholds
VERIFIER_MIN_CONFIDENCE=0.80
AUTO_CONTINUE_MAX_RISK=medium

# Persistence
SQLITE_PATH=./data/sop_agent.db
CHROMADB_PATH=./data/chromadb
UPLOAD_DIR=./data/uploads

# API and UI
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_URL=http://localhost:8000
LOG_LEVEL=INFO

# MCP
ENABLE_MCP=true
MCP_TRANSPORT=stdio

# Observability
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=your_langsmith_key
# LANGCHAIN_PROJECT=sop-agent

# Upload policy
MAX_FILE_SIZE_MB=20
MAX_FILES_PER_SESSION=10
```

---

## 18. Glossary

| Term | Definition |
|---|---|
| **SOP** | Standard Operating Procedure; a documented process for repeatable work |
| **LangGraph** | A framework for building stateful, resumable agent workflows as graphs |
| **RAG** | Retrieval-Augmented Generation; injecting retrieved evidence into model context |
| **Hybrid Retrieval** | Combining dense semantic retrieval with lexical retrieval and reranking |
| **Evidence Pack** | The compact set of source passages used to justify a step or decision |
| **Human-on-the-Loop** | A supervision model where the system proceeds by default but operators can intervene and the runtime pauses only on policy or uncertainty |
| **Approval Gate** | The graph node or policy action that pauses execution for operator input |
| **Replanning** | Recomputing the unfinished suffix of the plan when evidence or operator input changes the path |
| **GraphRAG / Graph Memory** | A relationship-aware retrieval layer built from entities and dependencies across documents |
| **MCP** | Model Context Protocol; a standard interface for exposing tools and context to models |
| **Checkpoint** | Durable persisted graph state that allows safe resume after interruption or failure |
| **SSE** | Server-Sent Events; HTTP event streaming used by the run console |
| **Collection Version** | The version tag that ties stored vectors to a specific embedding strategy |
| **Reasoning Profile** | The lane that maps workload type to provider/model defaults |

---

## 19. Technical Memorandum — Lead AI Architect Review

> **Date:** April 2026  
> **Reviewer Role:** Lead AI Systems Architect  
> **Mandate:** Determine whether this project is worth building in April 2026 and define the architecture required to make it worth building.

---

### 19.1 Executive Assessment

The earlier draft had a credible 2024/2025 shape, but it was no longer sufficient for a serious April 2026 build. Its main weaknesses were not only stale model names. The deeper issue was architectural posture: it still behaved like a static RAG application with a checklist UI, rather than a stateful workflow runtime with verification, replanning, and policy-aware supervision.

**Verdict:** The project remains worth building, but only in the modernized form captured in this revision.

### 19.2 What Was Obsolete

| Previous Pattern | Why It Is Obsolete in 2026 | Adopted Replacement |
|---|---|---|
| Static vector-only RAG as the main intelligence layer | Modern models can reason over larger context, call tools, and benefit from step-time retrieval and verification | Tiered retrieval with hybrid search, evidence packs, and replanning |
| Prompt-plus-JSON-repair as the structured output strategy | GPT-5.4, Claude 4.6, Gemini 2.5, and modern LangChain stacks support schema-first output far more reliably | Typed structured output via schema binding |
| Human-in-the-loop as the default control model | Over-pausing the runtime makes the product slow and operationally weak | Human-on-the-loop with policy-driven pauses |
| Three-provider story with no first-class Anthropic lane | Claude 4.6 is now a serious baseline provider, not an optional afterthought | Four first-class provider lanes: Anthropic, OpenAI, Gemini, Ollama |
| One-pass planning with weak correction mechanics | Real SOP execution needs verification and plan repair when assumptions change | Verifier and replanner nodes |
| Unqualified GraphRAG enthusiasm | Graph memory is powerful but not universally required | Optional graph-memory overlay behind a feature flag |

### 19.3 Version and Capability Corrections Adopted

This revision adopts the following stable-first April 2026 baselines:

- Python `3.14.3`
- LangGraph `1.1.6`
- LangChain `1.2.15`
- FastAPI `0.135.3`
- Streamlit `1.56.0`
- ChromaDB `1.5.5`
- Anthropic `claude-sonnet-4-6` and `claude-opus-4-6`
- OpenAI `gpt-5.4`, `gpt-5.4-mini`, and `gpt-5.4-nano`
- Gemini `gemini-2.5-flash` as the stable baseline lane

Preview capabilities are preserved as optional evaluation lanes, not silently promoted to defaults.

### 19.4 Why Static RAG Is No Longer Enough

Static RAG is not obsolete because retrieval is unnecessary. It is obsolete because **retrieval alone is no longer an adequate architecture** for workflow execution.

Modern frontier and near-frontier models changed the design space in four ways:

1. **Long context is now operationally relevant.** Larger context windows allow better initial planning and better exception handling, especially across multiple SOP documents.
2. **Structured outputs are now a practical baseline.** We no longer need to build the core runtime around malformed JSON recovery.
3. **Tool use is normal, not exotic.** MCP and provider tool interfaces make it reasonable to separate session control, retrieval, and reporting into explicit tools.
4. **Reasoning controls make adaptive orchestration worthwhile.** Hard steps should consume more reasoning budget than routine steps.

Therefore the correct 2026 architecture is not "retrieve once, answer once." It is "plan, retrieve, execute, verify, replan or escalate."

### 19.5 Architectural Decisions Made in This Revision

| Decision | Rationale |
|---|---|
| Python 3.14.3 baseline, 3.13 fallback only | Current stable runtime without pretending experimental features are production defaults |
| Claude 4.6 added as a first-class provider lane | Stable-first posture requires Anthropic to be part of the primary matrix |
| Structured output made mandatory | Removes brittle parsing and improves testability |
| Verifier and replanner added to the core graph | Fixes the main weakness of one-pass execution |
| Human-on-the-loop adopted | Preserves operator control without making the runtime unusably slow |
| Hybrid retrieval adopted as baseline | SOP work needs better recall than dense-only search usually delivers |
| Graph memory made optional | Avoids over-engineering while leaving a path for harder corpora |
| MCP treated as the preferred tool boundary | Positions the system for composition without replacing FastAPI as the app API |

### 19.6 Build Recommendation

Build this project if the team is willing to implement:

- typed structured outputs
- hybrid retrieval
- verification and replanning
- policy-driven approvals
- provider portability

Do **not** build it as a simple vector-search plus checklist shell. That version is no longer competitive and will waste development time.

### 19.7 Immediate Implementation Priorities

| Priority | Action |
|---|---|
| P0 | Implement the revised graph topology with verifier and replanner nodes |
| P0 | Implement schema-first model calls and remove JSON-repair-centric assumptions |
| P0 | Add Anthropic as a first-class provider in the model factory |
| P1 | Implement hybrid retrieval with lexical sidecar index |
| P1 | Add WAL mode and event-log persistence |
| P1 | Implement operator intervention endpoints and UI drawer |
| P2 | Add optional graph memory behind a feature flag |
| P2 | Add provider failover and regression evaluation harness |

---

*End of Technical Memorandum*

---

*End of Specification - v1.2 - April 2026*
