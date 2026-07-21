<p align="center">
  <img src="./docs/assets/canopy-logo.svg" alt="Canopy logo" width="120" />
</p>

# Canopy

Canopy turns any technical source (a paper, docs, your own notes) into a hands-on course of lessons and labs, then tracks whether you can actually *apply* what it teaches, not just whether you read it.

Local installation and environment configuration are in [docs/SETUP.md](./docs/setup/SETUP.md). Full details on each command below are there too.

## Quick start: one command, five processes

Nothing works end-to-end unless **all five** of these run at once. It's easy to start
only the web app and API and assume you're done — the app will look fine, but course
generation will silently never progress, because the worker is what actually does the
generation work.

```
npm run dev
```

runs all five together in one terminal (API, LLM gateway, sandbox runner, worker, web
app), labeled and color-coded, and exits everything together if any one of them dies. It
finds `.venv`'s Python itself — no manual activation needed, and it works the same on
macOS/Linux/Windows.

| Process | Port | What breaks if it's not running |
|---|---|---|
| `api` | 8000 | The whole app — this is the backend the web app talks to. |
| `gateway` | 8010 | Course generation, quiz grading, and the learning helper all fail or 503. |
| `sandbox` | 8020 | Coding-lab Run/Submit — the sandbox that executes learner code. |
| `worker` | — | **Course generation never progresses.** No error is shown — a course (or a Regenerate) just sits at "planning" forever. This is the process that actually drains the generation queue. |
| `web` | 3000 | The Next.js frontend itself. |

To run just one of these (e.g. to debug it in isolation), each also has its own script:
`npm run dev:api`, `dev:gateway`, `dev:sandbox`, `dev:worker`, `dev:web`. Windows/PowerShell
equivalents and the full explanation of each service are in
[docs/SETUP.md](./docs/setup/SETUP.md#3-run-the-services).

## Reference documents

Full index: [docs/README.md](./docs/README.md).

- [Product idea](./docs/product/IDEA.md)
- [Features](./docs/product/FEATURES.md)
- [Architecture](./docs/architecture/ARCHITECTURE.md)
- [Security](./docs/architecture/SECURITY.md)
- [Demo guide](./docs/demo/DEMO.md)
- [Demo recording script](./docs/demo/RECORDING_SCRIPT.md)
- [Market exploration](./docs/product/MARKET_EXPLORATION.md)
- [Competitive differentiation](./docs/product/COMPETITIVE_DIFFERENTIATION.md)
