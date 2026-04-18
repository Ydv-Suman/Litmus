# Litmus

Litmus is split into a FastAPI backend in `backend/` and a Vite + React frontend in `frontend/`.

## Security Rules

These rules are mandatory for all backend and frontend changes:

- Never hardcode secrets, API keys, access tokens, passwords, database URLs, or cloud credentials in source files, tests, commits, or examples.
- Load sensitive values only from environment variables or approved secret-management systems.
- Reject or sanitize all user-controlled input before using it in database queries, file paths, HTML rendering, or external service calls.
- Do not trust uploaded filenames, MIME types, or extensions alone for security-sensitive flows.
- Do not log secrets, authentication tokens, personal data, or raw resume contents.
- Any code that weakens authentication, authorization, input validation, file upload restrictions, or secret handling must be blocked until reviewed and fixed.

## Project Structure

- `backend/main.py`: FastAPI app entrypoint
- `backend/models/`: SQLAlchemy models
- `backend/routes/`: API route handlers
- `backend/alembic/`: Alembic migration config and revision files
- `frontend/src/`: React app source

## Backend Setup

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify the Python version inside the virtual environment:

```bash
python --version
```

It should report Python `3.10.x`.

Create `backend/.env` with your database connection:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB_NAME
```

Run the backend:

```bash
uvicorn main:app --reload
```

Deactivate the backend virtual environment when done:

```bash
deactivate
```


## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Other useful commands:

```bash
npm run build
npm run lint
npm run preview
```

## Database Migrations With Alembic

Alembic is configured in `backend/alembic/` and reads `DATABASE_URL` from `backend/.env`.

Activate the backend virtual environment before running Alembic:

```bash
cd backend
source .venv/bin/activate
```

From `backend/`, generate a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe the schema change"
```

Apply all pending migrations:

```bash
alembic upgrade head
```

Check the current migration version:

```bash
alembic current
```

View migration history:

```bash
alembic history
```

Roll back one migration:

```bash
alembic downgrade -1
```

Current initial migration:

- `92e5c7a2baff_create_applications_received_and_job_.py`

## Current Tables

- `job_listings`
- `applications_received`

`applications_received.job_id` references `job_listings.id`.
