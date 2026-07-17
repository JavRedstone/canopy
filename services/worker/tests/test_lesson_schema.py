import pytest
from pydantic import ValidationError

from worker.lesson_schema import LessonBundle, bundle_citations, reference_workspace, validate_lesson_bundle


def _quiz_item(**overrides: object) -> dict:
    base = {
        "id": "expiry-check",
        "kind": "mcq",
        "prompt_markdown": "What happens when a token's exp claim is in the past?",
        "options": [
            {"text": "It is rejected.", "explanation_markdown": "Correct: expired tokens must never validate."},
            {"text": "It is accepted.", "explanation_markdown": "Wrong: that would defeat expiry entirely."},
        ],
        "correct_option_index": 0,
        "correct_answers": [],
        "explanation_markdown": "Expiry is a hard boundary, not a hint.",
        "citations": ["chunk-a"],
    }
    base.update(overrides)
    return base


def _coding_bundle(**overrides: object) -> dict:
    base = {
        "schema_version": 2,
        "lesson_content": {
            "title": "Reject expired tokens",
            "explanation_markdown": "Tokens carry an expiry claim that must be checked.",
            "citations": ["chunk-a"],
            "worked_examples": [
                {"title": "Reading a claim", "body_markdown": "```python\ntoken['exp']\n```", "citations": []}
            ],
        },
        "workspace": {
            "environment_id": "python-basic",
            "files": [
                {"path": "solution.py", "content": "def is_expired(token):\n    ...\n", "visibility": "visible", "editable_regions": None}
            ],
        },
        "assessment": {
            "visible_tests": [
                {"path": "test_basic.py", "content": "from solution import is_expired\n\ndef test_expired_token_is_rejected():\n    assert is_expired({'exp': 0})\n"}
            ],
            "hidden_tests": [
                {"path": "test_solution.py", "content": "from solution import is_expired\n\ndef test_it():\n    assert is_expired({'exp': 0})\n"}
            ],
            "quiz_items": [_quiz_item()],
            "hints": ["Compare the exp claim against the current time."],
            "reference_solution_files": [
                {"path": "solution.py", "content": "def is_expired(token):\n    return token['exp'] < 1\n"}
            ],
        },
    }
    base.update(overrides)
    return base


def _conceptual_bundle(**overrides: object) -> dict:
    base = {
        "schema_version": 2,
        "lesson_content": {
            "title": "Why tokens expire",
            "explanation_markdown": "Expiry bounds the damage of a leaked token.",
            "citations": ["chunk-a"],
            "worked_examples": [],
        },
        "workspace": None,
        "assessment": {
            "visible_tests": [],
            "hidden_tests": [],
            "quiz_items": [_quiz_item()],
            "hints": [],
            "reference_solution_files": [],
        },
    }
    base.update(overrides)
    return base


def _assessment(bundle: dict, **overrides: object) -> dict:
    assessment = {**bundle["assessment"], **overrides}
    return {**bundle, "assessment": assessment}


def test_valid_coding_bundle_passes_validation() -> None:
    bundle = LessonBundle.model_validate(_coding_bundle())
    validate_lesson_bundle(bundle, ["chunk-a", "chunk-b"], require_workspace=True)


def test_valid_conceptual_bundle_passes_validation() -> None:
    bundle = LessonBundle.model_validate(_conceptual_bundle())
    validate_lesson_bundle(bundle, ["chunk-a"])


def test_conceptual_bundle_fails_workspace_requirement() -> None:
    bundle = LessonBundle.model_validate(_conceptual_bundle())
    with pytest.raises(ValueError, match="must include a workspace"):
        validate_lesson_bundle(bundle, ["chunk-a"], require_workspace=True)


def test_bundle_rejects_citation_outside_context() -> None:
    bundle = LessonBundle.model_validate(_coding_bundle())
    with pytest.raises(ValueError, match="cites a chunk outside"):
        validate_lesson_bundle(bundle, ["chunk-b"], require_workspace=True)


def test_quiz_citations_count_toward_bundle_citations() -> None:
    bundle = LessonBundle.model_validate(
        _assessment(_coding_bundle(), quiz_items=[_quiz_item(citations=["chunk-q"])])
    )
    assert "chunk-q" in bundle_citations(bundle)
    with pytest.raises(ValueError, match="cites a chunk outside"):
        validate_lesson_bundle(bundle, ["chunk-a"], require_workspace=True)


def test_bundle_rejects_path_traversal() -> None:
    bundle = _coding_bundle()
    bundle["workspace"]["files"] = [{"path": "../etc/passwd.py", "content": "x = 1\n"}]
    with pytest.raises(ValidationError):
        LessonBundle.model_validate(bundle)


def test_bundle_rejects_reference_not_covering_visible_paths() -> None:
    with pytest.raises(ValueError, match="exactly the visible"):
        LessonBundle.model_validate(
            _assessment(_coding_bundle(), reference_solution_files=[{"path": "other.py", "content": "x = 1\n"}])
        )


def test_bundle_rejects_starter_identical_to_reference_solution() -> None:
    bundle = _coding_bundle()
    bundle["workspace"]["files"][0]["content"] = bundle["assessment"]["reference_solution_files"][0]["content"]
    with pytest.raises(ValueError, match="identical to the reference solution"):
        LessonBundle.model_validate(bundle)


def test_bundle_rejects_test_file_colliding_with_workspace_path() -> None:
    with pytest.raises(ValueError, match="must not collide"):
        LessonBundle.model_validate(
            _assessment(_coding_bundle(), hidden_tests=[{"path": "solution.py", "content": "x = 1\n"}])
        )


def test_bundle_requires_a_discoverable_hidden_test_file() -> None:
    with pytest.raises(ValueError, match="hidden test file must be pytest-discoverable"):
        LessonBundle.model_validate(
            _assessment(_coding_bundle(), hidden_tests=[{"path": "checks.py", "content": "assert True\n"}])
        )


def test_bundle_rejects_non_discoverable_visible_test_file() -> None:
    with pytest.raises(ValueError, match="visible test file must be pytest-discoverable"):
        LessonBundle.model_validate(
            _assessment(_coding_bundle(), visible_tests=[{"path": "checks.py", "content": "assert True\n"}])
        )


def test_bundle_rejects_visible_and_hidden_test_sharing_a_path() -> None:
    with pytest.raises(ValueError, match="must not share a path"):
        LessonBundle.model_validate(
            _assessment(
                _coding_bundle(),
                visible_tests=[{"path": "test_solution.py", "content": "def test_a():\n    assert True\n"}],
            )
        )


def test_coding_bundle_requires_hidden_tests() -> None:
    with pytest.raises(ValueError, match="at least one hidden test"):
        LessonBundle.model_validate(_assessment(_coding_bundle(), hidden_tests=[]))


def test_conceptual_bundle_can_be_a_reading_only_activity() -> None:
    bundle = LessonBundle.model_validate(_assessment(_conceptual_bundle(), quiz_items=[]))
    assert bundle.workspace is None
    assert bundle.assessment.quiz_items == []


def test_conceptual_bundle_rejects_tests_without_workspace() -> None:
    with pytest.raises(ValueError, match="cannot carry tests"):
        LessonBundle.model_validate(
            _assessment(_conceptual_bundle(), hidden_tests=[{"path": "test_x.py", "content": "assert True\n"}])
        )


def test_multi_select_item_requires_valid_indices() -> None:
    item = _quiz_item(
        kind="multi_select",
        correct_option_index=None,
        options=[
            {"text": "A", "explanation_markdown": "Right."},
            {"text": "B", "explanation_markdown": "Right."},
            {"text": "C", "explanation_markdown": "Wrong."},
        ],
    )
    valid = LessonBundle.model_validate(
        _assessment(_conceptual_bundle(), quiz_items=[{**item, "correct_option_indices": [0, 1]}])
    )
    assert valid.assessment.quiz_items[0].correct_option_indices == [0, 1]
    with pytest.raises(ValueError, match="correct_option_indices"):
        LessonBundle.model_validate(
            _assessment(_conceptual_bundle(), quiz_items=[{**item, "correct_option_indices": [0, 7]}])
        )
    with pytest.raises(ValueError, match="correct_option_indices"):
        LessonBundle.model_validate(
            _assessment(_conceptual_bundle(), quiz_items=[{**item, "correct_option_indices": []}])
        )


def test_short_answer_item_requires_rubric_and_no_options() -> None:
    item = _quiz_item(
        kind="short_answer",
        options=[],
        correct_option_index=None,
        rubric_markdown="Must mention that expiry bounds the damage of a leaked token.",
    )
    valid = LessonBundle.model_validate(_assessment(_conceptual_bundle(), quiz_items=[item]))
    assert valid.assessment.quiz_items[0].rubric_markdown is not None
    with pytest.raises(ValueError, match="rubric_markdown"):
        LessonBundle.model_validate(
            _assessment(_conceptual_bundle(), quiz_items=[{**item, "rubric_markdown": None}])
        )
    with pytest.raises(ValueError, match="free-text"):
        LessonBundle.model_validate(
            _assessment(
                _conceptual_bundle(),
                quiz_items=[{**item, "options": [{"text": "A", "explanation_markdown": "x"}, {"text": "B", "explanation_markdown": "y"}]}],
            )
        )


def test_mcq_item_requires_correct_option_index_in_range() -> None:
    with pytest.raises(ValueError, match="correct_option_index"):
        LessonBundle.model_validate(
            _assessment(_conceptual_bundle(), quiz_items=[_quiz_item(correct_option_index=5)])
        )


def test_fill_item_requires_accepted_answers() -> None:
    with pytest.raises(ValueError, match="accepted answer"):
        LessonBundle.model_validate(
            _assessment(
                _conceptual_bundle(),
                quiz_items=[_quiz_item(kind="fill", options=[], correct_option_index=None, correct_answers=[])],
            )
        )


def test_reference_workspace_includes_context_files_and_all_tests() -> None:
    bundle = _coding_bundle()
    bundle["workspace"]["files"].append(
        {"path": "config.py", "content": "TOLERANCE = 1\n", "visibility": "inspectable", "editable_regions": None}
    )
    parsed = LessonBundle.model_validate(bundle)
    paths = [file.path for file in reference_workspace(parsed)]
    assert paths == ["solution.py", "config.py", "test_basic.py", "test_solution.py"]
