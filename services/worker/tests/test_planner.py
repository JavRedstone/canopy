import pytest

from worker.planner import CourseOutline, ModuleConcepts, validate_course_outline, validate_module_concepts


def _outline(**overrides: object) -> dict:
    base = {
        "course_title": "JWT basics",
        "source_set_hash": "source-hash",
        "audience": "Backend developers new to authentication.",
        "objectives": ["Understand JWT structure", "Validate tokens safely"],
        "language": "python",
        "modules": [
            {"id": "jwt-basics", "title": "JWT basics", "focus": "What a JWT is and its parts.", "lesson_count": 6},
            {"id": "validation", "title": "Validation", "focus": "Verifying signatures and claims.", "lesson_count": 6},
        ],
    }
    base.update(overrides)
    return base


def _concepts(entries: list[dict]) -> list:
    return ModuleConcepts.model_validate({"concepts": entries}).concepts


def test_course_outline_validation_accepts_matching_hash_and_budget() -> None:
    outline = CourseOutline.model_validate(_outline())
    validate_course_outline(outline, "source-hash", 12, 14)


def test_course_outline_validation_rejects_mismatched_source_hash() -> None:
    outline = CourseOutline.model_validate(_outline(source_set_hash="wrong-hash"))
    with pytest.raises(ValueError, match="source set"):
        validate_course_outline(outline, "source-hash", 12, 14)


def test_course_outline_validation_rejects_budget_out_of_range() -> None:
    outline = CourseOutline.model_validate(_outline())  # totals 12 lessons
    with pytest.raises(ValueError, match="between 13 and 14 lessons"):
        validate_course_outline(outline, "source-hash", 13, 14)


def test_course_outline_validation_rejects_one_topic_for_normal_course_lengths() -> None:
    outline = CourseOutline.model_validate(_outline(modules=[
        {"id": "jwt", "title": "JWT", "focus": "JWT fundamentals and validation.", "lesson_count": 8},
    ]))
    with pytest.raises(ValueError, match="at least two distinct modules"):
        validate_course_outline(outline, "source-hash", 8, 10)


def test_course_outline_validation_keeps_one_topic_available_for_short_courses() -> None:
    outline = CourseOutline.model_validate(_outline(modules=[
        {"id": "jwt", "title": "JWT", "focus": "JWT fundamentals.", "lesson_count": 6},
    ]))
    validate_course_outline(outline, "source-hash", 6, 7)


def test_course_outline_rejects_duplicate_module_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        CourseOutline.model_validate(
            _outline(
                modules=[
                    {"id": "dup", "title": "One", "focus": "First.", "lesson_count": 6},
                    {"id": "dup", "title": "Two", "focus": "Second.", "lesson_count": 6},
                ]
            )
        )


def test_module_concepts_validation_accepts_grounded_concepts_referencing_known_ids() -> None:
    concepts = _concepts(
        [
            {"id": "token-shape", "title": "Token shape", "kind": "conceptual", "summary_markdown": "Headers carry authentication information.", "prerequisites": ["headers"], "citations": ["chunk-b"]},
            {"id": "expiry", "title": "Token expiry", "kind": "conceptual", "summary_markdown": "Applications reject expired tokens.", "prerequisites": ["token-shape"], "citations": ["chunk-b"]},
            {"id": "signature", "title": "Signature checks", "kind": "conceptual", "summary_markdown": "Signatures establish authenticity.", "prerequisites": ["expiry"], "citations": ["chunk-b"]},
            {"id": "validate", "title": "Validate tokens", "kind": "coding", "summary_markdown": "Validate token expiry in code.", "prerequisites": ["expiry"], "citations": ["chunk-b"]},
            {"id": "validate-signature", "title": "Validate signatures", "kind": "coding", "summary_markdown": "Validate signatures in code.", "prerequisites": ["validate"], "citations": ["chunk-b"]},
            {"id": "token-assessment", "title": "Token assessment", "kind": "assessment", "summary_markdown": "Assess token validation.", "prerequisites": ["validate-signature"], "citations": ["chunk-b"]},
        ]
    )
    validate_module_concepts(concepts, ["chunk-a", "chunk-b"], ["headers"])


def test_module_concepts_validation_rejects_wrong_expected_count() -> None:
    concepts = _concepts(
        [
            {
                "id": "expiry",
                "title": "Token expiry",
                "kind": "coding",
                "summary_markdown": "Applications reject expired tokens.",
                "prerequisites": [],
                "citations": [],
            }
        ]
    )
    with pytest.raises(ValueError, match="exactly 2 concept"):
        validate_module_concepts(concepts, [], [], expected_count=2)


def test_module_concepts_validation_accepts_any_kind_mix_and_order() -> None:
    # The 3-lecture/2-lab/lecture-then-lab-then-assessment shape is prompt guidance, not a
    # hard requirement: a module with a single lecture, a lab before it, and no assessment
    # at all must still validate. Display order is guaranteed separately by course_map()'s
    # kind-based re-sort in services/api/app/repository.py, not by generation order.
    concepts = _concepts(
        [
            {"id": "lab", "title": "Lab", "kind": "coding", "summary_markdown": "Practice.", "prerequisites": [], "citations": []},
            {"id": "intro", "title": "Intro", "kind": "conceptual", "summary_markdown": "Intro.", "prerequisites": [], "citations": []},
        ]
    )
    validate_module_concepts(concepts, [], [])


def test_module_concepts_validation_rejects_multiple_assessments() -> None:
    concepts = _concepts(
        [
            {"id": "intro", "title": "Intro", "kind": "conceptual", "summary_markdown": "Intro.", "prerequisites": [], "citations": []},
            {"id": "check-one", "title": "Check one", "kind": "assessment", "summary_markdown": "Check.", "prerequisites": [], "citations": []},
            {"id": "check-two", "title": "Check two", "kind": "assessment", "summary_markdown": "Check.", "prerequisites": [], "citations": []},
        ]
    )
    with pytest.raises(ValueError, match="at most one assessment"):
        validate_module_concepts(concepts, [], [])


def test_module_concepts_validation_rejects_forward_reference() -> None:
    concepts = _concepts(
        [
            {"id": "one", "title": "One", "kind": "conceptual", "summary_markdown": "One.", "prerequisites": ["two"], "citations": ["chunk-a"]},
            {"id": "two", "title": "Two", "kind": "conceptual", "summary_markdown": "Two.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "three", "title": "Three", "kind": "conceptual", "summary_markdown": "Three.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "lab", "title": "Lab", "kind": "coding", "summary_markdown": "Practice.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "lab2", "title": "Lab 2", "kind": "coding", "summary_markdown": "Practice more.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "check", "title": "Check", "kind": "assessment", "summary_markdown": "Assess.", "prerequisites": [], "citations": ["chunk-a"]},
        ]
    )
    with pytest.raises(ValueError, match="not-yet-generated"):
        validate_module_concepts(concepts, ["chunk-a"], [])


def test_module_concepts_validation_rejects_self_reference() -> None:
    concepts = _concepts(
        [
            {"id": "one", "title": "One", "kind": "conceptual", "summary_markdown": "One.", "prerequisites": ["one"], "citations": ["chunk-a"]},
            {"id": "two", "title": "Two", "kind": "conceptual", "summary_markdown": "Two.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "three", "title": "Three", "kind": "conceptual", "summary_markdown": "Three.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "lab", "title": "Lab", "kind": "coding", "summary_markdown": "Practice.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "lab2", "title": "Lab 2", "kind": "coding", "summary_markdown": "Practice more.", "prerequisites": [], "citations": ["chunk-a"]},
            {"id": "check", "title": "Check", "kind": "assessment", "summary_markdown": "Assess.", "prerequisites": [], "citations": ["chunk-a"]},
        ]
    )
    with pytest.raises(ValueError, match="cannot depend on itself"):
        validate_module_concepts(concepts, ["chunk-a"], [])


def test_module_concepts_validation_accepts_goal_only_concepts_without_citations() -> None:
    concepts = _concepts(
        [
            {"id": "variables", "title": "Variables", "kind": "conceptual", "summary_markdown": "Store values.", "prerequisites": [], "citations": []},
            {"id": "values", "title": "Values", "kind": "conceptual", "summary_markdown": "Kinds of values.", "prerequisites": [], "citations": []},
            {"id": "reuse", "title": "Reuse", "kind": "conceptual", "summary_markdown": "Reuse values.", "prerequisites": [], "citations": []},
            {"id": "variables-lab", "title": "Variables lab", "kind": "coding", "summary_markdown": "Practice variables.", "prerequisites": [], "citations": []},
            {"id": "reuse-lab", "title": "Reuse lab", "kind": "coding", "summary_markdown": "Practice reuse.", "prerequisites": [], "citations": []},
            {"id": "variables-check", "title": "Variables assessment", "kind": "assessment", "summary_markdown": "Assess variables.", "prerequisites": [], "citations": []},
        ]
    )
    validate_module_concepts(concepts, [], [])


def test_module_concepts_validation_rejects_id_reused_across_modules() -> None:
    concepts = _concepts(
        [
            {"id": "headers", "title": "Duplicate", "kind": "conceptual", "summary_markdown": "Reuses an earlier module's ID.", "prerequisites": [], "citations": []},
            {"id": "second", "title": "Second", "kind": "conceptual", "summary_markdown": "Another lecture.", "prerequisites": [], "citations": []},
            {"id": "third", "title": "Third", "kind": "conceptual", "summary_markdown": "A third lecture.", "prerequisites": [], "citations": []},
            {"id": "lab", "title": "Lab", "kind": "coding", "summary_markdown": "Practice.", "prerequisites": [], "citations": []},
            {"id": "lab2", "title": "Lab 2", "kind": "coding", "summary_markdown": "Practice more.", "prerequisites": [], "citations": []},
            {"id": "check", "title": "Check", "kind": "assessment", "summary_markdown": "Assess.", "prerequisites": [], "citations": []},
        ]
    )
    with pytest.raises(ValueError, match="not unique"):
        validate_module_concepts(concepts, [], ["headers"])
