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

You need **all five** of the services below running at once. It's easy to start only the
API and web app and think you're done — the app will load fine, but course generation
will silently never progress, because nothing will be consuming the generation queue (see
the Worker section below).

### All five at once (recommended)

```
npm run dev
```

Starts every service below in one terminal, labeled and color-coded, using `.venv`'s
Python directly — no manual activation, and no OS-specific command needed. If any one
process dies, the rest are stopped too, since a partial set is worse than an obvious full
stop (see the Worker warning above for why a silently-missing worker is easy to miss).
Implemented in [`scripts/dev.js`](../../scripts/dev.js).

### One service at a time (debugging, or a config change that needs a restart)

| Service | npm script | Command (zsh) | Port |
|---|---|---|---|
| API backend | `npm run dev:api` | `python -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000` | 8000 |
| LLM gateway | `npm run dev:gateway` | `python -m uvicorn llm_gateway.main:app --app-dir services/llm_gateway --port 8010` | 8010 |
| Sandbox runner | `npm run dev:sandbox` | `python -m uvicorn sandbox_runner.main:app --app-dir services/sandbox_runner --port 8020` | 8020 |
| Worker | `npm run dev:worker` | `python -m worker.main` | — |
| Web app | `npm run dev:web` | `npm run dev:web` | 3000 |

Only `npm run dev` resolves `.venv`'s Python itself and works on any OS. The individual
`npm run dev:api`/`dev:gateway`/`dev:sandbox`/`dev:worker` shortcuts are a macOS/Linux
convenience that assume `.venv/bin/python` (they're just the zsh commands below, saved as
scripts) — on Windows, or with a different venv location, use the raw commands below
instead, or activate the virtual environment and run the plain `python -m ...` commands
directly.

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

## Health checks

Confirm each service actually came up, especially after `npm run dev` (all five start
concurrently, so a slow one can be easy to miss in the interleaved log output):

```
curl http://127.0.0.1:3000/          # web     -> 200
curl http://127.0.0.1:8000/health    # api     -> 200
curl http://127.0.0.1:8010/health    # gateway -> 200
curl http://127.0.0.1:8020/health    # sandbox -> 200
```

The **worker has no HTTP port** — confirm it's alive from its log output instead; you
should see repeating `POST .../rpc/read_generation_jobs 200 OK` and
`read_ingestion_jobs 200 OK` lines (prefixed `[worker]` under `npm run dev`).

## Troubleshooting

- A learning-helper 503 usually means the LLM gateway is stopped, still running old code, or lacks a working provider configuration. Restart the gateway after pulling helper changes.
- **A course (or a Regenerate) stuck at "planning" with no error is almost always the worker not running.** Course generation needs the worker, LLM gateway, and sandbox runner running in addition to the API and web app — see the table in [§3](#3-run-the-services). Check for a `python -m worker.main` process; if it's not there, start it.
- The current vertical slice uses Supabase Auth and the Supabase-backed repository when `APP_AUTH_MODE=supabase` and `APP_REPOSITORY_BACKEND=supabase` are set.
- **No local Supabase/Postgres is required to run the app.** Web, API, and worker all talk
  to whichever Supabase `APP_SUPABASE_URL` in `.env` points at (local or hosted, per
  [Database migrations](#database-migrations) above) via the service-role key and PGMQ
  RPCs — `npx supabase start` is only needed if that URL is the local one.

### A service's terminal output is hard to find

Each process under `npm run dev` is prefixed (`[api]`, `[gateway]`, `[sandbox]`,
`[worker]`, `[web]`) in one interleaved stream. If you'd rather have per-service log
files instead, run the individual `npm run dev:*` scripts (or the raw commands below)
each redirected to a file, e.g. on PowerShell: `npm run dev:worker *> .logs\worker.log`,
then `Get-Content .logs\worker.log -Tail 40 -Wait` to follow it. Next.js also writes its
own dev log at `apps\web\.next\dev\logs\next-development.log` regardless.

### Windows: a port is already in use

Local servers keep running until their terminal receives `Ctrl+C` or the process is stopped. If a terminal is no longer visible, an older API, gateway, or sandbox process can still hold its port.

**If you're using `npm run dev`, this shouldn't happen** — `concurrently` kills each
process's full tree (via the `tree-kill` package, which uses `taskkill /T` on Windows)
when you stop it or when another process in the group exits, which is exactly what
avoids the classic Windows gotcha where killing a wrapper script (`uvicorn`, `npm run
dev:web`) leaves the real child process running and still holding the port.

If a port is still stuck (e.g. after a hard crash, or from a service started outside
`npm run dev`), find and stop whatever's holding it. Either works:

```powershell
Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -Expand OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

```powershell
netstat -ano | Select-String ':8010'
# The final column is the process ID (PID). Inspect it, then stop only that PID:
Get-Process -Id <pid>
Stop-Process -Id <pid>
```

Swap `8010` for `3000` / `8000` / `8020` as needed, then relaunch that service. Common
local ports are web `3000`, API `8000`, LLM gateway `8010`, and sandbox runner `8020`.
