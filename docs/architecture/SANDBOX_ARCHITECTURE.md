# The Coding Lab Sandbox: Frontend UX and Backend Execution

**Scope:** How a learner's code goes from the in-browser editor to an isolated Docker container and back, for both the `apps/web` coding-lab UI and the `services/api` / `services/sandbox_runner` backend that executes it. Written against the current running code (commit-accurate as of this file's date), not the aspirational design in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Why a sandbox exists at all

A coding lesson's learner-submitted Python has to actually run, against the lesson's own test suite, to know whether it's correct. Running arbitrary, possibly-broken, possibly-adversarial code anywhere near the API process, the database, or the network is not something you do in-process. `services/sandbox_runner` is the **only** service in this codebase with Docker access; the API and worker never import a Docker SDK, they only ever talk to the sandbox runner over HTTP. That boundary is the whole point: a bug or exploit in learner code should be contained to a single disposable container, not able to reach Supabase, the LLM gateway, or any other service.

## Frontend: what the learner sees and does

All of this lives in [`components/concept-detail.tsx`](../../apps/web/components/concept-detail.tsx), specifically the `concept.kind === "coding"` branch (the "lab" layout, as opposed to the plain-prose lesson layout used for `concept.kind === "conceptual"`).

### The two-pane layout

- **Left pane** ("Instructions"): tabs between **Lesson** (the explanation, worked examples, hints, and the mastery-check quiz) and **Solution** (see below), in a fixed-width, normally-themed column.
- **Right pane** ("Workspace"): a nested dark [MUI theme](../../apps/web/lib/theme.ts) (`labTheme`) scoped to just this pane, so it reads as a code-editor surface regardless of the app's light theme elsewhere. Contains:
  - A row of **file tabs** (one per editable starter file, plus any read-only public test files with a lock icon), backed by a single [Monaco](https://microsoft.github.io/monaco-editor/) instance (`@monaco-editor/react`, dynamically imported with `ssr: false` since Monaco needs a real DOM).
  - **Run** and **Submit** buttons.
  - A fixed-height **console panel** with three tabs: **Testcase**, **Console**, **Test Result**.

### Run vs. Submit: two different backend calls

These are easy to conflate but hit different endpoints and mean different things:

| | Button | Endpoint | What it runs | Where the result shows |
|---|---|---|---|---|
| **Run** | `handleRunScript` | `POST /courses/{id}/concepts/{slug}/run-script` | The **Testcase** tab's scratch script (`scratch.py`, default: `from <module> import *`) as a plain Python script, no pytest, no grading | **Console** tab |
| **Submit** | `handleRun` | `POST /courses/{id}/concepts/{slug}/run` | The **full pytest suite** (public *and* hidden test files) against the learner's files | **Test Result** tab |

"Run" exists purely so a learner can `print()`-debug freely without it counting for anything. "Submit" is the graded action: on a pass, the API marks the lesson complete server-side (`repository.complete_coding_lesson`, in [`courses.py`](../../services/api/app/routers/courses.py#L94-L118)).

The **Test Result** tab parses the raw pytest output (via [`lib/pytest-output.ts`](../../apps/web/lib/pytest-output.ts)) into a per-test-case list with pass/fail/skip icons. Each failing case can be expanded individually to see just its own traceback (parsed out of pytest's `FAILURES`/`ERRORS` section); there's also a "Full raw output" toggle for the complete, unparsed pytest output as a fallback.

### The file-set contract (and why it matters)

Both `/run` and `/run-script` reject the request outright (`422 Unprocessable Content`, `"Submit exactly the lesson starter files."`) unless the submitted file paths are **exactly** the lesson's starter file paths, no more, no fewer (see `expected_paths` / `set(submitted) != expected_paths` in [`courses.py`](../../services/api/app/routers/courses.py#L104-L107)). This is a real, enforced contract, not just a suggestion, and the frontend has to respect it: `concept-detail.tsx` keeps a `submittableFiles` list, filtered down to only the starter-file paths, and always sends *that*, never the raw editor `files` state, to `runLesson`/`runLessonScript`.

That filtering matters because of the next feature:

### Revealing the solution

Clicking **Show solution** (left pane, Solution tab) opens a confirmation dialog first: the reveal isn't reversible-feeling by accident, so it's a deliberate click-through, not a silent action. Confirming:

1. Adds the lesson's reference solution files to the workspace as **new, separately-named tabs** (`classification_workflow.py` → `classification_workflow_solution.py`), rather than overwriting the learner's own files. The learner's work is never touched.
2. Switches the active tab to the new solution file. It's a normal, fully editable Monaco instance, not a read-only preview, so it can be tinkered with.
3. Because these solution tabs have paths outside the starter-file set, they're automatically excluded from what gets sent to Run/Submit by the `submittableFiles` filter above. Run and Submit always grade the learner's own files, never the solution; a hint under the editor says as much whenever a solution tab is active, so this isn't a silent surprise.

## Backend: the request's path to a container and back

```text
apps/web (Monaco + fetch)
      |
      v
FastAPI API  --validates exact file-set, loads public+hidden tests-->  SandboxRunnerClient (services/api/app/sandbox.py)
      |                                                                        |
      |  (X-Internal-Service-Token header)                                    v
      |                                                          sandbox_runner service (FastAPI)
      |                                                                        |
      |                                                                        v
      |                                                          DockerSandboxRunner (services/sandbox_runner/sandbox_runner/runner.py)
      |                                                                        |
      |                                                                        v
      |                                                          a fresh, disposable Docker container
      |                                                             (canopy-lesson-sandbox:python-basic)
      v
learner-safe JSON response (passed/output/exit_code/timed_out)
```

1. **API validates and assembles the file set.** `run_lesson`/`run_script` in [`courses.py`](../../services/api/app/routers/courses.py) check the exact-path contract above, then (for `/run` specifically) load `public_test_files` **and** `hidden_test_files` from the repository and append both to the submitted files before handing off to the sandbox.
2. **`SandboxRunnerClient`** ([`services/api/app/sandbox.py`](../../services/api/app/sandbox.py)) is a thin `httpx` client: the API process itself never touches Docker. It POSTs to `/internal/v1/runs` or `/internal/v1/scripts` on the sandbox runner, authenticated with an `X-Internal-Service-Token` header (in local development this header can be absent; production must set it, see the "not yet production-safe" section below).
3. **`sandbox_runner`'s FastAPI app** ([`services/sandbox_runner/sandbox_runner/main.py`](../../services/sandbox_runner/sandbox_runner/main.py)) validates the request shape with Pydantic (unique paths, size limits, `entry_path` must be one of the submitted files) and hands off to `DockerSandboxRunner`.
4. **`DockerSandboxRunner`** ([`services/sandbox_runner/sandbox_runner/runner.py`](../../services/sandbox_runner/sandbox_runner/runner.py)) does the actual execution:
   - Creates a **fresh container** per run from a curated `SandboxEnvironment` registry (`python-basic`, `python-ml`, `javascript-basic`, `go-basic`, `cpp-basic`, `c-basic`, each its own Dockerfile under [`sandbox_image/`](../../services/sandbox_runner/sandbox_image/), e.g. `python-basic` is `python:3.13-slim` + `pytest`/`pytest-timeout`), building the requested one lazily on first use if it doesn't exist yet. There is no path to an unregistered/arbitrary image.
   - Copies the submitted files in via Docker's `put_archive` (a tar stream built in-memory, nothing touches the host filesystem).
   - Runs the environment's own test/script command (e.g. `pytest -v -p no:cacheprovider .` / `python -u <entry_path>` for `python-basic`/`python-ml`; `node --test` / `node <entry_path>` for `javascript-basic`; `go test ./...` / `go run <entry_path>` for `go-basic`; `g++ ... *.cpp -o ... && ...` compile-then-run, linked against a bootstrapped doctest `main()`, for `cpp-basic`; `gcc -fsanitize=address ... *.c -o ... && ...` for `c-basic`, linked against a bootstrapped self-registering `TEST_CASE`/`CHECK` runner since C has no doctest equivalent) as the container's command.
   - Per-environment resource limits and GPU: most environments share one default (`mem_limit=256m`, one CPU), but `SandboxEnvironment` allows overriding `mem_limit`/`nano_cpus`/`pids_limit`/`timeout_seconds` per environment (`python-ml` needs meaningfully more of all three, since torch/CUDA alone is a few hundred MB before a lab does anything) and an opt-in `gpu` flag that requests a GPU device and transparently falls back to CPU-only if the host has no GPU/nvidia-container-toolkit (`_create_container`, catches the `APIError` and retries without the device request).
   - `c-basic` additionally compiles with `-fsanitize=address` (AddressSanitizer, including LeakSanitizer) rather than shelling out to Valgrind: it's compile-time instrumentation with no extra runtime privileges, verified to work under this sandbox's exact hardening (`cap_drop=ALL`, non-root, `no-new-privileges`); Valgrind's ptrace-style approach would need capabilities this container deliberately doesn't grant.
   - Applies real containment: `network_disabled=True` (no network at all), non-root user (`65534:65534`, i.e. `nobody`), `cap_drop=["ALL"]`, `no-new-privileges`, resource limits as above, and a wall-clock timeout (`container.wait(timeout=...)`, per-environment override or the runner's default) that kills and marks the run `timed_out` if exceeded.
   - Captures combined stdout+stderr (`container.logs(...)`, truncated to the last 16,000 characters) as the `output` field, and the process exit code.
   - **Always force-removes the container** in a `finally` block: every run is single-use and disposable, pass or fail.
5. **The API returns a narrow JSON shape** to the frontend: `{ passed, output, timed_out }` for Submit, `{ output, exit_code, timed_out }` for Run. `passed` is derived as `exit_code == 0 and not timed_out`.

### What's *not* production-hardened yet

This is a working **development** sandbox, not a hardened one, and it's worth being explicit about that rather than letting the strong-sounding container flags above imply more than they deliver. The current limitations are:

- **Submit currently runs and exposes hidden tests to the learner.** The raw pytest output returned from `/run` includes hidden-test names, assertions, and tracebacks on failure; there's no separation between "you passed/failed" and "here's exactly what the hidden test checked."
- **The container isn't a hostile-code-grade boundary.** It deliberately runs with `read_only=False` (Docker's archive-copy API rejects a read-only rootfs outright), and while it disables network/drops capabilities/limits resources, it's explicitly scoped as a local content-validation executor, not something meant to survive genuinely adversarial input in production. A production hardening pass would mean a rootless/microVM- or gVisor-class executor, a read-only image, seccomp/AppArmor policy, and distinct trust levels for learner-visible vs. hidden-evaluator runs.
- **The sandbox runner and LLM gateway ports are host-published in Compose, and internal auth is optional in development**: fine locally, not something to carry into a real deployment.

None of this affects how the *frontend* behaves today (Run and Submit work as described above), but it's the honest caveat on "isolated": isolated-enough-for-local-development, not yet isolated-enough-for-hostile-internet-input.
