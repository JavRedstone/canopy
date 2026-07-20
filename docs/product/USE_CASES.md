# Use cases — reference

**Purpose:** a side-by-side reference of plausible use cases for Canopy, each checked
against what the product can *actually do today* rather than what any plan describes.
"Feasibility today" below is graded against the real implementation — schemas, the
sandbox registry, ingestion, the auth model — verified in code, not assumed from intent.

This version is written against [`HACKATHON.md`](../demo/HACKATHON.md)'s own judging
lens rather than a business case: **potential impact** (a clear user, a specific pain
point, practical value), **design** (a complete, coherent product experience, not a
technical concept demo), and **quality of idea** (originality, real understanding of the
problem). Canopy's natural fit is the **Education** track.

## What actually works today

Read this first — it's the ground truth every use case below is checked against.

- **Multi-file source ingestion.** PDF, Markdown, or plain text, up to 6 MB each,
  attached to a course by `source_ids` (`services/api/app/routers/sources.py`). Multiple
  files per course is normal; a live repo or "watch this folder" integration doesn't
  exist — every packet is uploaded by hand.
- **Three coding-lab environments, not one.** `python-basic` (numpy/pandas/scikit-learn,
  implement-it-yourself framing), `python-ml` (numpy/pandas/scipy/scikit-learn/
  matplotlib/seaborn/PyTorch/torchvision — GPU-accelerated where the host has one, CPU
  otherwise, no TensorFlow), and `cpp-basic` (g++ 17 + doctest). A course picks one at
  creation (`courses.language`) and every lab in it targets that environment
  (`services/worker/worker/lesson_agent.py`, `services/sandbox_runner/`). Each lab is
  sandbox-verified before it's ever shown to a learner: hidden + visible pytest/doctest
  suites, a starter that's confirmed to fail, and a real repair loop that iterates
  against the sandbox rather than trusting the model's first answer.
- **Real citations.** Every claim in a lesson can carry an inline `[chunk-id]` marker
  that resolves to the actual excerpt it came from, clickable in the UI
  (`citation_excerpt`, `services/api/app/repository.py`).
- **A real mastery model, not a completion checkbox.** Two-track Bayesian Knowledge
  Tracing (`p(understand)` from quizzes, `p(apply)` from labs) with prerequisite-review
  nudges when a learner is struggling and the concept it builds on is shaky
  (`services/api/app/mastery.py`, `PrerequisiteRecommendation` in `schemas.py`).
- **A takeaway artifact.** The full course — lessons, worked examples, quizzes, cited
  references — exports as a real PDF "coursebook"
  (`export_coursebook`/`render_textbook_pdf`), not just a web page that stops existing
  when the trial ends.
- **A completion certificate.** Once every lesson in a course is done, a certificate
  (learner, course title, issue date, a deterministic id) is available and pops up
  automatically the next time the finished course is opened — exportable as its own PDF
  (`GET .../certificate`, `.../export/certificate`, `certificate_pdf.py`).
- **Free course cloning.** An owner can flip `is_shared` on; anyone with the course id
  can import a full copy — modules, concepts, lesson content, prerequisites, source
  attachments — under their own account. Import is pure database cloning, no worker/LLM
  call involved (`import_shared_course`,
  `supabase/migrations/20260719000000_course_sharing_and_import.sql`), so distributing
  one course to many learners costs nothing per additional learner. Each importer gets
  their *own* independent copy: their own progress, mastery, and submissions, with no
  link back to the original for the sharer to see how anyone else is doing.

## What's still missing

- **No cohort/manager view.** Sharing is Google-Docs-style (anyone with the link gets
  their own copy), not a live-shared course with a dashboard the sharer can watch. There
  is no "assign this to five people and see their progress" — that would need a real
  org/team layer, which doesn't exist (`courses.owner_id` is the only authorization axis
  anywhere in the schema).
- **No repository/codebase ingestion.** Sources are uploaded one file at a time by a
  human; there's no "point this at a GitHub repo."
- **Source parsing is prose-oriented.** A non-Markdown text file (what a code excerpt or
  config file would be uploaded as) gets one generic `section="Document"` label and
  naive character-count chunking (`services/worker/worker/parsing.py`) — a citation into
  prose looks much better than a citation into code.
- **One shared deployment.** Everything runs against a single Supabase project and a
  single LLM Gateway; there's no per-tenant isolation or private-deployment story.

## Use cases

### 1. Turn any source into a validated, hands-on course (solo self-study)

**Who:** a learner with a paper, a library's docs, or a textbook chapter, who wants more
than a summary — they want lessons that cite the real material, plus labs and quizzes
that actually check whether the concept landed.

**Workflow:** upload the source, set a goal (see
[`SAMPLE_COURSES.md`](./SAMPLE_COURSES.md) — the same source produces a conceptual
course, a hands-on course, or a from-scratch-implementation course depending on the
goal), work through the generated modules solo.

**Why it fits:** this is the use case that needs nothing Canopy doesn't already have —
no team layer, no non-Python-family sandbox, no repo ingestion. It's also the most
complete *product* experience end to end: cited lessons, sandbox-verified labs, real
mastery tracking, a PDF coursebook at the end. As a hackathon demo it's the safest
"show the whole loop working" path.

### 2. Learn a library or systems concept by actually using it

**Who:** someone who wants to get hands-on with a specific technical stack — PyTorch and
the classical ML toolkit, or C++ fundamentals like manual memory management and pointer
arithmetic — rather than reading about it.

**Workflow:** create a course with its language set to `python-ml` or `cpp`; every lab
in that course is generated, sandboxed, and graded against that environment
specifically. A `python-ml` lab can lean on real `torch.nn` modules and scikit-learn
estimators instead of hand-rolling them; a `cpp` lab compiles with g++ and is graded with
doctest.

**Why it fits:** this is the newest capability in the codebase and the most direct
"quality of idea" story — the sandbox isn't a fixed Python box, it's a small registry of
curated, resource-tuned environments (`services/sandbox_runner/sandbox_runner/runner.py`)
that the course-generation prompt set already knows how to target correctly (each
environment tells the model exactly what's importable, so a lab can't silently reference
a package that isn't there). It's also a good demo of the agentic repair loop actually
mattering: a generated lab that imports something unavailable, or whose starter already
passes, gets caught and fixed against a real sandbox run before a learner ever sees it.

### 3. One course, shared for free with many learners

**Who:** anyone who built a course worth reusing — a study-group organizer, a mentor, a
teammate who wants to hand a colleague the exact course they just went through — without
an org/team system existing yet.

**Workflow:** the owner turns sharing on and sends the course id/link; each recipient
imports their own copy in one action, with no regeneration cost paid twice for the same
material.

**Why it fits:** it's a genuine, non-obvious technical decision (clone at the database
layer instead of re-running generation) that turns an admitted structural gap — no team
layer — into something that still mostly works for the common case, one link at a time.
It's an easy, fast thing to demo (import finishes instantly, no waiting on a worker), and
it directly addresses potential impact: the thing worth sharing is the validated course
someone already built, not a prompt someone has to re-type.

### 4. Prove you actually learned it

**Who:** a learner (solo or from use case #3) who wants evidence of progress, not just a
feeling of having "gone through" the material.

**Workflow:** work through labs and quizzes; watch the per-concept mastery meter
(`p(understand)`/`p(apply)`) move as BKT updates on real observations, not a naive
percent-complete bar; get nudged back to a shaky prerequisite the moment it's actually
blocking progress on the current concept, instead of failing silently; once every lesson
is done, a certificate pops up automatically; export the finished course as a PDF
coursebook to keep.

**Why it fits:** this is the "design/complete product experience" criterion most
directly — the mastery model and prerequisite nudges are real inference over recorded
observations, not decoration, and the certificate plus PDF export are tangible artifacts
a demo can end on. It's less flashy to show in isolation than a live-coding lab, so it demos best paired
with #1 or #2 rather than standalone.
