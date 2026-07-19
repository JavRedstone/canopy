# Competitive differentiation

A quick, scannable reference for "why not just use X" — the reasoning behind this table
lives in [`MARKET_EXPLORATION.md`](./MARKET_EXPLORATION.md) (market map, full
competitive landscape, risks) and [`USE_CASES.md`](./USE_CASES.md) (what's actually
built vs. planned, verified against the code). This doc distills those into one table;
it isn't a separate source of truth.

## The core claim

No competitor combines **generated from your own material** with **executable,
hidden-test-graded practice**. Competitors sit in one of those two cells, not both:

| | Passive content (read / quiz) | Executable, graded practice |
|---|---|---|
| **Fixed, human-built catalog** | Coursera, Udemy | Codecademy, DataCamp, boot.dev |
| **Generated from *your* material** | NotebookLM, Coursebox, ChatGPT | **← Canopy** |

## Head-to-head

Every row for Canopy is checked against the running code (`services/`), not the product
plan — see [`USE_CASES.md`](./USE_CASES.md) for exactly how each was verified. ✅ = does
this well today. ⚠️ = partial or in progress. ❌ = doesn't do this / not it's core value.

| Capability | **Canopy** | NotebookLM | ChatGPT / general chatbot | Codecademy / DataCamp | GitHub Copilot / Cody |
|---|---|---|---|---|---|
| Learns from *your own* material (docs, code, PRs) | ✅ | ✅ | ✅ (paste/upload) | ❌ fixed catalog | ✅ (searches it) |
| Executable, hidden-test-graded practice | ✅ | ❌ | ⚠️ code execution exists, not curriculum-integrated or hidden-graded | ✅ fixed catalog only | ❌ |
| Multi-language sandbox (Python / JS / Go today) | ✅ | — | ⚠️ depends on the chat client | ✅ | — |
| Citations grounded to your actual source excerpts, clickable to the real text | ✅ | ✅ | ⚠️ often unverifiable | — | ⚠️ shows search results, not curated citations |
| Coherent, ordered curriculum (not isolated Q&A) | ✅ | ✅ (Learning Guide) | ❌ one conversation at a time | ✅ | ❌ |
| Per-concept mastery, tracked separately for *understanding* vs. *applying* | ✅ (dual-track BKT) | ❌ | ❌ | ⚠️ completion-based, not concept-level | ❌ |
| Self-repairing generation — a lesson is sandbox-verified before a learner ever sees it | ✅ | n/a | n/a | n/a (human-authored) | n/a |
| Team/org course assignment, cohort progress reporting | ❌ **not built yet** | ❌ | ❌ | ✅ | n/a |
| Repo/codebase-wide ingestion (vs. curated file packets) | ❌ **not built yet** | n/a | n/a | n/a | ✅ this is its whole job |

## Reading the gaps honestly

Two rows above are real, current weaknesses, not competitor spin — both are tracked in
[`USE_CASES.md`](./USE_CASES.md#structural-gaps-that-affect-every-use-case-below):

- **No org/team layer.** Every course is single-owner today. This blocks the B2B use
  cases that are the actual business case (see `MARKET_EXPLORATION.md` §4) until it's
  built — Codecademy for Business already has this.
- **No repo ingestion.** Sources are curated files uploaded one at a time, not a
  connected GitHub repo. Copilot/Cody's whole value is repo-scale, always-current
  context; Canopy's is depth and verified practice on a deliberately bounded packet.
  These are different trade-offs, not a strict subset — but it's worth being honest that
  Copilot answers "what does this file do" faster than Canopy does today.

Where Canopy wins is the two rows nothing else on this table has *at all*: a real
sandbox that grades against hidden tests, and mastery tracked as a signal separate from
"did you finish." Lead with those — see `MARKET_EXPLORATION.md` §9 for the exact
positioning language and the harder version of these "why not just use X" questions.
