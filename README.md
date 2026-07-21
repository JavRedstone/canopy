<p align="center">
  <img src="./docs/assets/canopy-logo.svg" alt="Canopy logo" width="120" />
</p>

# Canopy

**AI can explain anything. It can't tell you whether you actually learned it.**

Canopy turns any technical source (a paper, docs, your own notes) into a hands-on course of lessons and labs, then tracks whether you can actually *apply* what it teaches, not just whether you read it.

Local installation, environment configuration, and how to run all five services
(`npm run dev`) are all in [docs/SETUP.md](./docs/setup/SETUP.md).

## Built with GPT-5.6

GPT-5.6 is Canopy's own runtime model: the thing actually running when a learner uses
the product, not a build-time tool. It's routed through a provider-neutral gateway
(`services/llm_gateway/`) with per-task model tiering: the flagship "Sol" tier for the
one-shot, high-stakes calls (course outline planning, the agentic lab-repair loop),
and the faster "Luna" tier for the high-volume per-concept work:

- **Plans and writes every course.** Course outline planning, per-module concept
  generation, and per-lesson content and lab authoring are all GPT-5.6 structured-output
  calls (`services/worker/`), including inferring which coding-lab language (Python,
  Python ML/DL, or C++) fits a given source and goal, a call the learner never makes
  manually.
- **Generates and grades every assessment.** Quiz items, the low-stakes practice
  question pool, and short-answer rubric grading are all GPT-5.6 (`services/worker/`,
  `services/api/app/quiz.py`).
- **Drives the self-healing lab-repair loop.** When a generated lab's starter or
  reference solution fails its own sandbox run, GPT-5.6 gets the real pytest/doctest
  failure output back and repairs the specific files at fault, re-verified against the
  sandbox again before it ships, never trusted on a single attempt.
- **Powers the in-lesson learning helper.** The AI tutor a learner can ask for a hint,
  a simpler explanation, or a passage rewrite is GPT-5.6, prompted to guide without
  ever revealing the answer.

## Built with Codex

**Codex was the engineering tool that built the system around GPT-5.6**, used
throughout as an active collaborator rather than a one-off code generator:

- **Full-stack feature loops in one pass.** Non-trivial features (e.g. the practice
  question pool) went from a design doc through a Postgres migration, worker
  generation pass, API routes, and frontend UI in a single iterative Codex session,
  with the decision log kept alongside the code as it was made
  (`docs/architecture/PRACTICE_QUESTION_POOL.md`).
- **Live debugging from real evidence, not guesses.** When a lab build failed, Codex
  traced the failure from a live database row through the actual worker prompt and
  pytest traceback that caused it, rather than reasoning about it in the abstract.
  The fastest path we found working with Codex was always to hand it a concrete,
  reproducible failure to chase.
- **Product and design decisions, not just code.** Several real product calls were
  made through this collaboration and recorded as they happened: making coding-lab
  language selection automatic (inferred by the planner) instead of a manual dropdown;
  the practice pool's mastery-effect design (positive-only credit, capped below the
  graded-mastery bar); and the self-healing lab-repair loop's shape (generate → real
  sandbox run → feed back the actual failure → repair → re-verify) after the first
  version trusted a model's own claim of correctness too much.
- **Held to the same bar as the rest of the codebase.** Generated code went through
  the project's real test suites, not just visual review: see `services/api/tests/`,
  `services/worker/tests/`, and `services/llm_gateway/tests/` for the coverage that
  gated every merge.

**`/feedback` Codex session ID** for the thread where the majority of core
functionality was built: `019f7751-a64b-7192-bebf-b9a15311f54f`.

## Submission reference

Most important first. Full doc index: [docs/README.md](./docs/README.md).

| Doc | What it's for |
|---|---|
| [About / Devpost writeup](./docs/ABOUT_PUBLIC.md) | Inspiration, what it does, how it was built, challenges, what's next |
| [Technologies](./docs/TECHNOLOGIES.md) | The Devpost "Built with" tag list, and what each one actually does here |
| [Features](./docs/product/FEATURES.md) | Full feature checklist |
| [Setup](./docs/setup/SETUP.md) | Install + run instructions to test the repo |
| [Architecture](./docs/architecture/ARCHITECTURE.md) | System design across all five services |
| [Security](./docs/architecture/SECURITY.md) | Sandbox isolation and auth model |
| [Demo guide](./docs/demo/DEMO.md) | Demo narrative and judging-lens walkthrough |
| [Demo recording script](./docs/demo/RECORDING_SCRIPT.md) | Scene-by-scene script for the submission video |
| [Product idea](./docs/product/IDEA.md) | Founding design spec |
| [Market exploration](./docs/product/MARKET_EXPLORATION.md) | Market context |
| [Competitive differentiation](./docs/product/COMPETITIVE_DIFFERENTIATION.md) | How Canopy differs from existing tools |
