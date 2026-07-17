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
python -m pip install -e 'services/api[dev]' -e 'services/worker' -e 'services/llm_gateway[dev]' -e 'services/sandbox_runner[dev]'

npm install
npm run dev:web
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\services\api[dev] -e .\services\worker -e .\services\llm_gateway[dev] -e .\services\sandbox_runner[dev]

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

There is a single `.env` at the repository root. The web app, API, worker, LLM gateway, and sandbox runner read only their declared settings from it; in a composed deployment, only the LLM gateway receives the model-provider credential. Next.js only reads env files from `apps/web` itself, so `npm run dev:web` and `npm run build:web` automatically sync the root `.env` into `apps/web/.env.local` first (`apps/web/scripts/sync-env.js`, wired as `predev`/`prebuild`) — no manual step needed.

Run the API in a separate shell with the virtual environment active:

### macOS (zsh)

```zsh
python -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000
```

### Windows (PowerShell)

```powershell
python -m uvicorn app.main:app --app-dir .\services\api --reload --reload-dir services\api --port 8000
```

Run the private LLM gateway after configuring a model provider in your uncommitted `.env` file. The worker never receives provider credentials; it calls the gateway, which routes requests according to `APP_LLM_PROVIDER` (`openai`, `azure`, `aws`, or `aws_openai`; `APP_OPENAI_PROVIDER` still works as a legacy alias). OpenAI and Azure need `APP_OPENAI_API_KEY` (plus the `APP_AZURE_OPENAI_*` deployments for Azure). `aws` uses the Bedrock Converse API (Claude/Nova) with `APP_AWS_REGION`, the `APP_AWS_BEDROCK_*_MODEL` IDs, and standard AWS credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or a profile/role). `aws_openai` runs OpenAI GPT models (default `openai.gpt-5.4`) on Bedrock's `bedrock-mantle` Responses endpoint using a Bedrock API key (`APP_AWS_BEDROCK_API_KEY`), with embeddings still served by Titan via `bedrock-runtime` — see `.env.example`. Start the gateway and sandbox runner in separate shells before starting the worker:

### macOS (zsh)

```zsh
python -m uvicorn llm_gateway.main:app --app-dir services/llm_gateway --port 8010
python -m uvicorn sandbox_runner.main:app --app-dir services/sandbox_runner --port 8020
```

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m uvicorn llm_gateway.main:app --app-dir .\services\llm_gateway --port 8010
.\.venv\Scripts\python.exe -m uvicorn sandbox_runner.main:app --app-dir .\services\sandbox_runner --port 8020
```

Then start the worker:

### macOS (zsh)

```zsh
python -m worker.main
```

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m worker.main
```

The current vertical slice uses Supabase Auth and the Supabase-backed course repository when `APP_AUTH_MODE=supabase` and `APP_REPOSITORY_BACKEND=supabase` are set. A learner goal is enough to create and generate a course; optional source files upload directly to private Supabase Storage through path-bound signed tokens and add grounding citations. The worker consumes durable PGMQ jobs, parses supplied sources, calls the private LLM gateway for embeddings and generation, and sends code execution only to the private sandbox runner.

## Reference documents

- [Product idea](./docs/IDEA.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Scaffold status](./docs/SCAFFOLD_STATUS.md)
- [Sample course inputs](./docs/SAMPLE_COURSES.md)
