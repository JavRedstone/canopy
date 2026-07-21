# Canopy: Product Idea

**Status:** this is the founding design spec: the target vision, not a build log. A lot
of it has since shipped as specified (dual-track BKT, the self-repairing sandbox loop,
run/submit, source citations); a real chunk is still deliberately deferred (the LLM
diagnosis layer, remediation lesson generation, transfer exercises, just-ahead-of-time
caching). For what's actually running today, verified against the code, see
[`USE_CASES.md`](./USE_CASES.md) and [`ROADMAP.md`](./ROADMAP.md); for how the built
half holds up against the learning-science literature, see
[`PEDAGOGY_EVALUATION.md`](./PEDAGOGY_EVALUATION.md).

## One-Line Pitch

**Codecademy, but the entire course is generated from *your* documents, and it reshapes itself around *your* mastery.**

## Concept

Learners get the familiar Codecademy-style experience (explanation panel, code editor, terminal, checkpoint-based exercises) but with two fundamental differences:

**1. Generated from your materials.** Instead of a fixed catalog built by a curriculum team, the platform ingests textbooks, research papers, course notes, and documentation, and generates the full interactive course from them. Any material can become a hands-on coding course: a grad-level course reader, internal engineering docs, a niche research area with no existing course.

**2. Mastery-driven, not completion-driven.** Codecademy tracks whether you finished a lesson. This platform tracks *concept-level mastery* (inferred from code submissions, test failures, hint usage, and time-on-task) and uses it to re-sequence lessons, generate remediation, and clear up confusion before it compounds.

Lessons are generated just-ahead-of-time: while a student works on lesson N, the system prepares the next **canonical** lesson from the stable course spine, so shared content feels instant. Mastery state drives the learner's route and separately generated support layers (remediation, extra examples, or concise variants) rather than rewriting canonical lessons.

---

## The Learner Experience

Two views, one course:

### 1. Textbook View (read mode)

The generated course is rendered as a continuous, navigable, **versioned textbook**: chapters follow the concept graph, each section containing the generated explanation, worked examples, and diagrams, with citations linking back to the source material sections it was generated from. Its course spine (learning outcomes, concept graph, required sections, and completed lesson versions) is canonical for that course version, so learners can reliably review, bookmark, cite, and share it. Personalization changes the recommended route and adds separately versioned support layers (extra examples, refresher sections, or concise alternatives); it never silently rewrites a learner's completed course.

Embedded throughout: **quick-check quizzes** (NotebookLM-style) and inline "Try it →" buttons that jump into the split view with the matching exercise loaded.

### 2. Split View (practice mode)

The Codecademy-style lab, entered from a "Try it" link or the lesson sequence:

- **Left panel:** the lesson: explanation, examples, instructions. Streams in immediately.
- **Center:** Monaco code editor showing only the student-facing code (see "Workspace visibility" in the Sandbox Layer; the full environment is larger than what's shown).
- **Right/bottom:** terminal with live test output streamed over WebSockets, plus a structured test-results panel.

**Run vs. Submit (CodeSignal/LeetCode model):**
- **Run** executes the *visible* test cases on demand: a per-test results panel shows pass/fail, expected vs. actual output, error traces, and runtime. Students can run as often as they like; runs are logged as behavioral signals (iteration patterns) but are not BKT observations.
- **Submit** executes the full evaluation: visible tests + the hidden suite + static/runtime analysis. Submissions are what generate mastery observations.

This separation keeps the feedback loop tight (run freely, fail cheaply) while keeping the mastery signal clean (submissions are deliberate attempts).

### Quick-Check Quizzes

Auto-generated quiz items in the NotebookLM mold: multiple-choice and short fill-in questions produced from the source material and lesson content, each tagged with the concept it tests. They appear at the end of textbook sections, between coding lessons, and as fast remediation checks after a mini-lesson.

Quizzes pull double duty:
- **For the learner:** low-stakes retrieval practice with instant feedback and an explanation for each answer (citing the source section).
- **For the mastery engine:** cheap, high-frequency observations of **conceptual understanding**. Each concept maintains two linked mastery tracks: `p(understand)` for recall/explanation and `p(apply)` for implementing the idea in code. Quiz observations update the former; coding checkpoints update the latter. The decision layer reads both rather than collapsing them into one score. Guess/slip parameters are calibrated per item type and item quality. Four options are a useful prior, not a fixed guess rate.

All interaction signals (checkpoint passes/failures, quiz answers, hint requests, and work patterns) feed the mastery engine, with only assessed responses directly updating a mastery track.

**Adaptation is visible and controllable.** When the route changes, the learner sees what changed and why (for example, “two attempts on token expiry inserted a 7-minute refresher”). Learners can defer a recommendation, return to the original sequence, or choose a concise versus full explanation. The platform keeps a learning-history view of inserted refreshers, skipped drills, and achieved outcomes.

---

## High-Level Architecture

```text
      Educational Materials (PDFs, textbooks, papers, notes)
                          |
                          v
            ┌───────────────────────────┐
            │ Knowledge Ingestion        │
            │ chunk → embed → store      │
            └────────────┬──────────────┘
                          |
                          v
            ┌───────────────────────────┐
            │ Supabase                   │
            │ Postgres + pgvector         │
            │ auth · storage · queues     │
            │ model + lesson cache       │
            └────────────┬──────────────┘
                          |
                          v
            ┌───────────────────────────┐
            │ Curriculum Planner         │
            │ concept graph + roadmap    │
            └────────────┬──────────────┘
                          |
                          v
            ┌───────────────────────────┐
            │ Lesson Generation Agent    │◄──────────────┐
            │ (just-ahead-of-time)       │               │
            └────────────┬──────────────┘               │
                          |                              │
              single-shot generation of:                 │
              explanation · starter code ·                │
              tests · hints · solution                    │
                          |                              │
                          v                              │
            ┌───────────────────────────┐               │
            │ Sandbox Provisioning       │               │
            │ warm base env + file mount │               │
            │ background validation      │               │
            │ (repair loop only on fail) │               │
            └────────────┬──────────────┘               │
                          |                              │
                          v                              │
            ┌───────────────────────────┐               │
            │ Interactive Sandbox        │               │
            │ editor + terminal + tests  │               │
            └────────────┬──────────────┘               │
                          |                              │
                          v                              │
            ┌───────────────────────────┐               │
            │ Mastery Engine             │───────────────┘
            │ concept-level tracking     │
            │ remediation triggers       │
            └───────────────────────────┘
```

---

## Core Components

### 1. Knowledge Ingestion

Accepts PDFs, text, and docs. Pipeline: parse → chunk → embed → store in Supabase Postgres with pgvector, with metadata linking chunks to source sections. Supabase provides the relational data store for curriculum, lessons, mastery state, and sandbox metadata, plus Auth, Storage, and background queues.

Retrieval serves two purposes:
- Grounding lesson generation in the actual source material (correct terminology, notation, and examples from *the student's* documents).
- Letting explanations cite back to the source ("see §4.2 of your textbook"), which builds trust in generated content.

### 2. Curriculum Planner

Takes a learning goal plus the ingested material and produces a **versioned canonical concept graph**, not just a module list: concepts, prerequisite edges between them, and modules sequenced along that graph.

```json
{
  "concepts": [
    { "id": "http-basics", "prereqs": [] },
    { "id": "rest-apis", "prereqs": ["http-basics"] },
    { "id": "jwt-auth", "prereqs": ["rest-apis"] }
  ],
  "modules": [ ... sequenced over the concept graph ... ]
}
```

The concept graph matters because the mastery engine tracks state *per concept*: when a student struggles, the system knows which prerequisite to revisit.

### 3. Lesson Generation Agent (Just-Ahead-of-Time)

Canonical lessons are generated one step ahead of the learner from the stable course spine. A canonical bundle is learner-independent and cacheable for everyone on the same course version; it is pinned once delivered. Personalization creates separate learner-scoped support layers instead of rewriting canonical lessons.

**Canonical lesson inputs:**
- Target concept(s) from the curriculum.
- Retrieved source-material chunks.
- Canonical course version and resolved environment requirements.

**Support-layer-only inputs:**
- The learner's mastery tracks (which prerequisites are solid or shaky).
- Recent assessed error patterns, support level, and any behavior-verified diagnosis.

Output: a complete **canonical or learner-scoped support** bundle in a single structured generation call:
- Explanation + examples (streamed to the UI immediately).
- Starter code.
- Workspace manifest (file visibility + editable regions, which parts the student sees and can edit vs. hidden scaffold).
- Checkpoint tests.
- Hidden evaluation test suite (edge cases and robustness checks, concept-tagged, never shown to the student).
- Quick-check quiz items (concept-tagged MCQ / fill-in, with per-answer explanations and source citations).
- Graduated hints.
- Reference solution.
- Environment requirement (which catalog environment it needs; triggers the environment-builder if none exists).

No agent loop on the happy path: one call produces the whole bundle.

### 4. Sandbox Layer (Provisioning, Validation, and Evaluation)

The sandbox serves three roles, all on the same warm-environment infrastructure:

**Role 1: Learning environment (fast path):**
- **Environment catalog:** a registry of pre-built base environments (e.g., `python-basic`, `python-fastapi`, `node`, `python-datasci` with Jupyter-style kernel), dependencies pre-installed, kept as warm containers/templates. Python lessons can declare package requirements; a controlled provisioning job downloads and locks those packages into a versioned Python environment before it is warm-pooled. Learner sandboxes never install packages or receive network access at runtime. The catalog is *extensible*: when the curriculum planner emits a sandbox requirement no base environment satisfies, an environment-builder agent generates the base image definition, builds it, validates it (install check + smoke tests), and registers it in the catalog. First lesson needing it pays the build cost once; it's warm-pooled thereafter.
- Generated lesson files are mounted into a warm environment, with no per-lesson image build on the common path. Provisioning time: ~1 second.
- **Workspace visibility (hidden scaffold):** the instantiated environment is always *larger* than what the student sees: like an LLM notebook where one cell is shown but the whole kernel state exists behind it. The lesson bundle includes a **workspace manifest** declaring, per file: `visible | hidden`, and per visible file: `editable regions`. Hidden scaffold (test harnesses, setup/teardown, helper modules, pre-loaded data, the app skeleton around the function being taught) is fully present and running in the sandbox, but the editor initially renders only the focus area: a LeetCode-style function stub, a single module of a larger app, or one notebook section. This keeps exercises *realistic* while staying *focused*. A progressive-disclosure “Inspect the workspace” view can reveal the surrounding system read-only when it helps the learner connect the focused task to the larger application. The manifest also drives evaluation: edits are only accepted within editable regions.

**Role 2: Content validation (quality gate):**
- **Background validation:** while the student reads the explanation, the reference solution runs against the generated tests. Most lessons pass first try.
- **Repair path (only on validation failure):** the agent receives the failing test output, patches the lesson files, and re-validates. This self-repair loop is the quality guarantee: no student ever sees a broken exercise, because every exercise proved itself before release.

**Role 3: Student evaluation (mastery signal generation):**
An isolated evaluator sandbox receives the submitted snapshot and runs deeper evaluation that feeds the mastery engine; hidden-test artifacts never enter the learner's interactive sandbox:
- **Hidden test suites:** each lesson bundle includes evaluation tests beyond the visible checkpoints: edge cases and robustness checks, concept-tagged like everything else. Passing visible tests but failing hidden edge cases is a distinct applied-skill signal (“works, but fragile”). Feedback names the robustness category and the relevant concept without revealing the hidden case, so the learner receives a fair next step rather than an opaque failure.
- **Static and runtime analysis:** linting, anti-pattern detection, and runtime behavior (does the solution work by accident, e.g., hardcoded values that happen to pass?) run automatically on submission.
- **Diagnostic probes:** when the LLM diagnosis layer forms a behavioral hypothesis, it can generate a targeted probe test and execute it against the student's code in the sandbox. The probe verifies the observed behavior (for example, “the current implementation does not reject an expired token”), not an unobservable claim about the learner’s mental model. The remediation UI presents the diagnosis as a supported hypothesis and shows the evidence.
- **Mastery verification exercises:** when `p(apply)` approaches the mastery threshold, the system can issue a short, hint-free **transfer exercise** in a fresh sandbox: the same concept in a new context or API shape, rather than a repeat of the familiar scaffold. This is the applied-skill check before marking a coding concept mastered.

Validated **canonical** lesson bundles are cached by course version and lesson definition: the first learner pays the generation cost and subsequent learners receive the same revision instantly. Learner-scoped support bundles are generated only when an accepted adaptation event calls for them and are never shared across learners.

**Security:** student and generated code run in isolated environments with no network, CPU/memory limits, execution timeouts, and read-only system filesystems. (Managed sandbox services like E2B/Modal are a drop-in alternative to self-managed Docker if time is short.)

### 5. Interactive Sandbox

- **Frontend:** Next.js, **Base UI** component primitives, Monaco editor, xterm-style terminal, lesson viewer with streaming, progress display.
- **Backend:** FastAPI, container orchestration, WebSockets for stdout/stderr streaming.
- Flow: student code → backend → isolated environment → run checkpoint tests → stream results → feed mastery engine.

### 6. Mastery Engine

Replaces the vague "Evaluation Agent" with a concrete, per-concept mastery model. Each concept exposes two linked learner-facing signals: conceptual understanding (`p(understand)`) and applied implementation (`p(apply)`).

**Signals tracked per concept:**
- Checkpoint pass/fail, and number of attempts before passing.
- Which tests failed (mapped to concepts via test metadata generated with the lesson).
- Hidden evaluation-suite results (visible-pass/hidden-fail = "works but fragile", a distinct, finer-grained observation).
- Quiz answers (high-frequency observations for `p(understand)`).
- Static/runtime analysis flags on submissions.
- Run-iteration patterns (frequency and progression of visible-test runs before submit; behavioral context, not a direct BKT observation).
- Hint usage depth and whether a pass was independent or supported.
- Time-on-task relative to expected, treated only as optional context.

**Concrete adaptation rules (demonstrable, not hand-wavy):**
- **Remediation trigger:** N failed attempts on the same checkpoint → generate a scaffolded sub-lesson targeting the specific failing concept (smaller exercise, more worked examples), inserted before retrying.
- **Prerequisite fallback:** repeated failure on a concept whose prerequisite mastery is low → route back to a refresher on the prerequisite.
- **Acceleration:** consistently independent first-attempt passes across a module → recommend skipping redundant drill lessons or choosing concise upcoming explanations; the learner can keep the full path.
- **Support signal:** high hint usage with eventual passes → offer more worked examples or a scaffolded next lesson for that concept. Help-seeking is recorded as support level, not treated as a penalty.
- **Transparent adaptation:** every inserted refresher, skip recommendation, or explanation variant has a visible reason and a learner choice to accept, defer, or return to the canonical route.

#### The Mastery Model (ML specification)

**Model: per-concept Bayesian Knowledge Tracing (BKT).** Each concept in the curriculum graph gets two linked BKT instances: `p(understand)` for conceptual understanding and `p(apply)` for applied implementation. Quiz and explanation checks update the first; coding checkpoints and transfer exercises update the second. Four parameters are maintained per concept and observation track:

- `p(L0)`: prior probability of initial mastery
- `p(T)`: probability of learning the concept on each practice opportunity
- `p(G)`: guess rate (passing a checkpoint without mastery)
- `p(S)`: slip rate (failing a checkpoint despite mastery)

**Update rule.** On each relevant observation for a concept and its matching track:

```text
For the relevant track (`p(understand)` or `p(apply)`), let `p(L)` below refer to that track. If correct:
  p(L|obs) = p(L)(1 − p(S)) / [ p(L)(1 − p(S)) + (1 − p(L)) p(G) ]
If incorrect:
  p(L|obs) = p(L) p(S) / [ p(L) p(S) + (1 − p(L))(1 − p(G)) ]

Then apply learning:
  p(L) ← p(L|obs) + (1 − p(L|obs)) · p(T)
```

**Concept ↔ exercise mapping (Q-matrix).** Every generated checkpoint test is tagged with the concept IDs it exercises, emitted by the Lesson Generation Agent as part of the lesson bundle. A checkpoint result therefore updates exactly the concepts it tests: this is what makes failure diagnosis specific ("token validation" failed, not "the JWT lesson").

**Signal enrichment beyond correct/incorrect:**
- Hint usage records whether a successful observation was independent or supported; it does not discount mastery or penalize asking for help.
- Multiple attempts before passing are logged as failed assessed opportunities on the relevant track.
- Run patterns and time-on-task remain contextual signals only. They never lower a mastery probability or trigger adaptation by themselves.

**Parameter initialization (cold start).** No per-student training data exists on day one, so: `p(L0)` is set from curriculum position (higher for concepts whose prerequisites are mastered) plus an optional 3–5 question diagnostic at onboarding; `p(G)`/`p(S)` begin as conservative, track-specific priors and are calibrated from observed item performance; `p(T)` begins as a prior rather than a claim about the learner. Once real interaction data accumulates, parameters are refit per concept and observation track via EM on logged observations.

**Decision layer.** A concept declares which evidence it needs: conceptual-only concepts require `p(understand) ≥ 0.95`; coding concepts require both `p(understand) ≥ 0.95` and `p(apply) ≥ 0.95`, including a transfer exercise. The adaptation rules above read directly off the relevant track: remediation triggers when it stays below threshold after N opportunities; prerequisite fallback triggers when a concept fails while a prerequisite's matching track is low; acceleration triggers when the relevant track crosses threshold quickly and independently.

**Why BKT and not an LLM or deep model.** Recent evaluations show specialized knowledge-tracing models beat LLMs at predicting student performance while being orders of magnitude faster and cheaper: the LLM's job is generating content and tagging it with concepts, not being the tracker. Deep models (DKT/SAKT) outperform BKT on benchmark AUC but need substantial interaction data we won't have at launch; BKT is interpretable (each `p(understand)` and `p(apply)` is directly explainable to the learner), works from the first interaction, and has a clean upgrade path: log every observation in a KT-standard schema `(user, concept, track, timestamp, correct, support_level, attempts)` so a DKT/SAKT model can be trained as a drop-in replacement once data volume justifies it.

#### LLM Diagnosis Layer (the likely "why" behind the numbers)

BKT tracks *how much* a student knows; it cannot see *why* they're failing, because it only observes correct/incorrect. The richest signal in the system (the student's actual code, error output, and the diffs between attempts) is invisible to it. An LLM diagnosis layer closes that gap.

**Trigger-gated invocation.** The diagnosis LLM runs only when a BKT decision rule fires (remediation trigger or support signal), never on routine submissions. Cost scales with struggle, which is exactly when analysis is worth paying for; happy-path learners incur zero diagnosis cost.

**Input:** the target concept, the lesson content, the student's failed submissions with test output, and diffs between consecutive attempts.

**Output (a structured behavioral diagnosis hypothesis):**

```json
{
  "hypothesis": "The current implementation validates the JWT signature but does not check the expiry claim",
  "evidence": ["attempt 2 diff shows exp claim read but unused", "test_expired_token fails in all attempts"],
  "actual_failing_concept": "jwt-auth",
  "remediation_directive": "Scaffolded exercise isolating token lifecycle: issue → validate → expire"
}
```

**Probe verification.** Before a diagnosis is acted on, the underlying code behavior can be verified in the sandbox: the diagnosis layer generates a targeted probe test for its hypothesis and runs it against the student's submission (see Sandbox Role 3). The UI describes the result as a supported hypothesis, not a claim about the learner's private reasoning. Behavior-verified hypotheses can drive targeted remediation; unverified ones fall back to generic remediation.

**Two consumers of the diagnosis:**
1. **The Lesson Generation Agent** uses the remediation directive to generate a mini-lesson targeting the observed behavior, not a generic easier version of the same lesson. This is the difference between "let's try that again, slower" and "your current implementation does not check expiry: here's an exercise isolating token lifecycle."
2. **Recommendation routing, not observation rewriting:** if the diagnosis suggests a prerequisite gap (for example, the JWT checkpoint failed but the likely issue is HTTP headers), it recommends a prerequisite refresher. The original checkpoint result remains immutable and attributed to its declared concept; the diagnosis is stored separately with its evidence and confidence.

**Cold-start synergy.** Because concepts are generated fresh from each uploaded document, no concept ever has historical interaction data: the permanent cold-start case where semantic understanding is most valuable. The LLM layer compensates for exactly the situation where statistical models are weakest, while BKT handles the high-frequency tracking where LLMs are slowest and least accurate.

**Division of labor, summarized:** BKT is the cheap, always-on instrument panel; the LLM is the specialist called in when a warning light comes on.

**Storage.** `mastery(user_id, concept_id, p_understand, p_apply, opportunities, last_update)` in Supabase Postgres, plus an immutable append-only `observations` log and separately stored diagnosis hypotheses for refitting, audit, and future model upgrades.

**Signature demo moment:** fail the JWT exercise twice → watch the platform generate and insert a scaffolded "token validation basics" mini-lesson, live, with the concept's `p(apply)` visibly updating, the evidence-based behavioral hypothesis shown, and the remediation rule firing.

---

## Technology Stack

- **Frontend:** Next.js, React, **Base UI**, Tailwind CSS, Monaco, WebSockets.
- **Backend:** FastAPI, Docker SDK (or managed sandboxes: E2B / Modal), Supabase Queues (PGMQ) for generation and validation jobs.
- **AI (provider adapter layer):** all model calls go through a single internal interface (e.g., `LLMAdapter` with `generate_structured()`, `stream()`, `embed()`), so no agent talks to a vendor SDK directly. Primary target: **AWS Bedrock** (Claude, or other Bedrock-hosted models), but swapping to Azure OpenAI, the OpenAI API, or a local model is a one-file change per provider, not a refactor. Each agent (planner, lesson generator, diagnosis, repair loop) declares the capability it needs (structured output, streaming, long context) rather than a model name; the adapter maps capabilities to configured models per environment. Embeddings go through the same adapter (Bedrock Titan/Cohere embeddings, or any provider), keeping PgVector provider-neutral.
- **Data platform:** **Supabase**: Postgres + pgvector (users, curriculum, lessons, mastery state, cache, and source embeddings), Auth, Storage for uploads/artifacts, and Queues for background jobs. Row Level Security protects learner-owned records and files.
- **Deploy:** AWS: ECS Fargate for the app and generation workers; sandboxes on EC2 with a warm container pool (or a managed sandbox service like E2B/Modal if operating the pool isn't worth the time). Azure Container Apps remains a fallback if the provider choice changes.

---

## One-Week Build Plan

**Historical: this was the original week-one plan, written before the build started.**
The actual build tracked it closely for the ingestion/planner/sandbox/mastery core, but
diverged in two directions: it went *further* on environment breadth than planned here
(`python-ml`, `cpp`, and `c` sandboxes shipped, not just `python-basic`/`python-fastapi`;
see [`../architecture/SANDBOX_ARCHITECTURE.md`](../architecture/SANDBOX_ARCHITECTURE.md)),
and added features this plan didn't anticipate (a completion certificate, free course
sharing/cloning, quiz Markdown/LaTeX rendering). It deliberately did *not* build the LLM
diagnosis layer, remediation generation, or transfer exercises described below. Those
remain the highest-value unbuilt work per [`PEDAGOGY_EVALUATION.md`](./PEDAGOGY_EVALUATION.md).

**Days 1–2: Foundations.**
- LLM adapter layer: provider-agnostic interface (`generate_structured`, `stream`, `embed`), Bedrock provider implemented first, capability-based model config.
- Ingestion pipeline: PDF parse → chunk → embed → Supabase pgvector, with source-section metadata.
- Supabase schema and migrations: Auth-linked profiles, curriculum/concept graph, lesson cache, `mastery`, `observations`, Row Level Security policies, Storage buckets, and PGMQ queues.
- Curriculum Planner: goal + material → concept graph with prerequisite edges → module roadmap.
- Environment catalog: base images built and warm-pool orchestration working (`python-basic`, `python-fastapi`); controlled PyPI package provisioning resolves and locks lesson requirements into versioned Python environments before warm-pooling. The catalog registry schema is in place (environment-builder agent can land later; catalog design shouldn't assume a fixed set).

**Days 3–4: Generation pipeline.**
- Lesson Generation Agent: single-call structured lesson bundle (explanation, starter code, workspace manifest, concept-tagged tests, hidden evaluation suite, quiz items, hints, solution).
- Sandbox provisioning: file mount into warm env with manifest-driven visibility, background validation, repair loop on failure.
- Run/Submit execution paths: visible-test runner with per-test structured results; full evaluation on submit.
- Evaluation harness: hidden-suite execution + static/runtime analysis on student submissions, results emitted as concept-tagged observations.
- Lesson caching keyed on (concept, mastery profile band).
- Just-ahead-of-time scheduler: generate lesson N+1 during lesson N.

**Day 5: Mastery engine.**
- Dual-track BKT implementation per the spec above: conceptual quiz observations feed `p(understand)` and coding checkpoints feed `p(apply)`, with support level recorded but never penalized.
- Quiz observations flowing into the conceptual track with item-type-specific parameters.
- Adaptation rules live: remediation trigger, prerequisite fallback, acceleration, support signal, and transparent learner control.
- LLM diagnosis layer: trigger-gated behavioral-hypothesis analysis feeding structured directives to remediation generation, while preserving immutable checkpoint observations.
- Remediation lesson generation path (scaffolded sub-lesson insertion).
- Hint-free transfer-exercise path before a coding concept is marked mastered.

**Days 6–7: Learner experience + hardening.**
- Textbook view: canonical, versioned chapter/section rendering off the concept graph, embedded quizzes, source citations, "Try it →" jumps into split view, and visible adaptation history.
- Split view: streaming lesson viewer, Monaco editor with editable-region enforcement and progressive workspace inspection, Run/Submit buttons with per-test results panel, WebSocket terminal.
- Per-concept dashboard showing separate conceptual-understanding and applied-implementation signals, plus learner controls for adaptation recommendations.
- End-to-end flow testing with at least two real source documents from different domains.
- Sandbox security hardening: no-network containers, CPU/memory limits, timeouts, read-only system FS.
- Observability: generation latency, validation pass rate, repair-loop frequency (the "X% of lessons needed self-repair" stat is itself a compelling metric to surface).

**Deferred (post-week roadmap), still deferred today unless noted:**
- Environment-builder agent for fully automated catalog expansion (the catalog is still
  manually curated behind the same registry interface,
  `services/sandbox_runner/sandbox_runner/runner.py`, now with six environments instead
  of the original two).
- DKT/SAKT upgrade for the mastery model once observation data accumulates; EM refitting of BKT parameters.
- Multi-language *content* (course text in languages other than English), not to be
  confused with the multi-language sandbox *environments*, which shipped
  (`python`, `python-ml`, `cpp`, plus `javascript`/`go` in the standalone playground).
- Instructor analytics dashboard; cross-student lesson-quality learning (a lesson that
  triggers remediation for many students gets regenerated for everyone); citations
  linking explanations back into source PDF pages.

---

## Why This Matters

Existing AI education tools generate *content*. Codecademy provides *hands-on environments* but only for a fixed, human-built catalog. This platform is the intersection neither side covers:

- **Any document becomes a hands-on course**: generation grounded in the learner's own materials.
- **Mastery, not completion**: the course tracks what the learner actually understands
  versus can apply, separately, instead of a single finished/not-finished flag.
- **Trustworthy by construction**: every exercise validates itself (and repairs itself) before a learner sees it.
- **A real takeaway**: a certificate and a PDF coursebook a learner keeps, not a session
  that stops existing when the tab closes.

This is also the [OpenAI Build Week](../demo/HACKATHON.md) submission's core bet: the
judging criteria reward a complete product experience with a clear user and real impact,
not a technical concept demo: see [`MARKET_EXPLORATION.md`](./MARKET_EXPLORATION.md) for
how that shapes who this is being built and demoed for first.

The agentic loop, restated:

```text
Your documents → concept graph → just-ahead-of-time lessons
      → self-validating sandboxes → mastery signals
      → the course reshapes itself → better next lesson
```
