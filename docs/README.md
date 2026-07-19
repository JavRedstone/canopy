# Docs index

## [`product/`](./product/) — product & positioning

- [`IDEA.md`](./product/IDEA.md) — the product plan; source of truth for product intent.
- [`MARKET_EXPLORATION.md`](./product/MARKET_EXPLORATION.md) — business case, market map, target customers, competitive landscape, positioning, and risks. Consolidated from three earlier independent explorations that all converged on the same conclusion.
- [`COMPETITIVE_DIFFERENTIATION.md`](./product/COMPETITIVE_DIFFERENTIATION.md) — a scannable head-to-head table vs. NotebookLM, ChatGPT, Codecademy/DataCamp, and GitHub Copilot/Cody, distilled from `MARKET_EXPLORATION.md` and `USE_CASES.md`.
- [`USE_CASES.md`](./product/USE_CASES.md) — candidate use cases compared against what the product can actually do today, not just the plan's intent.
- [`SAMPLE_COURSES.md`](./product/SAMPLE_COURSES.md) — example course-creation inputs (goal text) and what they produce.
- [`PEDAGOGY_EVALUATION.md`](./product/PEDAGOGY_EVALUATION.md) — Canopy's teaching model evaluated against the learning-science literature: benefits, shortcomings, and prioritized fixes, with citations.
- [`ROADMAP.md`](./product/ROADMAP.md) — candidate features and improvements not yet scheduled, as a checklist.

## [`architecture/`](./architecture/) — architecture & security

- [`ARCHITECTURE.md`](./architecture/ARCHITECTURE.md) — the target system design. Treat as directional; it describes some capabilities (assignments, WebSockets, full adaptation) ahead of the current implementation.
- [`SANDBOX_ARCHITECTURE.md`](./architecture/SANDBOX_ARCHITECTURE.md) — the code-execution sandbox's design rationale.
- [`PRACTICE_QUESTION_POOL.md`](./architecture/PRACTICE_QUESTION_POOL.md) — design/build doc for the per-concept practice question pool (low-stakes drill + non-repeating bank).
- [`SECURITY.md`](./architecture/SECURITY.md) — current security posture across every service (auth, sandbox isolation, RLS, secrets). The most up to date source for anything security-related.
- `architecture-diagram.drawio` — client → API → worker/sandbox diagram source.

## [`demo/`](./demo/) — demo & hackathon

- [`DEMO.md`](./demo/DEMO.md) — the detailed demo narrative, golden path, and reliability checklist.
- [`RECORDING_SCRIPT.md`](./demo/RECORDING_SCRIPT.md) — the concise screen-by-screen script for recording.
- [`HACKATHON.md`](./demo/HACKATHON.md) — OpenAI Build Week submission rules and judging criteria.

## [`setup/`](./setup/) — setup

- [`SETUP.md`](./setup/SETUP.md) — local environment setup, running all five services (`npm run dev`), and Supabase migrations (local vs. hosted).

## [`archive/`](./archive/)

Superseded, point-in-time documents kept for history — each has a banner explaining what
replaced it. Not part of the current-docs reading path; skip unless you specifically want
project history.
