# ProposalPilot AI

ProposalPilot AI is an internal RFP intelligence and proposal strategy platform. It helps a delivery, sales, or consulting team turn an uploaded RFP into leadership-ready analysis, a multi-agent pursuit strategy, and a structured final proposal.

The product is built for demo reliability: source-grounded extraction, deterministic fallbacks, knowledge-base retrieval, executive call prep, architecture views, and a four-role AI War Room all work together in one end-to-end workflow.

## What It Does

ProposalPilot supports the full pursuit flow:

1. Upload an RFP or requirements document.
2. Extract source-grounded requirements, risks, gaps, domain tags, and complexity signals.
3. Generate a leadership-ready RFP analysis with:
   - Sentiment analysis
   - Must-ask clarification questions
   - Top delivery and commercial risks
   - VP-style talking points
   - Narrative strategy
   - Relevant internal knowledge evidence
   - Architecture detail and deployment/C4-style diagram data
4. Retrieve related past projects, architecture notes, and internal delivery evidence from the Knowledge Base.
5. Run an AI War Room with four specialist roles:
   - Solution Architect
   - CFO / Commercial Strategist
   - Competitor Analyst
   - Proposal Writer
6. Apply human guidance or call notes and regenerate the War Room strategy.
7. Generate a final structured proposal from the completed analysis and War Room outputs.

## Key Product Features

- RFP upload and async analysis recovery
- PDF, DOCX, TXT, and Markdown parsing
- Source-grounded RFP intelligence with deterministic fallback behavior
- Leadership-safe API response shaping that hides debug/noise fields
- Knowledge Base ingestion with metadata-rich hybrid retrieval
- Qdrant vector search plus PostgreSQL keyword fallback
- War Room multi-agent strategy synthesis with real-time WebSocket updates
- Human override loop for adding call notes, constraints, and stakeholder guidance
- Final proposal generation from analysis, War Room output, and relevant knowledge evidence
- Responsive React UI with dashboard, pipeline navigation, and proposal workspace
- Security-focused API headers and production-hidden API docs

## Demo Workflow

For a clean hackathon demo:

1. Start infrastructure with Docker.
2. Start the backend and frontend.
3. Open the Knowledge Base and ingest 2-5 relevant project examples.
4. Upload an RFP from **New RFP**.
5. Review **RFP Analysis**.
6. Open **War Room**, optionally add prospect-call notes, and run the agents.
7. Click **Build Proposal** and generate the final proposal.

If a knowledge-base item is newly added or re-added, it is immediately saved in PostgreSQL and indexed into Qdrant when vector services are available. If Qdrant or embeddings are unavailable during a demo, PostgreSQL keyword retrieval still provides a fallback.

## Architecture

```text
proposalpilot/
|-- frontend/                 React 19 + TypeScript + Vite
|   |-- src/
|   |   |-- pages/            Dashboard, New RFP, Analysis, War Room, Proposal, Knowledge Base
|   |   |-- api/              Axios API client and endpoint wrappers
|   |   |-- components/       App shell and shared UI
|   |   |-- hooks/            WebSocket and workflow hooks
|   |   `-- types/            Shared frontend types
|
|-- backend/                  FastAPI backend
|   |-- app/
|   |   |-- api/v1/           REST endpoints
|   |   |-- models/           SQLAlchemy models
|   |   |-- schemas/          Pydantic schemas
|   |   |-- services/         RFP, KB, LLM, proposal, vector services
|   |   |-- war_room/         LangGraph-style multi-agent orchestration
|   |   `-- tasks/            Celery app and ingestion tasks
|   `-- alembic/              Database migrations
|
|-- docker-compose.yml        PostgreSQL, Redis, Qdrant
|-- render.yaml               Backend deployment scaffold
|-- netlify.toml              Frontend deployment scaffold
`-- .env.example              Runtime configuration template
```

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite |
| UI | Custom CSS, lucide-react icons, TanStack Query |
| Backend | FastAPI, Pydantic v2, SQLAlchemy async |
| Database | PostgreSQL 16 |
| Vector DB | Qdrant hybrid retrieval |
| Task Queue | Celery + Redis for background ingestion tasks |
| AI Orchestration | LangChain, LangGraph-style War Room graph |
| LLM Providers | Groq by default; OpenAI, Azure OpenAI, Google, and Ollama supported |
| Document Parsing | PyMuPDF, python-docx |
| Migrations | Alembic |
| Testing | Pytest, pytest-asyncio, ESLint, Vite build |

## Prerequisites

- Docker Desktop
- Python 3.11 recommended
- Node.js 18+
- A Groq API key, or credentials for another configured LLM provider

## Environment Setup

Copy `.env.example` to `.env` in the project root:

```powershell
Copy-Item .env.example .env
```

Fill in the required values:

- `DATABASE_URL` - PostgreSQL connection string
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` - Redis URLs
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY` - Qdrant settings
- `LLM_PROVIDER` - `groq`, `openai`, `azure`, `google`, or `ollama`
- `GROQ_API_KEY` / `GROQ_API_KEYS` or the matching provider credential
- `LLM_MODEL` and `RFP_ANALYSIS_MODEL` - default to `openai/gpt-oss-120b`

The local `.env` file is intentionally ignored by git because it contains secrets.

## Start Infrastructure

From the repository root:

```powershell
docker compose up -d
docker compose ps
```

This starts:

- PostgreSQL on port `5432`
- Redis on port `6379`
- Qdrant on ports `6333` and `6334`

## Backend Setup

Create a virtual environment from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
cd backend
pip install -r requirements.txt
```

Run migrations:

```powershell
alembic upgrade head
```

Start the backend:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8124
```

Useful backend URLs:

- API health: `http://127.0.0.1:8124/api/v1/ping`
- API docs in development: `http://127.0.0.1:8124/api/docs`
- War Room WebSocket: `ws://127.0.0.1:8124/ws/war-room/{session_id}`

## Frontend Setup

In a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

`npm run dev` starts the backend automatically on port `8124` if it is not already healthy, then starts Vite.

Frontend URL:

```text
http://localhost:5173
```

If the backend is already running and you only want Vite:

```powershell
npm run dev:frontend
```

## Optional Celery Worker

Most user-facing RFP analysis and War Room flows run through the FastAPI service path. Celery remains available for background ingestion task support.

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
celery -A app.tasks.celery_app worker --loglevel=info -Q ingestion
```

## API Surface

Main REST endpoints:

| Area | Endpoint |
| --- | --- |
| Health | `GET /api/v1/ping` |
| RFP upload | `POST /api/v1/rfp/upload` |
| RFP list | `GET /api/v1/rfp` |
| RFP detail | `GET /api/v1/rfp/{session_id}` |
| Trigger analysis | `POST /api/v1/rfp/{session_id}/analyze` |
| Get analysis | `GET /api/v1/rfp/{session_id}/analysis` |
| Knowledge ingest | `POST /api/v1/knowledge/ingest` |
| Knowledge search | `GET /api/v1/knowledge/search` |
| Knowledge list | `GET /api/v1/knowledge/items` |
| Run War Room | `POST /api/v1/war-room/run` |
| War Room status | `GET /api/v1/war-room/{session_id}/status` |
| Human override | `POST /api/v1/war-room/override` |
| Generate proposal | `POST /api/v1/proposals/{session_id}/generate` |
| Latest proposal | `GET /api/v1/proposals/session/{session_id}/final` |

## Data and Retrieval Notes

Knowledge Base records use:

- Title
- Item type
- Domain
- Tech stack
- Tags
- Extra metadata
- Description
- Optional uploaded file text

Retrieval combines Qdrant vector search, BM25-style sparse retrieval, and PostgreSQL keyword fallback. RFP Analysis then reranks evidence to prefer real domain/capability overlap over generic terms like "data" or "integration".

If you change the metadata or searchable text model for existing knowledge items, delete and re-ingest those items so Qdrant receives fresh vectors.

## Quality and Safety

The application is designed for demo stability and responsible output:

- LLM extraction is source-grounded.
- Fallback analysis avoids hallucinating facts.
- Leadership responses hide raw debug payloads.
- Tender/admin boilerplate is filtered from public analysis.
- Knowledge evidence is only shown when retrieved matches pass relevance checks.
- API responses include security headers.
- Production mode disables FastAPI docs and OpenAPI routes.

## Verification

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests
```

Frontend lint:

```powershell
cd frontend
npm run lint
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Current release verification:

- Backend tests: `21 passed`
- Frontend lint: passing
- Frontend build: passing

## Deployment Notes

The repository includes:

- `render.yaml` for a Render backend service and PostgreSQL database scaffold
- `netlify.toml` for frontend static deployment

For production deployments:

- Set real `DATABASE_URL`, `QDRANT_*`, and LLM provider secrets in the hosting platform.
- Set `APP_ENV=production` and `APP_DEBUG=false`.
- Set `VITE_API_BASE_URL` to the deployed backend API base, for example `https://your-api.example.com/api/v1`.
- Set `VITE_WS_BASE_URL` to the deployed backend WebSocket host, for example `wss://your-api.example.com`.
- Do not commit `.env`.

## Hackathon Demo Checklist

- Docker services are healthy.
- Backend health endpoint returns OK.
- Frontend loads at `localhost:5173`.
- At least one relevant Knowledge Base project is ingested.
- RFP upload reaches the analysis page.
- RFP Analysis shows specific questions, risks, talking points, and architecture.
- War Room produces Architect, CFO, Competitor, and Proposal Writer outputs.
- Final Proposal generates from a completed War Room.

