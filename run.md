# Running the stack (Canopy)

How to bring the whole app up locally on **Windows**, where the logs are, and the
gotchas that bit us. Run everything **from the repo root** so each service finds the
root `.env` (they all load `env_file=".env"` relative to the current directory).

## Components & ports

| Component | Port | Command entrypoint | Needs |
|---|---|---|---|
| Web (Next.js) | 3000 | `npm run dev:web` | node deps |
| API (FastAPI) | 8000 | `uvicorn app.main:app` | python deps |
| LLM gateway | 8010 | `uvicorn llm_gateway.main:app` | python deps + OpenAI key |
| Sandbox runner | 8020 | `uvicorn sandbox_runner.main:app` | python deps + **Docker** |
| Worker | — (bg) | `python -m worker.main` | python deps |

- **No local Supabase / Postgres is needed.** Web, API, and worker all talk to the
  **remote hosted Supabase** project in `.env` (`APP_SUPABASE_URL`) via the service-role
  key and PGMQ RPCs. The `APP_DATABASE_URL=127.0.0.1:54322` line in `.env` is vestigial —
  you do **not** need to run `npx supabase start` for the app to work.
- **Docker** is only required by the **sandbox runner** (it executes lesson code in
  containers). Everything else works without it. Start Docker Desktop if you want the
  in-lesson code runner to work.
- All credentials (OpenAI key, Supabase keys) live in the single root `.env`.

## First-time setup

```powershell
# Python deps (once) — installs the 4 services editable into .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\services\api[dev] -e .\services\worker -e .\services\llm_gateway[dev] -e .\services\sandbox_runner[dev]

# Node deps (workspaces, hoisted to root node_modules)
npm install
```

> ⚠️ **Re-run `npm install` whenever `apps/web/package.json` changes.** The web app uses
> MUI / Emotion / Motion / Monaco; if the dev server 500s with `module-not-found:
> @mui/material` (or similar), the lockfile added deps that aren't installed yet.

## Start everything (from repo root)

Each in its own terminal, or backgrounded with output redirected to `.logs/` for easy
scanning. Create the log dir first: `mkdir .logs` (once).

```powershell
# 1. LLM gateway (8010)
.\.venv\Scripts\python.exe -m uvicorn llm_gateway.main:app --app-dir .\services\llm_gateway --host 127.0.0.1 --port 8010  *> .logs\gateway.log

# 2. Sandbox runner (8020) — needs Docker Desktop running
.\.venv\Scripts\python.exe -m uvicorn sandbox_runner.main:app --app-dir .\services\sandbox_runner --host 127.0.0.1 --port 8020  *> .logs\sandbox.log

# 3. API (8000)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\services\api --host 127.0.0.1 --port 8000  *> .logs\api.log

# 4. Worker (background poller)
$env:PYTHONPATH = "services\worker"; .\.venv\Scripts\python.exe -m worker.main  *> .logs\worker.log

# 5. Web (3000) — predev auto-syncs root .env -> apps/web/.env.local
npm run dev:web  *> .logs\web.log
```

Add `--reload` to any `uvicorn` line for hot-reload during development.

**Open the app at http://localhost:3000** (title: "Canopy").

## Health checks

```powershell
# HTTP services
curl http://127.0.0.1:3000/          # web  -> 200
curl http://127.0.0.1:8000/health    # api  -> 200
curl http://127.0.0.1:8010/health    # gateway -> 200
curl http://127.0.0.1:8020/health    # sandbox -> 200
```

The **worker has no HTTP port** — confirm it's alive by tailing its log; you should see
repeating `POST .../rpc/read_generation_jobs 200 OK` and `read_ingestion_jobs 200 OK`.

## Logs / debugging

- With the `*> .logs\<svc>.log` redirects above, tail any service:
  `Get-Content .logs\web.log -Tail 40 -Wait`
- Next.js also writes its own dev log at `apps\web\.next\dev\logs\next-development.log`.
- Worker log is the place to watch generation/ingestion job flow (it names the Supabase
  RPCs it calls).
- Gateway log shows OpenAI request/response issues (bad key, model name, rate limits).

## Stopping / restarting

**Windows gotcha:** killing the `npm run dev:web` / `uvicorn` wrapper does **not** always
kill the child `node` / `python` process — it can be orphaned and keep holding the port,
so a restart then fails with "port in use." Kill by port instead:

```powershell
# Free a port (e.g. 3000) by killing whatever listens on it
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -Expand OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

Swap `3000` for `8000` / `8010` / `8020` as needed. Then relaunch that service.
