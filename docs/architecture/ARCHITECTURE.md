# Architecture: Canopy

**Status:** Current implementation (updated 2026-07-19)

**Audience:** Product and engineering

**Diagram:** [architecture-diagram.drawio](./architecture-diagram.drawio), editable in [draw.io](https://app.diagrams.net/)

## Overview

Canopy converts learner-owned technical documents into source-grounded courses. A Next.js web app calls a FastAPI API. The API owns learner-facing reads and commands; a separate worker carries out ingestion, course planning, lesson generation, and validation from durable queues.

The runtime has four trust boundaries:

1. **Browser:** Untrusted learner input and local editor state.
2. **Application services:** FastAPI validates and authorizes learner actions; the worker performs durable background work.
3. **Private integration services:** The LLM gateway owns provider credentials; the sandbox runner owns Docker access.
4. **Supabase:** Auth, Postgres/pgvector, private Storage, and PGMQ queues are the durable platform.

## Runtime topology

```text
Learner browser
  │ HTTPS (Supabase Auth token)
  ▼
Next.js web app ──────────────────────────────┐
  │ REST                                       │ Auth + signed uploads
  ▼                                            ▼
FastAPI API ──────────────────────────► Supabase: Auth, Storage,
  │  │                                   Postgres + pgvector + PGMQ
  │  └── internal HTTP ─► Sandbox runner     ▲              │
  │                         └► Docker        │              │ queue polling
  └── internal HTTP ─► LLM gateway           │              ▼
                         └► model providers  └──── Worker service
```

The complete editable component diagram is [architecture-diagram.drawio](./architecture-diagram.drawio).

## Components and ownership

| Component | Owns | Responsibilities |
| --- | --- | --- |
| `apps/web` | Learner UI state | Next.js interface for courses, sources, concepts, labs, quiz activity, recommendations, sharing, and certificates. Calls the API with a Supabase access token. |
| `services/api` | Learner-facing HTTP contract | FastAPI routes, token verification, authorization, signed upload targets, course reads/mutations, PDF exports, mastery updates, and sandbox request validation. |
| `services/worker` | Background job execution | Polls ingestion and generation queues; parses sources, creates embeddings, plans courses, generates lessons, validates citations, and validates coding bundles. |
| `services/llm_gateway` | Model-provider integration | The only service with model-provider credentials. Serves structured generation, Responses-style tool turns, and embeddings over an internal API. |
| `services/sandbox_runner` | Code-execution integration | The only service with Docker access. Runs bounded workspaces in registered environments. |
| Supabase | Durable product state | Auth, Postgres relational state, pgvector retrieval, private object storage, server-side RPC, and PGMQ queues. |

The browser does not access provider APIs, Docker, queues, or application data writes directly. The API and worker call the LLM gateway and sandbox runner over internal HTTP.

## Data and queue model

### Durable data

Supabase Postgres is the system of record.

| Domain | Current tables / data |
| --- | --- |
| Identity | `profiles`, backed by `auth.users`; learner display names are stored on profiles. |
| Sources | `source_documents`, `source_document_versions`, `source_chunks`, and `course_sources`. Chunks include 1536-dimensional embeddings and citation locations. |
| Course content | `courses`, `course_versions`, `modules`, `concepts`, `concept_summaries`, `concept_prerequisites`, `lesson_definitions`, and immutable `lesson_revisions`. |
| Learning progress | `quiz_responses`, `submissions`, `observations`, `mastery`, `mastery_parameters`, and `adaptation_events`. |
| Product features | `certificates` plus course-level language, sharing, lesson-range, and quiz-attempt fields. |

The active course version is pinned by `courses.active_version_id`. Regeneration creates a new version rather than modifying published course content. Lesson revisions also retain a validation status.

Private Storage holds original source uploads and submission snapshots. Browser uploads use short-lived signed URLs issued by the API. Row Level Security is enabled on learner-owned data and Storage objects; server-side API and worker work uses service-role clients.

### Queues and reliability

PGMQ queues are `ingestion_jobs`, `generation_jobs`, and `evaluation_jobs`; the current worker consumes the first two.

- `ingestion_jobs` contains a `source_id` after upload completion.
- `generation_jobs` contains `course_planning` and `lesson_build` work.
- Messages have a visibility timeout. Transient integration failures remain for redelivery.
- Database claim functions make planning and lesson builds atomic; stale claims can be reclaimed.
- Failed lesson builds retain an error, have bounded automatic retries, and can be explicitly resumed.

## Main flows

### Upload, ingest, and plan

1. The browser authenticates with Supabase and requests an upload target from FastAPI.
2. It uploads a PDF, Markdown, or text file to the private `sources` bucket, then completes the upload through FastAPI.
3. The API enqueues ingestion. The worker extracts and chunks content, gets embeddings via the gateway, and stores parsed metadata and vectors.
4. The learner creates a course from ready sources. FastAPI creates a draft course/version and enqueues course planning.
5. The worker retrieves source chunks, requests a schema-constrained plan, and persists modules, concepts, prerequisites, cited summaries, and lesson definitions.
6. The planner enqueues lesson builds. The UI exposes content/build status and can resume failed builds.

### Build and validate a lesson

1. The worker atomically claims a lesson definition and retrieves cited context.
2. It generates structured lesson content through the gateway, then validates citations and schema consistency before checkpointing the content.
3. Conceptual lessons are stored as revisions. Coding lessons also receive a starter workspace, tests, and reference solution.
4. The sandbox runner must verify that the reference solution passes and that the starter workspace does not already pass all tests.
5. A bounded repair loop can use restricted `read_file`, `write_file`, and `run_tests` tools. It cannot rewrite tests.
6. The worker persists a `validated` or `failed` immutable revision and updates the definition build status.

### Learn, run, submit, and adapt

1. The browser loads course, concept, citation, progress, and recommendation data through FastAPI.
2. Learner code runs or submits through FastAPI. The API checks membership and files, maps the course language to an approved environment, and calls the sandbox runner.
3. The runner returns bounded output, exit status, and timeout status.
4. Quiz answers and learning activity append observations. The API updates the appropriate `understand` or `apply` mastery record using configured BKT parameters.
5. Recommendations are durable `adaptation_events`; accepting, deferring, or declining one does not alter historical submissions or observations.

## Private integration services

### LLM gateway

`services/llm_gateway` exposes internal-only endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /internal/v1/structured` | Schema-constrained planning and content generation. |
| `POST /internal/v1/responses` | Tool-capable turns for lesson repair and the learning helper. |
| `POST /internal/v1/embeddings` | Source-chunk embeddings. |

Adapters support OpenAI, Azure OpenAI, AWS Bedrock Converse, and Bedrock's OpenAI-compatible endpoint. Provider SDKs and credentials stay behind this boundary.

### Sandbox runner

`services/sandbox_runner` exposes internal run and script endpoints. Registered profiles include `python-basic`, `python-ml`, `cpp-basic`, `c-basic`, `go-basic`, and `javascript-basic`.

Callers select only an environment ID. They cannot choose a Docker image, host mount, network setting, command, or resource policy. The runner validates relative paths, suffixes, file count, and size; copies an in-memory tar workspace; runs the environment-defined command; and truncates output.

The development backend uses local Docker. Containers are ephemeral and constrained with network isolation, resource limits, non-root execution, dropped capabilities, no-new-privileges, and per-environment timeouts. In Compose, only the sandbox-runner service receives the Docker socket.

## Security boundaries

- FastAPI verifies Supabase Auth JWTs before protected learner operations.
- The browser's direct Supabase use is limited to Auth and authorized signed uploads.
- Sources are restricted to PDF, Markdown, and plain text, with a 6 MiB cap.
- Storage buckets are private and protected by RLS policies.
- Only the gateway has model-provider credentials; only the sandbox runner has Docker access.
- Sandbox requests use registered environments and validated workspace files.
- Public certificate verification and shared-course import use durable UUID capability links; course/progress data still requires an authenticated owner.

See [SECURITY.md](./SECURITY.md) and [SANDBOX_ARCHITECTURE.md](./SANDBOX_ARCHITECTURE.md) for detailed controls.

## Local deployment

`npm run dev` starts five processes: web on `3000`, API on `8000`, LLM gateway on `8010`, sandbox runner on `8020`, and the worker. The worker is required for ingestion and all course generation.

`docker-compose.yml` defines the four backend services. API and worker use Compose service names to reach the gateway and sandbox runner; Supabase is configured as an external or local platform dependency through environment variables.

## Implemented and deferred

Implemented: source-grounded planning, background generation, conceptual and coding lessons, citation retrieval, quiz/mastery persistence, approved sandbox profiles, course sharing/import, certificates, and Python, Python ML, or C++ course languages.

Not currently part of the runtime contract: browser WebSockets, arbitrary dependency provisioning or runtime installs, hidden-test grading, general-purpose learner images, instructor analytics, collaboration, cross-learner model training, and managed production sandbox infrastructure.

## Repository map

```text
apps/web/                       Next.js learner application
services/api/app/               FastAPI routes, repositories, learning logic, PDF exports
services/worker/worker/         ingestion, planning, retrieval, lesson build and repair
services/llm_gateway/           provider-neutral LLM integration
services/sandbox_runner/        Docker-backed registered-environment runner
packages/contracts/             JSON schemas and shared TypeScript contracts
supabase/migrations/            database, RLS, RPC, Storage, and PGMQ schema history
docs/architecture/              this document, security docs, editable diagram
```
