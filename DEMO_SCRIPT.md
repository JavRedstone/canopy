# Canopy demo script

## Setup before recording

- Use a course generated ahead of time from a real short source document.
- Confirm at least one conceptual lesson, one coding lab, and one coursebook export work.
- Keep Docker, the worker, sandbox runner, API, gateway, and web app running.
- Open the course list in one browser tab and the prepared course in another.

## Three-minute walkthrough

### 0:00 - 0:15: The problem

Show **My courses**.

> Most tools can summarize a document. Canopy turns a source you already have into a course that you can read, practice, and prove you understand.

Point out that each course has its own goal, source set, and progress.

### 0:15 - 0:40: Create a course from a source

Open **New course**. Show a real PDF, Markdown file, or text document and enter a focused goal, for example:

> I want to train and evaluate supervised learning models in Python.

> Canopy plans a course from the source and goal, then generates lessons, practice, and checks around that specific material.

Do not wait through live generation in the recording. Switch to the prepared course once the creation flow is visible.

### 0:40 - 1:05: Show the course artifact

On the prepared course page, show the Coursebook card and its module preview.

> This is not just a chat answer. The course has a durable structure: modules, reading lessons, labs, mastery checks, and the original source material behind it.

Open **Browse sources**. Briefly show the source library, then close it.

Click **Download coursebook**. Show the PDF cover, one styled lesson page, and the linked references appendix.

> The coursebook is a real PDF export, not a screenshot or a browser printout. It includes the learner-visible material and links citations to the references at the back.

### 1:05 - 1:35: Grounded reading and assessment

Open a conceptual lesson. Show the explanation, a worked example, and a quiz item.

Click an inline citation if one is visible.

> Lessons are grounded in the uploaded source. The learner can follow a claim back to the exact source excerpt instead of trusting an uncited summary.

Answer one quiz item.

> This is also learning evidence. Reading and applying are tracked separately.

### 1:35 - 2:20: The coding lab

Open a coding lesson. Show the starter code, tests, and **Run** button.

Make or reveal a small incomplete implementation. Run it once so a visible test fails. Use a hint, fix the implementation, run again, and then submit.

> The lab is real code in an isolated sandbox. Run gives fast visible-test feedback. Submit uses the full validation suite and records demonstrated application, not just completion.

If asked about reliability:

> Before a learner sees a coding lesson, Canopy validates the generated starter, tests, and reference solution in the same sandbox. Failed generation is retried and surfaced as a real build state instead of silently appearing complete.

### 2:20 - 2:45: Mastery

Return to the course and open **Mastery**.

> Canopy keeps two signals: understanding from conceptual checks and application from coding submissions. That makes it possible to distinguish “I read this” from “I can use this.”

Point out any prerequisite recommendation if available.

### 2:45 - 3:00: Close

Return to the Coursebook card or course list.

> Canopy turns your source material into something more useful than a summary: a grounded course, real practice, measured learning, and a coursebook you can keep.

## Fallback plan

- If generation is slow, use the prepared course immediately.
- If Docker is unavailable, do not demo a coding run; show the existing validated lab and Coursebook instead.
- If a source citation is unavailable, show the Coursebook references appendix.
- Keep a previously downloaded coursebook PDF open in a separate tab.
