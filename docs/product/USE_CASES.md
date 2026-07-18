# Use cases — reference

**Purpose:** a side-by-side reference of the plausible use cases for Canopy, each
checked against what the product can *actually do today* (2026-07-18) rather than
what the plan describes. This is not a recommendation — see
[`MARKET_EXPLORATION.md`](./MARKET_EXPLORATION.md) for the business case and
[`DEMO.md`](../demo/DEMO.md) for the one use case that's been scripted into a demo. This doc
exists because several of these use cases share a persona and a pitch sentence but
diverge hard on what they'd actually require from the current codebase.

"Feasibility today" below is graded against the real implementation, verified in code
(schemas, sandbox, ingestion, auth model) — not against the product plan's intent.

## Structural gaps that affect every use case below

Read this section first — it applies across the board, so it isn't repeated per row.

- **No org/team/multi-seat model.** `profiles`/`courses` are single-owner
  (`owner_id = auth.uid()`, one row, one person). There is no "assign this course to a
  team," no manager/admin view, no cohort progress reporting. Every use case involving
  a manager, instructor, or DevRel team distributing a course to *other people* needs
  this layer and doesn't have it — today, the person who uploads the source is the
  only person who can ever see or run the resulting course.
- **Sandbox executes Python only.** Hard-locked in two places: the lesson-workspace
  file-path schema (`_SAFE_PY_PATH` regex in `services/worker/worker/lesson_schema.py`)
  and the sandbox runner's `environment_id: Literal["python-basic"]`
  (`services/sandbox_runner/sandbox_runner/main.py`). No SQL, JS/TS, Go, etc. execution
  exists or is close to existing.
- **No repository/codebase ingestion.** Sources are uploaded one file at a time
  (PDF/Markdown/plain text, ≤6MB) and attached to a course by `source_ids`. Multiple
  files per course works; a live GitHub repo, a folder tree, or "watch this repo for
  changes" does not exist. `DEMO.md` already scopes around this by hand-curating a
  fictional file packet — that pattern generalizes to any use case below, but it's manual
  curation each time, not an integration.
- **Source parsing is prose-oriented.** Non-markdown text (which is what a code excerpt
  or config file would be uploaded as) gets a single generic `section="Document"` label
  and naive character-count chunking (`services/worker/worker/parsing.py`) — no
  per-file identity, no function/line-boundary awareness. Citations now show the real
  excerpt (see the citation-viewer work earlier in this doc's history), but a citation
  into a code file will look worse than one into prose.
- **No data-residency/deployment story yet.** Everything runs against one shared
  Supabase project and one shared LLM Gateway; there's no private-deployment or
  per-tenant isolation option. `MARKET_EXPLORATION.md` flags this as a required answer
  before a serious enterprise pilot — it's unresolved.

## Quick comparison

| Use case | Persona | Source material | Org/team layer needed? | Sandbox language needed | Feasibility today |
|---|---|---|---|---|---|
| [Internal API/SDK onboarding](#1-internal-apisdk-onboarding) | New engineer, onboarding | Internal docs, ADRs, code excerpts, PRs | Yes | Ideally matches the real stack (often not Python) | Partial |
| [Framework/platform migration](#2-frameworkplatform-migration) | Existing engineer adopting a new version | Migration guide, release notes, before/after code | Yes | Matches the framework's language | Partial |
| [Data & analytics enablement](#3-data--analytics-enablement) | Analyst | Data dictionary, SQL patterns, sample data | Yes | SQL (not supported at all) | Weak |
| [Technical partner certification](#4-technical-partner-certification) | External partner/integrator | Public API docs, integration guide | Yes, plus external-identity handling | Matches the partner API's language | Partial |
| [Niche computational course](#5-niche-computational-course-instructor-led) | Grad student / course participant | Course reader, paper set, methodology guide | Yes (instructor distributes to students) | Python (common for these) | Partial |
| [Advanced self-directed learner](#6-advanced-self-directed-learner) | Individual technical learner | Paper, docs, textbook chapter (PDF/Markdown) | No — single user by design | Python | **Strong** |

## 1. Internal API/SDK onboarding

**Persona:** a new or existing engineer who needs to work with a company-internal API,
SDK, or service (`MARKET_EXPLORATION.md`'s primary market; `DEMO.md`'s Maya).

**Workflow:** upload a service overview, an ADR, a code excerpt, and a recent PR as
separate Markdown/text files; set the goal to something like "safely add validation for
an expired authorization hold"; the learner reads source-cited lessons and does a lab
that edits one function inside a larger read-only file.

**What already works:** multi-file source packets (`source_ids: list[UUID]`), the
visible/inspectable + `editable_regions` workspace split needed for "edit one function
in a bigger file," real clickable citations back to the uploaded excerpt.

**What's missing:** the org/team layer (there's no way for an engineering manager to
assign this course to five new hires and see their progress — today only the uploader
has any course at all); the real code excerpt is very likely not Python, and the
sandbox can't run anything else, so the packet has to be adapted to a Python-equivalent
example rather than the team's actual code; no repo ingestion, so every new API surface
needs a manually curated file packet.

**Open question:** is a Python-only lab still convincing when the target audience's
actual code is TypeScript/Go/Java? This is the single biggest fit question for this use
case specifically, since it's the one `DEMO.md` is built around.

## 2. Framework/platform migration

**Persona:** an engineer who needs to move code across a breaking framework version.

**Workflow:** upload release notes, a migration guide, and before/after code samples;
the course teaches the new pattern and a lab makes the learner fix code that uses the
deprecated approach.

**What already works:** same multi-file ingestion and editable-workspace mechanics as
#1 above — this is architecturally the same shape of use case.

**What's missing:** same org/team gap; same language constraint (a migration lab is
only faithful if the sandbox runs the framework's actual language, which is Python-only
today — this rules out most JS-framework, mobile, or non-Python backend migrations
without translating the exercise into an unrelated language).

## 3. Data & analytics enablement

**Persona:** an analyst learning a governed data dictionary, SQL patterns, and
data-quality checks.

**Workflow:** upload a data dictionary and sample-data documentation; labs would have
the learner write and run SQL queries against safe sample data.

**What already works:** source ingestion and citation viewing work the same as any
other prose/markdown source.

**What's missing:** the actual lab mechanic — there is no SQL execution environment,
no sample-database sandbox, and no data-platform integration at all. This isn't a small
gap; it's a different sandbox from the one that exists (Python subprocess execution vs.
a scoped database connection). Production data must also never enter a learner sandbox,
which is a second design problem on top of the missing execution environment. Of
everything in this doc, this is the farthest from what's built.

## 4. Technical partner certification

**Persona:** an external partner/integrator engineer learning a company's public
partner API.

**Workflow:** upload the supported integration path's docs; labs simulate calling the
partner API and handling its error cases.

**What already works:** the same ingestion/citation/workspace mechanics as #1 and #2.

**What's missing:** everything #1 and #2 are missing, plus this one adds external
identity — partners aren't the same tenant as the company running Canopy, and there's
no concept of an external/guest account, license-gated access, or per-partner reporting
today. This use case inherits the org/team gap and adds a harder version of it.

## 5. Niche computational course (instructor-led)

**Persona:** a grad student or course participant in a niche/rapidly-changing technical
course; the instructor is the one building the course
(`MARKET_EXPLORATION.md`'s third audience).

**Workflow:** an instructor uploads a course reader, paper set, or methodology guide;
students go through the resulting course and labs.

**What already works:** PDF and Markdown ingestion (the natural format for a course
reader or paper), multi-file source packets, Python labs (a natural fit for
computational coursework), citations back to the reader.

**What's missing:** the org/team gap again — an instructor distributing one course to a
class of students has no mechanism to do that today; each student would need to be the
`owner_id` of their own independently-created course from the same uploaded material,
which also means paying the generation cost once per student rather than once per
class. Licensing/rights to the course reader is also an open question this doc doesn't
resolve (see `MARKET_EXPLORATION.md`'s "source material has ownership or licensing
restrictions" risk).

## 6. Advanced self-directed learner

**Persona:** an individual learning a specialized library, research technique, or
technical domain from papers/docs on their own
(`MARKET_EXPLORATION.md`'s explicit secondary market — "not the best first market").

**Workflow:** upload a paper or library's documentation (e.g. a scikit-learn chapter);
set a goal like implementing an algorithm from scratch; work through labs solo. This is
close to the existing [`SAMPLE_COURSES.md`](./SAMPLE_COURSES.md) examples.

**What already works:** everything — this is the one use case that needs no org/team
layer (single user, single course, by construction), fits the Python-only sandbox
without translation, and only needs PDF/Markdown/text sources, which is exactly what
ingestion supports today. It's also the use case `MARKET_EXPLORATION.md` explicitly
says *not* to lead the business on, because NotebookLM/ChatGPT are lower-friction
substitutes for a solo learner who doesn't strictly need validated labs.

**The tension worth naming:** this is the best-supported use case in the codebase today
and the one the business case says is the weakest wedge. Every use case with a stronger
business case (#1, #2, #4, #5) requires the org/team layer that doesn't exist yet, and
several also fight the Python-only sandbox. That gap — between "what's easiest to build
on top of today" and "what the market analysis says is defensible" — is the core
uncertainty this doc was written to make visible, not resolve.
