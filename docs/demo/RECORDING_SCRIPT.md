# Canopy recording script

This is the concise, screen-by-screen script for recording the product demo. For the
longer judging narrative, preparation checklist, and rationale, see [DEMO.md](./DEMO.md).

## Setup before recording

- Use a prepared course from a real primary source, such as "Attention Is All You Need."
- For the strongest visible goal, use: "Understand, implement, and reproduce the
  Transformer architecture from Attention Is All You Need."
- Prepare the **Transformer block implementation** lab to fail once, then pass after a
  small fix.
- Confirm the course has a cited lesson, mastery data, and a prerequisite recommendation.
- Keep Docker, the worker, sandbox runner, API, gateway, and web app running.
- Keep one real Codex-assisted diff or test result ready for the technical proof beat.

## Three-minute walkthrough

### 0:00 - 0:30: The learner problem

**Screen:** The original paper, then a prepared failed implementation attempt.

> Learning technical skills has a fundamental problem. The information is already
> available. You can read a paper, watch lectures, and ask AI unlimited questions. But
> understanding an explanation does not prove you can apply the concept.

> Most AI learning tools optimize for explanation. Canopy optimizes for demonstrated
> ability: practice, feedback, and evidence that you actually gained the skill.

### 0:30 - 0:50: The insight

**Screen:** New Course. Show the source and the learner goal.

> We realized AI education should not optimize for producing explanations. It should
> optimize for producing capability.

> Canopy transforms technical sources into a complete learning system: structured
> lessons, hands-on labs, adaptive feedback, and measurable mastery.

> Here we start with Attention Is All You Need. The goal is not just to read the paper.
> It is to understand the architecture, implement its core components, and reproduce key
> ideas from the work.

### 0:50 - 1:35: Source to demonstrated skill

**Screen:** Prepared course modules, scaled dot-product attention lesson, then the
Transformer block implementation lab.

> A learner starts with a difficult source and a goal. Canopy breaks it into the concepts,
> practice, and assessments needed to reach mastery.

Show the actual progression.

> The learner starts with the paper thesis and Transformer fundamentals, moves into the
> core components and training details, then reaches experiments and reproduction.

Open **Scaled dot-product attention** and its source reference.

> The lesson remains connected to the original source, so the learner can verify where a
> concept came from instead of trusting an opaque AI summary.

Open **Transformer block implementation**. Run the incomplete implementation and pause
briefly on the failure.

> This is where most AI learning stops. It explains the answer. Canopy makes the learner
> do the work.

Open the **Learning helper**, click **Give me a hint**, apply the small fix, and rerun.

> The learner moves from reading the attention mechanism to implementing the mechanism
> described in the paper. They encounter a real implementation failure, get lesson-aware
> guidance without the answer being handed over, and iterate until it works.

### 1:35 - 2:00: Evidence of learning

**Screen:** Mastery dashboard.

> Most education platforms measure completion. Canopy measures demonstrated ability.

Show the separate **Understand** and **Apply** signals.

> In this course, Canopy distinguishes understanding Transformer concepts from applying
> them in implementation and reproduction work. A learner can understand the theory but
> still struggle to build it, or write working code without understanding why it works.

> Underneath, Canopy uses evidence-based mastery tracking: conceptual checks update
> understanding, and coding submissions update applied skill. These are not completion
> percentages.

### 2:00 - 2:25: Prerequisite-aware adaptation

**Screen:** Prerequisite recommendation.

> When a learner struggles, Canopy does not just mark the lesson wrong. It identifies the
> shaky prerequisite and recommends the targeted concept to review.

> The system responds to demonstrated evidence from quizzes and submissions, not just
> time spent clicking through lessons.

### 2:25 - 2:45: Technical proof

**Screen:** Passing lab or validation state, then one real Codex-assisted repository diff
or test result.

> Building this required more than generating lessons. Canopy validates generated labs,
> executes learner code safely, evaluates submissions, and maintains learning state.

> GPT-5.6 powers curriculum generation, learning guidance, and repair workflows. Codex
> was part of our engineering workflow: we used it to iterate across the repository,
> diagnose failures, implement features, and validate the systems that make Canopy
> possible.

### 2:45 - 3:00: Close

**Screen:** Final slide.

> Canopy takes a learner from a source, to a course, to practice, to evidence of mastery,
> and then to the next concept they need to review.

> Technical knowledge is everywhere. The missing layer is turning knowledge into
> capability. Canopy creates the bridge between learning something and being able to do
> something.

## Fallback plan

- If generation is slow, switch to the prepared course immediately.
- If Docker is unavailable, show a prepared passing lab and its saved result rather than
  attempting a live run.
- If a prerequisite recommendation is unavailable, show the separate Understand and
  Apply values and say that recommendations are triggered by learner evidence.
- Keep the dev-only auto-complete dialog out of the recording. It is a test utility, not
  part of the learner experience.
