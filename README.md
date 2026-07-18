# Adaptive Source Learning

Local installation and environment configuration are in [docs/SETUP.md](./docs/SETUP.md). Full details on each command below are there too.

## Quick start: 5 processes, 5 terminals

Nothing works end-to-end unless **all five** of these are running at once. It's easy to start only the web app and API and assume you're done — the app will look fine, but course generation will silently never progress, because the worker is what actually does the generation work.

With `.venv` active in each terminal, from the repo root:

| # | Terminal command | Port | What breaks if it's not running |
|---|---|---|---|
| 1 | `python -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000` | 8000 | The whole app — this is the backend the web app talks to. |
| 2 | `python -m uvicorn llm_gateway.main:app --app-dir services/llm_gateway --port 8010` | 8010 | Course generation, quiz grading, and the learning helper all fail or 503. |
| 3 | `python -m uvicorn sandbox_runner.main:app --app-dir services/sandbox_runner --port 8020` | 8020 | Coding-lab Run/Submit — the sandbox that executes learner code. |
| 4 | `python -m worker.main` | — | **Course generation never progresses.** No error is shown — a course (or a Regenerate) just sits at "planning" forever. This is the process that actually drains the generation queue. |
| 5 | `npm run dev:web` | 3000 | The Next.js frontend itself. |

(Windows/PowerShell equivalents and the full explanation of each service are in [docs/SETUP.md](./docs/SETUP.md#3-run-the-services).)

## Reference documents

- [Product idea](./docs/IDEA.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Demo plan](./docs/DEMO.md)
- [Market exploration 3](./docs/MARKET_EXPLORATION_3.md)
