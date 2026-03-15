<h1 align="center">Meridian Logistics</h1>

<p align="center">
  Memphis-only conversational brokerage PoC for fast read workflows and confirmed single-step bookings.
</p>

<p align="center">
  <a href="https://github.com/maxpetrusenko/MeridianLogistics"><img src="https://img.shields.io/badge/repo-public-black" alt="Public repo"></a>
  <img src="https://img.shields.io/badge/scope-Memphis%20PoC-c97a42" alt="Scope">
  <img src="https://img.shields.io/badge/stack-FastAPI%20%2B%20React%20%2B%20Vite-1f6feb" alt="Stack">
</p>

## Overview

This repository packages the current Meridian Memphis proof of concept: product requirements, architecture and security working docs, contract artifacts, a FastAPI backend scaffold, and a React frontend prototype for structured chat responses.

Approved cheapest storage shape (production/shared-dev):

- Neon Postgres for relational state
- Backblaze B2 for generated PDFs, exports, replay fixtures, and other large artifacts
- Railway backend reads secrets and talks to both services
- Netlify frontend talks only to the backend

Local development fallback:

- SQLite for session/job state via MERIDIAN_STATE_DATABASE_URL (defaults to file-based SQLite)
- Same read/write paths, just local persistence instead of Neon

Core boundary:

- Memphis office only
- 90 day PoC
- Read-heavy operational queries
- Single-step booking writes only
- Explicit confirmation before any write
- Office and role scoped access only

## What Is In The Repo

| Area | Purpose |
| --- | --- |
| `prd.md` | product scope and acceptance boundary |
| `architecture-overview.md` | PoC architecture shape |
| `security-model.md` | permission and data-protection model |
| `docs/api/` | API documentation (async jobs, etc.) |
| `docs/plans/` | design and planning documents |
| `contracts/` | response, tool, permission, and checkpoint contracts |
| `backend/` | FastAPI app, orchestrator, controller, tool registry, write gateway |
| `frontend/` | Vite + React prototype for structured operational responses |
| `db/` | schema and view definitions |
| `evals/` | evaluation harness code |
| `reports/` | prior controller and implementation reports |

## Local Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn backend.app.main:app --reload
```

Backend app:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Storage notes:

- local dev can leave B2 values unset if upload flows are not under test
- production and shared dev should set both Neon URLs plus the B2 bucket credentials
- large generated artifacts should go to B2, not Postgres

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend app:

- UI: `http://127.0.0.1:5173`

## Validation

Backend contracts:

```bash
source .venv/bin/activate
pytest
```

Frontend checks:

```bash
cd frontend
npm test
npm run build
```

## Current Focus

The implementation currently centers on:

- safe structured responses for ops lookups
- controller checkpoint and precedence behavior
- permission-aware contract validation
- booking confirmation flow scaffolding

## Notes

- `AGENTS.md` and `CLAUDE.md` are both active repo instructions.
- Async job polling uses the opaque `job_poll_token` returned by the pending `/chat` response; see `docs/api/async-jobs.md` for complete job lifecycle documentation.
- `/chat` now accepts broker, office, and role only from trusted request state injected by server-side middleware. Raw `x-meridian-*` headers are rejected at the route seam, and the seeded Memphis fallback stays limited to local/dev or test. Client-supplied JSON identity fields remain compatibility-only and ignored.
- `.agents/` stores local agent manifests and should stay mostly tracked except transient runtime state.
- Generated runtime folders such as `.codex/`, `.claude/`, `agents/`, `skills/`, `frontend/node_modules/`, and `frontend/dist/` are intentionally ignored.
- Backend-only secrets now include `MERIDIAN_DATABASE_URL`, `MERIDIAN_DIRECT_DATABASE_URL`, `MERIDIAN_B2_ENDPOINT`, `MERIDIAN_B2_BUCKET_NAME`, `MERIDIAN_B2_ACCESS_KEY_ID`, and `MERIDIAN_B2_SECRET_ACCESS_KEY`.
- Frontend should only receive public API configuration such as `VITE_API_BASE_URL`.

## API Documentation

- `docs/api/async-jobs.md` - Async jobs API, lifecycle states, polling behavior, and security model
