# Canopy: Features

A checklist of what Canopy actually does today, verified against the running code (not
a roadmap, see [`ROADMAP.md`](./ROADMAP.md) for what's planned). Grouped by what a
learner or course owner actually experiences in the app.

## Course creation & sources

- [x] Turn any technical source into a generated course: upload a PDF, Markdown file,
      or plain text (up to 6 MB), or paste text directly
- [x] Multiple sources per course
- [x] Set a learning goal in your own words: the same source produces a different
      course depending on what you say you want from it
- [x] Adjustable course length (6–24 activities) and quiz retry attempts, set at creation
- [x] Automatic coding-lab language selection: the planner reads your goal and source
      and picks Python, Python (ML/DL), or C++ for you, no manual toggle
- [x] Live generation progress (sources → plan → lessons) with automatic refresh
- [x] Stall detection with a one-click "resume remaining lessons" if generation stalls
- [x] Full course regeneration, and single-lesson regeneration
- [x] Course settings: rename, change quiz attempts, change activity-count range
- [x] Course deletion
- [x] Source library viewer: see and re-download every document a course was built from

## Lessons, grounded in your source

- [x] Structured lessons generated directly from the source material, not a generic
      summary
- [x] Every claim can carry an inline citation back to the exact source excerpt it came
      from, one click to view the original passage
- [x] Worked examples embedded at the point in the lesson where they're relevant
- [x] Rich lesson rendering: Markdown, inline math, code blocks

## Hands-on coding labs

- [x] Real in-browser code editor (Monaco), multi-file workspaces
- [x] **Run** (quick, visible checks only) vs. **Submit** (full hidden test suite,
      counts toward mastery): a real "let me try it" loop before it counts
- [x] Every lab is self-verified before a learner ever sees it: the generator's starter
      code, and its own reference solution, are run against a real sandbox, and if
      either fails (starter secretly already passes, or the solution doesn't actually
      pass its own tests) the model iterates against the real failure output until it's
      right; no lab reaches a learner unverified
- [x] Scratch console: run arbitrary code against your lab's own functions to poke at
      an idea, without affecting grading
- [x] Reference solution reveal, gated behind a "you'll spoil it" confirmation, added as
      new editable/runnable files alongside your own work
- [x] Detailed test-result console: pass/fail per test case, expandable output, full raw
      log
- [x] Three coding environments: Python, Python (ML/DL: numpy/pandas/scikit-learn/
      PyTorch/torchvision), and C++

## Quizzes

- [x] Four question types: multiple choice, multi-select, fill-in-the-blank, short
      answer (rubric-graded)
- [x] Configurable attempt cap per course, with progressive answer/explanation reveal
- [x] Topic-level assessments that gate a module as a mastery checkpoint

## AI learning helper

- [x] In-context AI tutor for any lesson, lab, or quiz question: gives guided hints,
      never hands over the answer
- [x] Select any passage on the page and ask the helper about just that text
- [x] Ask the helper to rewrite a confusing passage, and apply the rewrite in place

## Practice mode

- [x] Low-stakes practice question pool per concept, separate from graded quizzes:
      answers reveal immediately and never lower your mastery
- [x] Practice scoped to one concept or the whole course
- [x] Configurable sessions: length, order (shuffle / weakest-first / course order),
      filter (new / everything / missed)
- [x] On-demand top-up when a scope runs out of unseen questions

## Mastery tracking & adaptive review

- [x] Dual-track mastery model: tracks **understanding** (from quizzes) and **applying**
      (from labs) separately per concept, not one blended completion percentage
- [x] Per-concept mastery meters and a course-wide mastery dashboard
- [x] Prerequisite-aware nudges: the moment you're struggling on a concept, Canopy
      identifies which shaky prerequisite it builds on and recommends reviewing that
      first, both inline right after a wrong answer and as a standing course-level list
- [x] Accept, defer, or dismiss a recommended review
- [x] Points: a gamified per-lesson completion reward on top of the real mastery signal

## Certificates & export

- [x] Full PDF "coursebook" export of a course (lessons, worked examples, quizzes,
      cited references), a real takeaway, not just a page that disappears
- [x] Completion certificate once every lesson in a course is done, with a public,
      shareable verification link and its own PDF export

## Sharing

- [x] One-click free course sharing via a link
- [x] Anyone with the link imports their own independent copy (their own progress,
      mastery, and submissions) at zero regeneration cost

## Account

- [x] Passwordless magic-link email sign-in
- [x] Editable display name (shown on certificates instead of a bare email)

## Standalone playground

- [x] Try the code runner in six languages (Python, Python ML/DL, JavaScript, Go, C++,
      C) with nothing saved and no course required

## The AI engineering behind it (hackathon-relevant)

- [x] GPT-5.6 powers course planning, lesson/lab authoring, quiz generation, and the
      learning helper
- [x] The self-healing lab-repair loop above is a real agent loop: generate → run in a
      real sandbox → feed the actual failure back to the model → repair → re-verify,
      not a single-shot generation trusted at face value
- [x] Codex was used as part of the engineering workflow to iterate across the repo,
      diagnose failures, and implement and validate features

---

## Developer / demo tooling (not learner-facing)

Dev-only, gated behind `NODE_ENV=development` and 404s server-side in production:
built to make the mastery/certificate/adaptive-review story demoable without grinding
through a course by hand.

- [x] Demo auto-complete: drives some or all of a course to completion (or a
      deliberately mixed mastery state) as an LLM standing in for the learner, through
      the same real grading/sandbox paths a human hits
- [x] Live progress banner for a running auto-complete job, per-lesson fill from the
      lesson page itself
- [x] Demo clear-progress: the undo, resets mastery/quiz/lab state back to
      never-attempted, per lesson or for the whole course
