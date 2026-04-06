# SOP Agent — API Reference

Base URL: `http://localhost:8000`

Interactive documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Table of Contents

- [Health Check](#health-check)
- [Document Ingestion](#document-ingestion)
- [Execution](#execution)
- [Intervention](#intervention)
- [Reports](#reports)
- [Sessions](#sessions)
- [MCP Protocol](#mcp-protocol)
- [Error Responses](#error-responses)

---

## Health Check

### `GET /health`

Returns backend health status.

**Response:**
```json
{
  "status": "ok",
  "version": "1.2.0"
}
```

---

## Document Ingestion

### `POST /api/v1/ingest`

Upload and ingest SOP documents. Supports PDF, DOCX, TXT, and Markdown files.

**Content-Type:** `multipart/form-data`

**Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | File[] | Yes | One or more SOP document files |
| `session_id` | string | No | Existing session ID (auto-generated if omitted) |
| `collection_name` | string | No | Collection name (auto-generated if omitted) |

**Request (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "files=@onboarding_sop.pdf" \
  -F "files=@it_security_policy.docx" \
  -F "session_id=my-session-123"
```

**Response (200):**
```json
{
  "session_id": "my-session-123",
  "collection_id": "coll_abc123",
  "collection_version": 1,
  "total_chunks": 87,
  "files_processed": ["onboarding_sop.pdf", "it_security_policy.docx"],
  "status": "ready"
}
```

**Error (400):**
```json
{
  "detail": "Unsupported file type: .exe. Allowed: .pdf, .docx, .txt, .md"
}
```

**Processing Pipeline:**
1. File validation (extension + MIME + size ≤ 20 MB)
2. Text extraction (pdfplumber / python-docx / plain read)
3. Recursive chunking (1000 chars, 200 overlap)
4. Embedding generation (provider-dependent)
5. Dual indexing: ChromaDB (dense) + SQLite FTS5 (lexical)
6. Document map creation (section-level index)

---

## Execution

### `POST /api/v1/execute`

Start or resume SOP execution for a session.

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Session with ingested documents |
| `task_description` | string | Yes | Natural language task description |

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-123",
    "task_description": "Execute the employee onboarding procedure for a new software engineer"
  }'
```

**Response (200):**
```json
{
  "session_id": "my-session-123",
  "status": "executing",
  "message": "Execution started"
}
```

> **Note:** Execution runs asynchronously in the background. Use the SSE stream endpoint to monitor progress.

### `GET /api/v1/execute/{session_id}/stream`

Subscribe to real-time execution events via Server-Sent Events (SSE).

**Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | path | Yes | Active execution session ID |

**Request:**
```bash
curl -N http://localhost:8000/api/v1/execute/my-session-123/stream
```

**Event Types:**

| Event | Data Fields | Description |
|---|---|---|
| `node_update` | `node`, `step_index`, `status`, `data` | Node completed processing |
| `approval_needed` | `step_index`, `step_title`, `confidence`, `reason` | Human approval required |
| `done` | `session_id`, `status`, `total_steps` | Execution completed |
| `error` | `message`, `node` | Error occurred |

**Example Event Stream:**
```
event: node_update
data: {"node": "planner", "step_index": 0, "status": "planned", "data": {"total_steps": 5}}

event: node_update
data: {"node": "executor", "step_index": 0, "status": "executed", "data": {"confidence": 0.92}}

event: approval_needed
data: {"step_index": 1, "step_title": "Set up workstation", "confidence": 0.65, "reason": "Low confidence"}

event: done
data: {"session_id": "my-session-123", "status": "completed", "total_steps": 5}
```

---

## Intervention

### `POST /api/v1/intervene`

Submit an operator intervention during execution (when approval is needed).

**Content-Type:** `application/json`

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Session awaiting intervention |
| `action` | string | Yes | One of: `approve`, `override`, `skip`, `abort`, `request_replan` |
| `override_text` | string | No | Required when action is `override` — replacement instructions |
| `reason` | string | No | Optional reason for the intervention decision |

**Actions:**

| Action | Effect |
|---|---|
| `approve` | Accept the recommended action; continue to next step |
| `override` | Replace action with `override_text`; continue |
| `skip` | Mark step as skipped; advance to next step |
| `abort` | Stop execution immediately; generate report |
| `request_replan` | Regenerate remaining plan steps |

**Request:**
```bash
# Approve a step
curl -X POST http://localhost:8000/api/v1/intervene \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-123",
    "action": "approve",
    "reason": "Verified with team lead"
  }'

# Override a step
curl -X POST http://localhost:8000/api/v1/intervene \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-123",
    "action": "override",
    "override_text": "Use the alternative vendor onboarding form instead",
    "reason": "Process changed last week"
  }'
```

**Response (200):**
```json
{
  "session_id": "my-session-123",
  "status": "resumed",
  "message": "Action 'approve' recorded for session"
}
```

---

## Reports

### `GET /api/v1/report/{session_id}`

Retrieve the execution report for a completed session.

**Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | path | Yes | Completed session ID |

**Response (200):**
```json
{
  "session_id": "my-session-123",
  "status": "completed",
  "report": "# SOP Execution Report\n\n## Session: my-session-123\n..."
}
```

### `GET /api/v1/report/{session_id}/download`

Export and download the report as a Markdown file.

**Response (200):**
```json
{
  "session_id": "my-session-123",
  "file_path": "./data/reports/report_my-session-123.md"
}
```

---

## Sessions

### `GET /api/v1/sessions`

List all sessions.

**Response (200):**
```json
{
  "sessions": [
    {
      "session_id": "my-session-123",
      "status": "completed",
      "task": "Execute onboarding...",
      "created_at": "2025-01-15T10:30:00Z"
    },
    {
      "session_id": "abc-456",
      "status": "awaiting_approval",
      "task": "Review safety checklist...",
      "created_at": "2025-01-15T11:00:00Z"
    }
  ]
}
```

### `GET /api/v1/sessions/{session_id}`

Get details for a specific session.

**Response (200):**
```json
{
  "session_id": "my-session-123",
  "status": "completed",
  "task": "Execute onboarding procedure",
  "collection_id": "coll_abc123",
  "total_steps": 5,
  "completed_steps": 5,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:45:00Z"
}
```

### `DELETE /api/v1/sessions/{session_id}`

Delete a session and its associated data.

**Response (200):**
```json
{
  "status": "deleted",
  "session_id": "my-session-123"
}
```

---

## MCP Protocol

SOP Agent implements a Model Context Protocol (MCP) server for integration with AI IDEs and agents.

### `GET /mcp/tools`

List available MCP tools.

**Response (200):**
```json
{
  "tools": [
    {
      "name": "ingest_sop",
      "description": "Ingest SOP documents from file paths",
      "parameters": {
        "file_paths": {"type": "array", "items": {"type": "string"}},
        "session_id": {"type": "string", "optional": true}
      }
    },
    {
      "name": "run_sop",
      "description": "Execute a task against ingested SOPs",
      "parameters": {
        "session_id": {"type": "string"},
        "task_description": {"type": "string"}
      }
    },
    {
      "name": "approve_step",
      "description": "Submit operator approval decision",
      "parameters": {
        "session_id": {"type": "string"},
        "action": {"type": "string"},
        "override_text": {"type": "string", "optional": true}
      }
    },
    {
      "name": "get_report",
      "description": "Retrieve execution report",
      "parameters": {
        "session_id": {"type": "string"}
      }
    }
  ]
}
```

### `POST /mcp/call`

Execute an MCP tool.

**Request Body:**
```json
{
  "name": "run_sop",
  "arguments": {
    "session_id": "session-123",
    "task_description": "Execute the safety inspection checklist"
  }
}
```

**Response (200):**
```json
{
  "result": {
    "session_id": "session-123",
    "status": "executing",
    "message": "Execution started"
  }
}
```

### `GET /mcp/sse`

SSE keepalive stream for MCP clients.

---

## Error Responses

All error responses follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request (validation error, unsupported file type) |
| `404` | Resource not found (session, report) |
| `422` | Unprocessable entity (Pydantic validation failure) |
| `429` | Rate limited |
| `500` | Internal server error |

### Common Error Scenarios

| Scenario | Status | Detail |
|---|---|---|
| Unsupported file type | 400 | "Unsupported file type: .exe" |
| Session not found | 404 | "Session not found: abc-123" |
| No documents ingested | 400 | "No documents ingested for session" |
| Execution already running | 400 | "Execution already in progress" |
| No approval pending | 400 | "No pending approval for session" |
| Rate limit exceeded | 429 | "Rate limit exceeded. Retry after 60s" |
