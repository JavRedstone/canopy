# Competitive differentiation

A quick, scannable reference for "why not just use X" — the reasoning behind this table
lives in [`MARKET_EXPLORATION.md`](./MARKET_EXPLORATION.md) (market map, full
competitive landscape, risks) and [`USE_CASES.md`](./USE_CASES.md) (what's actually
built vs. planned, verified against the code). This doc distills those into one table;
it isn't a separate source of truth.

## The core claim

Canopy turns trusted technical material into an implementation-focused coding course, not
merely a summary or a fixed catalog course. A paper, technical documentation, textbook
chapter, or curated internal packet becomes cited lessons, checks for understanding,
executable labs, and a durable Coursebook.

AI makes technical information abundant, but reading technical material is not the same
as understanding it, and understanding is not the same as implementation. Canopy closes
that gap with a source-grounded path from explanation to demonstrated application.

| | Fixed, human-built catalog | Learner-selected source material |
|---|---|---|
| **Read, watch, or ask questions** | Coursera, Udemy, YouTube | NotebookLM, ChatGPT |
| **Structured course with evidence of learning** | Codecademy, DataCamp, boot.dev | **← Canopy** |

## Head-to-head

Every row for Canopy is checked against the running code (`services/`), not the product
plan — see [`USE_CASES.md`](./USE_CASES.md) for exactly how each was verified. ✅ = does
this well today. ⚠️ = partial or in progress. ❌ = doesn't do this / not it's core value.

| Capability | **Canopy** | NotebookLM | ChatGPT / general chatbot | Codecademy / DataCamp | GitHub Copilot / Cody |
|---|---|---|---|---|---|
| Learns from learner-selected primary material (papers, docs, textbooks, curated files) | ✅ | ✅ | ✅ (paste/upload) | ❌ fixed catalog | ⚠️ repo context, not a learning flow |
| Executable, hidden-test-graded practice | ✅ | ❌ | ⚠️ code execution exists, not curriculum-integrated or hidden-graded | ✅ fixed catalog only | ❌ |
| Multi-language sandbox (Python, Python/ML, C++, C, JS, Go today) | ✅ | — | ⚠️ depends on the chat client | ✅ | — |
| Citations grounded to your actual source excerpts, clickable to the real text | ✅ | ✅ | ⚠️ often unverifiable | — | ⚠️ shows search results, not curated citations |
| Coherent, ordered curriculum with a reusable Coursebook | ✅ | ✅ (Learning Guide) | ❌ one conversation at a time | ✅ fixed catalog | ❌ |
| Per-concept mastery, tracked separately for *understanding* vs. *applying* | ✅ (dual-track BKT) | ❌ | ❌ | ⚠️ completion-based, not concept-level | ❌ |
| Self-repairing generation — a lesson is sandbox-verified before a learner ever sees it | ✅ | n/a | n/a | n/a (human-authored) | n/a |
| Team/org course assignment, cohort progress reporting | ❌ **not built yet** | ❌ | ❌ | ✅ | n/a |
| Repo/codebase-wide ingestion (vs. curated file packets) | ❌ **not built yet** | n/a | n/a | n/a | ✅ this is its whole job |

## Reading the gaps honestly

Two rows above are real, current weaknesses, not competitor spin — both are tracked in
[`USE_CASES.md`](./USE_CASES.md#whats-still-missing):

- **No org/team layer.** Every course is single-owner today; sharing is Google-Docs-style
  cloning, not a live-shared course with a progress dashboard. That's fine for the
  individual-learner and one-link-to-many-learners use cases this product targets today
  (see `USE_CASES.md`), but it's the gap that would matter most for the B2B enablement
  direction sketched in `MARKET_EXPLORATION.md` §4 — Codecademy for Business already has
  this.
- **No repo ingestion.** Sources are curated files uploaded one at a time, not a
  connected GitHub repo. Copilot/Cody's whole value is repo-scale, always-current
  context; Canopy's is depth and verified practice on a deliberately bounded packet.
  These are different trade-offs, not a strict subset — but it's worth being honest that
  Copilot answers "what does this file do" faster than Canopy does today.

Where Canopy wins is the complete learning loop around material the learner selected:
source-grounded lessons, an ordered path, assessment, real coding practice, references,
and a Coursebook they can keep. The sandbox and separate understanding/application
mastery show that the outcome is not just a learner who read a source, but one who can
build with it.
