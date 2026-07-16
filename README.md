# Adaptive Source Learning

An adaptive coding-course platform that turns learner goals into canonical technical courses, with optional source documents for additional grounding and citations.

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

### macOS (zsh)

```zsh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e 'services/api[dev]' -e 'services/worker'

npm install
npm run dev:web
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\services\api[dev] -e .\services\worker

npm install
npm run dev:web
```

Start local Supabase from the repository root:

### macOS (zsh)

```zsh
npx supabase start
npx supabase db reset
```

### Windows (PowerShell)

```powershell
npx supabase start
npx supabase db reset
```

Copy `.env.example` to `.env` and replace the local Supabase keys printed by `npx supabase start`.

On macOS:

```zsh
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

There is a single `.env` at the repository root, shared by `apps/web`, `services/api`, and `services/worker`. Next.js only reads env files from `apps/web` itself, so `npm run dev:web` and `npm run build:web` automatically sync the root `.env` into `apps/web/.env.local` first (`apps/web/scripts/sync-env.js`, wired as `predev`/`prebuild`) — no manual step needed.

Run the API in a separate shell with the virtual environment active:

### macOS (zsh)

```zsh
python -m uvicorn app.main:app --app-dir services/api --reload --port 8000
```

### Windows (PowerShell)

```powershell
python -m uvicorn app.main:app --app-dir .\services\api --reload --port 8000
```

Run the worker after adding `APP_OPENAI_API_KEY` to your uncommitted `.env` file. The worker calls OpenAI directly by default; set `APP_OPENAI_PROVIDER=azure` plus the `APP_AZURE_OPENAI_*` values (see `.env.example`) to route the same calls through an Azure OpenAI resource instead:

### macOS (zsh)

```zsh
python -m worker.main
```

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m worker.main
```

The current vertical slice uses Supabase Auth and the Supabase-backed course repository when `APP_AUTH_MODE=supabase` and `APP_REPOSITORY_BACKEND=supabase` are set. A learner goal is enough to create and generate a course; optional source files upload directly to private Supabase Storage through path-bound signed tokens and add grounding citations. The worker consumes durable PGMQ jobs, parses supplied sources, creates 1536-dimensional embeddings, and generates a validated canonical course map centered on the goal.

## Reference documents

- [Product idea](./docs/IDEA.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Scaffold status](./docs/SCAFFOLD_STATUS.md)
- [Sample course inputs](./docs/SAMPLE_COURSES.md)
