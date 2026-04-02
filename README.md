# Job Agent API

Production-oriented FastAPI backend for parsing job descriptions, tailoring resumes, generating PDFs, and (optionally) driving LinkedIn Easy Apply with Playwright.

## Stack

- Python 3.11+
- FastAPI, Pydantic, Uvicorn
- React + Vite + TypeScript + Tailwind (`frontend/`)
- Jinja2 (HTML) + Playwright Chromium (PDF)
- SQLAlchemy 2 async + SQLite (swap URL for PostgreSQL)
- Playwright for LinkedIn automation
- **Google Gemini** (optional) for AI resume tailoring vs. rule-based fallback

## Gemini resume tailoring (recommended)

Tailoring uses **Gemini** when an API key is set; otherwise the same endpoints use deterministic rules (reordering, light summary tweak). Set:

```bash
# In .env (see .env.example). GEMINI_API_KEY also works as an alias.
APP_GEMINI_API_KEY=your_key_from_aistudio
APP_GEMINI_MODEL=gemini-2.0-flash
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey). Restart the API after changing env vars.

- **`GET /api/config/paths`** includes `gemini_configured` and `gemini_model` (no secrets).
- Request body **`force_heuristic: true`** on `POST /api/tailor-resume` or `POST /api/me/optimize` skips Gemini.

## Setup

```bash
cd job-agent
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # optional overrides
```

Run the API (from project root so `config/settings.yaml` and paths resolve).

**`uvicorn: command not found`** means the virtualenv is not active (or deps are not installed). Use one of these:

```bash
# Option A — activate the venv, then run (uvicorn is on PATH)
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option B — no activation; call the module from the venv’s Python
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option C — Makefile (same as B)
make dev
```

- OpenAPI docs: `http://localhost:8000/docs`
- Health: `GET /health` (also `GET /api/health`)

## Web UI (React)

**Development (hot reload, recommended):** two terminals — API on 8000, Vite on 5173.

```bash
# Terminal 1 — API
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — UI (proxies /api, /health, /docs to the API)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** — the UI calls the API through Vite’s proxy.

**Production (single server):** build the SPA, then run Uvicorn. The API serves `frontend/dist` at `/` when that folder exists.

```bash
cd frontend && npm install && npm run build
cd .. && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** for the UI; **http://localhost:8000/docs** for OpenAPI.

## Configuration

- Defaults: `config/settings.yaml`
- Overrides: environment variables with prefix `APP_` (see `app/config.py` and `.env.example`)
- Key paths: `APP_TEMPLATES_DIR`, `APP_OUTPUT_DIR`, `APP_DATA_DIR`, `APP_DATABASE_URL`
- **CORS:** `APP_CORS_ORIGINS` — comma-separated list (defaults include `http://localhost:5173` for the Vite dev server)

## Sample data

- `data/sample_resume.json` — example resume
- `data/sample_job.txt` — example job posting

## API

REST routes are under **`/api`**. PDFs can be downloaded with **`GET /api/files/{filename}.pdf`** after generation.

### Authentication (JWT)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Body: `{ "email", "password" }` → `{ access_token, token_type }` |
| POST | `/api/auth/login` | Same as register; returns bearer token |
| GET | `/api/me` | Current user (header: `Authorization: Bearer <token>`) |
| GET | `/api/me/resume` | Stored resume JSON for the user (or null) |
| PUT | `/api/me/resume` | Body: `{ "resume": { ... } }` — save profile to DB |
| POST | `/api/me/resume/upload` | Multipart `file`: `.json` (schema) or `.pdf` (text extracted + heuristics; max 5 MB) |
| POST | `/api/me/optimize` | Body: `{ "job_description": "..." }` — tailors **saved** resume |

Set **`APP_JWT_SECRET`** in production (see `.env.example`).

### Other

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/parse-job` | Parse raw job description |
| POST | `/api/tailor-resume` | Tailor resume to job (parsed or raw JD) — guest / no auth |
| POST | `/api/generate-pdf` | Render PDF to configured output directory |
| GET | `/api/files/{filename}` | Download a generated PDF (basename only) |
| POST | `/api/apply` | LinkedIn Easy Apply (best-effort; DOM changes often) |
| GET | `/api/config/paths` | Resolved paths (no secrets) |

## Notes

- **LinkedIn:** Respect site terms; automation may require login flows not covered here. Selectors in `app/automation/linkedin.py` are fallbacks and may need updates.
- **PostgreSQL:** Set `APP_DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname` and install `asyncpg`.
- **LLM:** `JobParserService.parse` is heuristic; replace internals with your model provider when ready.

## Project layout

```
app/
  api/           # routes, dependencies
  services/      # parser, resume, PDF, matching
  schemas/     # Pydantic models
  models/      # SQLAlchemy
  automation/  # Playwright
  utils/       # logging
  main.py
config/
frontend/      # Vite + React SPA
templates/     # Jinja2 (resume.html)
data/          # samples + SQLite file
output/        # generated PDFs
```
