# Technologies

Devpost's "Built with" field caps out at 25 tags. Here's the list, ready to paste in,
plus what each one is actually doing in Canopy (not just present in a `package.json`).

## Built with (25 tags)

```
GPT-5.6, Codex, Python, TypeScript, Next.js, React, FastAPI, Pydantic, Supabase,
PostgreSQL, pgvector, pgmq, Docker, OpenAI, Azure OpenAI, AWS Bedrock, Material UI,
Monaco Editor, pytest, AddressSanitizer, PyTorch, scikit-learn, Node.js, Go, C++
```

## What each one actually does here

**AI**
- **GPT-5.6**: Canopy's runtime model: plans courses, writes lessons and labs, grades
  quizzes, drives the lab-repair loop, powers the learning helper. Routed across two
  tiers (Sol for one-shot high-stakes calls, Luna for high-volume per-lesson work).
- **Codex**: the engineering tool used to build the system around GPT-5.6, from schema
  migrations through worker, API, and frontend, in the same iterative sessions that
  produced this repo's commit history.

**Backend**
- **Python**: every backend service (API, worker, LLM gateway, sandbox runner).
- **FastAPI**: the framework behind all four Python services.
- **Pydantic**: request/response schemas and the structured-output contracts GPT-5.6
  is held to on every generation call.

**Frontend**
- **TypeScript** / **Next.js** / **React**: the web app.
- **Material UI**: the component library the whole UI is built on.
- **Monaco Editor**: the in-browser code editor for coding labs.

**Data, queue, and auth**
- **Supabase**: Auth (magic-link email), Storage (uploaded sources), and the Postgres
  database, all in one.
- **PostgreSQL**: the database underneath Supabase.
- **pgvector**: embeddings and semantic search over source-document chunks (RAG
  grounding for lesson generation and citations).
- **pgmq**: the Postgres-native message queue backing ingestion, course planning, and
  lesson-build jobs.

**Model providers** (behind one internal gateway interface)
- **OpenAI**, **Azure OpenAI**, **AWS Bedrock**: three interchangeable backends; a
  provider outage or pricing change is a config change, not a rewrite.

**Sandbox & coding-lab languages**
- **Docker**: every generated lab executes in a locked-down, single-use, no-network,
  non-root, all-capabilities-dropped container. The sandbox runner is the only service
  with Docker socket access.
- **pytest**: the test framework for Python (and Python ML/DL) labs.
- **PyTorch**, **scikit-learn**: the real libraries available in the Python ML/DL lab
  environment (GPU-capable where available).
- **C++**: its own curated lab environment, compiled and run in the sandbox.
- **AddressSanitizer**: memory-safety checking for C labs, chosen specifically because
  Valgrind's ptrace-based approach doesn't work under the sandbox's `cap_drop=ALL`
  hardening.
- **Node.js**, **Go**: two more supported sandbox/playground language environments.

Full feature list: [`docs/product/FEATURES.md`](./product/FEATURES.md). Full
architecture: [`docs/architecture/ARCHITECTURE.md`](./architecture/ARCHITECTURE.md).
