import pytest

from worker.planner import CoursePlan, validate_course_plan


def test_course_plan_validation_accepts_grounded_acyclic_plan() -> None:
    plan = CoursePlan.model_validate(
        {
            "course_title": "JWT basics",
            "source_set_hash": "source-hash",
            "concepts": [
                {
                    "id": "headers",
                    "title": "Authorization headers",
                    "kind": "conceptual",
                    "summary_markdown": "Tokens travel in headers.",
                    "prerequisites": [],
                    "citations": ["chunk-a"],
                },
                {
                    "id": "expiry",
                    "title": "Token expiry",
                    "kind": "coding",
                    "summary_markdown": "Applications reject expired tokens.",
                    "prerequisites": ["headers"],
                    "citations": ["chunk-b"],
                },
            ],
            "modules": [
                {"id": "jwt-basics", "title": "JWT basics", "concept_ids": ["headers", "expiry"]}
            ],
        }
    )

    validate_course_plan(plan, "source-hash", ["chunk-a", "chunk-b"])


def test_course_plan_validation_rejects_a_cycle() -> None:
    plan = CoursePlan.model_validate(
        {
            "course_title": "Cycle",
            "source_set_hash": "source-hash",
            "concepts": [
                {
                    "id": "one",
                    "title": "One",
                    "kind": "conceptual",
                    "summary_markdown": "One.",
                    "prerequisites": ["two"],
                    "citations": ["chunk-a"],
                },
                {
                    "id": "two",
                    "title": "Two",
                    "kind": "conceptual",
                    "summary_markdown": "Two.",
                    "prerequisites": ["one"],
                    "citations": ["chunk-a"],
                },
            ],
            "modules": [{"id": "module", "title": "Module", "concept_ids": ["one", "two"]}],
        }
    )

    with pytest.raises(ValueError, match="acyclic"):
        validate_course_plan(plan, "source-hash", ["chunk-a"])


def test_course_plan_validation_accepts_goal_only_plan_without_citations() -> None:
    plan = CoursePlan.model_validate(
        {
            "course_title": "Python foundations",
            "source_set_hash": "goal-only-source-hash",
            "concepts": [
                {
                    "id": "variables",
                    "title": "Variables",
                    "kind": "coding",
                    "summary_markdown": "Store and reuse values with variables.",
                    "prerequisites": [],
                    "citations": [],
                }
            ],
            "modules": [{"id": "basics", "title": "Basics", "concept_ids": ["variables"]}],
        }
    )

    validate_course_plan(plan, "goal-only-source-hash", [])
