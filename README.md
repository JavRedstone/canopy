# Adaptive Source Learning

An adaptive coding-course platform that turns source documents into canonical, source-grounded technical courses with learner-controlled support layers.

## Repository layout

- `apps/web` — Next.js learner application using Base UI.
- `services/api` — FastAPI command/API service.
- `services/worker` — asynchronous ingestion and generation worker scaffold.
- `packages/contracts` — versioned shared JSON contracts.
- `supabase` — local Supabase configuration, migrations, RLS, Storage, and PGMQ setup.
- `docs` — product and system design documents.

## Local prerequisites

- Node.js 22+
- Python 3.13+
- Docker Desktop
- Supabase CLI for local Supabase services (installed as a project development dependency)

Python dependencies are installed in the project-local `.venv`; nothing is installed globally.

## First-run plan

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\services\api[dev] -e .\services\worker

npm install
npm run dev:web
```

Start local Supabase from the repository root:

```powershell
npx supabase start
npx supabase db reset
```

Copy `.env.example` to `.env` and replace the local Supabase keys printed by `npx supabase start`.

Run the API in a separate shell with the virtual environment active:

```powershell
python -m uvicorn app.main:app --app-dir .\services\api --reload --port 8000
```

Run the worker after adding `APP_OPENAI_API_KEY` to your uncommitted `.env` file:

```powershell
.\.venv\Scripts\python.exe -m worker.main
```

The current vertical slice uses Supabase Auth and the Supabase-backed course repository when `APP_AUTH_MODE=supabase` and `APP_REPOSITORY_BACKEND=supabase` are set. The memory adapter remains available only for isolated development tests. Source files upload directly to private Supabase Storage through path-bound signed tokens. The worker consumes durable PGMQ jobs, parses sources, creates 1536-dimensional embeddings, and generates a validated canonical course map.

## Reference documents

- [Revised product idea](./docs/REVISED_IDEA.md)
- [System design](./docs/SYSTEM_DESIGN.md)
- [Scaffold status](./docs/SCAFFOLD_STATUS.md)
