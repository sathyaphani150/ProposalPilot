# ProposalPilot AI — Hackathon Master Plan
> **12-Day Execution Blueprint | Source of Truth**
> Current Date: June 6, 2026 | Deadline: ~June 18, 2026

---

## Problem Statement Summary

**ProposalPilot AI** is an internal RFP intelligence platform that:
1. Reads client requirements (RFPs, emails, briefs)
2. Searches the company's internal knowledge base (past projects, repos, docs)
3. Prepares a **Prospect Call Prep Pack** (before the call)
4. Runs a **Multi-Agent War Room** (Architect + CFO + Competitor + Proposal Writer)
5. Generates a **Final Proposal Package** (after the call, including cost estimates, architecture, delivery plan)

---

## Proposed Changes

### System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROPOSALPILOT AI                            │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   React +    │    │   FastAPI    │    │   LangGraph      │  │
│  │  TypeScript  │◄──►│   Backend   │◄──►│   War Room       │  │
│  │  + shadcn/ui │    │   (Async)   │    │   Orchestrator   │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                             │                      │            │
│                    ┌────────┴──────┐    ┌──────────┴────────┐  │
│                    │  PostgreSQL   │    │  Qdrant Vector DB │  │
│                    │  (Sessions,  │    │  (RAG Embeddings) │  │
│                    │   Proposals) │    │                   │  │
│                    └───────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Full Technical Architecture (Layer by Layer)

```
CLIENT LAYER
  React 18 + TypeScript + Vite
  shadcn/ui + Tailwind CSS
  React Query (TanStack Query v5)
  Zustand (lightweight state)
  WebSockets (real-time agent streaming)
  React PDF Viewer (proposal preview)

API GATEWAY LAYER
  FastAPI (Python 3.11+)
  Pydantic v2 (request/response validation)
  JWT Auth (python-jose)
  WebSocket endpoints (agent streaming)
  Background Tasks (Celery + Redis)
  CORS, Rate limiting (slowapi)

DOCUMENT PROCESSING LAYER
  PyMuPDF (PDF parsing)
  python-docx (DOCX parsing)
  Unstructured.io (fallback multi-format)
  Semantic chunking (LangChain TextSplitter)

EMBEDDING & VECTOR LAYER
  Embedding: text-embedding-3-small (OpenAI) 
             OR nomic-embed-text (local/Ollama)
  Vector Store: Qdrant (Docker, persistent)
  Hybrid Search: Dense + BM25 + RRF reranking
  Collections: rfp_docs, internal_kb, proposals

RAG & RETRIEVAL LAYER
  LangChain retrieval chains
  Cohere Rerank (or cross-encoder reranker)
  Metadata filtering (project_type, domain, year)
  Confidence scoring

AGENT ORCHESTRATION LAYER
  LangGraph (stateful graph execution)
  Supervisor pattern (War Room Coordinator)
  4 Specialized Agents:
    - Tech Architect Agent
    - CFO / Pricing Agent
    - Competitor Strategist Agent  
    - Proposal Writer Agent
  Human-in-the-loop interrupts
  LangSmith tracing (observability)

LLM LAYER
  Primary: Azure OpenAI GPT-4o
  Fallback: OpenAI GPT-4o
  Structured output: JSON mode / function calling
  Streaming: Server-Sent Events

OUTPUT GENERATION LAYER
  python-docx (DOCX export)
  ReportLab / WeasyPrint (PDF export)
  Jinja2 templates (proposal formatting)

STORAGE LAYER
  PostgreSQL 16 (via SQLAlchemy async + Alembic)
  Redis (Celery broker + session cache)
  MinIO / Local File Storage (uploaded docs)
```

---

## Tech Stack (Final Decision)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | React 18 + TypeScript + Vite | Fast HMR, type safety, ecosystem |
| **UI Components** | shadcn/ui + Tailwind CSS | Production-quality components |
| **State** | TanStack Query + Zustand | Server state + client state |
| **Backend** | FastAPI (Python 3.11) | Async-native, Pydantic, WebSocket |
| **Auth** | JWT + python-jose | Simple, stateless |
| **Agent Framework** | LangGraph | Stateful graphs, human-in-loop |
| **LLM** | OpenAI GPT-4o / Azure OpenAI | Best instruction following |
| **Embeddings** | text-embedding-3-small | Best cost/performance |
| **Vector DB** | Qdrant (Docker) | Hybrid search, filtering, fast |
| **Relational DB** | PostgreSQL 16 | Reliability, JSON support |
| **Task Queue** | Celery + Redis | Async doc ingestion |
| **File Parsing** | PyMuPDF + python-docx | Robust extraction |
| **Reranking** | Cross-encoder (local) | Improves RAG precision |
| **Export** | python-docx + WeasyPrint | DOCX + PDF output |
| **Observability** | LangSmith | Agent trace debugging |
| **Containerization** | Docker Compose | Dev environment parity |

---

## Project Folder Structure

```
proposalpilot/
├── frontend/                          # React + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── layout/               # Sidebar, Navbar, Shell
│   │   │   ├── rfp/                  # RFP upload, viewer, analysis
│   │   │   ├── knowledge-base/       # KB browser, upload UI
│   │   │   ├── war-room/             # Agent chat, real-time stream
│   │   │   ├── proposal/             # Proposal editor, preview
│   │   │   └── shared/               # Cards, Badges, Modals
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── NewRFP.tsx
│   │   │   ├── RFPAnalysis.tsx
│   │   │   ├── PrepPack.tsx
│   │   │   ├── WarRoom.tsx
│   │   │   ├── ProposalEditor.tsx
│   │   │   └── KnowledgeBase.tsx
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── stores/                   # Zustand stores
│   │   ├── api/                      # API client (axios + react-query)
│   │   ├── types/                    # TypeScript types
│   │   └── lib/                      # Utils, constants
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                           # FastAPI
│   ├── app/
│   │   ├── main.py                   # FastAPI app entry
│   │   ├── config.py                 # Settings (pydantic-settings)
│   │   ├── database.py               # SQLAlchemy async engine
│   │   ├── deps.py                   # Dependency injection
│   │   │
│   │   ├── api/                      # Route handlers
│   │   │   ├── v1/
│   │   │   │   ├── rfp.py            # RFP upload & analysis endpoints
│   │   │   │   ├── knowledge.py      # KB ingestion & search
│   │   │   │   ├── sessions.py       # Session management
│   │   │   │   ├── war_room.py       # Agent orchestration endpoints
│   │   │   │   ├── proposals.py      # Proposal CRUD + export
│   │   │   │   └── ws.py             # WebSocket endpoints
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── rfp.py
│   │   │   ├── session.py
│   │   │   ├── proposal.py
│   │   │   └── knowledge_item.py
│   │   │
│   │   ├── schemas/                  # Pydantic schemas
│   │   │   ├── rfp.py
│   │   │   ├── session.py
│   │   │   └── proposal.py
│   │   │
│   │   ├── services/                 # Business logic
│   │   │   ├── document_parser.py    # PDF/DOCX → text
│   │   │   ├── rfp_engine.py         # RFP structured extraction
│   │   │   ├── embedding_service.py  # Embed + store in Qdrant
│   │   │   ├── rag_service.py        # Hybrid retrieval
│   │   │   ├── matcher_service.py    # Past project matching
│   │   │   └── export_service.py     # DOCX/PDF generation
│   │   │
│   │   ├── agents/                   # LangGraph agents
│   │   │   ├── state.py              # AgentState TypedDict
│   │   │   ├── graph.py              # Main War Room graph
│   │   │   ├── supervisor.py         # Coordinator node
│   │   │   ├── architect_agent.py    # Tech Architect
│   │   │   ├── cfo_agent.py          # CFO / Pricing
│   │   │   ├── competitor_agent.py   # Competitor Strategist
│   │   │   ├── proposal_agent.py     # Proposal Writer
│   │   │   └── tools/                # Agent tools
│   │   │       ├── rag_tool.py
│   │   │       ├── cost_calculator.py
│   │   │       └── template_filler.py
│   │   │
│   │   └── tasks/                    # Celery background tasks
│   │       ├── celery_app.py
│   │       ├── ingestion_tasks.py    # Async doc ingestion
│   │       └── war_room_tasks.py     # Async agent runs
│   │
│   ├── alembic/                      # DB migrations
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml                 # PostgreSQL + Redis + Qdrant
├── .env.example
└── README.md
```

---

## Database Schema

### PostgreSQL Tables

```sql
-- RFP Sessions
CREATE TABLE rfp_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500),
    client_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'uploaded', 
    -- uploaded | analyzed | prep_generated | war_room | proposal_ready
    original_file_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RFP Analysis Results
CREATE TABLE rfp_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES rfp_sessions(id),
    business_problem TEXT,
    functional_requirements JSONB,   -- array of strings
    non_functional_requirements JSONB,
    data_needs JSONB,
    integration_needs JSONB,
    compliance_needs JSONB,
    timeline_risks JSONB,
    missing_info JSONB,
    scope_boundaries JSONB,
    raw_llm_output JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Base Items
CREATE TABLE knowledge_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type VARCHAR(50), -- project | repo | doc | proposal | case_study
    title VARCHAR(500),
    description TEXT,
    domain VARCHAR(255),
    tech_stack JSONB,
    file_path TEXT,
    qdrant_collection VARCHAR(100) DEFAULT 'internal_kb',
    qdrant_point_ids JSONB,   -- list of vector IDs
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- War Room Sessions
CREATE TABLE war_room_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfp_session_id UUID REFERENCES rfp_sessions(id),
    status VARCHAR(50) DEFAULT 'idle', -- idle | running | paused | complete
    human_overrides JSONB DEFAULT '{}',
    call_notes TEXT,
    agent_outputs JSONB DEFAULT '{}',  -- keyed by agent name
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Proposals
CREATE TABLE proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfp_session_id UUID REFERENCES rfp_sessions(id),
    war_room_session_id UUID REFERENCES war_room_sessions(id),
    proposal_type VARCHAR(50), -- prep_pack | final_proposal
    content JSONB,             -- structured proposal sections
    docx_path TEXT,
    pdf_path TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## API Design (Key Endpoints)

### RFP Module
```
POST   /api/v1/rfp/upload          → Upload RFP file → returns session_id
GET    /api/v1/rfp/{session_id}    → Get session details
POST   /api/v1/rfp/{session_id}/analyze  → Trigger RFP analysis (async)
GET    /api/v1/rfp/{session_id}/analysis → Get structured analysis result
```

### Knowledge Base
```
POST   /api/v1/knowledge/ingest    → Upload KB doc (PDF/DOCX/README)
GET    /api/v1/knowledge/search    → Hybrid search (q=, filters)
GET    /api/v1/knowledge/items     → List all KB items
DELETE /api/v1/knowledge/{id}      → Remove from KB + Qdrant
```

### Prep Pack
```
POST   /api/v1/sessions/{id}/prep-pack/generate  → Generate prep pack
GET    /api/v1/sessions/{id}/prep-pack           → Get prep pack
POST   /api/v1/sessions/{id}/call-notes          → Save call notes
```

### War Room
```
POST   /api/v1/war-room/{session_id}/start       → Launch agents
POST   /api/v1/war-room/{session_id}/override    → Human intervention
GET    /api/v1/war-room/{session_id}/status      → Poll current state
WS     /ws/war-room/{session_id}                 → Real-time agent stream
```

### Proposals
```
POST   /api/v1/proposals/{session_id}/generate   → Generate final proposal
GET    /api/v1/proposals/{id}                    → Get proposal content
POST   /api/v1/proposals/{id}/export             → Export DOCX or PDF
GET    /api/v1/proposals/{id}/download/{format}  → Download file
```

---

## LangGraph War Room — Agent Design

```python
# AgentState — shared across all nodes
class WarRoomState(TypedDict):
    rfp_analysis: RFPAnalysis
    retrieved_projects: List[KnowledgeMatch]
    call_notes: str
    human_overrides: HumanOverrides
    
    # Agent outputs
    architect_output: ArchitectOutput      # solution, stack, architecture
    cfo_output: CFOOutput                  # cost, margin, rates
    competitor_output: CompetitorOutput    # win strategy, differentiators
    proposal_draft: str                    # draft proposal text
    
    # Control flow
    messages: Annotated[List[BaseMessage], add_messages]
    next_agent: str
    iteration: int
    is_complete: bool
```

### Graph Flow
```
START
  └── supervisor_node (routes based on state)
        ├── architect_node  (solution design + stack)
        ├── cfo_node        (costing + margins)
        ├── competitor_node (win strategy)
        └── proposal_node   (writes final proposal)
              └── HUMAN_INTERRUPT (user can override)
              └── supervisor_node (re-routes if override)
  └── END
```

### Key Agent Prompts Strategy
- **Architect Agent**: Given RFP analysis + similar past projects → output: solution design, recommended stack, architecture diagram (mermaid), reusable components, assumptions
- **CFO Agent**: Given scope from architect → output: resource matrix (roles × hours), rate card, total estimate, margin analysis, risk-adjusted ranges
- **Competitor Agent**: Given client domain + RFP → output: competitor landscape, our differentiators, win themes, risk flags
- **Proposal Agent**: Given all above outputs → synthesize into complete proposal with all sections, compliance matrix, executive summary

---

## Phase-Wise Execution Plan

### Phase 1: Foundation & Infrastructure (Days 1–2)
**Goal**: Working skeleton with DB, vector store, file upload

#### Day 1 Tasks
- [ ] Create monorepo folder structure (`proposalpilot/`)
- [ ] Set up `docker-compose.yml` (PostgreSQL 16 + Redis + Qdrant)
- [ ] Backend: FastAPI app skeleton, config, CORS, health check
- [ ] Backend: SQLAlchemy async engine + Alembic setup
- [ ] Backend: Run all DB migrations (all 5 tables)
- [ ] Backend: Document parser service (PDF + DOCX → text)
- [ ] Frontend: Vite + React + TypeScript init
- [ ] Frontend: shadcn/ui + Tailwind setup
- [ ] Frontend: Layout shell (sidebar + header + main)
- [ ] Frontend: Dashboard page (empty state)

#### Day 2 Tasks
- [ ] Backend: Qdrant collections creation on startup
- [ ] Backend: Embedding service (OpenAI embeddings)
- [ ] Backend: `/api/v1/rfp/upload` endpoint (multipart form)
- [ ] Backend: File storage service (save to disk/MinIO)
- [ ] Frontend: RFP upload component (drag-drop UI)
- [ ] Frontend: API client setup (axios + React Query)
- [ ] Frontend: Upload flow → session creation → redirect
- [ ] **Integration test**: Upload PDF → file saved → session in DB

---

### Phase 2: RFP Engine + Knowledge Base (Days 3–4)
**Goal**: RFP analysis works end-to-end + KB ingestion pipeline

#### Day 3 Tasks
- [ ] Backend: RFP Understanding Engine
  - Structured extraction prompt (business problem, requirements, risks)
  - JSON-mode output parsing with Pydantic
  - Store in `rfp_analyses` table
- [ ] Backend: `/api/v1/rfp/{id}/analyze` endpoint (async via Celery)
- [ ] Frontend: RFP Analysis page
  - Shows extracted: problem, requirements, risks, missing info
  - Section cards with color coding
  - Status polling until analysis complete

#### Day 4 Tasks
- [ ] Backend: Knowledge Base ingestion pipeline
  - Parse → chunk (semantic chunking) → embed → store in Qdrant
  - Metadata storage in PostgreSQL `knowledge_items`
- [ ] Backend: Hybrid search (dense + BM25 + RRF reranking)
- [ ] Backend: `/api/v1/knowledge/*` endpoints
- [ ] Frontend: Knowledge Base page
  - Upload KB documents UI
  - Browse existing knowledge items
  - Search interface
- [ ] **Integration test**: Ingest 3 sample past projects → search for them

---

### Phase 3: Past Expertise Matcher + Prep Pack (Days 5–6)
**Goal**: Match past projects to RFP and generate Prospect Call Prep Pack

#### Day 5 Tasks
- [ ] Backend: Past Expertise Matcher service
  - Query Qdrant with RFP vectors
  - Classify match type: Exact / Partial / Adjacent / None
  - Return confidence scores + matched items
- [ ] Backend: Architecture Recommender
  - If match: suggest architecture from past project
  - If no match: generate potential architecture with assumptions
- [ ] Backend: Prep Pack Generator
  - Past expertise story
  - Prospect call narrative
  - Discovery questions (business, data, integration, architecture)
  - Risk areas + scope guardrails
  - Proposed architecture direction

#### Day 6 Tasks
- [ ] Backend: `/api/v1/sessions/{id}/prep-pack/*` endpoints
- [ ] Frontend: Prep Pack page
  - Beautiful, print-ready layout
  - Sections: Summary | Past Projects | Call Narrative | Discovery Questions | Risks
  - Copy-to-clipboard per section
  - Export as PDF button
- [ ] Frontend: Call notes input component
- [ ] **Integration test**: Full flow → RFP → Analysis → Prep Pack

---

### Phase 4: Multi-Agent War Room (Days 7–9)
**Goal**: Working multi-agent LangGraph orchestration with real-time streaming

#### Day 7 Tasks
- [ ] Backend: LangGraph agent graph scaffold
  - `WarRoomState` TypedDict
  - Supervisor node (routing logic)
  - Graph compilation + checkpointing
- [ ] Backend: Tech Architect Agent
  - Tools: RAG search, architecture template filler
  - Output: solution design, stack, mermaid diagram, reusable components
- [ ] Backend: CFO Agent
  - Tools: cost calculator (hours × rates), risk adjuster
  - Output: resource matrix, total estimate, ranges
- [ ] WebSocket endpoint `/ws/war-room/{session_id}`
  - Stream agent thoughts + intermediate outputs
  - Send structured events: `{agent, type, content}`

#### Day 8 Tasks
- [ ] Backend: Competitor Strategist Agent
  - Tools: RAG search for competitor mentions, domain analysis
  - Output: competitor landscape, differentiators, win themes
- [ ] Backend: Proposal Writer Agent
  - Tools: template filler, section generator
  - Synthesizes ALL agent outputs
  - Produces structured JSON proposal with all sections
- [ ] Backend: Human-in-the-loop interrupt
  - Pause graph at defined breakpoints
  - Accept override instructions → reinject into state
  - Resume graph execution
- [ ] `/api/v1/war-room/*` endpoints (start, status, override)

#### Day 9 Tasks
- [ ] Frontend: War Room page
  - Real-time agent activity feed (WebSocket)
  - Agent cards: Architect | CFO | Competitor | Proposal Writer
  - Live status indicators (thinking / writing / done)
  - Human override panel (dropdown: model type, scope, regenerate)
  - Agent output preview panels (expandable)
- [ ] Frontend: WebSocket hook (`useWarRoom`)
- [ ] **Integration test**: Full war room run → 4 agents complete → outputs generated

---

### Phase 5: Proposal Generation + Export (Days 10–11)
**Goal**: Final Proposal Package with all sections + DOCX/PDF export

#### Day 10 Tasks
- [ ] Backend: Proposal Package generator
  - All 13 sections from spec:
    1. Executive Summary
    2. Client Problem Statement
    3. Proposed Solution
    4. Relevant Past Experience
    5. Technical Architecture
    6. Technology Stack
    7. Delivery Approach
    8. Resource Matrix
    9. Cost Estimation
    10. Competitive Positioning
    11. Compliance Matrix
    12. Assumptions & Exclusions
    13. Risks & Mitigation
- [ ] Backend: DOCX export (python-docx with branded template)
- [ ] Backend: PDF export (WeasyPrint / HTML-to-PDF)
- [ ] `/api/v1/proposals/*` endpoints (generate, get, export, download)

#### Day 11 Tasks
- [ ] Frontend: Proposal Editor page
  - All sections rendered in editable rich text (TipTap or Quill)
  - Section-by-section navigation
  - Inline edit + save
  - Version history indicator
- [ ] Frontend: Export modal (DOCX / PDF download)
- [ ] Frontend: Proposal preview (print-ready)
- [ ] **Integration test**: End-to-end full flow (RFP → Analysis → Prep → War Room → Proposal → Export)

---

### Phase 6: Polish, Demo Prep & Hardening (Day 12)
**Goal**: Demo-ready, stable, visually impressive

#### Day 12 Tasks
- [ ] Frontend: Dashboard — list all sessions with status pipeline
- [ ] Frontend: Animations + loading states for all async operations
- [ ] Frontend: Error handling + toasts
- [ ] Backend: Error handling + proper HTTP status codes
- [ ] Seed sample data: 5 past projects in KB, 1 sample RFP
- [ ] Demo script: Prepare realistic RFP + run full flow
- [ ] Docker Compose: one-command startup for judges
- [ ] README: Setup + architecture + screenshots
- [ ] Final QA pass

---

## UI/UX Design Vision

### Design Principles
- **Dark mode first** — professional internal tool aesthetic
- **Purple/indigo primary** — tech-forward, trustworthy
- **Card-based layout** — clear information hierarchy
- **Streaming animations** — show agents "thinking" in real time
- **Timeline/pipeline view** — visual progress through the workflow

### Key UI States Per Page

**Dashboard**: Session pipeline cards, status badges (Uploaded → Analyzed → Prep Ready → War Room → Proposal Ready), quick-create button

**RFP Analysis**: Split view — raw RFP preview (left) + structured extraction (right). Color-coded requirement types. Animated progress while analyzing.

**Prep Pack**: Print-quality layout. Section accordion. Highlighted discovery questions. Export-ready design.

**War Room**: The showpiece UI. Four agent cards arranged in a 2×2 grid. Real-time streaming text in each card. Timeline of agent handoffs. Human override drawer sliding from right.

**Proposal Editor**: Three-panel layout: section navigation (left) | editor (center) | preview (right). Progress indicator showing complete/incomplete sections.

---

## Key Technical Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM API rate limits | High | Implement retry with exponential backoff; cache results |
| Long RFP processing time | High | Celery async processing + WebSocket progress updates |
| War Room agents diverge | Medium | Supervisor validates each output before passing forward |
| Large file parsing failures | Medium | Use Unstructured.io as fallback; max file size = 20MB |
| Qdrant cold start on demo | Medium | Pre-warm collections + seed 5 real past projects |
| DOCX export formatting | Low | Use python-docx styles from a branded template.docx |
| Proposal quality inconsistency | Medium | Use GPT-4o with strict JSON schema output + validation |

---

## Day-by-Day Timeline Summary

| Day | Date | Focus | Deliverable |
|-----|------|--------|-------------|
| 1 | Jun 6 | Infrastructure + skeleton | Docker up, DB migrated, layout shell |
| 2 | Jun 7 | File upload + storage | RFP upload works end-to-end |
| 3 | Jun 8 | RFP Analysis Engine | Structured extraction from RFP |
| 4 | Jun 9 | Knowledge Base + RAG | KB ingestion + hybrid search |
| 5 | Jun 10 | Expertise Matcher | Match past projects to RFP |
| 6 | Jun 11 | Prep Pack Generator | Full Prep Pack with discovery questions |
| 7 | Jun 12 | War Room scaffold + Architect | First agent running + streaming |
| 8 | Jun 13 | CFO + Competitor + Proposal agents | All 4 agents working |
| 9 | Jun 14 | Human override + War Room UI | Interactive war room page |
| 10 | Jun 15 | Proposal generator + export | DOCX + PDF export working |
| 11 | Jun 16 | Proposal editor UI + full E2E | Complete user journey |
| 12 | Jun 17-18 | Polish + demo prep | Seed data, demo script, README |

---

## Open Questions

> [!IMPORTANT]
> **Q1: LLM Provider** — Do you have access to Azure OpenAI, OpenAI API, or Gemini API keys? This determines which LLM layer we use. Plan defaults to OpenAI GPT-4o.

> [!IMPORTANT]
> **Q2: Team Size** — Are you solo or with a team? This affects how we split work (frontend-focused vs backend-focused days).

> [!IMPORTANT]
> **Q3: Sample Data** — Do you have real past project documents (PDFs, READMEs, proposals) to seed the Knowledge Base? Or should we generate realistic synthetic data?

> [!WARNING]
> **Q4: Hackathon Judges** — Is the judging criteria: live demo, code quality, innovation, or all three? This affects how much we prioritize polish vs depth of implementation.

> [!NOTE]
> **Q5: Hosting** — Will the demo run locally, or do judges expect a live URL? If live: we'll need to add a brief deployment step to the plan.

---

## Verification Plan

### Automated Tests
- `pytest` for backend service unit tests (parser, embedding, RFP engine)
- `pytest-asyncio` for async endpoint tests
- React Testing Library for frontend component tests

### Manual Verification (E2E Demo Flow)
1. Upload a real RFP PDF → verify structured extraction is accurate
2. Ingest 3-5 past project documents → verify they appear in KB search
3. Generate Prep Pack → verify all sections are present and coherent
4. Add call notes → verify they influence war room outputs
5. Run War Room → verify all 4 agents produce output + streaming works
6. Apply human override (e.g., "reduce to MVP scope") → verify agents recalculate
7. Generate Final Proposal → verify all 13 sections present
8. Export as DOCX and PDF → verify downloads work and formatting is clean
