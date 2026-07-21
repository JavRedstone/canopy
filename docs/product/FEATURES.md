# Canopy — Features

Everything Canopy does today, verified against the running code rather than intent. Not a
roadmap: see [`ROADMAP.md`](./ROADMAP.md) for what is planned, and the
[Scaffolded, not shipped](#scaffolded-not-shipped) section at the end for capabilities the
schema supports but no code path produces.

---

## Course creation & sources

- Turn any technical source into a generated course: upload a PDF, Markdown file, or plain
  text (6 MB cap, enforced at both table and storage-bucket level), or paste text directly
- Multiple ordered sources per course
- Set a learning goal in your own words. The same source produces a different course
  depending on what you ask for
- Adjustable course length (6–24 activities) and quiz attempt cap (1–10), set at creation
  and editable later
- Automatic coding-language selection: the planner reads your goal and sources and picks
  Python, Python (ML/DL), or C++. Not a manual toggle, and deliberately not settable by the
  caller
- Live generation progress (sources → plan → lessons) with a step rail, per-step detail, a
  lessons-built bar, and automatic refresh
- Stall detection with one-click **Resume**, which re-queues only the lessons that never
  finished and keeps everything already built
- Full course regeneration, and single-lesson regeneration
- Course settings: rename, change quiz attempts, change the activity range
- Course deletion, including purging queued jobs so workers skip deleted rows
- Source library: see every document a course was built from, with per-source status
  (uploading / queued / processing / ready / failed) and signed-URL re-download

## Lessons, grounded in your source

- Structured lessons generated from the source material, not a generic summary
- Inline citations back to the exact excerpt a claim came from; one click opens the original
  passage with filename, section, and page
- Citation markers render as numbered superscripts, never raw UUIDs
- Worked examples and quiz questions interleaved at the point in the prose where they are
  relevant, via `{{example:N}}` / `{{quiz:N}}` markers the generator emits
- Rich rendering: Markdown, fenced code, lists, and LaTeX math through KaTeX (`$…$`,
  `$$…$$`, `\(…\)`, `\[…\]`)
- Three lesson shapes, each with its own generation prompt: conceptual lecture, coding lab,
  and integrative assessment checkpoint
- Reading-only lessons complete on view; anything with questions or code requires the work

## Hands-on coding labs

- Real in-browser Monaco editor, multi-file workspaces, full-viewport workspace layout
- **Run** (visible checks only, records nothing) vs. **Submit** (full suite including hidden
  tests, records applied-skill mastery) — a genuine "let me try it" loop before it counts
- Hidden tests stay hidden; the visible test files appear in the editor as read-only tabs so
  you can read what you are graded against
- Every lab is self-verified before a learner sees it. The generator's starter code must
  *fail* its tests and the reference solution must *pass* them, both run in a real sandbox.
  If either is wrong, an agentic repair loop edits and re-runs until it holds
- Scratch console: run arbitrary code against your lab's own functions to poke at an idea,
  with output and exit code, never affecting grading (Python labs)
- Reference solution reveal, gated behind a spoiler confirmation, added as **new** editable
  and runnable files alongside your own work rather than overwriting it, and excluded from
  grading
- Test console with per-case pass/fail, click-to-expand failure output, and full raw logs
- Three lab environments: Python, Python ML/DL (numpy/pandas/scikit-learn/PyTorch, GPU-
  capable), and C++

## Quizzes

- Four question types: multiple choice, multi-select, fill-in-the-blank, and short answer
  graded by an LLM against a rubric the learner never sees
- Per-course attempt cap with progressive reveal: while attempts remain, correct answers and
  explanations stay withheld
- A wrong guess never leaks the answer — only the option you picked is marked
- Answers persist across reloads and replay as answered
- Topic-level assessments that act as a module mastery checkpoint

## AI learning helper

- In-context tutor for any lesson, lab, or quiz question, prompted to guide rather than hand
  over answers, and structurally prevented from seeing hidden tests, correct answers, or
  rubrics
- Select any passage and ask about just that text, with native CSS Custom Highlight so the
  page DOM is never mutated
- Focus a specific quiz question and ask for a hint on it
- The helper sees your actual draft code, so hints are about what you wrote
- Context-sensitive quick prompts that change based on whether you are on prose, a lab, or a
  question
- Ask it to rewrite a confusing passage and apply the rewrite in place (client-side; not
  persisted across reload)

## Practice mode

- Low-stakes practice pool per concept, separate from graded quizzes: answers and every
  option's explanation reveal immediately, and a miss never lowers mastery
- Scoped to one concept or the whole course
- Configurable sessions: length (5/10/20/endless), order (shuffle / weakest-first / course
  order), filter (new / everything / missed), summarised back as a plain sentence
- Non-repeat rotation across sessions: never-seen first, then least-seen, then longest-ago
- Round-robin spread across concepts rather than draining one at a time
- Correct practice answers earn capped mastery credit (ceiling 0.85), so drilling can show
  progress but can never reach the mastery bar on its own
- On-demand top-up when a scope runs dry, plus automatic top-up before you hit empty

## Mastery tracking & adaptive review

- Dual-track Bayesian mastery per concept: **understand** (from quizzes and practice) and
  **apply** (from code submissions), never blended into one completion percentage
- Per-assessment-kind parameters, so a passing coding submission counts as stronger evidence
  than a lucky multiple-choice guess
- Tracks read "no data yet" rather than 0% until there is real evidence
- Per-concept meters with a threshold marker, and a course-wide mastery dashboard
- Prerequisite-aware nudges: when you are genuinely struggling *and* a prerequisite is shaky,
  Canopy names the prerequisite and recommends reviewing it first. Fires inline right after a
  wrong answer or failed submission, and again as a standing course-level list
- Transitive prerequisite closure, sorted weakest-first
- Accept, defer, or dismiss a recommendation; recommendations whose prerequisites have since
  improved drop off silently instead of nagging

## Certificates & export

- Full PDF coursebook export: every lesson, worked example, quiz, and a deduplicated
  reference section of cited source excerpts
- Completion certificate once every lesson is done, issued once and dated permanently
- Public, unauthenticated verification link keyed on an unguessable ID, with its own PDF
- Certificate PDF and web view share one layout, so they cannot drift

## Sharing & import

- One-click link sharing for a course
- Anyone with the link imports their own independent copy, with their own progress and
  mastery, at zero regeneration cost
- Import accepts a raw course ID or a pasted share link, and auto-opens pre-filled when you
  arrive via a share URL
- Sharing copies content only. Progress, mastery, submissions, and adaptation history are
  never cloned, and an unshared course is indistinguishable from a nonexistent one

## Account

- Passwordless magic-link email sign-in
- Editable display name, shown on certificates instead of a bare email

## Standalone playground

- Run code in six environments (Python, Python ML/DL, JavaScript, Go, C++, C) with nothing
  saved and no course required
- Each ships a runnable pass/fail example so the demo shows a real framework-reported failure
- Same hardened, network-disabled sandbox as real labs

## Platform & engineering

- **Provider-agnostic LLM gateway** with four implementations: OpenAI, Azure OpenAI,
  Bedrock-OpenAI, and Bedrock Converse (Claude Sonnet 4.5). Swappable by config
- **Per-task model routing** rather than one model everywhere:

  | Task | Default |
  |---|---|
  | Course outline, lesson repair | `gpt-5.6-sol` |
  | Module concepts, lesson build, helper, practice pool | `gpt-5.6-luna` |
  | Embeddings | `text-embedding-3-small` |

- Retrieval-grounded planning: source chunks are embedded and retrieved by relevance per
  course *and* per module, so each module is grounded in its own nearest passages
- Citation validation: a lesson that cites a chunk outside its concept's allowed set is
  rejected and regenerated
- Source excerpts are prompt-injection-hedged as untrusted reference material
- Three nested retry layers: schema-validation retry, citation-validation regeneration, and
  bounded job requeue. Transient errors never consume the retry budget
- Crash-safe builds: validated lesson content is checkpointed, so a worker restart mid-build
  does not re-pay for generation
- Sandbox hardening: network disabled, all capabilities dropped, non-root user,
  no-new-privileges, per-environment memory/CPU/PID limits, single-use containers
  force-removed
- Desktop-only gate resolved in pure CSS before first paint, using `pointer: fine` so tablets
  are correctly excluded

## Developer / demo tooling

Gated behind `NODE_ENV=development` in the UI, and 404 server-side in production.

- Demo auto-complete: an LLM plays the learner through some or all of a course, through the
  same real grading and sandbox paths a human hits
- Target fully-mastered or a deliberately mixed mastery state with a correct-rate slider
- Per-concept selection, live progress, per-concept result chips, and cancel
- Per-lesson fill from the lesson page itself
- Demo clear: resets mastery and attempt state back to never-attempted

---

## Scaffolded, not shipped

Present in the schema or type system, with **no code path that produces them**. Listed so
nobody demos them by accident.

| Capability | Status |
|---|---|
| Mastery decay | No decay logic. `mastery.last_update` is written but never read |
| Spaced-repetition scheduling | No scheduler column, job, or interval anywhere |
| Transfer checks | `kind='transfer_check'` allowed; never written. Every read filters `kind='lesson'` |
| Per-concept BKT tuning | `mastery_parameters` is created and cloned on import, but read by nothing; hard-coded defaults are used |
| Support / remediation artifacts | `support_lesson_artifacts` table never written to |
| Adaptive routing | `route_kind` allows four values; only `canonical` is ever written |
| Diagram generation | Does not exist anywhere in the codebase |
| Coding submissions table | `submissions` never written; grading is recorded as observations |
| Difficulty calibration | `practice_items.times_served` / `times_correct` incremented but never read |
| JavaScript / Go / C labs | Environments fully built and validated, but reachable only from the playground, not course generation |
| Points | Live API endpoint and typed client wrapper, but no UI surface since the header chip was removed |
