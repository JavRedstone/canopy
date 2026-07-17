# Scaffold status

This document records the current application scaffold, what has been verified, and the work deliberately deferred from the first Supabase-backed vertical slice.

## Scope and decisions

- **Web:** Next.js with React and [Base UI](https://base-ui.com/) as the initial component library.
- **API:** FastAPI.
- **Worker:** a separate Python worker process, prepared to consume PGMQ jobs.
- **Database, auth, storage, realtime:** Supabase.
- **Python environments:** dependencies are installed in the project-local `.venv`; no global Python installation is required.
- **Learning model:** canonical course content is shared and reviewable. Learner-specific adaptation is limited to route/path events and support artifacts such as remediation or concise variants.

The system design and product decisions remain in [ARCHITECTURE.md](ARCHITECTURE.md) and [IDEA.md](IDEA.md).

## Repository layout

```text
apps/web/                 Next.js learner experience
services/api/             FastAPI API
services/worker/          background worker shell
packages/contracts/       shared TypeScript contracts
supabase/                 local configuration, SQL migration, seed data
```

The root `package.json` defines the Node workspace. The Python services have their own `pyproject.toml` files and use the root `.venv`.

## Current vertical slice

The scaffold currently supports this Supabase-backed course flow:

1. Create a source record and receive a path-bound signed upload token.
2. Upload the file directly to private Supabase Storage, then confirm it with the API. The API verifies the stored object's path, size, and MIME type, marks it `ingesting`, and publishes a durable PGMQ job.
3. Create a draft course, its initial planning version, and a durable source-to-course association. A planning job is queued whether its sources are already ready or still ingesting.
4. The worker parses PDF, Markdown, or text; stores chunks and 1536-dimensional embeddings; then claims the draft version only after every attached source is ready.
5. The worker validates a structured, source-cited planner result and persists canonical concepts, modules, prerequisite edges, summaries, and lesson-definition slots atomically. The course then becomes `ready`.

The API verifies Supabase bearer tokens through Supabase Auth and uses a server-only client for database operations. Every repository query also filters by the verified owner ID; this prevents service-key access from crossing learner boundaries. The web app has sign-in, course-list, and new-course views. Its source form uploads PDF, Markdown, and text files up to 6 MB directly to the private `sources` bucket; no file data transits FastAPI. The Python worker uses server-only Supabase and OpenAI credentials; it never receives browser tokens.

`MemoryCourseRepository` and development auth remain available through explicit `APP_REPOSITORY_BACKEND=memory` and `APP_AUTH_MODE=development` settings, so tests do not use the live project.

## Supabase preparation

The migration set defines:

- profiles and authenticated-user trigger;
- source documents, courses, versions, canonical concepts and lessons;
- learner support artifacts, mastery observations and mastery state;
- assessment records and pgvector-backed memory;
- private `sources` and `submissions` Storage buckets;
- row-level security policies and PGMQ queues.
- explicit `course_sources` provenance records that retain each course's ordered source set.

The workspace is linked to its configured Supabase project. On 2026-07-16, all four migrations—including `20260716003000_ingestion_and_planning_jobs.sql`, which adds server-only queue functions and atomic plan persistence—were successfully deployed and their local and remote histories match. Credentials remain only in the uncommitted `.env` file.

The Supabase CLI is installed locally as the root `supabase` development dependency (verified as version `2.109.1`). Invoke it with `npx supabase ...`; it is intentionally not installed globally.

## Verification completed

- API and worker tests: `9 passed`.
- Ruff checks for the API and worker: passed.
- Web typecheck, lint, and production build: passed.
- A temporary API health check returned `repository: memory` in development mode.
- The Supabase Python client completed a read-only live query successfully.
- A live signed-upload token was minted successfully for the private `sources` bucket without storing test data.
- The OpenAI-backed worker is configured for `text-embedding-3-small` at 1536 dimensions (matching the `vector(1536)` column) and a configurable structured-output planner model. It is not started until `APP_OPENAI_API_KEY` is supplied.
- The live API configuration reports `repository: supabase` and rejects anonymous course requests.
- The isolated suite includes Supabase-session identity handling.

One upstream FastAPI/Starlette `TestClient` deprecation warning appears during the API test; it does not fail the test.

## Known limitations and follow-up work

- Run an authenticated end-to-end upload, ingestion, and planning check after adding the server-only OpenAI key.
- Add retries, dead-letter review, and operational metrics around the worker queues.
- Add asynchronous evaluation status and realtime authorization as specified in the system design.
- Mastery tracking is live (dual-track BKT): quiz answers feed `p(understand)`, coding **Submit** feeds `p(apply)`, written to `observations`/`mastery` via the API's service client. Run/Submit are now split — Run executes only the visible tests (no mastery effect), Submit executes the full suite and records the observation. Not yet built: adaptation-event triggers, the LLM diagnosis layer, transfer-check exercises, and per-checkpoint concept tagging (a lesson currently maps to its single concept).

`npm audit` currently reports two moderate vulnerabilities through Next.js's pinned transitive `postcss` dependency. A root override was tested but conflicts with Next.js's exact dependency declaration, so it was removed. Upgrade Next.js when it provides a compatible resolution; do not use a forced audit fix.

## Local commands

### macOS (zsh)

```zsh
# Web application
npm run dev:web

# API
source .venv/bin/activate
python -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000

# Supabase CLI
npx supabase --help
```

### Windows (PowerShell)

```powershell
# Web application
npm run dev:web

# API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\services\api --reload --port 8000

# Supabase CLI
npx supabase --help
```

The next integration sequence is an end-to-end worker run with a real source, then course-map/textbook rendering and canonical lesson generation.
