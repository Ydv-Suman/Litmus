# Litmus
An AI-powered hiring pipeline that takes candidates from raw PDF resume to a job-specific technical assessment in one flow. Recruiters get structured signal fast; candidates get a fair, role-aware bar instead of generic trivia.

---

## Inspiration
Hiring teams waste time on unqualified applicants, while strong candidates get lost in generic forms. We wanted a faster first filter: structured resume understanding, a clear bar to reach the next stage, and a job-specific technical assessment instead of one-size-fits-all trivia.

## Problem Statement
Traditional hiring pipelines rely on manual resume screening and generic assessments that fail both sides — recruiters waste hours on poor fits, and strong candidates get filtered out by keyword matching rather than actual skill alignment.

## Target Users
- **HR teams and recruiters** who want faster, fairer shortlisting without reading every PDF manually.
- **Candidates** who want their resume evaluated against the real requirements of a role.

---

## Why This Matters
Hiring is broken in both directions. Recruiters spend 80% of their time filtering rather than evaluating — most of that work is reading PDFs against a mental checklist. Candidates, meanwhile, invest hours in applications only to be rejected by keyword scanners that never understood their actual skills. Litmus shifts the bottleneck: AI handles the grunt work of parsing and scoring, so humans only engage at the stage where human judgment actually adds value. The assessment gate also raises the bar fairly — every candidate who advances faces the same role-specific challenge, not a generic quiz unrelated to the job.

## Key Features
- PDF resume upload with AI-powered structured extraction (skills, experience, projects).
- Automated resume–job fit scoring based on skill overlap and experience band.
- Optional GitHub and LinkedIn signal analysis as secondary scoring factors.
- Groq-generated technical assessments (MCQs + coding challenge) tailored to the role's stack and seniority.
- Token-gated assessment link delivered by email (SendGrid).
- JWT-authenticated HR dashboard with per-applicant scoring breakdown.

---

## What It Does
1. **Resume ingestion** — Applicant uploads a PDF. The backend extracts text, then Groq parses it into structured JSON (skills, experience, projects).
2. **Pipeline screening** — The parsed resume is scored against the actual job listing (skill overlap, experience band fit, optional GitHub/LinkedIn signals). A threshold gates advancement.
3. **Assessment generation** — Candidates above the threshold get a Groq-generated MCQ + coding challenge tailored to the role's stack and seniority. A unique token is issued and emailed via SendGrid.
4. **Assessment delivery** — The React frontend loads `/assessment/:token`, fetches questions from the API, and presents the timed assessment.
5. **HR dashboard** — HR users (JWT-authenticated) manage job listings, review scored applicants, and drill into individual candidate detail pages.

## Role of AI / Technology
- **Groq LLM** — drives two critical steps: resume parsing (PDF text → structured JSON) and assessment generation (role-aware MCQs + coding challenge from the job description).
- **Structured output validation** — JSON schemas and server-side validation keep the LLM output trustworthy in the critical path.
- **Scoring logic** — explicit, rule-based scoring (not a black box) so the pipeline score is interpretable and auditable.

---

## Challenges Faced
- **LLM + PDF reliability** — noisy PDF text, JSON validation failures, and model constraints; moving to the official Groq SDK and tighter validation resolved most issues.
- **Database migrations** — occasional Alembic revision drift between environments; fixing `alembic_version` and running migrations cleanly was necessary.
- **Email deliverability** — SendGrid 403 errors until sender verification and API permissions were correctly configured.
- **Scoring semantics** — separating resume–job fit, optional LinkedIn shape bonus, and GitHub analysis (informational vs. gating) so the pipeline stays understandable.

## Accomplishments
- An end-to-end flow: PDF → structured resume → job-aware scoring → gated assessment → shareable link.
- Assessments generated from the real job (stack + seniority), not generic LeetCode spam.
- Clear separation between "screening" and "assessment", with room to grow into grading and a final combined score.

## What We Learned
- Product clarity beats model cleverness — explicit scoring rules and thresholds are easier to trust than a black-box score.
- Infrastructure matters as much as features — migrations, secrets, and email setup are where demos quietly break.
- Structured outputs (JSON schemas + validation) are essential when LLMs are in the critical path.

---

## What's Next
- **Richer candidate signals** — analyze GitHub activity (code quality, consistency, relevant projects) and portfolios; add optional live coding or timed tests.
- **Scalability and reliability** — improve PDF parsing accuracy, validation robustness, and email delivery for production load.
- **Universal integrations** — plug into existing ATS platforms (like Canvas) so Litmus fits any hiring workflow without replacing it.

---

## Built With
FastAPI · Groq · PostgreSQL · SQLAlchemy · Alembic · AWS S3 · SendGrid · pypdf · React 19 · Vite · Tailwind CSS v4 · React Router v7
---
## Tech Stack
| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python 3.10) |
| Database | PostgreSQL + SQLAlchemy ORM |
| Migrations | Alembic |
| AI / LLM | Groq (resume parsing + assessment generation) |
| File storage | AWS S3 (resume PDFs) |
| Email | SendGrid |
| PDF parsing | pypdf |
| Frontend | React 19 + Vite + Tailwind CSS v4 |
| Routing | React Router v7 |

## Project Structure
```
Litmus/
├── backend/
│   ├── main.py                          # FastAPI app, CORS, router registration
│   ├── database.py                      # SQLAlchemy engine + session
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/                    # Migration history
│   ├── models/
│   │   ├── job_listing.py
│   │   ├── applications_received.py
│   │   └── hr_user.py
│   ├── routes/
│   │   ├── application_submission_service/application_submission_handler.py
│   │   ├── assessment_service/assessment_handler.py
│   │   ├── hr_auth_service/hr_auth_handler.py
│   │   └── job_listing_service/job_listing_handler.py
│   ├── service/
│   │   ├── resume_parser.py             # Groq-based PDF → structured JSON
│   │   ├── pipeline_screening.py        # Resume–job fit scoring
│   │   ├── resume_reality_match.py      # GitHub / LinkedIn signal analysis
│   │   ├── assessment_generator.py      # Groq-based MCQ + coding challenge
│   │   ├── email_notify.py              # SendGrid integration
│   │   ├── gmail_sender.py
│   │   └── linkedin_scraper.py
│   ├── s3_config/s3_helper.py           # S3 upload / presigned URL helpers
│   └── security/password_helper.py      # Bcrypt password hashing
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── src/
    │   ├── App.jsx                      # Route definitions
    │   ├── main.jsx
    │   ├── services/api.js              # Axios / fetch wrappers for backend calls
    │   ├── components/
    │   │   ├── Field.jsx
    │   │   ├── JobSelect.jsx
    │   │   └── PortalCard.jsx
    │   └── pages/
    │       ├── HomePage.jsx
    │       ├── ApplyPage.jsx            # Candidate application + resume upload
    │       ├── AssessmentPage.jsx       # Token-gated assessment UI
    │       ├── HrLoginPage.jsx
    │       ├── HrSignupPage.jsx
    │       ├── HrPage.jsx
    │       ├── HrDashboardPage.jsx      # Scored applicant list
    │       └── ApplicantDetailPage.jsx  # Full candidate breakdown
```

## Database Schema
| Table | Key Columns |
|---|---|
| `job_listings` | `id`, `title`, `description`, `required_skills`, `experience_band`, `owner_id` |
| `applications_received` | `id`, `job_id` (FK), `resume_s3_key`, `parsed_resume`, `pipeline_score`, `assessment_token`, `assessment_score`, `answers`, `analysis` |
| `hr_users` | `id`, `email`, `hashed_password`, `phone` |
## Security Rules
- Never hardcode secrets, API keys, access tokens, passwords, database URLs, or cloud credentials in source files, tests, commits, or examples.
- Load sensitive values only from environment variables or approved secret-management systems.
- Reject or sanitize all user-controlled input before using it in database queries, file paths, HTML rendering, or external service calls.
- Do not trust uploaded filenames, MIME types, or extensions alone for security-sensitive flows.
- Do not log secrets, authentication tokens, personal data, or raw resume contents.
- Any code that weakens authentication, authorization, input validation, file upload restrictions, or secret handling must be blocked until reviewed and fixed.

---

## Backend Setup
```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Create `backend/.env`:
```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB_NAME
GROQ_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET_NAME=...
SENDGRID_API_KEY=...
SENDGRID_FROM_EMAIL=...
SECRET_KEY=...
ALLOWED_ORIGINS=http://localhost:5173
```
Run the backend:
```bash
uvicorn main:app --reload
```
Health check:
```bash
curl http://localhost:8000/health
```
Deactivate when done:
```bash
deactivate
```
## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Create `frontend/.env`:
```env
VITE_API_BASE_URL=http://localhost:8000
```
Other commands:
```bash
npm run build      # production build → dist/
npm run preview    # serve the production build locally
npm run lint       # ESLint check
```
## Database Migrations (Alembic)
Always run from `backend/` with the virtual environment active.
```bash
cd backend
source .venv/bin/activate
```
| Task | Command |
|---|---|
| Apply all pending migrations | `alembic upgrade head` |
| Generate migration after model change | `alembic revision --autogenerate -m "describe change"` |
| Check current revision | `alembic current` |
| View full history | `alembic history` |
| Roll back one step | `alembic downgrade -1` |
### Migration History
| Revision | Description |
|---|---|
| `92e5c7a2baff` | Create `applications_received` and `job_listings` |
| `b2f6a1d9c4e7` | Add `hr_users` and job owner relation |
| `c3f7b2e1d5a8` | Add unique constraint on `hr_users.phone` |
| `d4e8f0a1b2c3` | Drop unique constraint on application contact fields |
| `e5a1b2c3d4e5` | Add pipeline screening and assessment fields |
| `f6b2c3d4e5a6` | Add assessment score fields |
| `g7c3d4e5f6a7` | Add analysis and answers fields |
## API Overview
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend liveness check |
| `POST` | `/apply` | Submit application + resume PDF |
| `GET` | `/assessment/{token}` | Fetch assessment by token |
| `POST` | `/assessment/{token}/submit` | Submit assessment answers |
| `POST` | `/hr/signup` | HR user registration |
| `POST` | `/hr/login` | HR user login (returns JWT) |
| `GET` | `/hr/applicants` | List all applicants (auth required) |
| `GET` | `/hr/applicants/{id}` | Applicant detail (auth required) |
| `GET` | `/jobs` | List job listings |
| `POST` | `/jobs` | Create job listing (auth required) |
