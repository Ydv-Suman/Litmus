# Litmus

Litmus is split into a FastAPI backend in `backend/` and a Vite + React frontend in `frontend/`.

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
