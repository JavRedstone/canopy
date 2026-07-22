# Canopy

**Demo video:** [https://www.youtube.com/watch?v=5FqJQYg25RM](https://www.youtube.com/watch?v=5FqJQYg25RM)

**`/feedback` Codex session ID:** the ID provided in the submission is shown on screen
at the [2:30 mark](https://youtu.be/5FqJQYg25RM?t=150) of the demo video.

**About the demo course:** every screenshot and sample PDF in this document is the
same real, generated course, built end to end from Vaswani et al.,
[*Attention Is All You Need*](https://arxiv.org/abs/1706.03762) (arXiv:1706.03762),
the Transformer paper. Not a mockup or a curated demo dataset.

## Inspiration

> Javier and I entered university at a strange time. We watched LLMs like GPT-3 become increasingly capable, and before long, they became a regular part of how we learned.
>
> At first, we used them for small things: clarifying a difficult paragraph, explaining an unfamiliar concept, or giving us another example when a lecture did not quite click. Then we started using them for almost everything. They could summarize papers, explain complex ideas, and answer nearly any question we had. Knowledge that once took hours to find was suddenly available in seconds. Life was great.
>
> For me especially, whenever I got stuck, I could ask ChatGPT for an explanation, read it, and think, "Okay, now I get it."
>
> Then my first exam came back. It was not pretty.
>
> That was when I realized I had confused understanding an explanation with understanding the material. Everything made sense while the answer was in front of me. Without it, much of that understanding disappeared.
>
> *Ethan*

LLMs have made it possible to teach yourself almost anything, from a research paper to a new framework or an unfamiliar codebase.

But LLMs were built to be helpful, and being helpful often means giving you the answer as quickly as possible. They can explain a concept, solve the problem, and even write the code, but they cannot tell whether you could do any of it yourself. A conversation history is not a model of what you have mastered.

This becomes especially important with technical material. You do not learn to code by watching someone else solve every problem. You learn by trying, getting stuck, debugging, and eventually doing it yourself. But LLMs are always eager to step in with the answer, and they rarely keep track of whether you actually learned the concept or just understood the explanation in the moment.

We started wondering what would happen if we combined the breadth and flexibility of LLMs with the structure of learning science.

What if AI did not just explain anything, but turned the material you actually wanted to learn into lessons, practice, and hands-on work? What if it tracked what you had demonstrated, challenged you where you were weak, and helped you build toward real mastery?

That is Canopy.

## What it does

Canopy brings together three things that are usually separated:

### 1. The scale of AI

Upload a research paper, documentation, textbook chapter, or your own notes, then tell Canopy what you want to learn. Canopy turns that material into a complete, hands-on course built specifically around your source and goal.

This gives learners the flexibility of an LLM without limiting them to a fixed catalogue of prebuilt courses.

### 2. The rigor of learning science

Canopy is designed around the idea that learning requires more than reading a good explanation. Learners retrieve information, write code, solve problems, make mistakes, receive feedback, and revisit weak prerequisites.

Instead of removing every difficult moment, Canopy creates opportunities to practise and apply each concept.

### 3. Mastery still has to be earned

Canopy does not treat scrolling through a lesson as proof that you learned it.

It separately tracks what you understand and what you can apply, using evidence from quizzes and hands-on labs. Learners must answer questions, implement concepts, run their code, debug mistakes, and demonstrate that they can complete the work themselves.

When a learner struggles, Canopy identifies the weak concept or prerequisite behind the mistake and directs them back to it.

![Canopy learner journey](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/demo/learner-journey-diagram.png)

Together, these three pillars allow Canopy to turn almost any technical source into a rigorous, hands-on course built around what the learner can actually demonstrate.

## How it works

Canopy takes learners through a complete learning loop, from the material they want to understand to evidence that they can actually apply it.

### 1. Start with the material you actually want to learn

Upload a research paper, documentation, textbook chapter, or your own notes. Then describe what you want to learn and what you want to be able to do with that knowledge.

Canopy uses the source and your goal to determine what concepts matter, how they depend on one another, and what kind of hands-on work would best demonstrate understanding.

### 2. Turn it into a complete course

Canopy generates a structured course with modules, lessons, worked examples, quizzes, practice questions, and coding labs.

The course is built specifically from your source rather than selected from a fixed catalogue. Lessons remain grounded in the original material, with citations that link explanations back to the passages they came from.

![Canopy course dashboard: the "Attention Is All You Need" course generated from the actual paper](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/course_landing_page.png)

*This course was generated directly from the "Attention Is All You Need" paper. The learner can move between course content, practice, and mastery from one dashboard.*

### 3. Learn actively, not passively

Each concept is taught through structured explanations, examples, retrieval practice, and immediate feedback.

Learners can ask the AI learning helper for a simpler explanation or a hint, but the helper is designed to guide rather than immediately reveal the answer.

![Lesson with the AI learning helper open, from the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/lesson_with_helper.png)

*A source-grounded lesson with inline citations, worked examples, and an AI helper that supports the learner without completing the assessment for them.*

### 4. Apply the concepts in real coding labs

For technical material, understanding an explanation is not enough. Learners need to implement the concept, run their code, inspect failures, and debug their mistakes.

Canopy generates hands-on coding labs inside a real editor. Before a lab reaches the learner, its reference solution is executed against hidden tests in a locked-down sandbox. If it fails, Canopy feeds the real failure back into the generation process, repairs the lab, and verifies it again.

Learners then complete the same kind of applied work themselves.

![Coding lab workspace with a prerequisite-review nudge, from the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/course_lab.png)

*A multi-head attention lab with a Monaco editor, live test results, and a prerequisite review recommendation based on the learner's previous performance.*

### 5. Track what the learner can actually do

Canopy does not treat lesson completion as mastery.

Each concept has two separate mastery signals:

* **Understand**, based on quiz and knowledge evidence
* **Apply**, based on hands-on lab performance

This distinction matters because a learner may recognize or explain a concept without being able to use it independently.

When a learner struggles, Canopy looks at the prerequisite relationships between concepts. If an earlier concept is weak, it recommends reviewing that concept before continuing.

![Mastery dashboard with per-concept Understand/Apply meters, for the "Attention Is All You Need" course](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/assets/mastery_landing.png)

*The mastery dashboard separates understanding from application and tracks each concept using evidence from quizzes and labs.*

The result is not simply an AI-generated course. It is a learning system that turns any source into structured instruction, hands-on practice, and measurable evidence of what the learner can actually do.

## A few more things you can do

Beyond the main course experience, we added a number of smaller features to make Canopy feel complete.

* Upload PDFs, Markdown, plain text, pasted notes, or multiple sources for the same course.
* Set your own learning goal, so the same source can produce a completely different course depending on what you want to learn.
* Watch course generation happen live, with progress updates for source processing, planning, and lesson creation.
* Resume a stalled course without losing the lessons that were already generated.
* Regenerate an entire course or just one lesson.
* Open any citation to view the exact source passage, page, and file it came from.
* Use a scratch console inside Python labs to test ideas without affecting your grade.
* Reveal a reference solution without overwriting your own code.
* Practise by weakest concept, course order, or shuffled questions, with sessions that avoid repeating the same material too often.
* Accept, defer, or dismiss review recommendations.
* Share a course through a link so someone else can create their own independent copy without copying your progress.
* Export the course as a PDF coursebook and earn a publicly verifiable completion certificate.
* Use the standalone playground to run Python, machine learning, JavaScript, Go, C++, or C without creating a course.
* Edit your course name, activity length, and quiz attempt limits after the course has already been created.

These features are not the main idea behind Canopy, but they helped us turn it from a prototype into something that feels much closer to a real learning platform.

## Built on learning science

Canopy's learning loop is built around active learning, retrieval practice, worked examples, productive struggle, and mastery based on demonstrated performance.

* **Learning by doing.** Learners answer questions, write code, run tests, debug failures, and apply concepts themselves instead of only reading explanations.

* **Retrieval instead of recognition.** Quizzes and low-stakes practice ask learners to recall ideas without the full answer in front of them.

* **Worked examples followed by practice.** Canopy introduces complex ideas with structured explanations and examples, then shifts toward increasingly independent problem-solving.

* **Separate understanding and application.** Bayesian Knowledge Tracing maintains two mastery estimates for each concept: **Understand**, based on quizzes, and **Apply**, based on coding submissions and hands-on work.

* **Mastery must be earned.** Low-stakes practice can improve a learner's estimate, but it cannot reach the mastery threshold on its own.

* **Prerequisite-aware review.** When a learner repeatedly struggles, Canopy checks whether an earlier prerequisite has already been attempted and remains weak before recommending review.

* **Current limitations and next steps.** The current model does not yet include spaced review, learner-calibrated parameters, fully adaptive remediation, or broader transfer checks. These are natural extensions of Canopy's existing practice engine, mastery ledger, prerequisite graph, sandbox, and grading pipeline.

## How we built it

Canopy is built as a five-service platform rather than a single AI request.

* a **Next.js web application** for the learner experience
* a **FastAPI API** for courses, assessments, and mastery
* a standalone **worker** for ingestion and course generation
* an **LLM gateway** for task-based model routing
* an isolated **sandbox runner** for executing generated code

Supabase provides authentication, storage, PostgreSQL, vector search, and the generation queue.

![Canopy runtime architecture](https://raw.githubusercontent.com/JavRedstone/canopy/refs/heads/main/docs/architecture/architecture-diagram.png)

*The five-service runtime. Course generation runs through the worker, while generated labs are verified through the isolated sandbox runner.*

### A staged course-generation pipeline

Canopy does not upload a document to one prompt and ask for a finished course.

The source is ingested and indexed for retrieval. GPT-5.6 then uses the learner's goal and relevant source material to plan the course structure, concepts, prerequisites, and coding environment.

Planning happens once at the course level. Once the concept graph is fixed, the worker generates lessons, quizzes, worked examples, practice items, and coding labs through separate jobs.

![How Canopy turns an uploaded source into a verified course](https://github.com/JavRedstone/canopy/raw/main/docs/assets/diagrams/generation-pipeline.png)

This separates high-stakes planning from high-volume content generation and keeps every lesson grounded in the learner's original material.

### What GPT-5.6 does at runtime

GPT-5.6 is not a chatbot added beside Canopy. It generates and evaluates the product's core learning experience.

Canopy routes each task based on its stakes and volume. High-stakes decisions use the flagship **Sol** tier, while high-volume generation and interaction use the faster **Luna** tier.

![GPT-5.6 task routing: planning and lab repair on the Sol tier, generation and the learning helper on the Luna tier](https://github.com/JavRedstone/canopy/raw/main/docs/assets/diagrams/model-routing.png)

| Task                          | Model tier        | Why                                                                                         |
| ----------------------------- | ----------------- | ------------------------------------------------------------------------------------------- |
| Course outline planning       | **Sol, flagship** | One high-stakes call defines the course structure, concept sequence, and coding environment |
| Per-module concept generation | **Luna, fast**    | Expands the course plan across modules                                                      |
| Lesson and lab authoring      | **Luna, fast**    | High-volume generation for every concept                                                    |
| Lab repair                    | **Sol, flagship** | The final verification step before generated work reaches a learner                         |
| Quiz and practice generation  | **Luna, fast**    | High-volume assessment generation                                                           |
| Short-answer grading          | **Luna, fast**    | Evaluates conceptual responses throughout the course                                        |
| In-lesson learning helper     | **Luna, fast**    | Provides explanations and hints without revealing assessment answers                        |

This routing lets Canopy spend more computation where one decision affects the entire course or determines whether generated code is safe to publish, while keeping repeated learner-facing interactions responsive.

### Generated code is verified, not trusted

The hardest engineering problem was safely generating coding labs that learners could rely on.

Canopy uses a bounded generate, execute, repair, and re-verify loop:

![The bounded generate, execute, repair and re-verify loop that every coding lab passes through before a learner sees it](https://github.com/JavRedstone/canopy/raw/main/docs/assets/diagrams/lab-repair-loop.png)

The model receives the actual traceback, compiler error, or failed assertion from the sandbox rather than a synthetic description of the problem.

Every execution runs in a fresh, locked-down container with no network access, a non-root user, resource limits, and all Linux capabilities removed.

A generated lab reaches the learner only after its reference solution passes in the real execution environment. If the repair loop cannot produce a valid lab within its retry budget, Canopy marks it as failed rather than quietly shipping broken content.

### Mastery tracks understanding and application separately

Canopy uses Bayesian Knowledge Tracing to update a per-concept mastery estimate after each assessed attempt.

The model considers:

* the learner's previous mastery estimate
* the chance of guessing correctly
* the chance of making a mistake despite mastery
* the chance that learning occurred during the attempt

Canopy maintains two independent tracks:

* **Understand**, updated through quizzes and conceptual assessments
* **Apply**, updated through coding submissions and hands-on work

This means a learner cannot master a coding concept simply by recognizing the correct explanation. They must also demonstrate that they can implement it.

Low-stakes practice can improve the learner's estimate, but it is capped below the mastery threshold. Practice helps, but stronger graded evidence is still required.

When a learner repeatedly struggles, Canopy checks the prerequisite graph and recommends earlier concepts that have already been attempted but remain weak.

![Quiz results feed the Understand track and coding submissions feed Apply; together they drive per-concept mastery and prerequisite-aware review](https://github.com/JavRedstone/canopy/raw/main/docs/assets/diagrams/mastery-model.png)

Together, these systems allow Canopy to generate learning content, verify the work it creates, and adapt recommendations using evidence from the learner's actual performance.

## Challenges we ran into

### Trusting generated code

An AI-generated coding lab is only useful if its instructions, starter code, reference solution, and hidden tests all agree.

Early versions of Canopy relied too heavily on the model's first attempt. We eventually built a verification loop that runs every reference solution in the real sandbox, returns the actual failure to GPT-5.6, repairs the lab, and verifies it again.

The loop still does not always succeed. During generation of our demo course, a beam-search lab repeatedly failed the same hidden edge case. Instead of quietly publishing broken material, Canopy marked the lab as failed.

That failure was frustrating, but it also proved that the system was behaving correctly.

### Running code without weakening security

Canopy executes both AI-generated code and learner-written code, so every submission has to be treated as untrusted.

Each execution runs inside a disposable, network-disabled, non-root container with strict resource limits. This created practical tradeoffs. For example, Valgrind required privileges that conflicted with our sandbox restrictions, so we used AddressSanitizer to preserve memory-safety testing without weakening isolation.

### Knowing when to help

Canopy should not immediately rescue learners whenever they struggle. Some difficulty is productive and gives learners the chance to reason through a problem themselves.

At the same time, leaving someone stuck for too long is not useful either.

Our current prerequisite recommendation uses repeated attempts and mastery thresholds to decide when to intervene. It works as a first step, but it also showed us that the right amount of support should eventually adapt to each learner.

## What we learned

The biggest lesson was that AI-generated work should never be trusted more than the evidence supporting it.

A lesson with citations can still be poorly grounded. A generated lab can look correct while failing its own tests. A passing submission can still reflect a narrow solution rather than deep understanding. A mastery percentage can look more precise than the data behind it.

That principle shaped both the product and the way we worked with Codex.

Codex was most effective when we gave it concrete evidence: a real database record, a failing test, an actual traceback, or a reproducible product behavior. The less abstract the problem was, the better the result.

We also learned that the strongest role for AI in education is not removing every difficult part. It is generating the structure, feedback, and opportunities that allow a learner to do the difficult part themselves.

## What is next

Our next priority is putting Canopy in front of real learners.

Our next planned pilot is with members of **UTMIST**, the University of Toronto Machine Intelligence Student Team, through its academics department. UTMIST members regularly teach themselves from research papers, documentation, and unfamiliar technical systems, which makes the club a strong environment for evaluating whether Canopy helps learners move from reading material to applying it.

That testing will help us evaluate:

* whether generated courses are genuinely useful
* where learners become confused or disengaged
* whether mastery estimates align with later performance
* which kinds of labs and assessments produce the strongest evidence
* when prerequisite recommendations are helpful rather than distracting

From there, the next product improvements are natural extensions of infrastructure that already exists:

* **Spaced review**, using the current practice engine to resurface mastered concepts over time
* **Adaptive remediation**, replacing fixed intervention thresholds with decisions based on the learner's trajectory
* **Stronger transfer exercises**, testing whether learners can apply the same principle in a different context
* **Better mastery calibration**, using real learner data instead of relying only on cold-start parameters
* **Repository ingestion**, allowing learners to generate courses directly from technical codebases
* **Cohort tools**, giving clubs, classrooms, and teams a shared view of learner progress

Canopy began with a simple realization: having an explanation in front of you is not the same as learning.

We built Canopy to see what AI-powered learning could look like when the AI creates the opportunity, but the learner still earns the mastery.

Thank you,

**Javier Huang and Ethan Qiu**