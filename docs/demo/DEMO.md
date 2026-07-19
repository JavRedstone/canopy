# Canopy Demo Plan

*Hackathon demo script — written July 17, 2026; revised July 19, 2026 to match the
individual-learner-first submission story in
[`../product/MARKET_EXPLORATION.md`](../product/MARKET_EXPLORATION.md) and the real,
running product rather than a fictional B2B scenario.*

**Format constraint:** [`HACKATHON.md`](./HACKATHON.md) caps the submission video at
**under 3 minutes** and requires it to explain how Codex/GPT-5.6 were used — both are
budgeted into the flow below, not an afterthought.

## Demo in one sentence

> Hand Canopy a source and a goal; it builds a real course — cited lessons, a
> sandbox-graded coding lab, a quiz, live mastery tracking — then proves you finished it
> with a certificate and a PDF coursebook. Every exercise validated and repaired itself
> against the sandbox before you ever saw it.

The demo should make one point unmistakable: **this is not a prettier chat with
documentation and not a generic course generator. It produces hands-on practice that's
graded for real, and it knows the difference between "you read it" and "you can do it."**

## The best demo story

### Persona

Not a fictional character — the demo *is* the product's actual best-supported use case
(`USE_CASES.md` #1): a learner with a source and a goal who wants more than a summary.
For a hackathon judge that reads as a grad student or engineer, not an enterprise buyer,
which is exactly the Education-track framing this submission is built for.

### Source packet

Use a real document, not a fictional one — the product's whole value is grounded
generation, so a real source makes every citation click land harder. A short ML
textbook chapter or library docs page (e.g. the scikit-learn user guide) works well and
matches [`SAMPLE_COURSES.md`](../product/SAMPLE_COURSES.md): the same source, different
goals, produces a conceptual course, a hands-on `python-ml` course, or an
algorithms-from-scratch course. Pick the hands-on goal for this demo — it's the one that
reaches a real coding lab fastest.

### Learner goal

> Learn how supervised learning models are trained and evaluated, and be able to train
> and tune a classifier myself.

## Recommended live demo flow (under 3 minutes)

### 1. The hook — 10s

Open "My courses." One line, no dwelling on account setup or file management:

> "Any source you have — a paper, a library's docs, a textbook chapter — becomes a real
> course: cited lessons, a graded coding lab, and proof you actually learned it."

### 2. Create the course — 25s

Upload the source, set the goal, hit generate. Use a course generated moments before this
recording started (or the dev-only demo auto-complete tool, see the reliability checklist
below) so the live segment shows the *result* — a structured module/concept outline —
without waiting on a live model call.

> "Codex built the whole generation pipeline behind this: a planner turns the source and
> goal into a concept graph, then a lesson agent writes each lesson — explanation, starter
> code, hidden tests, quiz items, a reference solution — as one structured call."

### 3. A cited lesson + a quiz — 25s

Open a conceptual lesson. Click an inline citation marker — it opens the exact source
excerpt the claim came from. Answer a quiz question (mcq or fill-in-blank; Markdown and
math render properly, including code blocks in the options).

> "Every claim traces back to the actual source, not a hallucinated citation. The quiz
> isn't decoration — it's the first mastery observation."

### 4. The coding lab — 55s

Navigate into a lab. Show the starter code, Monaco editor, and instructions. Make an
intentionally incomplete change, hit **Run**:

```text
1 test passed
1 test failed: expected accuracy above 0.8, got 0.62
```

Take a hint from the lesson helper (guides, doesn't hand over the answer), fix it, **Run**
again to confirm, then **Submit** — this is what's graded against the hidden suite and
what actually moves mastery.

> "This exact lab already proved itself once, before you ever saw it: Codex generated it,
> ran it against the hidden tests in the same sandbox you're using now, and when it
> failed, patched and re-verified it — the same generate → run → diagnose → patch →
> re-verify loop, just run on the lesson itself instead of on your submission. Nothing
> ships to a learner until it's proven itself."

### 5. Mastery, live — 20s

Switch to the Mastery tab. Point at one concept's `Understand` and `Apply` numbers moving
independently — quizzes feed one, labs feed the other — and a prerequisite-review nudge
if one is showing.

> "This isn't a completion checkbox. It's two separate, real probabilities, updated from
> what you actually did."

### 6. Finish — 30s

Navigate to (or fast-forward to, via a pre-completed second course) a fully finished
course. The certificate pops up automatically. Show it, then hit **Download coursebook**
on another finished course to show the PDF export.

> "Finish every lesson and a certificate is waiting for you — no digging for it. And the
> whole course exports as a real PDF: lessons, worked examples, quizzes, citations — a
> takeaway that outlives the tab."

### 7. Bonus, if time allows — 15s

Open the share toggle, copy the course link, switch accounts, import — instant, no
regeneration.

> "One person builds it, anyone imports their own copy for free — that's how this scales
> past a single learner without an org/team system yet."

## What must work live

| Capability | Demo requirement |
|---|---|
| Course creation | A goal and a real source produce a structured module/concept outline. A course generated just before recording is fine — don't let live generation latency eat the 3-minute budget. |
| Cited lesson | At least one concept with a clickable inline citation resolving to the real excerpt. |
| Quiz | At least one quiz item with Markdown/code rendering, answered live. |
| Coding lab | Editable starter code, a **Run** that fails meaningfully, a hint, a fix, a **Submit** that passes and updates mastery. |
| Mastery dashboard | `Understand`/`Apply` visibly different per concept, at least one clearly non-zero and moving. |
| Certificate | A finished course that auto-pops the certificate on open, plus the PDF export. |
| Coursebook | A finished course's "Download coursebook" produces a real PDF. |
| Sharing (bonus) | Toggle sharing, import under a second account, instantly. |

The existing product already supports all of this end to end — see
[`USE_CASES.md`](../product/USE_CASES.md) for exactly what's verified against the code.
If any generation step is unreliable on the day, prepare the course ahead of time and
spend the live segment on the learning/practice loop, not generation latency.

## What to simulate or defer

Do not overbuild these for a hackathon demo — none of them are built, and claiming them
live would be dishonest:

- full GitHub/repo ingestion — sources are uploaded files, not a connected repository;
- real pull-request syncing or automatic updates after a merge;
- an org/team assignment view or cohort progress dashboard (courses are single-owner;
  sharing is link-based cloning, not live-shared);
- the LLM diagnosis-and-remediation layer surfaced to the learner (the self-repair loop
  in step 4 runs on the lesson during generation, not as a learner-facing "the system
  diagnosed your mistake" moment yet);
- perfect adaptive resequencing — there's a prerequisite-review *nudge*, not a fully
  reshaped course.

## Demo reliability checklist

Prepare a "golden path" state before recording, don't generate live end to end:

- One course generated ahead of time with a real coding lab known to fail on first Run
  and pass after one small fix.
- A second course brought to full completion ahead of time (the dev-only demo
  auto-complete admin tool exists for exactly this — see
  [`ROADMAP.md`](../product/ROADMAP.md) — target "mixed" so the mastery dashboard shows
  varied, non-uniform numbers instead of a suspiciously uniform 100% everywhere), so the
  certificate/coursebook segment doesn't depend on live grading.
- Citations, quiz items, and lab test output are all real — nothing staged or faked, just
  pre-generated so the recording doesn't wait on a model call.
- Completion state resets cleanly (fresh account or seeded data) if a re-record is
  needed.
- The source packet, a screen recording of the whole golden path, and fallback
  screenshots are all available offline in case a live call fails during recording.

## Judging narrative

Mapped directly to [`HACKATHON.md`](./HACKATHON.md)'s four criteria:

### Potential impact

A learner with a source and a goal — a paper, a library's docs, a textbook chapter —
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
The self-validating sandbox — a lesson proves itself against hidden tests before a
learner ever sees it — is the specific mechanism that makes that combination trustworthy
instead of just plausible.

### Technological implementation (Codex usage)

The generate → run → diagnose → patch → re-verify loop is the core agentic workflow:
Codex-assisted development built a pipeline where lesson generation never trusts its own
first answer — it's checked against a real sandbox, and repaired against real failure
output, before a learner is exposed to it. That loop runs across six curated sandbox
environments (`python-basic`, `python-ml` with GPU-capable PyTorch/scikit-learn,
`cpp-basic`, `c-basic`, `javascript-basic`, `go-basic`), not one fixed toolchain.

### Credible future

Start with an individual learner and their own material (built, demoed here). The same
mechanism scales into internal engineering onboarding once an org/team layer exists —
see [`MARKET_EXPLORATION.md`](../product/MARKET_EXPLORATION.md) §4.2 — but that's the
deliberate next phase, not a claim this submission makes.

## Suggested spoken script

> "Any source you have can become a real course. I'll hand Canopy a chapter on
> supervised learning and a goal: I want to actually train and tune a classifier, not
> just read about one.
>
> It builds a course — lessons that cite the real source, a quiz, and a coding lab.
> Codex built the pipeline that generates this: every lesson is checked against a real
> sandbox and repaired if it fails, before I ever see it.
>
> Here's the lab. My first attempt fails a real test. I take a hint — not the answer —
> fix it, and submit. That's graded against hidden tests, and it just moved my mastery
> score — not a completion checkbox, a real probability that updates from what I actually
> did.
>
> Finish the course, and a certificate is waiting — plus the whole thing exports as a PDF
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

1. Canopy turns a source you already have into a real, hands-on course — not a summary.
2. It goes beyond chat: a graded sandbox and a real mastery model, not just reading or
   chatting.
3. Every exercise proved itself against the sandbox — repaired if it failed — before a
   learner ever saw it. That loop is the actual Codex-driven engineering in this system.
