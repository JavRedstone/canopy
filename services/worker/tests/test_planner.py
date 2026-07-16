import pytest

from worker.planner import CourseSkeleton, ModuleConcepts, validate_course_skeleton, validate_module_concepts


def test_course_skeleton_validation_accepts_matching_source_hash() -> None:
    skeleton = CourseSkeleton.model_validate(
        {
            "course_title": "JWT basics",
            "source_set_hash": "source-hash",
            "modules": [{"id": "jwt-basics", "title": "JWT basics"}],
        }
    )

    validate_course_skeleton(skeleton, "source-hash")


def test_course_skeleton_validation_rejects_mismatched_source_hash() -> None:
    skeleton = CourseSkeleton.model_validate(
        {
            "course_title": "JWT basics",
            "source_set_hash": "wrong-hash",
            "modules": [{"id": "jwt-basics", "title": "JWT basics"}],
        }
    )

    with pytest.raises(ValueError, match="source set"):
        validate_course_skeleton(skeleton, "source-hash")


def test_course_skeleton_rejects_duplicate_module_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        CourseSkeleton.model_validate(
            {
                "course_title": "JWT basics",
                "source_set_hash": "source-hash",
                "modules": [{"id": "dup", "title": "One"}, {"id": "dup", "title": "Two"}],
            }
        )


def test_module_concepts_validation_accepts_grounded_concepts_referencing_known_ids() -> None:
    concepts = ModuleConcepts.model_validate(
        {
            "concepts": [
                {
                    "id": "expiry",
                    "title": "Token expiry",
                    "kind": "coding",
                    "summary_markdown": "Applications reject expired tokens.",
                    "prerequisites": ["headers"],
                    "citations": ["chunk-b"],
                }
            ]
        }
    ).concepts

    validate_module_concepts(concepts, ["chunk-a", "chunk-b"], ["headers"])


def test_module_concepts_validation_rejects_forward_reference() -> None:
    concepts = ModuleConcepts.model_validate(
        {
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
                    "prerequisites": [],
                    "citations": ["chunk-a"],
                },
            ]
        }
    ).concepts

    with pytest.raises(ValueError, match="not-yet-generated"):
        validate_module_concepts(concepts, ["chunk-a"], [])


def test_module_concepts_validation_rejects_self_reference() -> None:
    concepts = ModuleConcepts.model_validate(
        {
            "concepts": [
                {
                    "id": "one",
                    "title": "One",
                    "kind": "conceptual",
                    "summary_markdown": "One.",
                    "prerequisites": ["one"],
                    "citations": ["chunk-a"],
                }
            ]
        }
    ).concepts

    with pytest.raises(ValueError, match="cannot depend on itself"):
        validate_module_concepts(concepts, ["chunk-a"], [])


def test_module_concepts_validation_accepts_goal_only_concepts_without_citations() -> None:
    concepts = ModuleConcepts.model_validate(
        {
            "concepts": [
                {
                    "id": "variables",
                    "title": "Variables",
                    "kind": "coding",
                    "summary_markdown": "Store and reuse values with variables.",
                    "prerequisites": [],
                    "citations": [],
                }
            ]
        }
    ).concepts

    validate_module_concepts(concepts, [], [])


def test_module_concepts_validation_rejects_id_reused_across_modules() -> None:
    concepts = ModuleConcepts.model_validate(
        {
            "concepts": [
                {
                    "id": "headers",
                    "title": "Duplicate",
                    "kind": "conceptual",
                    "summary_markdown": "Reuses an earlier module's ID.",
                    "prerequisites": [],
                    "citations": [],
                }
            ]
        }
    ).concepts

    with pytest.raises(ValueError, match="not unique"):
        validate_module_concepts(concepts, [], ["headers"])
