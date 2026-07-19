from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.llm import LLMGatewayError
from app.main import app
from app.quiz import ShortAnswerGrade, grade_quiz_answer, withhold_answer
from app.repository import get_repository
from app.routers.courses import get_quiz_grader
from app.schemas import QuizAnswerRequest


MCQ_ITEM = {
    "id": "expiry-check",
    "kind": "mcq",
    "prompt_markdown": "What happens to an expired token?",
    "options": [
        {"text": "It is rejected.", "explanation_markdown": "Correct: expiry is a hard boundary."},
        {"text": "It is accepted.", "explanation_markdown": "Wrong: that would defeat expiry."},
    ],
    "correct_option_index": 0,
    "correct_option_indices": [],
    "correct_answers": [],
    "rubric_markdown": None,
    "explanation_markdown": "Expired tokens must never validate.",
    "citations": [],
}

MULTI_SELECT_ITEM = {
    **MCQ_ITEM,
    "id": "claims-check",
    "kind": "multi_select",
    "options": [
        {"text": "exp", "explanation_markdown": "Correct."},
        {"text": "iat", "explanation_markdown": "Correct."},
        {"text": "color", "explanation_markdown": "Not a JWT claim."},
    ],
    "correct_option_index": None,
    "correct_option_indices": [0, 1],
}

FILL_ITEM = {
    **MCQ_ITEM,
    "id": "fill-check",
    "kind": "fill",
    "options": [],
    "correct_option_index": None,
    "correct_answers": ["rejected", "denied"],
}

SHORT_ANSWER_ITEM = {
    **MCQ_ITEM,
    "id": "short-check",
    "kind": "short_answer",
    "options": [],
    "correct_option_index": None,
    "rubric_markdown": "Must mention that expiry bounds the damage of a leaked token.",
}


class FakeGrader:
    def __init__(self, grade: ShortAnswerGrade | None = None, error: Exception | None = None) -> None:
        self.grade = grade
        self.error = error
        self.calls: list[dict] = []

    def structured(self, *, task: str, input: list[dict], output_model: type) -> ShortAnswerGrade:
        self.calls.append({"task": task, "input": input, "output_model": output_model})
        if self.error:
            raise self.error
        assert self.grade is not None
        return self.grade


def test_mcq_correct_choice_reveals_option_explanations() -> None:
    result = grade_quiz_answer(MCQ_ITEM, QuizAnswerRequest(selected_option_index=0), FakeGrader())

    assert result.correct is True
    assert [option.correct for option in result.options] == [True, False]
    assert result.options[1].explanation_markdown == "Wrong: that would defeat expiry."


def test_mcq_wrong_choice_is_incorrect() -> None:
    result = grade_quiz_answer(MCQ_ITEM, QuizAnswerRequest(selected_option_index=1), FakeGrader())
    assert result.correct is False


def test_mcq_missing_selection_is_rejected() -> None:
    with pytest.raises(HTTPException) as caught:
        grade_quiz_answer(MCQ_ITEM, QuizAnswerRequest(), FakeGrader())
    assert caught.value.status_code == 422


def test_multi_select_requires_exact_set() -> None:
    exact = grade_quiz_answer(MULTI_SELECT_ITEM, QuizAnswerRequest(selected_option_indices=[1, 0]), FakeGrader())
    partial = grade_quiz_answer(MULTI_SELECT_ITEM, QuizAnswerRequest(selected_option_indices=[0]), FakeGrader())
    over = grade_quiz_answer(MULTI_SELECT_ITEM, QuizAnswerRequest(selected_option_indices=[0, 1, 2]), FakeGrader())

    assert exact.correct is True
    assert partial.correct is False
    assert over.correct is False


def test_fill_matches_case_and_whitespace_insensitively() -> None:
    result = grade_quiz_answer(FILL_ITEM, QuizAnswerRequest(answer_text="  ReJected "), FakeGrader())
    wrong = grade_quiz_answer(FILL_ITEM, QuizAnswerRequest(answer_text="accepted"), FakeGrader())

    assert result.correct is True
    assert wrong.correct is False
    assert wrong.correct_answers == ["rejected", "denied"]


def test_short_answer_uses_llm_judge_and_returns_feedback() -> None:
    grader = FakeGrader(grade=ShortAnswerGrade(correct=True, feedback_markdown="You nailed the damage-bounding point."))

    result = grade_quiz_answer(SHORT_ANSWER_ITEM, QuizAnswerRequest(answer_text="Expiry limits how long a stolen token works."), grader)

    assert result.correct is True
    assert result.feedback_markdown == "You nailed the damage-bounding point."
    assert grader.calls[0]["task"] == "quiz_grading"
    judge_input = grader.calls[0]["input"][1]["content"]
    assert "Rubric" in judge_input and "stolen token" in judge_input


def test_withhold_answer_strips_the_reveal_but_keeps_the_verdict() -> None:
    graded = grade_quiz_answer(SHORT_ANSWER_ITEM, QuizAnswerRequest(answer_text="close but incomplete"),
                               FakeGrader(grade=ShortAnswerGrade(correct=False, feedback_markdown="You're missing the damage-bounding point.")))
    graded.options = grade_quiz_answer(MCQ_ITEM, QuizAnswerRequest(selected_option_index=1), FakeGrader()).options
    graded.correct_answers = ["rejected"]

    withheld = withhold_answer(graded)

    assert withheld.correct is False
    assert withheld.feedback_markdown == "You're missing the damage-bounding point."
    assert withheld.explanation_markdown == ""
    assert withheld.options == []
    assert withheld.correct_answers == []


def test_short_answer_gateway_failure_returns_503() -> None:
    grader = FakeGrader(error=LLMGatewayError("down"))
    with pytest.raises(HTTPException) as caught:
        grade_quiz_answer(SHORT_ANSWER_ITEM, QuizAnswerRequest(answer_text="Expiry limits damage."), grader)
    assert caught.value.status_code == 503


class QuizRepository:
    """Tracks recorded attempts in memory so tests can assert on the enforcement flow
    without a real database -- max_attempts is fixed per instance for the test at hand."""

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self.responses: list[tuple[str, bool]] = []

    def quiz_item(self, owner_id: object, course_id: object, slug: str, item_id: str) -> dict:
        assert item_id == "expiry-check"
        return MCQ_ITEM

    def quiz_progress(self, owner_id: object, course_id: object, slug: str, item_id: str) -> tuple[int, int, bool]:
        used = [result for recorded_id, result in self.responses if recorded_id == item_id]
        return self.max_attempts, len(used), any(used)

    def record_quiz_response(self, owner_id: object, course_id: object, slug: str, item_id: str, answer: object, grade: object) -> int:
        self.responses.append((item_id, grade.correct))
        return len([recorded_id for recorded_id, _ in self.responses if recorded_id == item_id])

    def prerequisite_recommendation(self, owner_id: object, course_id: object, slug: str) -> None:
        # These tests exercise attempt enforcement, not the struggle heuristic -> never recommends.
        return None


def test_answer_endpoint_grades_and_reveals_feedback() -> None:
    repository = QuizRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: FakeGrader()
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-expiry/quiz-items/expiry-check/answer",
            json={"selected_option_index": 0},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True
    assert body["item_id"] == "expiry-check"
    assert len(body["options"]) == 2
    assert body["attempts_used"] == 1
    assert body["attempts_remaining"] == 2
    assert repository.responses == [("expiry-check", True)]


def test_answer_endpoint_reports_attempts_remaining_after_a_wrong_answer() -> None:
    repository = QuizRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: FakeGrader()
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-expiry/quiz-items/expiry-check/answer",
            json={"selected_option_index": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is False
    assert body["attempts_used"] == 1
    assert body["attempts_remaining"] == 2
    # Attempts remain, so the answer is held back -- verdict only, no reveal to read off the wire.
    assert body["explanation_markdown"] == ""
    assert body["options"] == []
    assert body["correct_answers"] == []


def test_answer_endpoint_reveals_the_answer_on_the_final_wrong_attempt() -> None:
    repository = QuizRepository(max_attempts=2)
    repository.responses = [("expiry-check", False)]
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: FakeGrader()
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-expiry/quiz-items/expiry-check/answer",
            json={"selected_option_index": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is False
    assert body["attempts_remaining"] == 0
    # No attempts left: the full reveal comes back so the learner still learns the answer.
    assert body["explanation_markdown"] == "Expired tokens must never validate."
    assert [option["correct"] for option in body["options"]] == [True, False]


def test_answer_endpoint_rejects_once_attempts_are_exhausted() -> None:
    repository = QuizRepository(max_attempts=2)
    repository.responses = [("expiry-check", False), ("expiry-check", False)]
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: FakeGrader()
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-expiry/quiz-items/expiry-check/answer",
            json={"selected_option_index": 0},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    # The rejected attempt must not be recorded as a third attempt.
    assert repository.responses == [("expiry-check", False), ("expiry-check", False)]


def test_answer_endpoint_allows_a_correct_reanswer_even_when_attempts_are_spent() -> None:
    repository = QuizRepository(max_attempts=1)
    repository.responses = [("expiry-check", True)]
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: FakeGrader()
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-expiry/quiz-items/expiry-check/answer",
            json={"selected_option_index": 0},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
