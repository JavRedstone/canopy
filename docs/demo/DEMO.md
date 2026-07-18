# Canopy Demo Plan

*Hackathon demo exploration — July 17, 2026*

## Demo in one sentence

> Drop in the knowledge around an unfamiliar engineering system; Canopy turns it into a short, source-grounded path where a developer learns the mental model, practises a change, and proves they can apply it.

The demo should make one point unmistakable: **Canopy is not a prettier chat with documentation and not a generic course generator. It produces an actionable learning path with runnable practice.**

## The best demo story

### Persona

Maya is a developer joining the payments team. She has been assigned a small change to the authorization flow, but the knowledge is scattered across a service overview, an ADR, an SDK guide, and a recent pull request.

She does not need a twelve-week course on backend engineering. She needs to understand this system well enough to make a safe contribution.

### Source packet

Use a small, internally consistent fictional source packet, not a real customer repository:

- `payments-service-overview.md` — request flow and service ownership;
- `idempotency-adr.md` — why retry safety matters;
- `authorization.ts` — a focused implementation excerpt;
- `authorization.test.ts` — representative tests;
- `PR-1842.md` — a recent change that introduced a new decline reason.

Keep the source material compact enough that every explanation, lab, and citation can be visually tied back to it. Fictional sources prevent privacy concerns and make the happy path reliable.

### Learner goal

> Learn the authorization pipeline and safely add validation for an expired authorization hold.

## Recommended live demo flow (3–4 minutes)

### 1. The before state — 15 seconds

Open a simple “My courses” page. Frame the pain:

> “A developer has the docs and code, but no guided route from reading to confidently making a change.”

Avoid spending time on account setup, file-management details, or a long landing page.

### 2. Create the learning path — 30–45 seconds

Show the source packet and learner goal. Generate the course.

The important reveal is a visible outline such as:

```text
Authorization Pipeline
  ✓ 1. Request lifecycle
  → 2. Idempotency and retries
    3. Decline-reason change
    4. Lab: trace the expired-hold path
    5. Lab: add expiry validation
    6. Assessment: choose a safe implementation point
```

Narrate the design choice: “Instead of one giant lesson, Canopy creates a sequence of short explanations, practice, and a check for transfer.”

If generation takes time, use realistic streaming/progress states or a prepared course. Do not let a live model call determine whether the demo succeeds.

### 3. Establish understanding — 35–45 seconds

Open a short conceptual lesson. Show:

- a concise explanation of the request path;
- a highlighted source citation that opens the relevant excerpt;
- a small question such as “Why must an authorization retry return the original result?”; and
- automatic completion after a read-only lesson, or an explicit correct answer for a quiz.

This is where the demo earns its claim of source grounding. A citation should look concrete, not decorative.

### 4. The runnable lab — 60–75 seconds

Navigate through the persistent course outline into the expiry-validation lab. Show the starter code, task, and tests.

The learner makes an intentionally incomplete change. Click **Run**:

```text
1 test passed
1 test failed: expected EXPIRED_HOLD, received AUTHORIZED
```

Offer a progressive hint that points to the relevant condition without writing the full solution. The learner adds the expiry branch, runs again, and passes.

Then click **Submit** to distinguish experimentation from evaluated completion. Show the lesson’s completion state updating in the fixed course outline.

The central visual is not the code editor alone. It is the loop:

```text
Understand → try → receive evidence → improve → demonstrate application
```

### 5. Assessment and celebration — 30–40 seconds

Show a compact scenario assessment:

> “A retry arrives after the hold expires. Which layer should enforce expiry and why?”

After answering, show the celebration/completion state, progress checkmarks, and a clear “next lesson” action. This makes Canopy feel like a learning product rather than an isolated code exercise.

### 6. Finish with the business insight — 20 seconds

Return to the course map or a lightweight outcome panel:

> “Canopy turns the knowledge around a codebase into an approved, reusable route to a developer’s first safe change. Teams reduce repeated explanations; developers gain confidence through actual practice.”

Do not claim a time-to-productivity improvement unless it was measured. State it as the outcome a pilot would test.

## What must work live

Prioritize this narrow vertical slice:

| Capability | Demo requirement |
|---|---|
| Course creation | A goal and compact source packet result in a structured sequence. Prepared data is acceptable as a reliability fallback. |
| Learning experience | Fixed, collapsible course outline; current item, completion checkmarks, and next/previous navigation. |
| Short lessons | At least two concise conceptual lessons, with source references. |
| Coding lab | Editable starter code, Run feedback, and a deterministic successful solution path. |
| Assessment | One small transfer-style question that marks completion. |
| Progress | Completion visibly updates both in the lesson and on the course page. |
| Finish | A satisfying but brief celebration state. |

The existing product direction already supports much of this learning flow. If any part is unreliable, prepare a fully generated course and spend the live demo on learning and practice rather than generation latency.

## What to simulate or defer

Do not overbuild these for a hackathon demo:

- full GitHub installation, organisation permissions, or repository-wide indexing;
- real pull-request syncing or automatic updates after merge;
- perfect adaptive mastery modelling;
- arbitrary-language sandbox support;
- multi-user management, team analytics, and billing;
- broad course authoring controls.

Use a fictional PR/change document in the source packet. It demonstrates the developer-native use case without claiming that Canopy is a production GitHub integration today.

## Demo reliability checklist

Prepare a “golden path” course before presenting.

- The course has at least six activities: three short concepts, two labs, and one assessment.
- All explanations cite a source excerpt that exists in the displayed packet.
- The lab has a known initial failure and a known passing solution.
- The test output is deterministic and readable.
- Completion can be reset in a fresh demo account or seeded data state.
- The source packet, generated course, and fallback screenshots are available offline.
- No API key, private repository, or live external model call is necessary to complete the live story.

If presenting a live generate action, pre-generate the same course in another tab/session and use it immediately if the call is slow or fails.

## Judging narrative

### Problem

Engineering knowledge is trapped in repositories, documentation, PRs, and senior engineers’ heads. New contributors can search for answers, but struggle to form a reliable mental model and practise safely before touching production work.

### Insight

AI code tools can explain a file or search a codebase. The missing layer is structured learning: ordering the concepts, making the learner apply them, and recording evidence of understanding.

### Solution

Canopy converts approved engineering context into a compact path of explanations, labs, and assessments. It is source-grounded, practical, and reusable by the team.

### Why now

AI makes it feasible to transform changing technical context into learning material quickly. But it must be paired with guarded source selection, deterministic labs, and human review—not treated as an automatic source of truth.

### Credible future

Start with curated source packets. Later, connect approved repositories, architecture docs, and change metadata so learning paths can be refreshed as a system evolves.

## Suggested spoken script

> “Meet Maya. She just joined the payments team and needs to make one safe change—not complete a generic backend course. Her team’s knowledge is spread through docs, code, and a recent PR.
>
> We give Canopy that bounded context and her goal. It creates a short path: first the request lifecycle, then idempotency, then two small labs, then an assessment.
>
> In this lab, Maya has to handle an expired authorization hold. Her first attempt fails a meaningful test. Canopy gives her evidence and a hint, but does not just write the answer. Once she fixes it, she submits and the path records demonstrated completion.
>
> Code assistants help you find an answer. Canopy helps a team turn its engineering knowledge into a reusable route to understanding and safe contribution.”

## Assets to prepare

- Fictional payments source packet, with clearly labeled code and docs.
- A seeded course using the exact source packet.
- A lab that fails on one recognizable edge case and passes after one small edit.
- A concise slide or opening screen containing the product sentence.
- A fallback screen recording of the whole golden path.
- Optional architecture diagram: client → authorization service → ledger, showing where the expiry rule belongs.

## Success criteria

After the demo, a viewer should be able to repeat all three ideas without prompting:

1. Canopy is for learning the concepts behind a specific engineering system, not generic coding education.
2. It goes beyond chat by creating structured, hands-on practice and evidence of understanding.
3. Its first business use case is helping teams onboard developers and explain changing technical systems.
