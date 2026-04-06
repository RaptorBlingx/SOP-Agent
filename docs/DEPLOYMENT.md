# SOP Agent — Deployment Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Docker Compose](#docker-compose)
- [Manual Production Deployment](#manual-production-deployment)
- [Environment Configuration](#environment-configuration)
- [Monitoring & Logs](#monitoring--logs)
- [Backup & Recovery](#backup--recovery)
- [Scaling Considerations](#scaling-considerations)

---

## Prerequisites

### System Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 cores | 4 cores |
| RAM | 512 MB | 2 GB |
| Disk | 1 GB | 10 GB (dependent on document volume) |
| Python | 3.12+ | 3.12+ |
| OS | Linux, macOS, Windows (WSL2) | Ubuntu 22.04+ |

### External Dependencies

- **LLM API access**: At least one of Gemini, OpenAI, Anthropic, or local Ollama
- **libmagic1**: System library for MIME type detection (`apt install libmagic1`)
- **Docker** (optional): For containerized deployment

---

## Local Development

### 1. Clone Repository

```bash
git clone https://github.com/RaptorBlingx/SOP-Agent.git
cd SOP-Agent
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and preferences
```

### 5. Initialize Database

```bash
python scripts/init_db.py
```

### 6. Start Services

```bash
# Terminal 1: Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
streamlit run frontend/app.py --server.port 8501
```

### 7. Verify

```bash
curl http://localhost:8000/health
# → {"status": "ok", "version": "1.2.0"}
```

Open http://localhost:8501 for the Operator Console.

---

## Docker Compose

### Quick Start

```bash
# 1. Configure
cp .env.example .env && nano .env

# 2. Build and start
docker compose up --build -d

# 3. Verify
docker compose ps
curl http://localhost:8000/health
```

### docker-compose.yml Overview

The compose file defines two services:

| Service | Image | Port | Description |
|---|---|---|---|
| `backend` | `./Dockerfile` | 8000 | FastAPI + LangGraph backend |
| `frontend` | `./Dockerfile.frontend` | 8501 | Streamlit Operator Console |

### Volume Mounts

```yaml
volumes:
  - ./data:/app/data          # SQLite DB + ChromaDB + uploads
  - ./.env:/app/.env:ro       # Environment config (read-only)
```

The `./data` directory persists all state across container restarts.

### Health Checks

The backend container includes a health check:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 5
```

### Operations

```bash
# View logs
docker compose logs -f
docker compose logs backend -f
docker compose logs frontend -f

# Restart a service
docker compose restart backend

# Rebuild after code changes
docker compose up --build -d

# Stop all services
docker compose down

# Stop and remove volumes (removes data)
docker compose down -v
```

---

## Manual Production Deployment

### System Setup (Ubuntu)

```bash
# System packages
sudo apt update && sudo apt install -y python3.12 python3.12-venv libmagic1 curl

# Application user
sudo useradd -m -s /bin/bash sopagent
sudo su - sopagent

# Clone and install
git clone https://github.com/RaptorBlingx/SOP-Agent.git
cd SOP-Agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env

# Initialize
python scripts/init_db.py
mkdir -p data/uploads data/chromadb data/reports
```

### Systemd Service (Backend)

Create `/etc/systemd/system/sop-agent-backend.service`:

```ini
[Unit]
Description=SOP Agent Backend
After=network.target

[Service]
Type=simple
User=sopagent
WorkingDirectory=/home/sopagent/SOP-Agent
Environment=PATH=/home/sopagent/SOP-Agent/.venv/bin:/usr/bin
ExecStart=/home/sopagent/SOP-Agent/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Systemd Service (Frontend)

Create `/etc/systemd/system/sop-agent-frontend.service`:

```ini
[Unit]
Description=SOP Agent Frontend
After=sop-agent-backend.service

[Service]
Type=simple
User=sopagent
WorkingDirectory=/home/sopagent/SOP-Agent
Environment=PATH=/home/sopagent/SOP-Agent/.venv/bin:/usr/bin
ExecStart=/home/sopagent/SOP-Agent/.venv/bin/streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable sop-agent-backend sop-agent-frontend
sudo systemctl start sop-agent-backend sop-agent-frontend

# Check status
sudo systemctl status sop-agent-backend
sudo systemctl status sop-agent-frontend
```

---

## Environment Configuration

See [README.md](../README.md#configuration) for the full configuration table.

### Provider-Specific Setup

#### Google Gemini (Default)
```env
MODEL_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

#### OpenAI
```env
MODEL_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o
```

#### Anthropic
```env
MODEL_PROVIDER=anthropic
EMBEDDING_PROVIDER=openai          # Anthropic doesn't provide embeddings
OPENAI_API_KEY=your-openai-key     # Needed for embeddings
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

#### Ollama (Local, No API Key)
```env
MODEL_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Ensure Ollama is running and models are pulled:
```bash
ollama serve &
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

---

## Monitoring & Logs

### Structured Logging

The application outputs structured JSON logs. Key log fields:
- `timestamp` — ISO 8601
- `level` — DEBUG/INFO/WARNING/ERROR
- `module` — Source module
- `message` — Log message (PII-redacted)

### Log Level Configuration

```env
LOG_LEVEL=INFO    # DEBUG, INFO, WARNING, ERROR
```

### LangSmith Tracing (Optional)

For detailed LLM call tracing:
```env
ENABLE_LANGSMITH=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=sop-agent
```

View traces at https://smith.langchain.com.

### Health Endpoint

```bash
# Basic health check
curl http://localhost:8000/health

# Watch with interval
watch -n 5 'curl -s http://localhost:8000/health | python3 -m json.tool'
```

---

## Backup & Recovery

### Database Backup

SQLite in WAL mode supports hot backup:

```bash
# Simple file copy (safe with WAL mode)
cp data/sop_agent.db data/sop_agent.db.backup
cp data/sop_agent.db-wal data/sop_agent.db-wal.backup 2>/dev/null
cp data/sop_agent.db-shm data/sop_agent.db-shm.backup 2>/dev/null

# Or use sqlite3 .backup command
sqlite3 data/sop_agent.db ".backup data/backup_$(date +%Y%m%d).db"
```

### ChromaDB Backup

```bash
# ChromaDB uses file-based persistence
tar czf chromadb_backup_$(date +%Y%m%d).tar.gz data/chromadb/
```

### Full Backup

```bash
tar czf sop_agent_backup_$(date +%Y%m%d).tar.gz \
  data/sop_agent.db* \
  data/chromadb/ \
  data/uploads/ \
  data/reports/ \
  .env
```

### Recovery

```bash
# Stop services
docker compose down  # or systemctl stop sop-agent-*

# Restore
tar xzf sop_agent_backup_20250115.tar.gz

# Restart
docker compose up -d  # or systemctl start sop-agent-*
```

---

## Scaling Considerations

### Current Limitations

- **SQLite**: Single-writer design. Not suitable for horizontal scaling.
- **ChromaDB**: File-based persistence. Single-instance only.
- **In-Memory State**: LangGraph checkpointer is in-memory by default.

### For Higher Scale

1. **Database**: Migrate to PostgreSQL with `asyncpg` for concurrent writes
2. **Vector Store**: Use hosted ChromaDB, Pinecone, or Qdrant for distributed vectors
3. **Checkpointer**: Use LangGraph's PostgreSQL checkpointer for durable state
4. **Workers**: With PostgreSQL, increase `--workers` for parallel request handling
5. **Queue**: Add Celery/Redis for background execution task management
6. **Load Balancer**: Nginx or Traefik in front of multiple backend instances

### Resource Estimation

| Documents | Chunks (est.) | ChromaDB Size | SQLite Size | RAM Usage |
|---|---|---|---|---|
| 10 | ~500 | ~50 MB | ~5 MB | 512 MB |
| 100 | ~5,000 | ~500 MB | ~50 MB | 1 GB |
| 1,000 | ~50,000 | ~5 GB | ~500 MB | 2 GB+ |
