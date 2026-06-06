# ProposalPilot AI

Internal RFP Intelligence Platform powered by Multi-Agent AI.

## Quick Start

### Prerequisites
- Docker Desktop (for PostgreSQL, Redis, Qdrant)
- Python 3.11+
- Node.js 18+

### 1. Start Infrastructure

> **Important**: Make sure Docker Desktop is running first.

```powershell
# From project root
docker compose up -d
```

Verify services are healthy:
```powershell
docker compose ps
```

### 2. Backend Setup

```powershell
cd backend

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy env file (edit it with your LLM API key!)
Copy-Item ..\env.example .env   # or it's already copied at root level

# Run database migrations (your team can use this to sync)
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/api/docs

### 3. Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Frontend available at: http://localhost:5173

### 4. Start Celery Worker (for background tasks)

```powershell
cd backend
# Activate venv first
celery -A app.tasks.celery_app worker --loglevel=info -Q ingestion,war_room
```

---

## Team Setup (Syncing DB Changes)

When a teammate creates a new Alembic migration:
```powershell
cd backend
# Activate your venv
alembic upgrade head
```

To create a new migration after model changes:
```powershell
alembic revision --autogenerate -m "describe_your_change"
alembic upgrade head
```

---

## Architecture

```
proposalpilot/
├── frontend/        # React 18 + TypeScript + Vite
├── backend/         # FastAPI + LangGraph + Celery
│   ├── app/
│   │   ├── api/v1/  # Route handlers
│   │   ├── agents/  # LangGraph war room agents
│   │   ├── models/  # SQLAlchemy ORM
│   │   ├── schemas/ # Pydantic v2 schemas
│   │   ├── services/ # Business logic
│   │   └── tasks/   # Celery background tasks
│   └── alembic/     # DB migrations
└── docker-compose.yml  # PostgreSQL + Redis + Qdrant
```

## Environment Variables

Copy `.env.example` to `.env` in the project root and fill in:
- `APP_SECRET_KEY` — any long random string
- `JWT_SECRET_KEY` — any long random string  
- `DATABASE_URL` — auto-filled for local Docker setup
- `OPENAI_API_KEY` or `AZURE_OPENAI_*` — your LLM credentials

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| UI | shadcn/ui-inspired components + Custom CSS |
| State | TanStack Query v5 + Zustand |
| Backend | FastAPI (Python 3.11) |
| Agents | LangGraph |
| LLM | OpenAI GPT-4o / Azure OpenAI |
| Vector DB | Qdrant (hybrid search) |
| Database | PostgreSQL 16 |
| Task Queue | Celery + Redis |
| Migrations | Alembic |
