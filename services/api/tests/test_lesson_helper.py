from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.repository import get_repository
from app.routers.courses import LessonHelperAnswer, get_quiz_grader
from app.schemas import ConceptDetailResponse, LessonPreview, LessonWorkspaceFile, QuizItemPreview, QuizOptionPreview


class FakeHelperGrader:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def structured(self, *, task: str, input: list[dict], output_model: type) -> LessonHelperAnswer:
        self.calls.append({"task": task, "input": input, "output_model": output_model})
        return LessonHelperAnswer(answer_markdown="Try re-reading the constraint on token expiry.", replacement_markdown=None)


class HelperRepository:
    def __init__(self, detail: ConceptDetailResponse) -> None:
        self.detail = detail

    def concept_detail(self, owner_id: object, course_id: object, slug: str) -> ConceptDetailResponse:
        return self.detail


CODING_DETAIL = ConceptDetailResponse(
    slug="core-pattern",
    title="Core pattern",
    kind="coding",
    summary_markdown="Summary",
    citations=[],
    generation_status="built",
    lesson=LessonPreview(
        status="built",
        title="Core pattern",
        explanation_markdown="Implement the function.",
        starter_files=[LessonWorkspaceFile(path="solution.py", content="def solve(): ...")],
        hints=["Think about edge cases."],
        public_test_files=[],
        solution_files=[LessonWorkspaceFile(path="solution.py", content="def solve(): return 42  # the real answer")],
        worked_examples=[],
        quiz_items=[],
        quiz_max_attempts=3,
    ),
)

ASSESSMENT_DETAIL = ConceptDetailResponse(
    slug="token-quiz",
    title="Token quiz",
    kind="assessment",
    summary_markdown="Summary",
    citations=[],
    generation_status="built",
    lesson=LessonPreview(
        status="built",
        title="Token quiz",
        explanation_markdown="",
        starter_files=[],
        hints=[],
        public_test_files=[],
        solution_files=[],
        worked_examples=[],
        quiz_items=[
            QuizItemPreview(
                id="expiry-check",
                kind="mcq",
                prompt_markdown="What happens to an expired token?",
                options=[QuizOptionPreview(text="It is rejected."), QuizOptionPreview(text="It is accepted.")],
                attempts_used=0,
                correct=None,
                previous_answer=None,
                previous_grade=None,
            )
        ],
        quiz_max_attempts=3,
    ),
)


def test_helper_includes_only_the_learners_own_starter_files_for_a_lab() -> None:
    grader = FakeHelperGrader()
    repository = HelperRepository(CODING_DETAIL)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: grader
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/core-pattern/helper",
            json={
                "question": "Why is my function failing?",
                "workspace_files": [
                    {"path": "solution.py", "content": "def solve(): return None"},
                    {"path": "not_a_starter_file.py", "content": "SECRET = 1"},
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sent_context = grader.calls[0]["input"][1]["content"]
    assert "def solve(): return None" in sent_context
    assert "not_a_starter_file.py" not in sent_context
    assert "SECRET" not in sent_context
    # The reference solution must never reach the model, regardless of what the learner sends.
    assert "the real answer" not in sent_context


def test_helper_includes_the_focused_quiz_question_but_never_grading_fields() -> None:
    grader = FakeHelperGrader()
    repository = HelperRepository(ASSESSMENT_DETAIL)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: grader
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-quiz/helper",
            json={"question": "I'm stuck, can you help?", "quiz_item_id": "expiry-check"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    sent_context = grader.calls[0]["input"][1]["content"]
    assert "What happens to an expired token?" in sent_context
    assert "It is rejected." in sent_context
    system_prompt = grader.calls[0]["input"][0]["content"]
    assert "correct answer" in system_prompt.lower()


def test_helper_ignores_an_unknown_quiz_item_id() -> None:
    grader = FakeHelperGrader()
    repository = HelperRepository(ASSESSMENT_DETAIL)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: grader
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/token-quiz/helper",
            json={"question": "Help?", "quiz_item_id": "does-not-exist"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
