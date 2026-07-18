# Security

This document describes the security architecture of Canopy: trust boundaries between
components, how each layer authenticates and authorizes requests, and where untrusted
input (learner code, uploaded documents, LLM output) is contained. It reflects the
system as implemented, not aspirational policy.

For product architecture see [`ARCHITECTURE.md`](ARCHITECTURE.md); for the
sandbox specifically see [`SANDBOX_ARCHITECTURE.md`](SANDBOX_ARCHITECTURE.md).

## 1. System topology and trust boundaries

```text
 Browser (untrusted)
   |  HTTPS, learner's own Supabase session JWT
   v
 Next.js app (apps/web)            -- no server secrets, no API routes/middleware
   |  Bearer <learner JWT>
   v
 FastAPI API (services/api)        -- public-facing, holds Supabase service-role key
   |  X-Internal-Service-Token            |  X-Internal-Service-Token
   v                                      v
 LLM Gateway (services/llm_gateway)  Sandbox Runner (services/sandbox_runner)
   |  provider API keys                   |  docker.sock (host Docker control)
   v                                       v
 OpenAI / Azure OpenAI / AWS Bedrock   Ephemeral, hardened Docker containers
                                        (learner code + AI-generated code execution)

 Worker (services/worker) -- polls Supabase queues (pgmq via SECURITY DEFINER RPCs),
   calls LLM Gateway and Sandbox Runner with the same internal token, writes results
   back through the Supabase service-role key. No public network exposure.

 Supabase (Postgres + pgvector, Auth, Storage, queues) -- RLS enforced for any
   client using an end-user JWT; API/worker use the service-role key and enforce
   authorization themselves (see §3).
```

Four independent trust zones exist:

1. **Browser** — fully untrusted. Holds only the learner's own Supabase session and
   public config.
2. **Public backend (API)** — untrusted input arrives here (HTTP requests, learner
   code submissions), but the service itself is trusted once a request is authenticated.
3. **Internal services (worker, LLM gateway, sandbox runner)** — reachable only from
   other backend services on the internal network, gated by a shared bearer token.
   Never exposed to the browser.
4. **Sandbox containers** — the one place arbitrary, adversarial code actually runs.
   Treated as fully hostile even though most of its input is AI-generated, not
   learner-submitted (see §5).

## 2. Frontend (Next.js, `apps/web`)

- No `middleware.ts` and no `app/api/*` route handlers exist. The only server-executed
  code is the Supabase OAuth/OTP callback (`app/auth/callback/route.ts`), which
  exchanges a code for a session and sets cookies.
- All Supabase config (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`)
  and the API base URL (`NEXT_PUBLIC_API_URL`) are intentionally public (`NEXT_PUBLIC_`
  prefixed) — the frontend never holds a server-only secret. `scripts/sync-env.js`
  exists specifically to keep non-public vars (Supabase service-role key, OpenAI keys)
  out of `apps/web/.env.local`.
- Route protection is enforced per-layout (`app/courses/layout.tsx` calls
  `supabase.auth.getUser()` server-side and redirects unauthenticated visitors), not
  via a global middleware gate. Every protected route currently sits under that layout.
- Every backend call attaches `Authorization: Bearer <learner's own Supabase JWT>` —
  the frontend never sends an internal service token or any other privileged secret.
- No `dangerouslySetInnerHTML`, `eval`, or `new Function`; Markdown is rendered through
  a hand-rolled parser that produces React elements directly, not injected HTML. React's
  default JSX escaping is otherwise relied on for XSS protection.
- `next.config.ts` sets no security headers (no CSP, no `X-Frame-Options`, etc.) today.

## 3. API layer (`services/api`)

**Authentication** (`app/dependencies.py`): two modes controlled by `APP_AUTH_MODE`.
- `development`: trusts an `X-Demo-User-Id` header, or falls back to a hardcoded demo
  UUID. No verification. Never intended to run outside local dev.
- `supabase`: requires `Authorization: Bearer <token>`; the token is validated by
  calling Supabase Auth's `auth.get_user(token)` (via the service-role client) rather
  than verifying the JWT signature locally. The resulting `user.id` becomes the
  authenticated identity for the request.

**Authorization**: the API uses the Supabase **service-role key**, which bypasses Row
Level Security entirely (see §7). Authorization is therefore enforced in application
code, not the database: every repository method in `app/repository.py` takes the
authenticated `current_user` and filters/scopes every query by owner (`.eq("user_id", ...)`
or an equivalent join), for all ~1,500 lines of course, lesson, submission, and mastery
access. There is no row the API will return or mutate without an explicit
owner/user match against the caller's identity.

**CORS**: origins are restricted to `APP_CORS_ORIGINS` (defaults to
`http://localhost:3000`), `allow_credentials=True`, methods/headers wide open. Make
sure production sets `APP_CORS_ORIGINS` to the real deployed origin(s) only.

**Egress to internal services**: the API is the only component besides the worker that
calls the LLM Gateway and Sandbox Runner, using the shared `APP_INTERNAL_SERVICE_TOKEN`
(§6). The API itself never touches Docker or holds LLM provider keys.

## 4. Worker (`services/worker`)

Runs detached from any public port — it only polls Supabase-backed job queues
(`pgmq` via `read_ingestion_jobs`/`read_generation_jobs`, `SECURITY DEFINER` RPCs
granted only to `service_role`; see §7) and calls the LLM Gateway and Sandbox Runner
with the internal token, same as the API. It holds the Supabase service-role key to
write generated course/lesson content back to Postgres. There is no learner-facing
entry point into the worker — job payloads originate from API-side enqueue calls that
are themselves scoped to the requesting user's own course/source.

The worker is also the source of AI-generated code: `lesson_agent.py` /
`lesson_build.py` drive an LLM to write lesson starter code and reference solutions,
which are validated by actually executing them in the sandbox (`content_validation`
profile) before being shown to a learner. AI-generated code is treated with the same
distrust as learner-submitted code — it runs in the identical hardened container (§5).

## 5. Sandbox Runner (`services/sandbox_runner`) — code execution isolation

This is the only component that executes arbitrary code (learner lab submissions via
the API's `learner_visible` profile, and AI-generated solutions/tests via the worker's
`content_validation` profile) and the only component with Docker access.

- **Narrow internal API**: `POST /internal/v1/runs` (pytest) and
  `/internal/v1/scripts` (arbitrary entry-point script), gated by
  `X-Internal-Service-Token`, with a fail-closed startup check
  (`require_runtime_configuration`) that refuses to boot outside `development`
  without a token configured.
- **Input validation**: file paths are restricted to relative, `.py`-suffixed,
  traversal-free (`..` rejected), depth-limited paths; file and workspace-total size
  caps (20 KB / file, 128 KB / run, ≤20 files); the archive sent to Docker is *built*
  from these validated inputs server-side rather than extracted from attacker-supplied
  tar bytes, avoiding the classic `tarfile` path-traversal class of bug.
- **No shell anywhere in the execution path**: commands are passed to the Docker SDK
  as argv lists (`["pytest", ...]`, `["python", "-u", entry_path]`) — never
  `shell=True`, `subprocess`, `os.system`, or `eval`.
- **Per-run container hardening** (`sandbox_runner/runner.py`): `network_disabled=True`
  (no network access, so no exfiltration/SSRF from inside sandboxed code),
  `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, non-root user
  (`65534:65534`, i.e. `nobody`), `mem_limit=256m`, 1 CPU (`nano_cpus=1_000_000_000`),
  `pids_limit=64`, and a wall-clock timeout that kills and force-removes the container.
  Every container is single-use and removed in a `finally` block regardless of outcome.
- **Architectural risk accepted by design**: the sandbox-runner container itself has
  `/var/run/docker.sock` mounted (docker-outside-of-docker, [`docker-compose.yml`](docker-compose.yml))
  so it can launch sibling containers. That gives the sandbox-runner *process* root-
  equivalent control of the host. No RCE path into that process was found in review
  (inputs are tightly validated, no shell/eval surface), but because a bug there would
  be catastrophic rather than merely contained, this service's own code surface should
  stay minimal and any change to it should get extra scrutiny. In any real deployment,
  `sandbox-runner` must sit on an internal-only network with no public port —
  the local [`docker-compose.yml`](../docker-compose.yml) publishes `8020` to the host
  for dev convenience only.

See [`SANDBOX_ARCHITECTURE.md`](SANDBOX_ARCHITECTURE.md) for the full design
rationale.

## 6. Service-to-service authentication (internal token)

The API, worker, LLM Gateway, and Sandbox Runner all share one bearer secret,
`APP_INTERNAL_SERVICE_TOKEN`, checked with a plain `!=` comparison (not
constant-time — low practical risk given these are internal-network-only calls, but
worth swapping for `hmac.compare_digest` opportunistically). Every internal service
fails closed: if no token is configured and `APP_ENVIRONMENT != development`, the
service refuses to start (`require_runtime_configuration`) or the endpoint returns
503. There is currently a single shared token across all three internal services
rather than per-service credentials — a compromise of any one internal service's
token grants access to the same endpoints from any caller on the internal network.

## 7. Data layer (Supabase)

- **Row Level Security** is enabled on all 21 application tables. Most have explicit
  `auth.uid()`-based policies (direct ownership, e.g. `courses.owner_id = auth.uid()`,
  or a join back to an owning course/assignment, e.g. `quiz_responses`/`submissions`
  scoped via `assignment_id`). Storage buckets (`sources`, `submissions`) are scoped by
  a `(storage.foldername(name))[1] = auth.uid()::text` path-prefix check.
- Seven tables (`source_document_versions`, `source_chunks`, `concept_prerequisites`,
  `modules`, `lesson_definitions`, `lesson_revisions`, `mastery_parameters`) have RLS
  **enabled with no policy defined** — this is default-deny for any non-service-role
  client, not a gap; they're only ever touched via the service-role key or
  `SECURITY DEFINER` RPCs below, never directly by an end-user session.
- **`service_role` key**: held only by the API and worker (`app/settings.py`,
  `app/supabase.py`), never by the frontend. It bypasses RLS entirely, which is why
  the API's application-layer ownership checks (§3) — not RLS — are the actual
  authorization boundary for API-served reads/writes.
- **~29 `SECURITY DEFINER` functions** implement the job-queue and course-generation
  pipeline (e.g. `enqueue_course_planning`, `claim_lesson_build`, `apply_course_plan`,
  `read_ingestion_jobs`/`archive_ingestion_job`, `delete_course`). All are explicitly
  `revoke`d from `public`/`anon`/`authenticated` and `grant`ed only to `service_role`
  — an authenticated end-user session cannot invoke any of them directly, only the
  backend can.

## 8. Secrets management

- All LLM provider credentials (OpenAI key, Azure endpoint, AWS Bedrock credentials)
  live only in the LLM Gateway's environment — the API and worker never see them,
  they only call the gateway's internal HTTP API.
- `.env` and `.env.local` are gitignored repo-wide; `apps/web/.env.local` is
  regenerated from the root `.env` by `scripts/sync-env.js`, which filters to
  `NEXT_PUBLIC_*` keys only, so a server secret added to the root `.env` cannot
  accidentally leak into the frontend bundle via that script.
- No CI/CD workflows are currently configured in this repo (no `.github/workflows`),
  so there's no secrets-in-CI surface to audit yet — revisit this section once one
  exists.

## 9. Known limitations / accepted risk

- **Local dev auth bypass by design**: `APP_AUTH_MODE=development` and the sandbox/
  gateway's "no token required in development" fallback are intentionally open and
  must never be set in a deployed environment. There's no runtime assertion outside
  `require_runtime_configuration()` preventing `APP_ENVIRONMENT=development` from
  being set in production by mistake — this is an operational/config-discipline
  control, not a code-enforced one.
- **Shared internal token** across three internal services (§6) rather than per-service
  credentials.
- **No security headers / CSP** on the Next.js app yet.
- **Sandbox-runner's `docker.sock` mount** is an inherent trade-off of the
  docker-outside-of-docker pattern (§5) — it cannot be fully eliminated without
  switching to a different isolation mechanism (e.g. gVisor/Firecracker via a
  dedicated execution host), only contained through network isolation and a minimal,
  well-audited code surface in that one service.

## 10. Reporting a vulnerability

This is a hackathon-stage project without a formal disclosure program. If you find a
security issue, open an issue in this repository or contact the maintainer directly
rather than filing a public issue with exploit details.
