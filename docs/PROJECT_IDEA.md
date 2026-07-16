# AI-Powered Adaptive Learning Platform: Full Summary

## Concept

An AI-powered learning platform that transforms educational goals and learning materials into **personalized, interactive coding experiences**.

The system ingests:

* Natural language learning goals.
* Textbooks.
* Research papers.
* Course notes.
* Documentation.
* Other educational documents.

Instead of generating an entire course upfront, the platform uses **Just-In-Time (JIT) generation**. Each lesson is independently created by an AI Lesson Generation Agent based on:

* The curriculum roadmap.
* Retrieved knowledge from learning materials.
* Student progress.
* Previous mistakes.

Each generated lesson includes:

* Concept explanations.
* Examples.
* Coding exercises.
* Expected learning outcomes.
* Sandbox requirements.

The Sandbox Generator Agent then uses Codex to autonomously create, test, and refine the coding environment required for that lesson.

The system continuously improves by analyzing student interactions and adapting future lessons and sandbox experiences.

---

# High-Level Architecture

```text
                 Learning Goal / Educational Materials
        (Text, PDFs, Research Papers, Textbooks, Notes)
                              |
                              v
                 ┌─────────────────────────┐
                 │ Knowledge Ingestion     │
                 │ Document Processing     │
                 └────────────┬────────────┘
                              |
                              v
                 ┌─────────────────────────┐
                 │ PostgreSQL + PgVector   │
                 │ Knowledge Base          │
                 └────────────┬────────────┘
                              |
                              v
                 ┌─────────────────────────┐
                 │ Curriculum Planner      │
                 │ Azure OpenAI            │
                 └────────────┬────────────┘
                              |
                              v
                  Learning Roadmap
                  Modules + Objectives
                              |
                              v
                 ┌─────────────────────────┐
                 │ Lesson Generation Agent │
                 │ Azure OpenAI            │
                 └────────────┬────────────┘
                              |
                              v
          Generates individual lessons on demand:

          - Explanation
          - Examples
          - Exercises
          - Evaluation criteria
          - Sandbox goal
                              |
                              v
                 ┌─────────────────────────┐
                 │ Sandbox Generator Agent │
                 │ Codex Powered           │
                 └────────────┬────────────┘
                              |
                              v
             Autonomous Engineering Loop:

             Plan → Generate → Execute → Evaluate → Adapt

                              |
                              v
                 ┌─────────────────────────┐
                 │ Interactive Sandbox     │
                 │ Docker Environment      │
                 └────────────┬────────────┘
                              |
                              v
                 Student Completes Exercise
                              |
                              v
                 ┌─────────────────────────┐
                 │ Evaluation Agent        │
                 │ Azure OpenAI            │
                 └────────────┬────────────┘
                              |
                              v
             Adapt Lesson + Sandbox Generation

                              |
                              └──────────────► Future Lessons
```

---

# Core Components

## 1. Knowledge Ingestion Layer

The platform accepts educational sources:

* Text descriptions.
* Textbooks.
* Research papers.
* Lecture materials.
* Documentation.

The documents are processed and stored.

### PostgreSQL + PgVector

PgVector stores:

* Document embeddings.
* Knowledge chunks.
* Reference material.

PostgreSQL stores:

* Users.
* Learning progress.
* Curriculum structures.
* Generated lessons.
* Sandbox metadata.
* Interaction history.

This allows agents to retrieve relevant context when generating lessons.

---

# 2. Curriculum Planner Agent

The Curriculum Planner creates the high-level learning path.

Example input:

> "Teach undergraduate students backend development."

Output:

```json
{
  "modules": [
    {
      "topic": "HTTP fundamentals"
    },
    {
      "topic": "REST APIs"
    },
    {
      "topic": "Authentication"
    },
    {
      "topic": "Deployment"
    }
  ]
}
```

The planner creates the roadmap but does not generate every lesson immediately.

---

# 3. Lesson Generation Agent

Lessons are generated individually using a JIT approach.

When a student reaches a lesson, the agent considers:

* Curriculum objective.
* Retrieved educational materials.
* Student knowledge level.
* Previous failures.
* Learning history.

Example:

Input:

> Lesson: Authentication

Output:

```json
{
  "objective": "Implement JWT authentication",
  "concepts": [
    "tokens",
    "authorization",
    "middleware"
  ],
  "exercise": {
    "task": "Secure a FastAPI endpoint"
  },
  "sandbox_goal": {
    "language": "Python",
    "framework": "FastAPI",
    "requirements": [
      "Create login endpoint",
      "Validate JWT",
      "Protect routes"
    ]
  }
}
```

The lesson agent creates the **sandbox specification**, but does not build the environment.

---

# 4. Sandbox Generator Agent (Codex Powered)

The Sandbox Generator Agent is the core differentiator.

Its purpose:

> Take a lesson goal and autonomously create a complete, validated coding environment.

It receives:

* Lesson objectives.
* Exercise requirements.
* Technical constraints.
* Expected outcomes.

---

## Sandbox Generation Workflow

```text
Lesson Sandbox Goal
          |
          v
        Codex
          |
          v
Create Repository
          |
          v
Generate:

- Starter Code
- Instructions
- Tests
- Grading Logic
- Hints
- Reference Solution
- Environment Setup
          |
          v
Build Docker Sandbox
          |
          v
Run Automated Validation
          |
          v
Failures?
     |
     +---- Yes
     |
     v
Codex analyzes errors
     |
     v
Updates repository
     |
     v
Re-run validation
          |
          v
Validated Sandbox
```

Codex performs:

* Multi-file repository generation.
* Code implementation.
* Test creation.
* Debugging.
* Iterative refinement.

---

## Example

Learning goal:

> "Teach recursion."

Generated sandbox:

```text
recursion-lab/

├── README.md
├── starter.py
├── tests/
│   └── test_recursion.py
├── hints/
├── solution.py
└── Dockerfile
```

Before students access it:

* Tests execute.
* Environment builds.
* Instructions are validated.
* Errors are fixed automatically.

---

# 5. Interactive Student Sandbox

Students interact with the generated environment through a browser.

## Frontend

* Next.js.
* Monaco Editor.
* Terminal interface.
* Lesson viewer.
* Progress display.

## Backend

* FastAPI.
* Docker SDK.
* WebSockets.

Execution flow:

```text
Student Code
      |
      v
FastAPI Backend
      |
      v
Docker Sandbox
      |
      v
Run Tests
      |
      v
Stream stdout/stderr
      |
      v
Evaluation Feedback
```

Each lesson receives its own isolated execution environment.

---

# 6. Evaluation Agent and Adaptive Learning Loop

The Evaluation Agent analyzes student interactions.

It considers:

* Code submissions.
* Test failures.
* Debugging patterns.
* Time spent.
* Hint usage.
* Repeated mistakes.

Its purpose is not only grading.

It determines:

* What concepts the student struggles with.
* Whether explanations are unclear.
* Whether exercises are too difficult.
* How lessons should be modified.

---

## Adaptive Feedback Loop

```text
Student Interaction
        |
        v
Sandbox Data
        |
        v
Evaluation Agent
        |
        +--> Identify Knowledge Gaps
        +--> Detect Confusing Explanations
        +--> Adjust Difficulty
        +--> Recommend Improvements
        |
        v
Lesson Generation Agent
        |
        +--> Modify Explanations
        +--> Change Examples
        +--> Adjust Exercises
        |
        v
Sandbox Generator Agent
        |
        +--> Modify Project Structure
        +--> Update Tests
        +--> Improve Hints
        |
        v
Improved Learning Experience
```

Example:

Student repeatedly fails JWT authentication.

The system adapts:

Before:

> "Implement JWT authentication."

After:

* Adds token lifecycle visualization.
* Provides smaller guided exercises.
* Adds additional examples.
* Adjusts hidden tests.

---

# Technology Stack

## Frontend

* Next.js
* React
* Tailwind CSS / shadcn UI
* Monaco Editor
* WebSockets

## Backend

* FastAPI
* Docker SDK
* Agent orchestration
* Background task management

## AI

* Azure OpenAI GPT models
* Codex for autonomous sandbox generation
* Evaluation agents

## Database

PostgreSQL:

* User data.
* Curriculum.
* Lessons.
* Progress.
* Sandbox metadata.

PgVector:

* Textbooks.
* Research papers.
* Documentation.
* Educational materials.

## Infrastructure

Possible deployment:

Azure:

* Azure Container Apps.
* Azure Container Instances.

AWS:

* ECS Fargate.

---

# Why This Fits the Hackathon

Most AI education tools focus on:

* Answering questions.
* Summarizing information.
* Generating explanations.

This platform focuses on:

> **Creating and continuously improving executable learning environments.**

The core agentic loop:

```text
Educational Material
        ↓
Curriculum Planning
        ↓
Lesson Generation
        ↓
Sandbox Goal Creation
        ↓
Codex Builds Environment
        ↓
Sandbox Validates Itself
        ↓
Student Learns
        ↓
Evaluation Agent Adapts Experience
        ↓
Improved Future Lessons
```

Codex is essential because it enables autonomous software engineering: creating repositories, generating code, running tests, debugging failures, and iterating until a working educational environment is produced. The result is not just AI-generated content, but a continuously improving system that builds the environments where learning happens.
