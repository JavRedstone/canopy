# Architecture Audit — 2026-07-16

> **Archived — point-in-time audit, not current state.** Re-verified 2026-07-18: the
> flagship P0 finding (hidden-test output returned to the learner) is **still accurate**
> — `submit_lesson` (`services/api/app/routers/courses.py`) runs `public_test_files +
> hidden_test_files` and returns the combined raw pytest `output` unfiltered, so a failing
> hidden test's assertion/traceback still reaches the learner. Only `run_lesson` (visible
> tests only) is separated. The sandbox environment catalog has also grown beyond what's
> described here (Python/JS/Go now, not just `python-basic`). Don't assume any other
> finding below is still open or resolved without checking current code — this file
> wasn't kept up to date. See [`../architecture/SECURITY.md`](../architecture/SECURITY.md) for the current security
> posture and [`../README.md`](../README.md) for current docs.

**Status:** Current-state code audit

**Scope:** Static review of the repository at this commit, its service boundaries, contracts, tests, and local Compose configuration. This is not a production penetration test and does not prove live provider, Supabase, or Docker behavior.

## Executive summary

The codebase now has the right high-level split for model access and code execution:

- `services/llm_gateway` centralizes provider selection and provider credentials.
- `services/sandbox_runner` is the only component with Docker access.
- API and worker use narrow HTTP clients rather than importing provider or Docker SDKs.
- Supabase remains the system of record for identity, relational state, Storage, vectors, and PGMQ work queues.

That is meaningful progress, but the learner execution path is **not safe to release yet**. The current learner-visible run endpoint executes hidden tests and returns the raw pytest output. The sandbox is a useful development runner, not yet a production-grade hostile-code boundary. Several contracts and the aspirational architecture document have also drifted from the running code.

## Current runtime map

```text
Next.js web app
      |
      v
FastAPI API ---------------------> Supabase (Auth, Postgres, Storage, PGMQ)
      |                                       ^
      |                                       |
      +--> SandboxRunnerClient                 Worker
                |                               |  \
                v                               |   +--> LLMGatewayClient
       sandbox-runner service                    |            |
                |                               |            v
                v                               +----> LLM gateway
    Docker development executor                               |
                                                            providers
                                              OpenAI | Azure OpenAI | AWS Bedrock
```

## What is implemented well

| Area | Assessment | Evidence |
| --- | --- | --- |
| Model boundary | Implemented | The gateway owns provider selection and credentials; the worker talks through `LLMGatewayClient`. |
| Sandbox boundary | Implemented | API and worker use `SandboxRunnerClient`; Docker imports are confined to `services/sandbox_runner`. |
| Provider flexibility | Implemented, not live-verified | OpenAI, Azure OpenAI, Bedrock Converse, and Bedrock's OpenAI-compatible endpoint have adapters and unit coverage. |
| Source ownership | Implemented | Upload records are owner-bound, browser uploads use signed Storage URLs, and repository queries apply owner filters. |
| Planner and lesson validation | Partially implemented | Pydantic validates course/lesson output and the worker retries malformed structured responses. |
| Lesson repair | Implemented | The worker generates, executes, repairs through bounded tools, and performs a final sandbox verification. |
| Shared contracts | Started | Gateway and sandbox JSON schemas exist, but are not yet the single executable source of truth. |

## Findings

### P0 — Hidden tests are executed and exposed through the learner run endpoint

`POST /courses/{course_id}/concepts/{slug}/run` loads public and hidden test files, sends both to the sandbox, then returns the raw pytest output to the learner. See [`courses.py`](../../services/api/app/routers/courses.py#L73-L88).

This violates the architecture's required learning/evaluator separation. A failing hidden test can reveal its name, assertion, file path, data, and source line through pytest output. It also makes a free learner run equivalent to hidden evaluation.

**Required fix before release:**

1. Run only `public_test_files` from the learner-visible endpoint.
2. Move hidden tests to a separate queued evaluator command and worker-owned result path.
3. Return a constrained learner-safe result: a category and concept, never raw hidden-test output.
4. Add an integration test proving hidden test text cannot appear in any learner response.

### P1 — The sandbox runner is development containment, not a production hostile-code sandbox

The execution container correctly disables network access, runs as a non-root UID, drops Linux capabilities, limits memory/CPU/PIDs, bounds runtime, and force-removes the container. Those are strong baseline controls.

However, the runner deliberately creates the execution container with `read_only=False`; its own comment explains why the Docker archive workflow needs it. See [`runner.py`](../../services/sandbox_runner/sandbox_runner/runner.py#L85-L116). The service also receives the Docker socket in Compose ([`docker-compose.yml`](../../docker-compose.yml#L64-L71)). This is appropriate only as a tightly controlled development executor.

The `content_validation` and `learner_visible` profiles are request labels today; they do not select different runtime policies. A future hidden evaluator would therefore not yet have a distinct trust boundary.

**Required path:**

- Keep this Docker implementation for local content validation only.
- Before accepting adversarial learner code in production, use a rootless/microVM or gVisor-class executor, enforce a read-only image plus controlled ephemeral workspace, add seccomp/AppArmor policy, and give learner-visible, hidden-evaluator, and builder validation distinct policies.
- Pin registered environment images by immutable digest. The current `python-basic` tag is mutable and can be built lazily by the runner.

### P1 — Private services are host-published and development authentication is optional

Compose publishes the LLM gateway on `8010` and the sandbox runner on `8020`. In `development`, an absent internal token is accepted by both services. See [`docker-compose.yml`](../../docker-compose.yml#L36-L71) and the `*_internal_request_allowed` guards.

This is convenient locally, but it must not become a deployment default—especially for the sandbox runner.

**Required path:** bind local-only ports to loopback or keep them internal to the Compose network; require service identity outside a local profile; use mTLS or a workload identity in production; and never expose the Docker-backed runner through an ingress.

### P1 — Sandbox contracts have drifted from the runtime API

[`sandbox-runner.schema.json`](../../packages/contracts/schemas/sandbox-runner.schema.json) describes only `/runs` with a maximum of 15 files. The runtime permits 20 files and also exposes `/scripts`, which has no corresponding shared contract. The public API schema accepts general `LessonWorkspaceFile` values; invalid script paths are discovered by the downstream runner and become a generic `503` because the client maps all non-2xx responses to `SandboxError`.

**Required path:** make the versioned contract cover every runner endpoint and generate or validate both client and server models from it. Preserve caller errors as `422`, and reserve `503` for unavailable runner infrastructure.

### P2 — The course repository owns too many unrelated responsibilities

[`SupabaseCourseRepository`](../../services/api/app/repository.py#L208) currently handles course reads/writes, source metadata, signed upload issuance, Storage verification, PGMQ enqueueing, lesson projection, and HTTP error translation. It is an effective vertical-slice implementation but is becoming a high-coupling boundary.

**Required path:** separate application services (`SourceService`, `CourseService`, `LessonService`) from persistence repositories, a `SourceArtifactStore`, and a typed `JobPublisher`. Keep Supabase as the first implementation behind those ports.

### P2 — Queue and ingestion durability are incomplete

`QueueAdapter` directly encodes PGMQ function names in the worker ([`ingestion.py`](../../services/worker/worker/ingestion.py#L37-L64)). Retryable work relies on the queue visibility timeout, with no explicit attempt count, backoff policy, dead-letter workflow, operator view, or idempotency ledger.

The worker also deletes prior parser-version rows in `_replace_document_version` ([`ingestion.py`](../../services/worker/worker/ingestion.py#L452-L469)), which conflicts with the architecture's stated immutable source-version history.

**Required path:** introduce typed jobs with a retry budget and DLQ, emit queue-age/attempt metrics, retain parsed versions, and atomically mark all document-version artifacts as ready or failed.

### P2 — Retrieval is ordered chunk selection, not semantic retrieval

`_course_context` selects the most recent document versions and then takes the first configured chunk limit in creation order ([`ingestion.py`](../../services/worker/worker/ingestion.py#L508-L541)). It does not perform vector similarity search against the learner goal or current concept.

This will work for short sources but weakens grounding as source sets grow. It also increases prompt cost because context relevance is not optimized.

**Required path:** add a retrieval service that queries pgvector with the goal/concept query, applies per-document diversity and token budgets, and records selected chunk IDs for auditability.

### P2 — The LLM gateway has a solid provider seam but lacks operational policy

The gateway supports structured output, repair tool turns, embeddings, and provider selection. The worker validates structured output locally and asks for correction up to three times ([`llm.py`](../../services/worker/worker/llm.py#L22-L71)), which is a good quality safeguard.

It does not yet enforce per-task input/output token budgets, tenant quotas, concurrency/rate limits, idempotency keys, cost/usage records, request correlation, or prompt/version registry. The runtime request model also accepts every gateway task at `/structured`, while the checked-in JSON contract limits that operation to planning and lesson-build tasks.

**Required path:** make task policy server-owned: task → allowed provider/model, schema ID/version, token limit, retry policy, redaction rule, and telemetry dimensions. Do not rely on each caller to choose an arbitrary schema and model task correctly.

### P3 — The canonical architecture document remains aspirational in several areas

[`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) describes assignments, hidden evaluation, WebSockets, submissions, mastery/BKT, adaptation, package provisioning, and a broader `packages/domain`/`packages/adapters` layout. Those capabilities are not present in the current API/worker implementation.

The current code supports sources, planning, generated lessons, public test files, sandboxed runs, and regeneration. Treat the architecture document as a target design; this audit and `SCAFFOLD_STATUS.md` should be the current-state references until the missing services exist.

## Recommended delivery order

1. **Block P0:** split learner visible tests from hidden evaluation and redact all evaluator output.
2. **Harden the runner:** production executor decision, immutable environments, separate runner profiles, internal-only access, and execution telemetry.
3. **Stabilize contracts:** one versioned schema source for lesson bundles, all sandbox endpoints, LLM task requests, and public API projections.
4. **Extract workflow boundaries:** typed queue publisher/consumer, artifact store, source and course application services, retries/DLQ/metrics.
5. **Implement the actual learning loop:** assignments, submission evaluation, immutable observations, mastery, adaptations, and realtime authorization.
6. **Add retrieval and provisioning:** semantic source selection and a separately privileged environment-provisioning service.

## Verification baseline

The repository contains API, worker, gateway, and sandbox-runner test suites. This audit should be updated whenever a release changes a boundary, contract, trust level, or deployment model. In particular, the P0 regression test for hidden-test non-disclosure must be added before the next learner-run change is merged.
