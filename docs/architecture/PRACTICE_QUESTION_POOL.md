# Practice Question Pool — build doc

> Status: **design, pre-implementation.** Captures the decisions reached so far plus a
> concrete build plan. Settled decisions are marked ✅; open decisions needing a call are
> marked ❓ with a recommendation.

## 1. Why / current state

Two roadmap items overlap here (`docs/product/ROADMAP.md`):

- **Practice mode** — "a low-stakes way to drill concepts outside of graded flow."
- **Changing questions / question bank** — "draw from a pool so repeated attempts and
  reviews don't reuse the same questions."

"Practice question pool" is the intersection: a **per-concept bank of drill questions** the
learner can practice against, low-stakes, non-repeating.

**What exists today.** There is no separate practice system. What we call practice questions
are `quiz_items` co-generated with each lesson in a single structured call
(`services/worker/worker/lesson_agent.py` → `_generate_content` → `LessonContentBundle`):

- Small and fixed at plan time: 1–2 (coding), 2–3 (conceptual), 3–4 (assessment). Capped at
  8 per lesson (`services/worker/worker/lesson_schema.py`).
- Types: `mcq` / `multi_select` / `fill` / `short_answer`, with per-option explanations,
  accepted answers, or a hidden rubric, plus source citations.
- "Practice" vs "mastery" is only a **convention** — ordering + an inline `{{quiz:N}}` marker
  (`INTERLEAVE_INSTRUCTION`), not a schema field.
- **Every** answer is graded and writes an `understand`-track observation → BKT mastery
  (`quiz.py` + `repository.record_quiz_response`). No low-stakes path exists.

The three gaps a pool closes: **fixed/small**, **no rotation/variety**, **all graded**.

## 2. Decisions

### Settled ✅

- **Generate at plan time**, not at runtime. Pool questions carry answer keys / rubrics that
  must stay server-side and be withheld; plan-time amortizes cost across all learners and
  gives the placement/mastery machinery a stable set to reason about. (The runtime lesson
  helper is learner-facing and must never hold answer keys.)
- **Its own generation pass**, reusing the existing `QuizItem` + validate + checkpoint
  machinery — *not* folded into the lesson-content call. This matches the codebase's existing
  two-pass split (content vs. sandbox-validated coding artifacts, `lesson_build.py:1`), and
  unlocks the three properties folding would forfeit:
  1. **Independent top-up** ("generate 10 more for this concept") — the defining feature of a
     *pool*; impossible if welded to the prose call.
  2. **Failure isolation** — a bad distractor in question #14 must not force regenerating good
     prose.
  3. **Quality** — a focused call prompted specifically for variety / difficulty spread /
     non-overlap / distractor quality beats one oversized structured output.
  4. **Cadence/model independence** — can run on a cheaper model and/or backfill async off the
     critical render path.
- **Model: `gpt-5.6-luna`** (the builder tier), behind a **dedicated `practice_pool` gateway
  task** so it's independently tunable. Rationale: the pool is the same *kind* of work the
  builder already does for `quiz_items`, and it runs **per concept** (cost-sensitive) — the
  same stakes×frequency profile that put `lesson_build` on Luna. Reserve `gpt-5.6-sol` as a
  per-task **dial-up** if eval surfaces weak distractors / near-duplicates, or if the build is
  async (Sol's latency is then free). Not mini — mini is the no-answer-key helper tier.
- **Scope: both concept- and course-level (resolved 2026-07-19).** Practice is entered two ways
  over the *same* course-level machinery:
  - **Concept-level** — a "Practice this concept" panel on the concept page; scope = this one
    concept.
  - **Course-level** — a "Practice" tab on the course overview with a scope picker: *everything
    I've done so far* (default, progress-bounded), specific **modules**, or specific
    **lessons/concepts**. Un-reached / un-generated lessons show disabled so practice never
    spoils a lesson ahead of the learner.

  Both are the same request with different `scope` params; the concept panel is just a pre-filled
  single-concept scope.
- **Learner-chosen session options (resolved 2026-07-19).** What were internal calls (pool size,
  order, non-repeat) become a short pre-session config the learner sets: **scope**, **length**
  (N questions or endless), **order** (shuffle / weakest-first / course order), and **filter**
  (unseen only / include seen / **retry the ones I missed**). The engine takes this config as
  input and stays pure/deterministic.
- **Mastery effect: positive-only credit + struggle tracking (resolves Open #1, 2026-07-19).** A
  *correct* practice answer writes an `understand` observation tagged `assessment_kind='practice'`
  (high-guess params) that nudges BKT up **but is capped at ≈0.85** — practice can make a learner
  *proficient*, but the 0.95 "mastered" bar still requires graded quiz/coding evidence (the same
  0.85-vs-0.95 split as the placement plan). A *wrong* answer writes **no** mastery observation, so
  `p_understand` can never drop. Separately, **every** answer (right and wrong) is logged for
  struggle analytics — see the `practice_attempts` ledger in §3.2.

### Open ❓ (need a call before/while building)

1. **Generation timing.** ❓ *Recommend: separate async job* (`practice_pool_build`) enqueued
   after `lesson_build` finishes, so the lesson renders immediately and the pool backfills.
   Alternative: inline as a third step in `lesson_build` (simpler, but adds latency to first
   render).
2. **Pool size + top-up policy.** ❓ Suggest N ≈ 10–15 per concept initially, with a
   server-side top-up endpoint that appends another batch on demand.

*Resolved 2026-07-19:* mastery effect (positive-only, capped ≈0.85, + struggle ledger); storage
(dedicated `practice_items` table + `practice_attempts` rotation/struggle ledger, §3.2); scope
(both concept + course level); non-repeat (per-learner via `practice_attempts`).

## 3. Architecture

### 3.1 Generation pass (worker)

- New `PRACTICE_POOL_SYSTEM_PROMPT` + `generate_practice_pool(...)` in
  `services/worker/worker/lesson_agent.py`, producing a `list[QuizItem]` (reuse the existing
  `QuizItem` model and `QUIZ_KINDS_INSTRUCTION`; **omit** the `{{quiz:N}}` interleave
  instruction — pool items are standalone).
- **Ground on the finalized `explanation_markdown` + the same retrieved chunks** (via
  `citation_chunks(...)` from the concept's `citations_json`), mirroring how
  `generate_coding_artifacts` takes `lesson_explanation=content.lesson_content.explanation_markdown`.
  This makes pool questions test what the lesson *actually taught* and lets us pass the
  already-generated `quiz_items` in context to **avoid overlap** with them.
- Validate: citations ⊆ available chunks (reuse `validate_lesson_content`-style check),
  unique ids, plus new **variety/dedup** checks (no near-duplicate stems; a target spread
  across kinds and difficulty).

### 3.2 Storage

Target (recommended): migration adding `practice_items` keyed by `(course_version_id,
concept_id)`:

| column | purpose |
|---|---|
| `id`, `concept_id`, `course_version_id` | identity / scoping |
| `item_json` (jsonb) | the full `QuizItem` incl. grading material |
| `kind` | denormalized for filtering |
| `batch` / `created_at` | supports top-up batches + ordering |
| `times_served`, `times_correct` (optional) | per-item stats |

Per-learner rotation + struggle ledger: a dedicated **`practice_attempts`** table — one row per
answered practice question:

| column | purpose |
|---|---|
| `id`, `user_id` | identity / ownership |
| `course_version_id`, `concept_id`, `practice_item_id` | scoping + which question |
| `correct` (bool) | struggle signal |
| `created_at` | recency (rotation, "recently seen") |

This one table does triple duty: **non-repeat rotation** (prefer items with no / oldest row),
**per-learner struggle analytics** (accuracy per concept/item → weakest-first order, the "retry
my misses" filter, and later the `concept_struggling` → prereq-recommendation loop), and
**per-item difficulty** in aggregate (rolls up into the optional `times_served` / `times_correct`
above). Positive-only mastery is separate: a correct answer *also* writes a capped `practice`
observation (§2); a wrong answer touches only `practice_attempts`. RLS: rows are owned by the
learner (`user_id`) and scoped like `observations` — the API writes one row per answered question.
The pool itself (`practice_items`) is service-written on the worker and read scoped by course
ownership, as elsewhere.

MVP shortcut (if we defer the migration): `Assessment.practice_items: list[QuizItem]` in
`lesson_schema.py` + `packages/contracts/schemas/lesson-bundle.schema.json`, patched into the
bundle before `apply_lesson_bundle`. Strip it in `bundle_view` exactly like `quiz_items`.

### 3.3 Serving + grading (API — `services/api/app/routers/courses.py`)

Practice is **course-scoped** with a filter; the concept page just pins the scope to one concept.

- `GET /courses/{id}/practice?scope=done|modules|concepts&ids=…&count=N&order=shuffle|weakest|course&filter=unseen|all|missed`
  → fans out over the selected concepts' pools and returns N **previews** (answers stripped —
  reuse the `QuizItemPreview` stripping already in `lesson_bundle.py` / `bundle_view`), selected by
  the pure engine (§3.4). `scope=done` (default) is bounded by the learner's progress so it never
  serves an un-reached lesson. The concept-page panel calls this with `scope=concepts&ids=<slug>`.
- `POST /courses/{id}/practice/{item_id}/answer` → grade with the **existing**
  `grade_quiz_answer(item, answer, grader)` (`quiz.py`) — pure and kind-complete, reused as-is.
  **Practice path:** do NOT call `record_quiz_response` and do NOT count against the attempt cap.
  Always write a `practice_attempts` row; on a **correct** answer *additionally* write the capped
  positive `practice` observation (§2). Reveal grade + explanation immediately (no
  `withhold_answer`). Returns `QuizGradeResponse`.
- Optional `POST /courses/{id}/practice/refresh` (or a `top_up` flag) to trigger another generated
  batch for a concept when its pool is exhausted.

### 3.4 Selection / non-repeat engine (pure)

Mirror the codebase's pure-engine pattern (`mastery.py`, `placement.py`): a side-effect-free
`services/api/app/practice.py` that, given the in-scope pools (possibly spanning many concepts),
the learner's `practice_attempts` history, and the session config, returns the next batch. It
handles: cross-concept spread, `order` (shuffle / weakest-first by per-concept accuracy / course
order), `filter` (unseen / all / missed), and non-repeat (prefer items with no or oldest
`practice_attempts`). Deterministic given a seed → unit-tested in isolation; the repository owns
all IO.

### 3.5 UI (`apps/web`)

- Reuse `QuizQuestion` / `QuizSection` (`components/quiz.tsx`) — they already render
  `QuizItemPreview` and drive a grade call. Add a **practice variant** that hits the practice
  endpoint, reveals immediately, and loops (**Next question** / **New set**). Because credit is
  positive-only, a correct answer *may* refresh the mastery meter (it can only go up); a wrong
  answer does not.
- **Two entry points, one surface:**
  - **Concept-level** — a "Practice this concept" affordance on the concept page
    (`components/concept-detail.tsx`), opening the drill panel pinned to that concept.
  - **Course-level** — a "Practice" tab on the course overview (`components/course-detail.tsx`)
    with a **config panel**: scope (everything I've done / pick modules / pick lessons), length,
    order, and filter (incl. "retry the ones I missed"). Un-reached lessons appear disabled.
- Client calls in `apps/web/lib/api.ts`.

### 3.6 Model tiering (`services/llm_gateway`)

- Add `"practice_pool"` to the `GatewayTask` literal (`settings.py`).
- Add a `model_for` branch defaulting to the **builder** model with the same cross-provider
  fallback pattern as `lesson_repair` / `lesson_helper` (Azure → builder deployment, Bedrock →
  builder model, aws_openai → builder model). Env overrides: `openai_practice_pool_model` etc.
- Default `gpt-5.6-luna`; flip one task to `gpt-5.6-sol` if eval demands.

## 4. Prompt design notes

The pool's marginal-quality dimensions (what Luna must do well, where Sol would help):

- **Correct answer keys** — wrong keys are worse than wrong prose; this is graded material.
- **Plausible-but-wrong distractors** — the main lever for question quality; each option keeps
  its one-sentence `explanation_markdown`.
- **Non-overlap** — questions must not duplicate each other *or* the lesson's existing
  `quiz_items` (pass those in context).
- **Difficulty spread + kind mix** — deliberately span recall → application; mix kinds per
  `QUIZ_KINDS_INSTRUCTION`.
- **Grounding** — cite only real chunk IDs from the concept's retrieved context; empty
  citations when the concept has no sources (the existing zero-source policy).

## 5. Implementation plan

Milestones, most-leverage first:

- **M0 — pure selection engine + tests.** `practice.py` cross-concept next-batch selection with
  session config (order / filter / count) + non-repeat, unit tested (no IO). Cheapest,
  highest-leverage, mirrors `mastery.py`/`placement.py`.
- **M1 — generation pass.** `PRACTICE_POOL_SYSTEM_PROMPT` + `generate_practice_pool` in
  `lesson_agent.py`; validation (citations, uniqueness, dedup); worker test like
  `services/worker/tests/test_planner.py`. `practice_pool` gateway task.
- **M2 — storage + orchestration.** Table migration (or bundle field for the shortcut);
  wire generation (async `practice_pool_build` job, or inline in `lesson_build.py`);
  checkpoint separately.
- **M3 — API + `practice_attempts` migration.** Course-level `GET /courses/{id}/practice`
  (scope / order / filter / count) + `POST /courses/{id}/practice/{item_id}/answer` (positive-only:
  always write `practice_attempts`, capped `practice` observation on correct, no attempt-cap) +
  optional refresh. Preview-stripping reused from `lesson_bundle.py`.
- **M4 — UI.** Practice variant of `QuizSection`; **both** entry points — concept panel on
  `concept-detail.tsx` and a Practice tab + config panel on `course-detail.tsx` — plus
  `lib/api.ts` clients. Next-question / new-set.
- **M5 — quality.** Per-item stats, difficulty tags, top-up UX; consider Sol for the pool
  task if distractor/dedup eval is weak.

## 6. Testing

- Pure engine (`test_practice.py`, API side): selection prefers unseen, spreads kinds,
  deterministic.
- Generation (worker): validates a sample structured output — citations subset, unique ids,
  no near-duplicate stems, no overlap with the lesson quiz.
- Grading reuse: `grade_quiz_answer` already covered; add a route test asserting the
  low-stakes path writes **no** observation / leaves mastery unchanged.

## 7. Non-goals / risks / future

- **Non-goals (now):** changing the graded quick-check; certifying **mastered** (0.95) from
  practice — practice gives positive-only credit capped at ≈0.85; adaptive difficulty;
  non-English pools.
- **Risk:** answer-key correctness on Luna — mitigate with the dedup/validation pass and an
  easy Sol dial-up.
- **Future:** feed practice-derived signals into placement/forgetting features; per-item
  difficulty calibration from `times_correct`; spaced-repetition scheduling over the pool.
