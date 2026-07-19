# Canopy recording script

This is the concise, screen-by-screen script for recording the product demo. For the
longer judging narrative, preparation checklist, and rationale, see [DEMO.md](./DEMO.md).

## Setup before recording

- Use a prepared course from a real primary source, such as "Attention Is All You Need."
- Use the goal: "Understand and implement scaled dot-product attention."
- Prepare a lab state that fails once, then passes after a small fix.
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

Upload "Attention Is All You Need" with the goal: "Understand and implement scaled
dot-product attention."

### 0:50 - 1:35: Source to demonstrated skill

**Screen:** Prepared course modules, cited lesson, then the coding lab.

> A learner starts with any technical source and a learning objective. Canopy creates a
> structured path from that source, then asks the learner to demonstrate understanding, not just
> consume content.

Briefly show the generated modules and open a citation.

> The lesson remains connected to the original source, so the learner can verify where a
> concept came from instead of trusting an opaque AI summary.

Open the attention lab. Run the incomplete implementation and pause briefly on the failure.

> This is where most AI learning stops. It explains the answer. Canopy makes the learner
> do the work.

Open the **Learning helper**, click **Give me a hint**, apply the small fix, and rerun.

> The learner does not just receive generated code. They encounter a real implementation
> failure, get lesson-aware guidance without the answer being handed over, and iterate
> until it works.

### 1:35 - 2:00: Evidence of learning

**Screen:** Mastery dashboard.

> Most education platforms measure completion. Canopy measures demonstrated ability.

Show the separate **Understand** and **Apply** signals.

> A learner can understand the theory but fail to implement it, or write working code
> without understanding why it works. Canopy separates those signals.

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

> **Source → Course → Practice → Evidence → Adaptation**

> Technical knowledge is everywhere. The missing layer is turning knowledge into
> capability. Canopy creates the bridge between learning something and being able to do
> something.

## Fallback plan

- If generation is slow, switch to the prepared course immediately.
- If Docker is unavailable, show a prepared passing lab and its saved result rather than
  attempting a live run.
- If a prerequisite recommendation is unavailable, show the separate Understand and
  Apply values and say that recommendations are triggered by learner evidence.
