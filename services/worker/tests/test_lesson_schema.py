import pytest
from pydantic import ValidationError

from worker.lesson_schema import LessonBundle, validate_lesson_bundle


def _bundle(**overrides: object) -> dict:
    base = {
        "title": "Reject expired tokens",
        "explanation_markdown": "Tokens carry an expiry claim that must be checked.",
        "citations": ["chunk-a"],
        "starter_files": [{"path": "solution.py", "content": "def is_expired(token):\n    ...\n"}],
        "public_test_files": [
            {"path": "test_basic.py", "content": "from solution import is_expired\n\ndef test_expired_token_is_rejected():\n    assert is_expired({'exp': 0})\n"}
        ],
        "test_files": [
            {"path": "test_solution.py", "content": "from solution import is_expired\n\ndef test_it():\n    assert is_expired({'exp': 0})\n"}
        ],
        "reference_solution_files": [
            {"path": "solution.py", "content": "def is_expired(token):\n    return token['exp'] < 1\n"}
        ],
        "hints": ["Compare the exp claim against the current time."],
    }
    base.update(overrides)
    return base


def test_valid_bundle_passes_validation() -> None:
    bundle = LessonBundle.model_validate(_bundle())
    validate_lesson_bundle(bundle, ["chunk-a", "chunk-b"])


def test_bundle_rejects_citation_outside_context() -> None:
    bundle = LessonBundle.model_validate(_bundle())
    with pytest.raises(ValueError, match="cites a chunk outside"):
        validate_lesson_bundle(bundle, ["chunk-b"])


def test_bundle_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError):
        LessonBundle.model_validate(
            _bundle(starter_files=[{"path": "../etc/passwd.py", "content": "x = 1\n"}])
        )


def test_bundle_rejects_mismatched_reference_and_starter_paths() -> None:
    with pytest.raises(ValueError, match="exactly the starter file paths"):
        LessonBundle.model_validate(
            _bundle(reference_solution_files=[{"path": "other.py", "content": "x = 1\n"}])
        )


def test_bundle_rejects_test_file_colliding_with_starter_path() -> None:
    with pytest.raises(ValueError, match="must not collide"):
        LessonBundle.model_validate(
            _bundle(test_files=[{"path": "solution.py", "content": "x = 1\n"}])
        )


def test_bundle_requires_a_discoverable_test_file() -> None:
    with pytest.raises(ValueError, match="hidden test file must be pytest-discoverable"):
        LessonBundle.model_validate(
            _bundle(test_files=[{"path": "checks.py", "content": "assert True\n"}])
        )


def test_bundle_rejects_non_discoverable_public_test_file() -> None:
    with pytest.raises(ValueError, match="public test file must be pytest-discoverable"):
        LessonBundle.model_validate(
            _bundle(public_test_files=[{"path": "checks.py", "content": "assert True\n"}])
        )


def test_bundle_rejects_public_test_file_colliding_with_starter_path() -> None:
    with pytest.raises(ValueError, match="Public test files must not collide"):
        LessonBundle.model_validate(
            _bundle(public_test_files=[{"path": "solution.py", "content": "x = 1\n"}])
        )


def test_bundle_rejects_public_and_hidden_test_file_sharing_a_path() -> None:
    with pytest.raises(ValueError, match="Public and hidden test files must not share a path"):
        LessonBundle.model_validate(
            _bundle(public_test_files=[{"path": "test_solution.py", "content": "def test_a():\n    assert True\n"}])
        )
