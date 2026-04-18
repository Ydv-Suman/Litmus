<div align="center">

# Litmus

**Authentic AI-powered applicant tracking — verify what candidates claim, not just what they write.**

*Hawkathon 2026 · Theme: Tech for Career · Team: Bug Slayers*

---

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Redis](https://img.shields.io/badge/Redis-pub%2Fsub-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204-D97706?style=flat-square)](https://anthropic.com)

</div>

---

## The Problem

Traditional ATS systems filter candidates by keyword matching — they have no way to verify whether what a candidate writes is actually true. Resume inflation is widespread, and the current generation of ATS tools rewards well-formatted lies over genuine competence. At the same time, they penalize qualified candidates who lack polished online profiles, disproportionately affecting career changers, newer professionals, and underrepresented groups.

## What Litmus Does

Litmus is a multi-stage ATS that goes beyond keyword filtering. It:

1. **Parses** resumes into a structured, normalized schema
2. **Verifies** claimed skills and experience against public sources (GitHub, LinkedIn, portfolio sites)
3. **Assesses** unverifiable claims with an AI-generated micro-quiz tailored to the candidate's role
4. **Applies a fairness layer** — candidates without public portfolios are not penalized; the assessment is weighted higher instead
5. **Ranks** candidates with a transparent, explainable composite score that recruiters can audit

---

## Architecture

Litmus is built as a **microservices system** with seven independent Python services communicating over a **Redis pub/sub event bus**. Each service has a single responsibility and can be deployed, tested, and updated independently.

```
litmus/
├── services/
│   ├── gateway/          # API Gateway — FastAPI, JWT auth, routing
│   ├── ingestion/        # Resume parsing — PyMuPDF, python-docx, Claude
│   ├── job_match/        # Semantic fit scoring — Claude API
│   ├── verification/     # Portfolio verification — PyGithub, BeautifulSoup4, Claude
│   ├── assessment/       # Micro-quiz generation + grading — Claude API
│   ├── fairness/         # Weight adjustment for unverifiable candidates
│   └── scoring/          # Composite ranking + DB write — Supabase
├── frontend/             # React + Vite applicant portal + recruiter dashboard
├── shared/
│   └── schemas.py        # Pydantic models — single source of truth for all services
├── docker-compose.yml
└── .env.example
```

### Architecture Diagram

> The diagram below shows all seven services, the Redis event bus, and the Supabase read/write paths.

<!-- Architecture SVG — rendered on GitHub -->
<div align="center">

```
┌─────────────────┐                                    ┌─────────────────┐
│    Applicant    │                                    │    Recruiter    │
│  Resume + links │                                    │   Dashboard     │
└────────┬────────┘                                    └────────▲────────┘
         │                                                      │
         ▼                                                      │
┌─────────────────────────────────────────────────────────────────────────┐
│                          API Gateway                                    │
│                  Auth · Rate-limit · Routing · FastAPI                  │
└──────────┬───────────────────────┬────────────────────┬────────────────┘
           │                       │                    │
           ▼                       ▼                    ▼
  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
  │   Ingestion     │   │   Job Match     │   │  Dashboard Svc  │
  │ PyMuPDF · docx  │   │ Semantic fit    │   │ Ranked results  │
  │ → JSON schema   │   │ Claude API      │   │ + breakdown     │
  └────────┬────────┘   └────────┬────────┘   └────────▲────────┘
           │                     │                      │
           └──────────┬──────────┘                      │
                      ▼                                  │
  ════════════════════════════════════════════════════════════════════
         Redis pub/sub — async event bus (inter-service messaging)
  ════════════════════════════════════════════════════════════════════
       │              │              │              │
       ▼              ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │Verification│ │Assessment│  │ Scoring  │  │ Fairness │
  │PyGithub  │  │Claude gen│  │Composite │  │Reweight  │
  │BS4·Claude│  │+ grades  │  │rank      │  │if no     │
  │→ confidence│ │micro-quiz│  │formula   │  │portfolio │
  └──────────┘  └──────────┘  └────┬─────┘  └────┬─────┘
                                   │              │
                      ════════════════════════════════════
                           Results bus → write to DB
                      ════════════════════════════════════
                                        │
                                        ▼
                           ┌────────────────────────┐
                           │    Shared Database      │
                           │  Supabase (Postgres     │
                           │  + File Storage)        │
                           └────────────────────────┘
```

</div>

---

## Tech Stack

### Backend — all services

| Layer | Technology | Why |
|---|---|---|
| Service framework | **FastAPI** | Async-native, auto `/docs`, fastest Python API setup |
| Inter-service bus | **Redis pub/sub** | Async decoupling; Job Match + Verification run concurrently |
| Schema contract | **Pydantic** | Single `schemas.py` enforced across all services |
| Authentication | **PyJWT** | Stateless JWT for recruiter sessions — zero framework overhead |
| HTTP forwarding | **httpx** | Async-native; parallel Claude calls via `asyncio.gather()` |
| PDF parsing | **PyMuPDF (fitz)** | 3-line integration; handles 99% of PDF layouts |
| DOCX parsing | **python-docx** | Covers non-PDF resume uploads |
| GitHub verification | **PyGithub** | Free REST API wrapper; repos, languages, commits in 5 lines |
| Web scraping | **BeautifulSoup4 + requests** | LinkedIn + portfolio page scraping |
| AI — all services | **Claude Sonnet 4 (Anthropic)** | Resume normalization, fit scoring, question gen, grading, fairness notes |
| Database | **Supabase** | Hosted Postgres + REST API + file storage; instant setup, free tier |
| Containerization | **Docker + Docker Compose** | One command to run all 7 services locally |

### Frontend

| Layer | Technology | Why |
|---|---|---|
| Framework | **React 18 + Vite** | Fastest dev setup; hot reload |
| Styling | **Tailwind CSS** | Ship UI without writing stylesheets |
| Components | **shadcn/ui** | Pre-built tables, cards, badges, dialogs |
| Async state | **React Query** | Polling-based live dashboard (no WebSocket complexity) |
| HTTP client | **Axios** | Clean request/response handling |
| Icons | **Lucide React** | Consistent, lightweight icon set |

### Deployment

| Service | Platform | Why |
|---|---|---|
| Frontend | **Vercel** | Git push = deploy; free tier; zero config |
| All Python services + Redis | **Railway** | Per-service Dockerfile deploy; $5 trial credit |
| Local dev | **Docker Compose** | One `docker compose up` runs everything |

---

## Architectural Decisions

### Why microservices?

Each concern in Litmus is independently deployable and testable. The Verification Service can be updated — for example, adding Dribbble scraping for designers — without touching any other service. More importantly, the pipeline has genuine async characteristics: verifying a GitHub profile and scoring job fit are independent operations with variable latency. A monolith would serialize that latency; microservices let them run concurrently.

**Tradeoff acknowledged:** Microservices add coordination overhead and more complex local dev setup. We mitigated this with Docker Compose locally and Railway for deployment, and kept all services in Python to eliminate cross-language integration friction.

### Why Redis pub/sub over gRPC?

gRPC would give us strongly-typed protobuf contracts and faster serialization — real benefits in a production system at scale. We chose against it for two reasons:

First, gRPC is fundamentally synchronous RPC, which doesn't match our pipeline's shape. The core coordination problem is: "run Verification and Job Match in parallel, trigger Assessment and Scoring only when both complete." Redis pub/sub models this naturally — services publish results, the downstream subscriber waits for both. gRPC would require us to build that orchestration manually.

Second, the protobuf toolchain (`protoc`, plugin installation, codegen, stub management) carries a 2–4 hour setup cost that isn't justified in a 32-hour build window. We solve the schema contract problem instead with a single shared `schemas.py` of Pydantic models — same enforcement, zero extra tooling.

### Why Redis pub/sub over a monolithic request chain?

A chain of direct HTTP calls (gateway → ingestion → verification → assessment → scoring) creates tight coupling and serializes latency that should be parallel. Redis decouples the services: Ingestion publishes a `resume.parsed` event; both Verification and Job Match subscribe and run concurrently; Scoring subscribes to both result topics and fires only when both arrive. This is the correct model for a multi-step AI pipeline with variable latency.

**Fallback:** Every service also supports direct synchronous HTTP calls controlled by a `SYNC_MODE=true` environment variable. If Redis fails during development, one flag bypasses the bus entirely.

### Why Pydantic for schema contracts?

With seven services all reading and writing the same JSON structures, schema drift is a real risk — one service changes a field name and three others silently break. A single `shared/schemas.py` with Pydantic models gives us runtime validation at every service boundary, clear error messages when schemas mismatch, and a single file to update when the contract changes.

### Why the Fairness Service?

Verification-based scoring naturally disadvantages candidates without public online portfolios — disproportionately affecting older workers, career changers, and people from underrepresented backgrounds. The Fairness Service detects when verification confidence is low due to absent portfolio links (not due to flagged inconsistencies), downweights the verification score contribution, and upweights the assessment score. It also generates a plain-English note explaining the adjustment that surfaces in the recruiter dashboard. Equity is built into the architecture, not bolted on afterward.

### Why Supabase over raw Postgres?

Supabase provides a hosted Postgres instance, a REST API (PostgREST), file storage for uploaded resumes, and a browser dashboard for data inspection — all on the free tier, in about 10 minutes of setup. Standing up a raw Postgres server would cost an hour of configuration with no judging benefit.

---

## End-to-End Workflows

### Applicant flow

```
1.  Land on Litmus applicant portal
2.  Enter job ID (shared by recruiter) + basic contact info
3.  Upload resume (PDF or DOCX)
4.  Optionally paste GitHub, LinkedIn, or portfolio URLs
5.  Submit
         │
         ▼
6.  [Ingestion Service]
    PyMuPDF / python-docx extracts text
    Claude normalizes into structured JSON schema
    Event published: resume.parsed
         │
         ├──────────────────────────────┐
         ▼                              ▼
7.  [Job Match Service]          [Verification Service]
    Claude scores semantic        PyGithub checks repos,
    fit vs job description        languages, commit history
    → fit_score (0–100)           BS4 scrapes LinkedIn /
    → matched_skills[]            portfolio for consistency
    → missing_skills[]            Claude interprets evidence
    → seniority_match             → confidence per claim:
                                  verified / plausible /
                                  unverifiable / flagged
         │                              │
         └──────────────┬───────────────┘
                        ▼
8.  [Fairness Service] — runs in parallel
    Checks ratio of unverifiable claims
    If high: downweights verification score,
    upweights assessment score
    Generates plain-English fairness_note
                        │
                        ▼
9.  [Assessment Service]
    Identifies unverified / flagged claims
    Claude generates 5–8 targeted questions
    (role-agnostic: dev, nurse, designer, PM — all work)
    Questions calibrated to claimed seniority level
                        │
                        ▼
10. Applicant sees quiz in portal
    Timed (15-minute window)
    Free-text responses
                        │
                        ▼
11. [Assessment Service] — grading
    Claude grades each response 0–10
    Returns score + reasoning per question
                        │
                        ▼
12. [Scoring Service]
    Aggregates: fit_score · verification_score
              · assessment_score · fairness_weights
    Composite formula:
      (fit × 0.30) + (verification × 0.30)
      + (assessment × 0.30) + (consistency × 0.10)
    Writes final record to Supabase
                        │
                        ▼
13. Applicant sees: "Your application is complete."
```

---

### Recruiter flow

```
1.  Recruiter logs in (JWT session)
2.  Creates a Job Posting
    → Enters job title + full job description text
    → Receives shareable job link / ID
3.  Shares link with applicants (email, job board, etc.)

4.  As applications arrive, dashboard updates via polling
    (React Query refetches every 10 seconds)

5.  Candidate list shows per applicant:
    ┌─────────────────────────────────────────────────────┐
    │  Sarah Chen                          Score: 84/100  │
    │  ● Verified  ● Fit: 91%  ● Assessment: 78%          │
    │  [View full breakdown →]                            │
    ├─────────────────────────────────────────────────────┤
    │  James Okafor                        Score: 71/100  │
    │  ◐ Mostly verified  ● Fit: 76%  ● Assessment: 69%  │
    │  [View full breakdown →]                            │
    ├─────────────────────────────────────────────────────┤
    │  Maria Santos                        Score: 68/100  │
    │  ○ No portfolio — assessment weighted higher        │
    │  ● Fit: 72%  ● Assessment: 81%                     │
    │  [View full breakdown →]                            │
    └─────────────────────────────────────────────────────┘

6.  Recruiter clicks any candidate → full breakdown:
    • Which skills were verified and how (source shown)
    • Any flagged inconsistencies with explanation
    • Each quiz question + applicant's answer + Claude's
      grade (0–10) + Claude's reasoning
    • Fairness note if weights were adjusted

7.  Recruiter filters by:
    → Composite score range
    → Verification level (Verified / Partial / Low confidence)
    → Role fit threshold

8.  Recruiter advances or rejects candidates
    → Status visible to candidate in their portal
```

---

## Running Locally

### Prerequisites

- Docker + Docker Compose
- Node.js 20+
- An Anthropic API key
- A Supabase project (free tier)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/litmus.git
cd litmus
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY, JWT_SECRET
```

### 2. Start all services

```bash
docker compose up --build
```

This starts Redis, the API Gateway on `:8000`, and all six microservices on ports `8001–8006`.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Applicant portal: http://localhost:5173
# Recruiter dashboard: http://localhost:5173/recruiter
```

### 4. API docs

Each service exposes auto-generated Swagger docs:

| Service | URL |
|---|---|
| Gateway | http://localhost:8000/docs |
| Ingestion | http://localhost:8001/docs |
| Job Match | http://localhost:8002/docs |
| Verification | http://localhost:8003/docs |
| Assessment | http://localhost:8004/docs |
| Fairness | http://localhost:8005/docs |
| Scoring | http://localhost:8006/docs |

---

## Backend Install Reference

```bash
# All services (run inside each service directory or at root)
pip install fastapi uvicorn httpx python-multipart
pip install pyjwt bcrypt
pip install pymupdf python-docx
pip install PyGithub beautifulsoup4 requests
pip install redis
pip install supabase
pip install anthropic
pip install pydantic
```

```bash
# Frontend
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npm install @tanstack/react-query axios lucide-react
npx shadcn@latest init
npx shadcn@latest add card badge progress button table dialog input label textarea
```

---

## Shared Schema Contract

All services import from `shared/schemas.py`. This is the single source of truth for inter-service message shapes.

```python
# shared/schemas.py (abbreviated)
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class VerificationConfidence(str, Enum):
    VERIFIED = "verified"
    PLAUSIBLE = "plausible"
    UNVERIFIABLE = "unverifiable"
    FLAGGED = "flagged"

class Experience(BaseModel):
    title: str
    company: str
    years: float
    description: str

class ParsedResume(BaseModel):
    candidate_id: str
    name: str
    email: str
    skills: list[str]
    experience: list[Experience]
    education: list[dict]
    links: dict[str, Optional[str]]  # github, linkedin, portfolio
    claimed_seniority: str

class VerificationResult(BaseModel):
    candidate_id: str
    confidence_per_skill: dict[str, VerificationConfidence]
    overall_confidence: float  # 0.0–1.0
    flagged_inconsistencies: list[str]
    sources_checked: list[str]

class AssessmentResult(BaseModel):
    candidate_id: str
    questions: list[str]
    responses: list[str]
    scores: list[float]      # 0–10 per question
    reasoning: list[str]     # Claude's grade justification
    overall_score: float

class FairnessAdjustment(BaseModel):
    candidate_id: str
    adjusted: bool
    verification_weight: float
    assessment_weight: float
    fairness_note: Optional[str]

class CompositeScore(BaseModel):
    candidate_id: str
    fit_score: float
    verification_score: float
    assessment_score: float
    final_score: float
    fairness_note: Optional[str]
    rank: Optional[int]
```

---

## Environment Variables

```bash
# .env.example
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
JWT_SECRET=your-jwt-secret-min-32-chars
REDIS_URL=redis://localhost:6379
SYNC_MODE=false          # Set true to bypass Redis (direct HTTP fallback)

# Optional: GitHub token for higher rate limits (60 → 5000 req/hr)
GITHUB_TOKEN=ghp_...
```

---

## Known Limitations & Demo Notes

- **LinkedIn scraping** is done with BeautifulSoup4 + realistic request headers. LinkedIn has bot detection — for the live demo, responses for test candidates are pre-cached locally. Real scraping works in the background.
- **Assessment questions** are generated fresh per candidate by Claude. Expect 8–12 seconds for question generation.
- **Total pipeline latency** per candidate is 20–35 seconds due to multiple Claude API calls. Job Match and Verification run concurrently via `asyncio.gather()` to reduce this. A progress indicator in the applicant portal reflects each stage.
- **Supabase free tier** pauses after inactivity. For demo stability, keep a lightweight ping running or upgrade to the $25/month tier for the event weekend.

---

## Team

**Bug Slayers** — Hawkathon 2026

| Name | Role |
|---|---|
| Samarpan Koirala | — |

---

## License

MIT
