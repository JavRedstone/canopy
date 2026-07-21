# Canopy

**Demo video:** [https://www.youtube.com/watch?v=5FqJQYg25RM](https://www.youtube.com/watch?v=5FqJQYg25RM)

**`/feedback` Codex session ID:** the ID provided in the submission is shown on screen
at the [2:30 mark](https://youtu.be/5FqJQYg25RM?t=150) of the demo video.

**About the demo course:** every screenshot and sample PDF in this document is the
same real, generated course, built end to end from Vaswani et al.,
[*Attention Is All You Need*](https://arxiv.org/abs/1706.03762) (arXiv:1706.03762),
the Transformer paper. Not a mockup or a curated demo dataset.

## Inspiration

Technical knowledge is everywhere (papers, docs, textbooks, internal engineering
notes), and AI can explain any of it on demand. But explanation was never the hard
part. The hard part is finding out, honestly, whether you can *do* the thing the
material describes. A chat window will happily walk you through the Transformer
architecture and leave you feeling like you understand it; it won't tell you that your
own implementation of scaled dot-product attention silently transposes two axes. That
gap, confident-sounding explanation standing in for verified capability, is where
real cost shows up: in an interview, in a code review, in production, at exactly the
moment it's most expensive to discover.

Codecademy proved people will work through structured, hands-on courses when the
content is curated for them. But curation doesn't scale to "the paper I'm actually
reading this week" or "our team's internal API docs." We wanted the Codecademy
experience (lessons, a real editor, checkpoint exercises) generated from *any*
source, on demand, and adaptive to what you've actually demonstrated instead of what
you've merely scrolled past. That's Canopy.

![Canopy course dashboard: the "Attention Is All You Need" course generated from the actual paper](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/course_landing_page.png)
*The "Attention Is All You Need" course: the coursebook hero, module outline, and the
Content / Practice / Mastery tabs a learner moves between.*

## What it does

Canopy turns a source you provide (a paper, docs, a textbook chapter, your own pasted
notes) into a full, hands-on course: structured lessons cited back to the exact
passage they came from, coding labs, and quizzes, generated specifically for the goal
you state in your own words. It doesn't stop at telling you what you got wrong. It
takes action on it: it generates the lab, runs it, repairs it if it's broken, and the
moment you're struggling on a concept it identifies the exact shaky prerequisite behind
that struggle and routes you back to it, rather than just flagging a low score and
leaving you to figure out why.

![Canopy learner journey](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/demo/learner-journey-diagram.png)
*Source → course → practice → evidence of mastery → the next concept to review: the
loop Canopy runs, not a linear course you finish once.*

- **Source-grounded lessons.** Every claim can carry an inline citation that resolves
  to the real excerpt it came from: verifiable, not an opaque summary.
- **Real, sandbox-verified coding labs**, not toy exercises: three curated
  environments (Python, Python ML/DL with GPU-capable PyTorch/scikit-learn, and C++),
  auto-selected from your goal and source. Every lab is run against a real sandbox
  before a learner ever sees it.
- **A real mastery model, not a completion checkbox.** Two independent Bayesian
  Knowledge Tracing tracks per concept (understanding from quizzes and applying
  from labs), plus prerequisite-aware nudges: the moment you're struggling, Canopy
  identifies the shaky earlier concept it builds on and points you back to it.
- **A low-stakes practice pool** to drill a concept without it counting against you,
  an AI learning helper that hints without handing over the answer, a PDF coursebook
  and completion certificate to keep. Sample PDFs from this same
  [*Attention Is All You Need*](https://arxiv.org/abs/1706.03762) course:
  [coursebook](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/Attention-is-All-You-Need-coursebook.pdf),
  [certificate](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/Attention-is-All-You-Need-certificate.pdf). And free
  one-click course sharing: anyone with the link gets their own independent copy at
  zero regeneration cost.

![Lesson with the AI learning helper open, from the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/lesson_with_helper.png)
*A source-grounded lesson from the "Attention Is All You Need" course (numbered
citations, worked examples) with the learning helper open mid-conversation: asked to
"explain this more simply," it does, without ever just handing over the answer to a
quiz or lab.*

**What's actually different, and why it matters:** generic AI chat can explain a
concept but has no model of what you've demonstrated, so it can't tell you when you've
actually got it. Fixed-catalog platforms (Codecademy, Coursera) solve verification but
only for content someone already curated, so they can't touch your paper or your
team's docs. Canopy is the combination neither offers: generated from *your* material,
*and* held to the same verify-before-you-move-on standard as a hand-built course.
Every lab sandbox-checked before it ships, every mastery signal earned from a real
graded observation, not a checkbox.

![Coding lab workspace with a prerequisite-review nudge, from the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/course_lab.png)
*A lab from the "Attention Is All You Need" course: multi-head attention tensor
operations. Monaco editor, Run/Submit, live test results, with a prerequisite-review
nudge surfaced inline ("Review recommended first... 18% understand") the moment it's
relevant, not buried in a separate report.*

![Mastery dashboard with per-concept Understand/Apply meters, for the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/mastery_landing.png)
*Every concept in the "Attention Is All You Need" course, two independent tracks each.
This is a real run: 6/16 concepts mastered, individual understand/apply
percentages, observation counts per concept. Not a completion checkbox.*

Full feature list: [`docs/product/FEATURES.md`](https://github.com/JavRedstone/canopy/blob/main/docs/product/FEATURES.md).

## How we built it

Five services: a **Next.js** web app, a **FastAPI** API, a standalone **worker**
that drains the generation queue, a provider-neutral **LLM gateway** microservice
(routes OpenAI, Azure OpenAI, and AWS Bedrock behind one interface, with per-task
model tiering, GPT-5.6's flagship "Sol" tier for one-shot, high-stakes calls like
course planning and lab repair, the faster "Luna" tier for the high-volume per-lesson
work), and a **sandbox runner** microservice (the only container with Docker socket
access) that executes every generated lab in a locked-down, single-use, no-network,
non-root container across six language environments. **Supabase** (Postgres +
pgvector + pgmq + Auth + Storage) is the data, queue, and auth layer underneath all of
it.

### Technologies

| Technology | Category | Role in Canopy |
|---|---|---|
| GPT-5.6 | AI | Runtime model: plans courses, writes lessons/labs, grades quizzes, drives the lab-repair loop, powers the learning helper |
| Codex | AI | Engineering tool used to build the system itself, from migrations through worker/API/frontend |
| Python | Backend | Every backend service: API, worker, LLM gateway, sandbox runner |
| FastAPI | Backend | Framework behind all four Python services |
| Pydantic | Backend | Request/response schemas and GPT-5.6's structured-output contracts |
| TypeScript, Next.js, React | Frontend | The web app |
| Material UI | Frontend | Component library the UI is built on |
| Monaco Editor | Frontend | In-browser code editor for coding labs |
| Supabase | Data & auth | Auth (magic-link email), Storage (uploaded sources), and the Postgres database |
| PostgreSQL | Data & auth | The database underneath Supabase |
| pgvector | Data & auth | Embeddings/semantic search over source chunks: RAG grounding and citations |
| pgmq | Data & auth | Postgres-native queue for ingestion, planning, and lesson-build jobs |
| OpenAI, Azure OpenAI, AWS Bedrock | Model providers | Three interchangeable backends behind one gateway interface |
| Docker | Sandbox | Every lab runs in a locked-down, single-use, no-network, non-root container |
| pytest | Sandbox | Test framework for Python / Python ML-DL labs |
| PyTorch, scikit-learn | Sandbox | Real libraries available in the Python ML/DL lab environment |
| C++ | Sandbox | Its own curated, compiled lab environment |
| AddressSanitizer | Sandbox | Memory-safety checking for C labs, chosen since Valgrind needs ptrace privileges the sandbox doesn't grant |
| Node.js, Go | Sandbox | Two more supported lab/playground language environments |

Full breakdown: [`docs/TECHNOLOGIES.md`](https://github.com/JavRedstone/canopy/blob/main/docs/TECHNOLOGIES.md).

![Canopy runtime architecture](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/architecture/architecture-diagram.png)
*The five-service runtime, including the agentic lab-repair loop in detail (Worker +
LLM Gateway + Sandbox Runner): generate, run for real, feed back the actual failure,
repair, re-verify, bounded retries, never trusted on one attempt.*

**Built for real deployment, not just a demo run:**

- Every generated lab executes in a resource-limited, network-disabled, non-root,
  all-capabilities-dropped container, so untrusted model-authored code can never touch
  the host or reach the network.
- Every learner-facing table is behind Postgres row-level security, and tables
  carrying answer keys (`practice_items`, `lesson_revisions`) have no public policy at
  all: service-role only.
- The LLM gateway abstracts three provider backends behind one interface, so a
  provider outage or pricing change is a config change, not a rewrite.
- Dev-only tooling (the demo auto-complete/clear commands used to drive a course to a
  finished state for testing) is environment-gated and 404s outside local development
  rather than merely being hidden in the UI.

### What GPT-5.6 actually does at runtime

It's not a bolt-on chat feature. It's the thing generating and grading the product's
actual content, every time, routed per-task between two tiers so cost matches stakes:

| Task | Tier | Why |
|---|---|---|
| Course outline planning | Sol (flagship) | One high-stakes call per course: sets the whole plan, including which coding-lab language fits the source and goal |
| Per-module concept generation | Luna (fast) | Fills in the outline already fixed by Sol |
| Lesson & lab content authoring | Luna (fast) | Runs on every concept in every course: volume, not one-shot stakes |
| Lab repair loop | Sol (flagship) | The last line of defense before a lab ships, worth paying for |
| Quiz & practice-pool generation, short-answer grading | Luna (fast) | High-volume, per-question work (`services/api/app/quiz.py`) |
| In-lesson learning helper | Luna (fast) | In-context Q&A, prompted to guide without ever revealing the answer |

### How Codex actually collaborated on the build

Used throughout as an active collaborator, not a one-off code generator:

- **Full-stack feature loops in one pass.** Non-trivial features, e.g. the practice
  question pool, went from a design doc through a Postgres migration, worker
  generation pass, API routes, and frontend UI in a single iterative session, with the
  decision log kept alongside the code as it was made
  (`docs/architecture/PRACTICE_QUESTION_POOL.md`).
- **Live debugging from real evidence, not guesses.** When a lab build failed in a
  running instance, Codex traced the failure from a live database row through the
  actual worker prompt and pytest traceback that caused it, rather than reasoning
  about it in the abstract. The fastest path we found working with Codex was always
  to hand it a concrete, reproducible failure to chase, not an abstract description of
  a bug.
- **Real product and design decisions, not just code**, made through this
  collaboration and recorded as they happened: making coding-lab language selection
  automatic (inferred by the planner) instead of a manual dropdown; the practice
  pool's mastery-effect design (positive-only credit, capped below the graded-mastery
  bar); and the self-healing lab-repair loop's shape
  (generate → real sandbox run → feed back the actual failure → repair → re-verify)
  after an earlier version trusted a model's own claim of correctness too much.
- **Held to the same bar as the rest of the codebase.** Generated code went through
  the project's real test suites, not just visual review: `services/api/tests/`,
  `services/worker/tests/`, and `services/llm_gateway/tests/` gated every merge.

## Challenges we ran into

- **Isolation without giving up real test fidelity.** C labs need genuine memory-
  safety checking to teach manual memory management honestly, but our sandbox drops
  every Linux capability and runs as a non-root user, which breaks Valgrind, since
  it needs ptrace-style privileges we deliberately don't grant. We compiled with
  AddressSanitizer instead: compile-time instrumentation, verified to work under the
  exact hardening the sandbox already enforces.
- **Trusting generated code.** An LLM-authored lab is only as good as its own
  reference solution actually passing its own hidden tests. We built a real repair
  loop (generate, run in the actual sandbox, feed the real failure output back to the
  model, regenerate, re-verify) so a lab never reaches a learner on the strength of
  the model's first attempt or its own claim of correctness. That loop has a bounded
  retry budget for a reason: it doesn't always win. On our own
  [*Attention Is All You Need*](https://arxiv.org/abs/1706.03762) course, a
  beam-search decoding lab's reference solution kept missing one specific hidden case
  after every repair attempt:

  ```
  FAILED test_beam_search_hidden.py::test_beam_search_uses_length_penalty_when_ranking_candidates
      out = beam_search_decode(model, [7], beam_size=2, length_penalty=0.6, ...)
  >   assert out == [2, 3, 0]
  E   AssertionError: assert [1, 0] == [2, 3, 0]
  ```

  Length-penalized beam ranking is a genuinely fiddly implementation detail, and the
  model kept landing on the same wrong ranking across attempts. The lab correctly
  landed in a terminal `failed` state instead of quietly shipping broken, exactly the
  fail-closed behavior the loop is designed for. The product's own "Regenerate"
  action (a fresh generation attempt, not a repair of the broken one) is the real
  recovery path from there.
- **Making the prerequisite nudge fire on real evidence, not noise.** It only
  triggers when a learner is genuinely struggling on the current concept *and* a
  prerequisite it builds on has actually been practiced and is measurably shaky.
  Getting that threshold right took real tuning against the BKT math, not a guess.
- **Being honest about our own mastery model.** We evaluated Canopy's design against
  the actual learning-science literature (`docs/product/PEDAGOGY_EVALUATION.md`) and
  found real gaps: a fixed "mastered" threshold and a fixed number of failed
  attempts before intervention, in a system where the assistance-dilemma and
  expertise-reversal research says the right amount of support should adapt to the
  learner, not be a constant.

## Accomplishments that we're proud of

Canopy is pre-launch, so we don't have real-user metrics yet, but every accomplishment
below is a concrete mechanism designed to produce a measurable outcome the moment it's
in front of learners, not a hoped-for one:

- **Canopy verifies. It doesn't trust, assume, or ship-and-hope.** Every lab is
  generated, run against a real sandbox, and repaired from the real failure before a
  learner ever sees it: an agentic loop that earns the word, not a single-shot
  generation trusted at face value. Zero unverified labs reach a learner, by
  construction, not by review effort.
- **Canopy measures applying, not clicking.** Dual-track BKT and prerequisite-aware
  review respond to demonstrated evidence (a quiz answered, a lab actually passed),
  not time spent on the page. A learner, or a hiring manager reading a certificate,
  gets a signal tied to graded evidence instead of a completion percentage.
- Three real, curated, resource-tuned sandbox environments that the generation prompts
  know how to target correctly, instead of one generic Python box.
- Free, instant course cloning via a link: a genuine product answer to not having a
  team/org layer yet. Sharing a course with ten people costs exactly what sharing it
  with one does.
- The whole loop actually works end to end, live: source → generated course →
  sandbox-verified labs → mastery tracking → PDF certificate.

![Canopy completion certificate for the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/certificate_completion.png)
*Completion certificate for the "Attention Is All You Need" course, issued once every
lesson is done, verifiable at its own public link. Sample PDF:
[certificate](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/Attention-is-All-You-Need-certificate.pdf),
[coursebook](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/Attention-is-All-You-Need-coursebook.pdf).*

## What we learned

Canopy's foundations (active learning, retrieval practice, worked examples,
immediate feedback, mastery framing) are strong by the actual research, and a few
choices (dual-track mastery, the self-validating sandbox, source grounding) are ahead
of typical edtech. But holding the product up against the literature surfaced the
same lesson twice: **trusting a generated artifact more than it's earned** (an
extracted concept graph treated as a validated progression, a green test suite
treated as a clean mastery signal) is where the real risk lives, and **fixed
constants where the evidence demands adaptivity** is where the clearest next wins are.
We also learned that Codex is most effective on a real, multi-service codebase when
you hand it a concrete, reproducible failure (a specific database row, a specific
pytest traceback) rather than an abstract instruction.

## What's next for Canopy

Canopy is built as a platform, not a single feature: every item below extends
infrastructure that's already shipped rather than starting from scratch:

- **Spaced re-retrieval of already-mastered concepts**: the highest-confidence
  pedagogy fix per our own evaluation, and it reuses the quiz engine already built.
- **An adaptive remediation trigger**, replacing the current fixed "N failed
  attempts" constant with something sensitive to the learner's actual level.
- **A real cohort/team layer**: a shared progress dashboard for a group, not just
  Google-Docs-style link sharing. The single biggest structural gap today, and the
  clearest path to broader (classroom, team, org) adoption.
- **Repository/codebase ingestion**: point a course at a GitHub repo instead of
  uploading files by hand.
- Multiple content languages, and a broader UI polish pass.
