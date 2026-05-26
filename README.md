# U.S. Patent Intelligence Platform

React + Flask platform for browsing recent U.S. patent publications/grants and generating AI summaries **only when a user requests one**.

## Key Behavior
- Ingestion stores metadata and source text sections.
- No background mass summarization.
- AI summary generation is on-demand from the patent detail page.
- Summaries are cached by publication/model/prompt/source hash to conserve tokens.

## Monorepo Layout
- `backend/`: Flask API, ingestion pipeline, summary worker, DB models.
- `frontend/`: React SPA (Vite).
- `scripts/`: web/worker startup scripts used in Docker and Railway.
- `PATENT_INGESTION_PLAN.md`: full architecture and feasibility plan.

## Backend API
- `GET /api/health`
- `GET /api/patents`
- `GET /api/patents/{publication_number}`
- `POST /api/patents/{publication_number}/summaries`
- `GET /api/summaries/{job_id}`
- `POST /api/admin/ingest/incremental` (admin token required)
- `POST /api/admin/ingest/backfill` (admin token required)

## Environment Variables
Copy `.env.example` and configure these at minimum:
- `DATABASE_URL`
- `REDIS_URL`
- `USPTO_API_KEY`
- `OPENAI_API_KEY`
- `ADMIN_API_TOKEN`

Optional but useful:
- `USE_SAMPLE_DATA_ON_FAILURE=true` (dev fallback)
- `OPENAI_SUMMARY_MODEL=gpt-4.1-mini`
- `SUMMARY_MAX_OUTPUT_TOKENS=1400`

## Local Development

### Option A: Docker Compose (recommended)
```bash
docker compose up --build
```

App will be available at `http://localhost:8000`.

### Option B: Run web + worker manually
Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m flask --app wsgi:app init-db
python run.py
```

Worker (separate terminal):
```bash
cd backend
python worker.py
```

Frontend dev server (optional if not using Docker):
```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` to your backend API base when running separately.

## First-Time Data Ingestion
Trigger incremental ingest (example: last 30 days, up to 500 records):
```bash
curl -X POST http://localhost:8000/api/admin/ingest/incremental \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: change-me" \
  -d '{"days": 30, "limit": 500}'
```

If USPTO API is unavailable and `USE_SAMPLE_DATA_ON_FAILURE=true`, the app loads bundled sample patents.

## Railway Deployment (Production)

### 1. Create Infrastructure
Create these Railway resources:
- PostgreSQL service
- Redis service
- Web service (this repo)
- Worker service (same repo)

### 2. Web Service Settings
- Build: Dockerfile (root `Dockerfile`)
- Start command: `sh /app/scripts/start-web.sh`
- Optional config-as-code file: `railway.json`

### 3. Worker Service Settings
- Build: Dockerfile (root `Dockerfile`)
- Start command: `sh /app/scripts/start-worker.sh`
- Optional config-as-code file: `railway.worker.json`

### 4. Required Environment Variables (both web + worker)
- `DATABASE_URL` (Railway Postgres URL)
- `REDIS_URL` (Railway Redis URL)
- `USPTO_API_BASE=https://api.uspto.gov/api/v1`
- `USPTO_API_KEY=<your_uspto_key>`
- `OPENAI_API_KEY=<your_openai_key>`
- `ADMIN_API_TOKEN=<strong_secret>`
- `RQ_ASYNC=true`
- `APP_DEBUG=false`
- `USE_SAMPLE_DATA_ON_FAILURE=false` (recommended for production)

### 5. Initialize Data
After first deploy, call admin endpoint once:
```bash
curl -X POST https://<your-railway-domain>/api/admin/ingest/incremental \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <ADMIN_API_TOKEN>" \
  -d '{"days": 30, "limit": 1000}'
```

## Operational Notes
- Summary jobs are queued in Redis (`rq` queue name: `summaries`).
- If queue is unavailable, API falls back to inline summary execution.
- Summary cache key includes `publication_number + model + prompt_version + summary_mode + source_hash`.
- Change `PROMPT_VERSION` to force regeneration after prompt upgrades.

## Security Notes
- Keep admin endpoints protected using `ADMIN_API_TOKEN`.
- Never expose `OPENAI_API_KEY` in the frontend.
- Serve over HTTPS in production.

## Disclaimer
AI summaries are technical aids and are **not legal advice**.
