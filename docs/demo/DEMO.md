# Canopy Demo Plan

*Hackathon demo script, written July 17, 2026; revised July 19, 2026 to match the
individual-learner-first submission story in
[`../product/MARKET_EXPLORATION.md`](../product/MARKET_EXPLORATION.md) and the real,
running product rather than a fictional B2B scenario.*

**Format constraint:** [`HACKATHON.md`](./HACKATHON.md) caps the submission video at
**under 3 minutes** and requires it to explain how Codex/GPT-5.6 were used. Both are
budgeted into the flow below, not an afterthought.

For a concise script to read while recording, use
[`RECORDING_SCRIPT.md`](./RECORDING_SCRIPT.md).

## Demo in one sentence

> Canopy transforms technical knowledge into demonstrated skill.

The demo should make one point unmistakable: **this is not a prettier chat with
documentation and not a generic course generator. It is a learning platform with an
AI-generated curriculum engine, execution environment, and mastery system.**

The explanatory line beneath that claim is: **AI can explain anything. Canopy helps you
actually learn it.**

The product magic is an AI-created closed learning loop: **teach → practice → evaluate →
adapt**.

## The best demo story

### Persona

Not a fictional character: the demo *is* the product's actual best-supported use case
(`USE_CASES.md` #1): a learner with a source and a goal who wants more than a summary.
For a hackathon judge that reads as a grad student or engineer, not an enterprise buyer,
which is exactly the Education-track framing this submission is built for.

### Source packet

Use a real document, not a fictional one: grounded generation makes every citation click
land harder. A primary research paper such as "Attention Is All You Need," a textbook
chapter, or official library documentation works well. Lead with the research-paper
course because it demonstrates that a difficult primary source can become an
implementation-focused coding course, rather than a static summary.

### Learner goal

> Understand, implement, and reproduce the Transformer architecture from Attention Is All
> You Need.

### Problem credibility

Geoffrey Litt, a Design Engineer at Notion, calls human understanding the new bottleneck
as agents produce more code. His talk is independent validation for the problem, not the
product claim: Canopy turns source-grounded understanding into a structured
implementation path and verifies the learner's application of it. Cite [his written
talk](https://www.geoffreylitt.com/2026/07/02/understanding-is-the-new-bottleneck.html)
once in the submission materials or final slide, rather than making it a major demo beat.

### GPT-5.6 and Codex credibility

Keep this brief in the video: GPT-5.6 powers curriculum generation, lesson-aware learner
guidance, and repair workflows; Codex accelerated implementation and testing of the
curriculum pipeline, sandbox integration, validation workflows, and product UI. Name
the Sol/Luna routing in written submission material only if useful. Before claiming any
of it, verify the active provider is actually configured with GPT-5.6 deployments.

## Recommended live demo flow (under 3 minutes)

### 1. The learner problem (30s)

Open the original paper, then a prepared failed implementation attempt.

> "Learning technical skills has a fundamental problem. The information is already
> available, but understanding an explanation does not prove you can apply the concept.
> Most AI learning tools optimize for explanation. Canopy optimizes for demonstrated
> ability: practice, feedback, and evidence that you gained the skill."

### 2. The insight (20s)

Upload the source, set the goal, hit generate. Use a course generated moments before this
recording started (or the dev-only demo auto-complete tool, see the reliability checklist
below) so the live segment shows the *result* (a structured module/concept outline)
without waiting on a live model call.

> "AI education should not optimize for producing explanations. It should optimize for
> producing capability. Canopy transforms technical sources into structured lessons,
> hands-on labs, adaptive feedback, and measurable mastery."

> "Here the source is Attention Is All You Need. The goal is not just to read the paper;
> it is to understand the architecture, implement its core components, and reproduce key
> ideas from the work."

> "The hard part is not generating text. It is generating a learning system that remains
> connected to the source, produces executable practice, and verifies that the learner
> can succeed."

### 3. Source to demonstrated skill (45s)

Show the generated progression.

> "The learner starts with the paper thesis and Transformer fundamentals, moves into the
> core components and training details, then reaches experiments and reproduction."

Open **Scaled dot-product attention**. Click its inline citation marker to open the
source reference. Answer a quiz question (mcq or fill-in-blank; Markdown and math render
properly, including code blocks in the options).

Move quickly into the **Transformer block implementation** lab. Show an incomplete
implementation and pause on the failing run.

> "This is where most AI learning stops. It explains the answer. Canopy makes the learner
> do the work."

Then show the Learning helper's hint, a small fix, and a passing run. The failure,
feedback, repair, and result are the demo's magic moment.

> "Lessons stay connected to the source, so learners can verify where concepts came from
> instead of trusting an opaque AI summary. The quiz is the first check that they actually
> understand it."

> "Canopy does not just summarize the paper. It builds a learning path from reading its
> ideas to implementing and reproducing them."

### 4. Evidence of learning (25s)

Switch to the Mastery tab. Point at one concept's `Understand` and `Apply` numbers moving
independently (quizzes feed one, labs feed the other) and a prerequisite-review nudge
if one is showing.

> "Most learning platforms measure completion. Canopy measures mastery. A learner can
> understand the theory but struggle to implement it, or write code without understanding
> why it works. Canopy makes that difference visible."

> "Underneath, Canopy uses evidence-based mastery tracking: conceptual checks update
> understanding, and coding submissions update applied skill. These are not completion
> percentages."

For this course, frame the Apply track as evidence from implementation and reproduction
work. Do not claim that the mastery model has a separate reproduction score.

### 5. Prerequisite-aware adaptation (25s)

Show a prerequisite recommendation if one is available.

> "When a learner struggles, Canopy identifies the shaky prerequisite and recommends the
> targeted concept to review. It responds to demonstrated evidence, not just completion."

### 6. Technical proof (20s)

Return to the passing lab or its validation state.

> "The sandbox validates the course before learners see it. Generated starter code,
> tests, and reference solutions run in the same environment, so broken labs are caught
> before delivery."

Then show one real repository diff, test result, or recorded Codex session.

> "Building this required more than generating lessons. GPT-5.6 powers curriculum
> generation, learning guidance, and repair workflows. Codex was part of our engineering
> workflow: we used it to iterate across the repository, diagnose failures, implement
> features, and validate the systems that make Canopy possible."

### 7. Close (15s)

> "Technical knowledge is everywhere. The missing layer is turning knowledge into
> capability. Canopy creates the bridge between learning something and being able to do
> something."

End on a five-second final slide, then say:

> "Canopy takes a learner from a source, to a course, to practice, to evidence of mastery,
> and then to the next concept they need to review."

### 8. Follow-up features, outside the primary cut

Open the share toggle, copy the course link, switch accounts, import: instant, no
regeneration.

> "One person builds it, anyone imports their own copy for free: that's how this scales
> past a single learner without an org/team system yet."

Keep the Coursebook and sharing flow out of the primary three-minute recording. They are
useful follow-ups, but they dilute the central source-to-skill story.

## What must work live

| Capability | Demo requirement |
|---|---|
| Course creation | A goal and a real source produce a structured module/concept outline. A course generated just before recording is fine; don't let live generation latency eat the 3-minute budget. |
| Cited lesson | At least one concept with a clickable inline citation resolving to the real excerpt. |
| Quiz | At least one quiz item with Markdown/code rendering, answered live. |
| Coding lab | Editable starter code, a **Run** that fails meaningfully, a hint, a fix, a **Submit** that passes and updates mastery. |
| Mastery dashboard | `Understand`/`Apply` visibly different per concept, at least one clearly non-zero and moving. |
| Certificate | A finished course that auto-pops the certificate on open, plus the PDF export. |
| Coursebook | A finished course's "Download coursebook" produces a real PDF. |
| Sharing (bonus) | Toggle sharing, import under a second account, instantly. |

The existing product already supports all of this end to end: see
[`USE_CASES.md`](../product/USE_CASES.md) for exactly what's verified against the code.
If any generation step is unreliable on the day, prepare the course ahead of time and
spend the live segment on the learning/practice loop, not generation latency.

Do not show the dev-only demo auto-complete control in the recording. It is a testing
utility, not part of the learner experience.

## What to simulate or defer

Do not overbuild these for a hackathon demo; none of them are built, and claiming them
live would be dishonest:

- full GitHub/repo ingestion: sources are uploaded files, not a connected repository;
- real pull-request syncing or automatic updates after a merge;
- an org/team assignment view or cohort progress dashboard (courses are single-owner;
  sharing is link-based cloning, not live-shared);
- the LLM diagnosis-and-remediation layer surfaced to the learner (the self-repair loop
  in step 4 runs on the lesson during generation, not as a learner-facing "the system
  diagnosed your mistake" moment yet);
- perfect adaptive resequencing: there's a prerequisite-review *nudge*, not a fully
  reshaped course.

## Demo reliability checklist

Prepare a "golden path" state before recording, don't generate live end to end:

- One course generated ahead of time with a real coding lab known to fail on first Run
  and pass after one small fix.
- A second course brought to full completion ahead of time (the dev-only demo
  auto-complete admin tool exists for exactly this, see
  [`ROADMAP.md`](../product/ROADMAP.md); target "mixed" so the mastery dashboard shows
  varied, non-uniform numbers instead of a suspiciously uniform 100% everywhere), so the
  certificate/coursebook segment doesn't depend on live grading.
- Citations, quiz items, and lab test output are all real: nothing staged or faked, just
  pre-generated so the recording doesn't wait on a model call.
- Completion state resets cleanly (fresh account or seeded data) if a re-record is
  needed.
- The source packet, a screen recording of the whole golden path, and fallback
  screenshots are all available offline in case a live call fails during recording.

## Judging narrative

Mapped directly to [`HACKATHON.md`](./HACKATHON.md)'s four criteria:

### Potential impact

A learner with a source and a goal (a paper, a library's docs, a textbook chapter)
today gets either a passive summary (NotebookLM, a chatbot) or nothing at all if no
course exists for that material. Canopy gets them a validated, hands-on course with real
evidence they can do the thing, not just describe it.

### Design

A complete loop, not a tech demo: source in, structured course out, a real coding
sandbox with Run/Submit, a dual-track mastery model, a certificate, a PDF takeaway. Every
piece is reachable from the same course page, not a disconnected feature list.

### Quality of idea

The empty quadrant no competitor occupies: generated from *your* material **and**
executable, hidden-test-graded practice, at once (see
[`../product/COMPETITIVE_DIFFERENTIATION.md`](../product/COMPETITIVE_DIFFERENTIATION.md)).
The self-validating sandbox (a lesson proves itself against hidden tests before a
learner ever sees it) is the specific mechanism that makes that combination trustworthy
instead of just plausible.

### Technological implementation (Codex usage)

The generate → run → diagnose → patch → re-verify loop is the core agentic workflow:
Codex-assisted development built a pipeline where lesson generation never trusts its own
first answer: it's checked against a real sandbox, and repaired against real failure
output, before a learner is exposed to it. That loop runs across six curated sandbox
environments (`python-basic`, `python-ml` with GPU-capable PyTorch/scikit-learn,
`cpp-basic`, `c-basic`, `javascript-basic`, `go-basic`), not one fixed toolchain.

### Credible future

Start with an individual learner and their own material (built, demoed here). The same
mechanism scales into internal engineering onboarding once an org/team layer exists
(see [`MARKET_EXPLORATION.md`](../product/MARKET_EXPLORATION.md) §4.2), but that's the
deliberate next phase, not a claim this submission makes.

## Suggested spoken script

> "Any source you have can become a real course. I'll hand Canopy a chapter on
> supervised learning and a goal: I want to actually train and tune a classifier, not
> just read about one.
>
> It builds a course: lessons that cite the real source, a quiz, and a coding lab.
> Codex built the pipeline that generates this: every lesson is checked against a real
> sandbox and repaired if it fails, before I ever see it.
>
> Here's the lab. My first attempt fails a real test. I take a hint, not the answer,
> fix it, and submit. That's graded against hidden tests, and it just moved my mastery
> score, not a completion checkbox, a real probability that updates from what I actually
> did.
>
> Finish the course, and a certificate is waiting, plus the whole thing exports as a PDF
> I keep. And if I want to share it, anyone can import their own copy for free, no
> regeneration.
>
> Chat tools can explain a document. Canopy proves you can do the thing it taught."

## Assets to prepare

- A real source document (short ML chapter or library docs page) and its matching goal.
- A course generated ahead of time with a lab known to fail on first Run and pass after
  one small fix.
- A second, fully completed course (via the demo auto-complete tool, mixed target) for
  the mastery/certificate/coursebook segment.
- A concise opening line/slide containing the one-sentence pitch.
- A fallback screen recording of the whole golden path.

## Success criteria

After the demo, a viewer should be able to repeat all three ideas without prompting:

1. Canopy turns a source you already have into a real, hands-on course, not a summary.
2. It goes beyond chat: a graded sandbox and a real mastery model, not just reading or
   chatting.
3. Every exercise proved itself against the sandbox, repaired if it failed, before a
   learner ever saw it. That loop is the actual Codex-driven engineering in this system.
