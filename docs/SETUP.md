# Local setup

## Prerequisites

- Node.js 22+
- Python 3.13+
- Docker Desktop
- Supabase CLI (available as a project development dependency)

Python dependencies live in the project-local `.venv`; nothing needs a global Python install.

## 1. Install dependencies

### macOS (zsh)

```zsh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e 'services/api[dev]' -e 'services/worker' -e 'services/llm_gateway[dev]' -e 'services/sandbox_runner[dev]'
npm install
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\services\api[dev] -e .\services\worker -e .\services\llm_gateway[dev] -e .\services\sandbox_runner[dev]
npm install
```

## 2. Start Supabase and configure `.env`

From the repository root:

```powershell
npx supabase start
npx supabase db reset
Copy-Item .env.example .env
```

On macOS, use `cp .env.example .env` for the last command.

Replace the Supabase values in `.env` with the local keys printed by `npx supabase start`, then configure one LLM provider. `.env.example` documents the supported OpenAI, Azure, AWS Bedrock, and Bedrock OpenAI configurations.

There is one root `.env`. The web app, API, worker, LLM gateway, and sandbox runner read only the settings relevant to them. `npm run dev:web` synchronizes the root values required by Next.js into `apps/web/.env.local`; do not manually edit that generated file.

## Database migrations

Check `APP_SUPABASE_URL` in `.env` to see which Supabase you're pointed at: a local address (from `npx supabase start`) means local, a `https://<ref>.supabase.co` URL means a real hosted project.

### Local

`npx supabase db reset` (§2 above) applies every file under `supabase/migrations/` to the local stack. Re-run it after pulling new migrations.

### Hosted

New migration files don't apply themselves to a hosted project — push them explicitly from the repository root:

```powershell
npx supabase link --project-ref <ref>
npx supabase migration list   # diff local files against what's already applied remotely
npx supabase db push          # apply everything pending, in order
```

`<ref>` is the subdomain in `APP_SUPABASE_URL` (e.g. `https://cbyhaonzgoxnrpqifmuf.supabase.co` → `cbyhaonzgoxnrpqifmuf`).

**None of this needs the database password.** `link`/`migration`/`db push` authenticate as your Supabase *account* — via a cached access token from an earlier `supabase login`, or a `SUPABASE_ACCESS_TOKEN` env var — against Supabase's management API, not as a direct Postgres connection. `npx supabase projects list` is a quick way to confirm the CLI is already authenticated before linking; if it prompts to log in instead, run `npx supabase login` first.

This is unrelated to `APP_DATABASE_URL` in `.env`, which is a full Postgres connection string (password included) that the application's own services use to talk to the database directly — the CLI doesn't read or need it for migrations.

## 3. Run the services

You need **all five** of the services below running at once, each in its own terminal with the virtual environment active. It's easy to start only the API and web app and think you're done — the app will load fine, but course generation will silently never progress, because nothing will be consuming the generation queue (see the Worker section below).

| Service | Command (zsh) | Port |
|---|---|---|
| API backend | `python -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000` | 8000 |
| LLM gateway | `python -m uvicorn llm_gateway.main:app --app-dir services/llm_gateway --port 8010` | 8010 |
| Sandbox runner | `python -m uvicorn sandbox_runner.main:app --app-dir services/sandbox_runner --port 8020` | 8020 |
| Worker | `python -m worker.main` | — |
| Web app | `npm run dev:web` | 3000 |

The API is the backend; the LLM gateway is a separate internal dependency used for generation, short-answer grading, and the learning helper.

### API backend — port 8000

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\services\api --reload --reload-dir services\api --port 8000
```

```zsh
python -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000
```

### LLM gateway — port 8010 (not the API backend)

```powershell
.\.venv\Scripts\python.exe -m uvicorn llm_gateway.main:app --app-dir .\services\llm_gateway --port 8010
```

```zsh
python -m uvicorn llm_gateway.main:app --app-dir services/llm_gateway --port 8010
```

Restart this service after changing a gateway task or any `APP_*_MODEL` setting. The learning helper specifically depends on the `lesson_helper` task and its helper-model configuration. Starting it does **not** start the API backend; run the port-8000 command above as well.

### Sandbox runner — port 8020

```powershell
.\.venv\Scripts\python.exe -m uvicorn sandbox_runner.main:app --app-dir .\services\sandbox_runner --port 8020
```

```zsh
python -m uvicorn sandbox_runner.main:app --app-dir services/sandbox_runner --port 8020
```

### Worker — required for course generation, no port, no error if you forget it

This process reads the `ingestion` and `generation` queues and does the actual work: ingesting sources, planning courses, and building lessons. **If it isn't running, nothing tells you** — a new course or a Regenerate just sits at "planning" indefinitely, with no error in the UI or the API logs, because the job that would move it forward was enqueued but nothing is there to pick it up.

```powershell
.\.venv\Scripts\python.exe -m worker.main
```

```zsh
python -m worker.main
```

### Web app

```powershell
npm run dev:web
```

```zsh
npm run dev:web
```

## Troubleshooting

- A learning-helper 503 usually means the LLM gateway is stopped, still running old code, or lacks a working provider configuration. Restart the gateway after pulling helper changes.
- **A course (or a Regenerate) stuck at "planning" with no error is almost always the worker not running.** Course generation needs the worker, LLM gateway, and sandbox runner running in addition to the API and web app — see the table in [§3](#3-run-the-services). Check for a `python -m worker.main` process; if it's not there, start it.
- The current vertical slice uses Supabase Auth and the Supabase-backed repository when `APP_AUTH_MODE=supabase` and `APP_REPOSITORY_BACKEND=supabase` are set.

### Windows: a port is already in use

Local servers keep running until their terminal receives `Ctrl+C` or the process is stopped. If a terminal is no longer visible, an older API, gateway, or sandbox process can still hold its port.

Find the process holding a port (for example, the LLM gateway on 8010):

```powershell
netstat -ano | Select-String ':8010'
```

The final column is the process ID (PID). Inspect it, then stop only that PID:

```powershell
Get-Process -Id <pid>
Stop-Process -Id <pid>
```

Start the service again using its command above. Common local ports are API `8000`, LLM gateway `8010`, and sandbox runner `8020`.
