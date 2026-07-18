"""Coverage for the split generation schema: LessonContentBundle and
CodingArtifactsBundle carry the same consistency rules LessonBundle used to enforce as
one unit, and _compose_bundle must assemble them back into an identical stored shape."""

import pytest
from pydantic import ValidationError

from worker.lesson_build import _compose_bundle
from worker.lesson_schema import (
    CodingArtifactsBundle,
    LessonContentBundle,
    Workspace,
    bundle_content_citations,
    validate_lesson_content,
)


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


def _content(**overrides: object) -> dict:
    base = {
        "lesson_content": {
            "title": "Reject expired tokens",
            "explanation_markdown": "Tokens carry an expiry claim that must be checked.",
            "citations": ["chunk-a"],
            "worked_examples": [
                {"title": "Reading a claim", "body_markdown": "```python\ntoken['exp']\n```", "citations": []}
            ],
        },
        "quiz_items": [_quiz_item()],
        "hints": ["Compare the exp claim against the current time."],
    }
    base.update(overrides)
    return base


def _artifacts(**overrides: object) -> dict:
    base = {
        "workspace": {
            "environment_id": "python-basic",
            "files": [
                {"path": "solution.py", "content": "def is_expired(token):\n    ...\n", "visibility": "visible", "editable_regions": None}
            ],
        },
        "visible_tests": [
            {"path": "test_basic.py", "content": "from solution import is_expired\n\ndef test_expired_token_is_rejected():\n    assert is_expired({'exp': 0})\n"}
        ],
        "hidden_tests": [
            {"path": "test_solution.py", "content": "from solution import is_expired\n\ndef test_it():\n    assert is_expired({'exp': 0})\n"}
        ],
        "reference_solution_files": [
            {"path": "solution.py", "content": "def is_expired(token):\n    return token['exp'] < 1\n"}
        ],
    }
    base.update(overrides)
    return base


# -- LessonContentBundle -----------------------------------------------------------

def test_valid_content_bundle_passes_validation() -> None:
    content = LessonContentBundle.model_validate(_content())
    validate_lesson_content(content, ["chunk-a", "chunk-b"])


def test_content_rejects_citation_outside_context() -> None:
    content = LessonContentBundle.model_validate(_content())
    with pytest.raises(ValueError, match="cites a chunk outside"):
        validate_lesson_content(content, ["chunk-b"])


def test_quiz_citations_count_toward_content_citations() -> None:
    content = LessonContentBundle.model_validate(_content(quiz_items=[_quiz_item(citations=["chunk-q"])]))
    assert "chunk-q" in bundle_content_citations(content)
    with pytest.raises(ValueError, match="cites a chunk outside"):
        validate_lesson_content(content, ["chunk-a"])


def test_content_rejects_duplicate_quiz_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        LessonContentBundle.model_validate(_content(quiz_items=[_quiz_item(), _quiz_item()]))


def test_content_has_no_workspace_field_at_all() -> None:
    # The old unified schema needed a "set workspace to null" instruction for conceptual
    # lessons; the split schema makes that structurally impossible instead.
    assert "workspace" not in LessonContentBundle.model_fields


# -- CodingArtifactsBundle ----------------------------------------------------------

def test_valid_artifacts_bundle_passes_validation() -> None:
    CodingArtifactsBundle.model_validate(_artifacts())


def test_artifacts_rejects_reference_not_covering_visible_paths() -> None:
    with pytest.raises(ValueError, match="exactly the visible"):
        CodingArtifactsBundle.model_validate(
            _artifacts(reference_solution_files=[{"path": "other.py", "content": "x = 1\n"}])
        )


def test_artifacts_rejects_starter_identical_to_reference_solution() -> None:
    artifacts = _artifacts()
    artifacts["workspace"]["files"][0]["content"] = artifacts["reference_solution_files"][0]["content"]
    with pytest.raises(ValueError, match="identical to the reference solution"):
        CodingArtifactsBundle.model_validate(artifacts)


def test_artifacts_rejects_test_file_colliding_with_workspace_path() -> None:
    with pytest.raises(ValueError, match="must not collide"):
        CodingArtifactsBundle.model_validate(
            _artifacts(hidden_tests=[{"path": "solution.py", "content": "x = 1\n"}])
        )


def test_artifacts_rejects_visible_and_hidden_test_sharing_a_path() -> None:
    with pytest.raises(ValueError, match="must not share a path"):
        CodingArtifactsBundle.model_validate(
            _artifacts(visible_tests=[{"path": "test_solution.py", "content": "def test_a():\n    assert True\n"}])
        )


def test_artifacts_requires_hidden_tests() -> None:
    with pytest.raises(ValueError, match="at least one hidden test"):
        CodingArtifactsBundle.model_validate(_artifacts(hidden_tests=[]))


def test_artifacts_requires_a_discoverable_hidden_test_file() -> None:
    with pytest.raises(ValueError, match="hidden test file must be pytest-discoverable"):
        CodingArtifactsBundle.model_validate(_artifacts(hidden_tests=[{"path": "checks.py", "content": "assert True\n"}]))


def test_artifacts_rejects_non_discoverable_visible_test_file() -> None:
    with pytest.raises(ValueError, match="visible test file must be pytest-discoverable"):
        CodingArtifactsBundle.model_validate(_artifacts(visible_tests=[{"path": "checks.py", "content": "assert True\n"}]))


def test_artifacts_has_no_citations_field_at_all() -> None:
    # Citations only ever live on content; the artifacts model doesn't carry any.
    assert "citations" not in CodingArtifactsBundle.model_fields


# -- _compose_bundle ------------------------------------------------------------------

def test_compose_bundle_assembles_a_coding_lesson_matching_the_old_unified_shape() -> None:
    content = LessonContentBundle.model_validate(_content())
    artifacts = CodingArtifactsBundle.model_validate(_artifacts())

    bundle = _compose_bundle(content, artifacts)

    assert bundle.lesson_content == content.lesson_content
    assert bundle.workspace == artifacts.workspace
    assert bundle.assessment.visible_tests == artifacts.visible_tests
    assert bundle.assessment.hidden_tests == artifacts.hidden_tests
    assert bundle.assessment.reference_solution_files == artifacts.reference_solution_files
    assert bundle.assessment.quiz_items == content.quiz_items
    assert bundle.assessment.hints == content.hints


def test_compose_bundle_produces_a_workspace_less_conceptual_lesson() -> None:
    content = LessonContentBundle.model_validate(_content())

    bundle = _compose_bundle(content, artifacts=None)

    assert bundle.workspace is None
    assert bundle.assessment.visible_tests == []
    assert bundle.assessment.hidden_tests == []
    assert bundle.assessment.reference_solution_files == []
    assert bundle.assessment.quiz_items == content.quiz_items


def test_compose_bundle_result_still_enforces_lesson_bundle_consistency() -> None:
    # Composition doesn't bypass LessonBundle's own validator -- e.g. a caller passing
    # mismatched workspace/reference-solution paths would still be caught on construction.
    content = LessonContentBundle.model_validate(_content())
    bad_workspace = Workspace.model_validate(
        {"files": [{"path": "other.py", "content": "def f():\n    ...\n", "visibility": "visible", "editable_regions": None}]}
    )
    artifacts = CodingArtifactsBundle.model_validate(_artifacts())
    artifacts.workspace = bad_workspace  # plain assignment skips re-validation (no validate_assignment config)
    with pytest.raises(ValidationError, match="exactly the visible"):
        _compose_bundle(content, artifacts)
