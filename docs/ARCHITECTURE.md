# Architecture — Adaptive, Source-Grounded Coding Courses

**Status:** Draft for implementation
**Audience:** Product and engineering team
**Source of truth for product intent:** [`IDEA.md`](./IDEA.md)

## 1. Purpose

This document translates the product idea into an implementable system. The platform accepts learner-owned technical material, creates a stable course from it, delivers focused coding labs, and adapts the learner's *route* using demonstrated conceptual and applied understanding.

The central product distinction is:

> A canonical, source-grounded course with a personalized, learner-controlled path through it.

The canonical course is stable and reviewable. Personalization adds or recommends support; it does not silently rewrite a learner's past work or the required course spine.

## 2. Product decisions captured here

| Decision | System implication |
| --- | --- |
| Course spine is canonical | A course version pins its source set, concept graph, required nodes, and delivered lesson revisions. |
| Adaptation is visible and optional | Every recommendation has a reason, can be accepted/deferred/dismissed, and appears in learning history. |
| Conceptual and applied learning are distinct | Mastery stores `understand` and `apply` tracks rather than one blended score. |
| Help-seeking is not penalized | Hints record a support level but never lower mastery. |
| Run patterns and time are contextual | They may inform presentation, but cannot independently lower mastery or cause remediation. |
| Diagnosis is evidence-backed but humble | It describes an observed code behavior and a supported hypothesis, not a claim about a learner's private reasoning. |
| Raw learning evidence is immutable | Diagnoses may recommend a prerequisite refresher but never reassign the original submission result. |
| Focused editing and authentic systems coexist | The editor starts with a small editable surface and offers progressive, read-only workspace inspection. |
| Robustness feedback must remain useful | Hidden evaluation reports the failed robustness category and concept without revealing test cases. |
| Applied mastery requires transfer | A coding concept requires a short fresh-context verification exercise before it is marked mastered. |

## 3. Scope

### MVP capabilities

- Authenticate a learner and let them create, resume, and manage multiple independent courses from uploaded Markdown, text, or PDF documents.
- Capture a learner goal and generate a versioned canonical concept graph and module roadmap.
- Generate, validate, and deliver Python-focused lesson bundles just ahead of the learner.
- Resolve course-declared Python dependencies into versioned, reusable Python environments before a learner starts a lab.
- Render a textbook view, split coding-lab view, source citations, and a learner-visible course route.
- Run visible tests on demand and evaluate a submitted snapshot against visible and hidden tests.
- Record immutable observations and maintain per-concept `understand` and `apply` mastery tracks.
- Insert or recommend a targeted remediation lesson after an evidence-based trigger.
- Show why an adaptation was recommended and let the learner control it.

### Explicit non-goals for the initial build

- Multi-language environments and automatic general-purpose environment-image creation. Python package variants are in scope.
- Instructor analytics, collaboration, grading, and roster management.
- Cross-learner model training or content-quality learning.
- A fully calibrated production psychometric model.
- Source editing, document synchronization, or enterprise document-management integrations.

## 4. Architecture

```text
                         +-----------------------------+
                         |       Next.js web app        |
                         | textbook | lab | progress UI |
                         +-------------+---------------+
                                       |
                              HTTPS / WebSocket
                                       |
                         +-------------v---------------+
                         |        FastAPI API           |
                         | auth | course | run | submit |
                         +----+----------+-----------+--+
                              |          |           |
                    +---------v--+  +----v----+  +---v----------------+
                    | Supabase   |  | Sandbox adapter               |
                    | Postgres + |  | learning | evaluator            |
                    | pgvector   |  +-------------------------------+
                    | Auth       |
                    | Storage    |
                    | Queues     |
                    +------+-----+
                           |             |
                    +------v--------------------------------------------+
                    |              Worker processes                     |
                    | ingest | plan | generate | validate | diagnose     |
                    +-------------------------+-------------------------+
                                              |
                                   +----------v----------+
                                   | Model-provider       |
                                   | adapter              |
                                   +----------------------+
```

### 4.1 Runtime components

| Component | Responsibilities | Does not own |
| --- | --- | --- |
| Next.js app + Base UI | Learner interface, accessible component primitives, streaming display, local editor state, WebSocket connection | Course truth, mastery updates, test authority |
| FastAPI API | Verifies Supabase Auth tokens, authorizes commands, validates requests, serves course APIs, and controls WebSocket sessions | Long-running generation or execution |
| Worker service | Ingestion, retrieval, planning, lesson generation, validation, diagnosis, remediation creation | Browser sessions |
| Supabase | Postgres + pgvector, Auth, Storage for source/submission artifacts, and PGMQ-backed queues | Sandbox execution and product command logic |
| Model adapter | Structured generation, streaming generation, embeddings; provider-neutral request/response normalization | Product rules or persistence |
| Sandbox adapter | Starts a learning runtime and separate evaluation runtime behind one internal interface | Mastery or grading decisions |

### 4.2 Provider and sandbox boundaries

The codebase defines adapters rather than allowing application code to call a model or sandbox SDK directly.

```python
class LLMAdapter(Protocol):
    async def generate_structured(self, request: StructuredGenerationRequest) -> dict: ...
    async def stream(self, request: StreamRequest) -> AsyncIterator[str]: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

class SandboxAdapter(Protocol):
    async def create_learning_session(self, request: LearningSessionRequest) -> SandboxSession: ...
    async def run_visible_tests(self, request: VisibleRunRequest) -> RunResult: ...
    async def evaluate_submission(self, request: EvaluationRequest) -> EvaluationResult: ...
```

The first implementation can target the team’s selected model provider and one `python-basic` environment. The adapter contract keeps that choice isolated while preserving a clear interface for later providers and managed sandbox services.

### 4.3 Supabase responsibilities

Supabase is the default cloud data platform:

- **Auth:** the browser signs in with Supabase Auth. FastAPI verifies the resulting JWT before serving product commands.
- **Database:** Supabase Postgres stores all relational state; pgvector stores source-chunk embeddings.
- **Storage:** private buckets store source uploads, parsed artifacts, lesson artifacts, and submission snapshots. Browser uploads use short-lived signed URLs.
- **Queues:** Supabase Queues (PGMQ) stores durable background jobs. Workers poll queues with server credentials; browsers never enqueue or consume worker jobs directly.

The browser communicates directly with Supabase only for authentication and authorized file uploads. Course planning, lesson delivery, submissions, mastery updates, and sandbox commands remain FastAPI-owned operations.

### 4.4 Python package provisioning

Python dependencies are an environment concern, not a learner-runtime concern. A lesson can request packages through structured `package_requirements`; it cannot supply a shell command or arbitrary installation script.

1. The planner or lesson generator emits normalized package names and version constraints.
2. `EnvironmentProvisioner` resolves the constraints against the approved Python package index, downloads packages in a dedicated provisioning environment, and produces an exact lockfile.
3. The provisioner builds or layers an immutable environment image, runs import and smoke tests, and registers the resulting image digest as a new `environment_definition`.
4. Learning and evaluator sandboxes use the registered environment with egress disabled. They do not run `pip install` and cannot download packages at runtime.

The first implementation supports public PyPI packages required by a course. Package policy, registry choice, and vulnerability scanning stay behind the provisioner; the runtime contract is always a resolved environment ID and lockfile hash.

### 4.5 Lesson sandbox builder

The Docker sandbox's first and primary role is not isolating untrusted learner code (that is the separate, later-built evaluator sandbox in §4.1's `SandboxAdapter`). It is giving the **content-generation agent itself** a real place to write files, execute them, and observe results — so a coding lesson's exercise proves itself before any learner ever sees it, matching the self-repair guarantee described in `docs/IDEA.md`.

The worker (`services/worker/worker/`) runs this as a background job per coding-concept lesson slot, triggered automatically the moment a course finishes planning:

1. **Trigger.** `apply_course_plan` calls `enqueue_lesson_builds`, which queues a `lesson_build` job on the existing `generation_jobs` queue for every coding-kind `lesson_definitions` row (`supabase/migrations/20260716004000_lesson_build_jobs.sql`). A `lesson_definitions.build_status` column (`pending → building → built | failed`) makes the claim atomic, mirroring the existing `claim_course_planning` pattern.
2. **Generate (single-shot).** `generate_lesson_bundle` (`worker/lesson_agent.py`) makes one `responses.parse` call — the same structured-output house pattern as course planning — grounded in the concept's own cited source chunks, producing a `LessonBundle` (`worker/lesson_schema.py`): starter files (with the target behavior left unimplemented), test files, a reference solution, an explanation, and hints. `validate_lesson_bundle` checks citation grounding and path consistency before anything touches Docker.
3. **Execute for real.** `DockerSandbox` (`worker/sandbox.py`) runs the reference solution against the tests inside a disposable, network-isolated container (`services/worker/sandbox_image/`, a minimal `python:3.13-slim` + pytest image, built lazily on first use). This is real execution, not a simulated check.
4. **Repair (multi-step, only on failure).** If the reference solution fails its own tests, `repair_bundle` hands the model three tools — `read_file`, `write_file`, `run_tests` — and lets it iterate: inspect, patch, re-run for real inside the sandbox, repeat. The loop is capped (`lesson_build_max_attempts`, `lesson_build_max_tool_calls`); the final pass/fail always comes from the sandbox's own last real run, never from the model's self-report.
5. **Persist.** `apply_lesson_bundle` writes the resulting `lesson_revisions` row with `validation_status = validated | failed`, whether or not it ultimately passed — a lesson that exhausts its retry budget is recorded, not silently dropped, so it is visible for review and reclaimable later.

Containment for this step is scoped to its actual threat model: content the worker itself asked a trusted LLM call to generate, not adversarial learner input. Network-disabled, memory/CPU/PID-limited, wall-clock-timeout containers are enough to stop a runaway process; this is deliberately lighter than what the eventual learner-facing evaluator sandbox will need.

Explicitly out of scope for this pass: the learner-facing "run my code" endpoint, WebSocket streaming, the Monaco editor frontend, the separate evaluator sandbox for graded submissions, and multi-language/environment-catalog support (`environment_definitions` is untouched).

## 5. Course, versioning, and personalization model

### 5.1 Canonical course model

A **course** is the learner's goal plus an immutable source set. A **course version** is a generated canonical structure for that source set. A learner profile can own any number of independent courses; each course has its own source set, course versions, path, assignments, and mastery records. A source document may be selected for more than one course, but learning evidence never crosses course boundaries.

The course version owns:

- source-document versions and hashes;
- concept graph and prerequisite edges;
- module order and required concept nodes;
- canonical lesson references and citation map;
- environment requirements; and
- generation schema and prompt versions.

Canonical lesson revisions are deliberately **learner-independent**. They are generated from the canonical lesson definition, its course version, cited source material, and resolved environment — never from an individual learner's mastery state. A canonical revision is shared, cacheable course content.

When a learner receives a canonical lesson, its exact shared revision is pinned to that learner's assignment. A later canonical repair creates a new revision; it never changes a delivered revision in place.

### 5.2 Personalized path model

Personalization is represented as **path events** around the course graph:

- `recommend_remediation`
- `assign_remediation`
- `recommend_skip_drill`
- `choose_concise_explanation`
- `defer_recommendation`
- `complete_transfer_check`

Every event contains `reason_code`, human-readable explanation, supporting observation IDs, creation time, learner decision, and resulting route change. The UI can therefore display a durable learning history.

When an accepted path event needs generated support, it creates a **learner-scoped support artifact** — such as a remediation mini-lesson, extra worked examples, or a concise explanation variant. Support artifacts may consume that learner's mastery and diagnosis context; they are not canonical lesson revisions and are never shared with other learners.

### 5.3 Source provenance

Every generated factual explanation, worked example, quiz explanation, and concept definition stores one or more citation anchors:

```json
{
  "source_document_id": "doc_123",
  "source_version": 1,
  "chunk_id": "chunk_456",
  "page": 42,
  "section": "4.2 Token expiration",
  "quote_start": 128,
  "quote_end": 342
}
```

The learner interface renders these anchors as “View source” links. The source set is the course's grounding context; source updates create a new course version rather than silently changing an existing one.

## 6. Domain data model

The initial relational model is intentionally normalized around immutable evidence and versioned course content.

| Table | Key fields | Notes |
| --- | --- | --- |
| `profiles` | `id`, `email`, `created_at` | `id` references Supabase Auth's `auth.users`; learners only in MVP. |
| `source_documents` | `id`, `owner_id`, `filename`, `mime_type`, `storage_key`, `sha256`, `status` | Raw upload metadata, ownership, and private Supabase Storage object key. |
| `source_document_versions` | `id`, `document_id`, `parser_version`, `parsed_storage_key`, `created_at` | Parsed output is reproducible. |
| `source_chunks` | `id`, `document_version_id`, `text`, `embedding`, `page`, `section`, `offsets` | Retrieval and citation anchor. |
| `courses` | `id`, `owner_id`, `goal`, `source_set_hash`, `active_version_id` | One of many independent course containers owned by a learner. |
| `course_versions` | `id`, `course_id`, `version`, `status`, `planner_schema_version` | Canonical, immutable course structure. |
| `concepts` | `id`, `course_version_id`, `slug`, `title`, `kind` | `kind` is conceptual-only or coding. |
| `concept_summaries` | `concept_id`, `summary_markdown`, `citations_json`, `revision` | Planner-generated, cited summaries render the textbook view before full lessons are prepared. |
| `concept_prerequisites` | `concept_id`, `prerequisite_concept_id` | Directed acyclic graph edges. |
| `modules` | `id`, `course_version_id`, `position`, `title` | Stable module sequence. |
| `lesson_definitions` | `id`, `course_version_id`, `module_id`, `concept_id`, `kind` | Canonical lesson or transfer-check slot. |
| `lesson_revisions` | `id`, `lesson_definition_id`, `revision`, `bundle_json`, `validation_status` | Learner-independent canonical bundle, shared and never modified in place. |
| `support_lesson_artifacts` | `id`, `user_id`, `course_version_id`, `target_concept_id`, `triggering_event_id`, `kind`, `bundle_json`, `validation_status` | Learner-scoped remediation, example, or concise-support bundle. |
| `learner_lesson_assignments` | `id`, `user_id`, `lesson_revision_id?`, `support_artifact_id?`, `route_kind`, `status` | Database constraint requires exactly one canonical revision or learner-scoped support artifact. |
| `submissions` | `id`, `assignment_id`, `snapshot_key`, `submitted_at` | Immutable submitted workspace snapshot. |
| `test_results` | `id`, `submission_id`, `visibility`, `category`, `status`, `details_json` | Store visible details and safe hidden-test summaries separately. |
| `quiz_responses` | `id`, `assignment_id`, `quiz_item_id`, `response_json`, `result`, `submitted_at` | Idempotent, auditable quiz answer record. |
| `observations` | `id`, `user_id`, `concept_id`, `track`, `assessment_kind`, `result`, `support_level`, `evidence_id`, `created_at` | Append-only assessment evidence. |
| `mastery` | `user_id`, `concept_id`, `track`, `p_l`, `opportunities`, `last_update` | One row per learner/concept/track. |
| `mastery_parameters` | `course_version_id`, `concept_id`, `track`, `assessment_kind`, `p_l0`, `p_t`, `p_g`, `p_s` | Track- and assessment-kind-specific BKT parameters. |
| `diagnoses` | `id`, `submission_id`, `hypothesis`, `evidence_json`, `probe_result`, `confidence` | Separate from observations. |
| `adaptation_events` | `id`, `user_id`, `course_version_id`, `event_type`, `reason_json`, `decision`, `created_at` | Learner-controlled path changes. |
| `environment_definitions` | `id`, `name`, `image_digest`, `language`, `package_lock_hash`, `status` | Versioned base or package-layered environments. |
| `environment_package_requirements` | `environment_id`, `package_name`, `requested_spec`, `resolved_version` | Auditable package request and resolved lock data. |

Use UUID primary keys, UTC timestamps, and tenant ownership checks on every query. Store large binaries and submission workspaces in private Supabase Storage buckets; retain their immutable pointer and hash in Supabase Postgres. Enable Row Level Security on every learner-owned table and Storage bucket.

## 7. Core contracts

### 7.1 Planner output

The planner must return structured JSON conforming to a versioned schema. The API refuses free-form planner output.

```json
{
  "course_title": "Building secure JWT APIs",
  "source_set_hash": "sha256:...",
  "concepts": [
    {
      "id": "jwt-expiry",
      "title": "JWT expiration",
      "kind": "coding",
      "summary_markdown": "How expiration claims bound a token's validity.",
      "prerequisites": ["http-auth-headers"],
      "citations": ["chunk_456"]
    }
  ],
  "modules": [
    {
      "id": "module-auth",
      "title": "JWT authentication foundations",
      "concept_ids": ["http-auth-headers", "jwt-expiry"]
    }
  ]
}
```

Validation rules:

- every concept has at least one source citation;
- every concept summary has at least one source citation;
- every prerequisite refers to a concept in the same version;
- the graph is acyclic;
- every module references known concepts;
- a coding concept declares an approved environment.

### 7.2 Lesson bundle

```json
{
  "schema_version": 1,
  "lesson_definition_id": "lesson_123",
  "target_concepts": ["jwt-expiry"],
  "lesson_content": {
    "title": "Reject expired tokens",
    "explanation_markdown": "...",
    "citations": ["chunk_456"],
    "worked_examples": []
  },
  "workspace": {
    "environment_id": "python-basic@sha256:...",
    "files": [
      { "path": "app/auth.py", "visibility": "visible", "editable_regions": ["validate_token"] },
      { "path": "app/config.py", "visibility": "inspectable" }
    ]
  },
  "assessment": {
    "visible_tests": [],
    "hidden_test_categories": ["expired-token", "malformed-claim"],
    "quiz_items": [],
    "hints": [],
    "reference_solution": "..."
  }
}
```

`hidden_tests` and the complete reference solution are persisted as restricted evaluator artifacts, not returned through the learner lesson API.

The generator may emit an environment request before this bundle is finalized:

```json
{
  "language": "python",
  "base_environment": "python-basic",
  "package_requirements": [
    { "name": "PyJWT", "version": ">=2.8,<3" },
    { "name": "fastapi", "version": ">=0.110,<1" }
  ]
}
```

`EnvironmentProvisioner` resolves this request into an immutable `environment_id` and package lock. The final lesson revision references that resolved ID, never an unpinned package range.

### 7.3 Observation contract

```json
{
  "user_id": "user_123",
  "concept_id": "jwt-expiry",
  "track": "apply",
  "result": "incorrect",
  "assessment_kind": "coding_submission",
  "support_level": "hint_2",
  "evidence_id": "submission_456",
  "created_at": "2026-07-15T22:00:00Z"
}
```

`observations` are append-only. A later diagnosis may create an adaptation event, but cannot mutate `concept_id`, `track`, or `result` in this record.

## 8. Service flows

### 8.1 Ingest and create a canonical course

1. Learner uploads files and supplies a learning goal.
2. API creates `source_documents`; the browser uploads directly to a private Supabase Storage path with a short-lived signed URL, then confirms completion and enqueues parsing through Supabase Queues.
3. Worker extracts text, identifies sections/pages, chunks it, embeds chunks, and writes `source_chunks`.
4. Worker calls the planner with the goal and retrieved source context. The planner returns the canonical graph, module roadmap, and a cited summary for each concept.
5. Schema and graph validators verify the planner output.
6. API creates `courses`, `course_versions`, concepts, concept summaries, graph edges, modules, and canonical lesson-definition slots in one transaction.
7. UI immediately renders the stable course map and summary-based textbook view, then begins preparing the first expanded canonical lesson revision.

### 8.2 Deliver a lesson just ahead of time

1. The route resolver identifies either the learner's next canonical lesson-definition slot or an accepted support event that must be fulfilled first.
2. For a canonical slot, the worker retrieves only the canonical definition, course-version source chunks, and resolved environment requirements. It does **not** receive learner mastery or diagnosis context. For support, the worker retrieves the accepted event, its evidence, relevant learner mastery, diagnosis context, and cited source chunks.
3. Worker generates either a learner-independent canonical lesson bundle for the existing definition or a learner-scoped support bundle for the accepted event.
4. If the bundle requests Python packages not already present in a registered environment, `EnvironmentProvisioner` resolves, downloads, locks, builds, and smoke-tests the package layer.
5. Validator checks schema, citation references, manifest constraints, resolved environment identity, and reference-solution execution.
6. A successful canonical bundle becomes a cacheable `lesson_revision`; a successful support bundle becomes a `support_lesson_artifact` owned by the triggering learner. The learner receives an immutable assignment to exactly one of them.
7. While the assignment is active, the scheduler may prepare the next canonical revision independently. It creates a support artifact only after a learner-specific path event requires one.

### 8.3 Run visible tests

1. Browser sends the current editable-file snapshot to `POST /assignments/{id}/runs`.
2. API validates assignment ownership and editable-region constraints.
3. Sandbox adapter runs only visible tests in a learning session.
4. Test events stream to the browser by WebSocket.
5. API stores run telemetry as context, not as a mastery observation.

### 8.4 Answer a quiz

1. Browser sends a quiz item response to `POST /assignments/{id}/quiz-responses` with an idempotency key.
2. API verifies that the quiz item belongs to the learner's pinned assignment and records one immutable `quiz_response`.
3. The quiz grader returns immediate feedback and appends an `understand` observation whose `assessment_kind` is `quiz_mcq` or `quiz_fill`.
4. Mastery service updates the matching conceptual BKT track transactionally and evaluates any applicable adaptation rule.
5. API returns the answer explanation, source citations, updated conceptual signal, and any recommendation.

### 8.5 Submit a checkpoint

1. Browser sends an immutable snapshot to `POST /submissions`.
2. API stores the snapshot in private Supabase Storage, enqueues evaluation through Supabase Queues, and returns `202 Accepted` with `status: queued`.
3. The evaluator sandbox receives the submitted artifact and runs visible tests, hidden robustness tests, and approved static/runtime checks.
4. Evaluator emits structured results: pass/fail, affected concept, robustness category, and safe learner feedback.
5. Mastery service appends assessment observations to `understand` and/or `apply` as declared by the assessment contract.
6. Mastery service updates its BKT state transactionally, then evaluates adaptation rules.
7. API publishes submission results and any proposed path change to the browser.

The learner UI shows an explicit queued/running state until the `submission:{submission_id}` event arrives. The MVP latency target is evaluation completion at p95 under 15 seconds; queue age and evaluation duration are monitored separately.

The learning sandbox never receives hidden-test artifacts. The separate evaluator sandbox is the authority for hidden evaluation.

### 8.6 Diagnosis and remediation

1. A remediation or support trigger includes relevant submission IDs and observation IDs.
2. Worker asks the diagnosis model for a structured behavioral hypothesis with evidence.
3. A targeted probe may verify the code behavior against the submitted snapshot.
4. The diagnosis is stored separately from the immutable observation log.
5. If behavior is verified, the platform proposes a targeted remediation lesson; otherwise it proposes generic support.
6. Learner accepts, defers, or declines the recommendation. The decision becomes an `adaptation_event` and the route resolver uses it on the next scheduling pass.

## 9. Mastery and adaptation design

### 9.1 Two linked tracks

Each concept has one or both tracks:

- `understand`: retrieval, explanation, and short-answer/quiz evidence;
- `apply`: code checkpoint, robustness, and transfer-exercise evidence.

Coding concepts require both tracks to satisfy their threshold. Conceptual-only concepts need only `understand`. The dashboard displays both explicitly rather than implying a single opaque mastery value.

### 9.2 BKT update boundary

The BKT service accepts only normalized assessment observations. It does not consume raw terminal text, elapsed time, number of edits, or an LLM diagnosis as direct evidence.

```text
assessment result -> immutable observation -> matching BKT track update
support/context data -> recommendation presentation only
diagnosis hypothesis -> remediation recommendation only
```

Parameters are keyed by `(course_version, concept, track, assessment_kind)`, not merely by concept and track. For example, `quiz_mcq`, `quiz_fill`, `coding_submission`, and `transfer_exercise` can each have distinct guess and slip parameters. This prevents a multiple-choice answer from being weighted like a coding submission. The initial implementation uses conservative priors; the log schema supports later parameter fitting without changing the learner-facing model.

### 9.3 Adaptation rules

| Trigger | System action | Learner control |
| --- | --- | --- |
| Repeated failed applied attempts | Propose scaffolded remediation focused on the failed concept | Accept, defer, return to canonical node |
| Failure plus low prerequisite track | Propose prerequisite refresher | Accept or continue current node |
| Consistently independent success | Recommend concise explanation or skip a redundant drill | Keep full route or accept |
| Supported success | Offer more examples or scaffolded next task | Accept or decline |
| Near-threshold applied mastery | Assign a fresh-context, hint-free transfer check | Required only when the coding concept needs applied mastery |

Every action records a plain-language reason and the evidence IDs that supported it.

## 10. API surface

All endpoints are prefixed with `/api/v1`, authenticated, and enforce course ownership.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/sources` | Create upload record and return upload target. |
| `POST` | `/sources/{id}/complete` | Confirm upload and enqueue ingestion. |
| `GET` | `/sources/{id}` | Poll ingestion state and source metadata. |
| `POST` | `/courses` | Create a course from source IDs and learning goal. |
| `GET` | `/courses` | List the authenticated learner's courses with active version, progress summary, and last activity. |
| `GET` | `/courses/{id}` | Course metadata, active canonical version, and route summary. |
| `GET` | `/courses/{id}/map` | Canonical graph plus learner path events. |
| `GET` | `/courses/{id}/next` | Read-only preview of the next canonical node or available recommendation; creates nothing. |
| `POST` | `/courses/{id}/assignments/next` | Materialize the next assignment idempotently and return the existing active assignment when present. |
| `GET` | `/lessons/{assignment_id}` | Return learner-safe pinned lesson revision. |
| `POST` | `/assignments/{id}/runs` | Run visible tests against current snapshot. |
| `POST` | `/assignments/{id}/quiz-responses` | Record and grade an idempotent quiz response, then update `understand`. |
| `POST` | `/assignments/{id}/submissions` | Persist snapshot and enqueue full evaluation. |
| `GET` | `/submissions/{id}` | Submission and safe result summary. |
| `GET` | `/courses/{id}/mastery` | Per-concept `understand` and `apply` tracks. |
| `POST` | `/adaptations/{id}/decision` | Accept, defer, or decline a recommendation. |
| `GET` | `/courses/{id}/history` | Delivered lessons and adaptation timeline. |

WebSocket channels:

- `run:{run_id}` for visible-test output;
- `generation:{assignment_id}` for lesson preparation and streaming content;
- `submission:{submission_id}` for evaluation completion and adaptation proposals.

The browser presents its Supabase JWT when opening a WebSocket. FastAPI verifies the token and authorizes the user against the channel's assignment, run, or submission owner before subscribing or publishing events.

## 11. Security and privacy baseline

- Enable Row Level Security on every learner-owned Supabase table and Storage bucket. FastAPI also enforces owner/tenant checks for every command.
- Store source documents and submission snapshots with private Supabase Storage object keys; issue short-lived signed upload/download URLs only after authorization.
- Keep Supabase secret/service-role keys in server and worker environments only; they are never shipped to the browser.
- Treat every uploaded document and retrieved chunk as untrusted data in model prompts. System instructions and tool permissions are never derived from source text.
- Restrict model inputs to the minimum source chunks and learner evidence required for the task.
- Run learner and evaluator code as an unprivileged user with egress disabled, read-only base filesystem, resource/PID/time limits, no host mounts, and an ephemeral writable layer. Only the dedicated package-provisioning job may access the approved package registry.
- Enforce editable-region rules on the server; client-side editor restrictions are only a usability aid.
- Keep hidden evaluator artifacts separate from learner-visible artifacts and redact test internals from responses and logs.
- Make source deletion and course deletion explicit product actions; both delete or tombstone dependent stored artifacts according to the team's retention policy.

## 12. Observability and quality gates

### Required event names

- `source.ingestion.completed` / `source.ingestion.failed`
- `course.planned` / `course.plan_rejected`
- `lesson.generated` / `lesson.validation_failed` / `lesson.repaired`
- `sandbox.run.completed` / `submission.evaluated`
- `mastery.updated`
- `adaptation.proposed` / `adaptation.decided`
- `diagnosis.created` / `diagnosis.probe_completed`

### Initial metrics

- ingestion and planning latency;
- lesson-generation and validation-pass rate;
- time to first runnable lesson;
- visible-run and submission latency;
- remediation proposal/acceptance rate;
- transfer-check completion rate;
- percentage of lessons requiring repair;
- source-citation coverage per lesson.

### Quality gates before a lesson is assignable

1. Lesson bundle matches its JSON schema.
2. Every target concept and generated factual section has valid source anchors.
3. Environment exists, matches the requested image digest, and has a resolved package lock matching the lesson revision.
4. Reference solution passes visible and hidden evaluation.
5. Learner API projection contains no hidden tests, reference solution, or restricted files.

## 13. Initial implementation order

1. **Foundation:** repository layout, API shell, Next.js web shell with Base UI, Supabase project/configuration, database migrations, RLS policies, Storage buckets, PGMQ queues, and Supabase Auth integration.
2. **Sources and course planning:** upload flow, parser/chunker, embeddings, retrieval, structured planner, graph validation, cited concept summaries, and course-map/textbook UI.
3. **Canonical lesson pipeline:** lesson schema, model adapter, Python package provisioner and lockfile registry, shared canonical bundle persistence, citation rendering, validation harness, and first pinned assignment.
4. **Lab runtime:** Monaco workspace, visible run path, WebSocket output, Python sandbox adapter, server-side edit validation.
5. **Assessment and mastery:** separate evaluator path, quiz-response flow, observation log, assessment-kind-aware dual-track BKT service, mastery dashboard, and queued-submission state.
6. **Adaptation:** rule engine, learner-visible recommendations/history, learner-scoped support-bundle generation, diagnosis/probe path, transfer check.

## 14. Proposed repository layout

Use a small monorepo so the contracts shared by the web app, API, and workers remain versioned together.

```text
apps/
  web/                    # Next.js learner experience
services/
  api/                    # FastAPI HTTP and WebSocket service
  worker/                 # Background ingestion/generation/evaluation jobs
packages/
  contracts/              # Versioned JSON Schema and generated types
  domain/                 # Shared domain rules: route, mastery, observations
  adapters/               # LLM, storage, queue, and sandbox interfaces
  sandbox-runner/         # Learning/evaluator sandbox implementations
supabase/
  migrations/             # Postgres schema, RLS, pgvector, and PGMQ migrations
  seed.sql                # Local demo data
infra/
  compose/                # Local worker and sandbox services
docs/
  ARCHITECTURE.md
  IDEA.md
```

`packages/contracts` is the integration boundary: planner output, lesson bundles, sandbox requests/results, and API request/response types are defined there before feature code is written.

## 15. MVP acceptance scenario

A learner uploads an API-authentication document, chooses a goal, receives a stable course map, and completes a cited JWT lesson. They can run visible tests freely. After two submissions that fail token-expiration handling, the evaluator records applied evidence, the system shows a supported behavioral hypothesis, and proposes a token-expiry refresher. The learner accepts it, sees the route change in their history, completes a fresh-context transfer exercise, and sees `understand` and `apply` separately on the mastery dashboard.

## 16. Deferred design decisions

These decisions do not block scaffolding because they are isolated behind contracts:

- concrete model-provider configuration and model selection;
- concrete sandbox implementation for the learner-facing evaluator sandbox (managed service versus self-managed runtime) — the lesson sandbox builder's implementation is decided (§4.5: self-managed Docker);
- Supabase plan, region, and production backup configuration;
- production retention period and deletion workflow;
- instructor/admin roles and analytics;
- parameter-fitting strategy after sufficient observation data exists.
