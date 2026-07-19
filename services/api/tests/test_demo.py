import threading
import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.quiz import ShortAnswerGrade
from app.repository import get_repository
from app.routers import demo as demo_module
from app.routers.courses import get_lesson_sandbox, get_quiz_grader
from app.routers.demo import DemoLabAttempt, DemoLabFile, DemoShortAnswer
from app.sandbox import SandboxFile, SandboxRunResult
from app.schemas import (
    ConceptDetailResponse,
    CourseMapConcept,
    CourseMapModule,
    CourseMapResponse,
    LessonPreview,
    LessonWorkspaceFile,
    QuizItemPreview,
    QuizOptionPreview,
)

MCQ_RAW = {
    "id": "mcq-1", "kind": "mcq", "prompt_markdown": "2+2?",
    "options": [{"text": "3", "explanation_markdown": "no"}, {"text": "4", "explanation_markdown": "yes"}],
    "correct_option_index": 1, "correct_option_indices": [], "correct_answers": [],
    "rubric_markdown": None, "explanation_markdown": "4 is right", "citations": [],
}

SHORT_ANSWER_RAW = {
    "id": "sa-1", "kind": "short_answer", "prompt_markdown": "Explain X",
    "options": [], "correct_option_index": None, "correct_option_indices": [], "correct_answers": [],
    "rubric_markdown": "Must mention X clearly.", "explanation_markdown": "...", "citations": [],
}


class DemoRepository:
    def __init__(self) -> None:
        self.quiz_responses: list[tuple[str, bool]] = []
        self.lab_submissions: list[bool] = []

    def course_map(self, owner_id: object, course_id: object) -> CourseMapResponse:
        return CourseMapResponse(
            course_id=course_id,
            version=1,
            modules=[
                CourseMapModule(
                    title="Module 1", position=1,
                    concepts=[
                        CourseMapConcept(slug="quiz-concept", title="Quiz Concept", kind="assessment", summary_markdown="s"),
                        CourseMapConcept(slug="lab-concept", title="Lab Concept", kind="coding", summary_markdown="s"),
                    ],
                )
            ],
        )

    def _preview(self, item_id: str, kind: str, prompt_markdown: str, options: list[QuizOptionPreview]) -> QuizItemPreview:
        # Mirrors what the real repository would compute from persisted quiz_responses,
        # so _process_quiz_items' already-correct/attempts-exhausted skip logic is exercised for real.
        used = [correct for recorded_id, correct in self.quiz_responses if recorded_id == item_id]
        return QuizItemPreview(
            id=item_id, kind=kind, prompt_markdown=prompt_markdown, options=options,
            attempts_used=len(used), correct=True if any(used) else (False if used else None),
        )

    def concept_detail(self, owner_id: object, course_id: object, slug: str) -> ConceptDetailResponse:
        if slug == "quiz-concept":
            return ConceptDetailResponse(
                slug=slug, title="Quiz Concept", kind="assessment", summary_markdown="s", citations=[],
                generation_status="built",
                lesson=LessonPreview(
                    status="built", title="Quiz Concept", explanation_markdown="", starter_files=[], hints=[],
                    quiz_items=[
                        self._preview("mcq-1", "mcq", "2+2?", [QuizOptionPreview(text="3"), QuizOptionPreview(text="4")]),
                        self._preview("sa-1", "short_answer", "Explain X", []),
                    ],
                    quiz_max_attempts=3,
                ),
            )
        return ConceptDetailResponse(
            slug=slug, title="Lab Concept", kind="coding", summary_markdown="s", citations=[],
            generation_status="built",
            lesson=LessonPreview(
                status="built", title="Lab Concept", explanation_markdown="Implement add.",
                starter_files=[LessonWorkspaceFile(path="solution.py", content="def add(a, b):\n    return 0\n")],
                hints=["Use +"],
                public_test_files=[LessonWorkspaceFile(path="test_basic.py", content="from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")],
                quiz_items=[], quiz_max_attempts=3,
            ),
        )

    def quiz_item(self, owner_id: object, course_id: object, slug: str, item_id: str) -> dict:
        return MCQ_RAW if item_id == "mcq-1" else SHORT_ANSWER_RAW

    def quiz_progress(self, owner_id: object, course_id: object, slug: str, item_id: str) -> tuple[int, int, bool]:
        used = [correct for recorded_id, correct in self.quiz_responses if recorded_id == item_id]
        return 3, len(used), any(used)

    def record_quiz_response(self, owner_id: object, course_id: object, slug: str, item_id: str, answer: object, grade: object) -> int:
        self.quiz_responses.append((item_id, grade.correct))
        return len([recorded_id for recorded_id, _ in self.quiz_responses if recorded_id == item_id])

    def lesson_workspace(self, owner_id: object, course_id: object, slug: str) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile], str]:
        return (
            [LessonWorkspaceFile(path="solution.py", content="def add(a, b):\n    return 0\n")],
            [LessonWorkspaceFile(path="test_basic.py", content="from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")],
            [],
            "python-basic",
        )

    def record_coding_submission(self, owner_id: object, course_id: object, slug: str, passed: bool) -> None:
        self.lab_submissions.append(passed)

    def prerequisite_recommendation(self, owner_id: object, course_id: object, slug: str) -> None:
        return None


class DemoSandbox:
    def run_pytest(self, files: list[SandboxFile], *, environment_id: str = "python-basic") -> SandboxRunResult:
        content = next((file.content for file in files if file.path == "solution.py"), "")
        passed = "return a + b" in content
        return SandboxRunResult(exit_code=0 if passed else 1, output="1 passed" if passed else "1 failed", timed_out=False)


class DemoGrader:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def structured(self, *, task: str, input: list[dict], output_model: type):
        self.calls.append({"task": task, "input": input})
        if output_model is ShortAnswerGrade:
            # The real short-answer grading call answer_quiz_item makes on whatever text
            # our own demo_autocomplete call generated below -- a second, independent
            # LLM round trip, exactly as it would be for a real learner's answer.
            assert task == "quiz_grading"
            correct = "X is defined as" in input[1]["content"]
            return ShortAnswerGrade(correct=correct, feedback_markdown="Feedback." if correct else "Missing the point.")
        assert task == "demo_autocomplete"
        system_content = input[0]["content"]
        if output_model is DemoShortAnswer:
            correct = "Write a correct answer" in system_content
            return DemoShortAnswer(answer_text="X is defined as..." if correct else "I'm not sure, maybe Y?")
        if output_model is DemoLabAttempt:
            correct = "your best, complete, correct" in system_content
            content = "def add(a, b):\n    return a + b\n" if correct else "def add(a, b):\n    return 0\n"
            return DemoLabAttempt(files=[DemoLabFile(path="solution.py", content=content)])
        raise AssertionError(f"unexpected output_model {output_model}")


class GatedGrader(DemoGrader):
    """Blocks the first structured() call on an Event, so a test can deterministically
    catch the job mid-run (to check live status or cancel) instead of racing a
    near-instantaneous fake. Every call after the gate opens proceeds normally."""

    def __init__(self, gate: threading.Event) -> None:
        super().__init__()
        self.gate = gate
        self.reached_gate = threading.Event()

    def structured(self, *, task: str, input: list[dict], output_model: type):
        self.reached_gate.set()
        assert self.gate.wait(timeout=5), "test never opened the gate"
        return super().structured(task=task, input=input, output_model=output_model)


def _wait_for_completion(client: TestClient, course_id: object, job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/courses/{course_id}/demo/auto-complete/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["state"] != "running":
            return body
        time.sleep(0.01)
    raise AssertionError("Demo job did not finish within the test timeout")


def test_auto_complete_is_not_found_outside_development(monkeypatch) -> None:
    monkeypatch.setattr(demo_module, "get_settings", lambda: SimpleNamespace(environment="production"))
    repository = DemoRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    try:
        response = TestClient(app).post(f"/api/v1/courses/{uuid4()}/demo/auto-complete", json={"target": "mastered"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_auto_complete_mastered_answers_correctly_and_submits_a_passing_lab() -> None:
    repository = DemoRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(f"/api/v1/courses/{course_id}/demo/auto-complete", json={"target": "mastered"})
        assert start.status_code == 202
        # Not asserting state == "running" here: the fakes are fast enough that the
        # background thread can legitimately finish before this response is even read.
        status_body = _wait_for_completion(client, course_id, start.json()["job_id"])
    finally:
        app.dependency_overrides.clear()

    assert status_body["state"] == "completed"
    assert status_body["completed"] == status_body["total"] == 2
    results = {result["concept_slug"]: result for result in status_body["results"]}
    assert results["quiz-concept"]["quiz_items_correct"] == 2
    assert results["quiz-concept"]["quiz_items_incorrect"] == 0
    assert results["lab-concept"]["lab_passed"] is True
    assert repository.lab_submissions == [True]
    assert all(correct for _item_id, correct in repository.quiz_responses)


def test_auto_complete_mixed_with_zero_correct_rate_still_reaches_completion() -> None:
    # A "mixed" run's whole point is to leave real wrong-answer observations on the
    # mastery record without stranding the course below 100% -- a lesson only completes
    # once every quiz item has been answered correctly at least once and a lab has
    # actually passed, so an uncorrected wrong answer would make the certificate
    # unreachable from this mode. Every deliberately-wrong first attempt should still
    # get a corrective follow-up when attempts allow.
    repository = DemoRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(f"/api/v1/courses/{course_id}/demo/auto-complete", json={"target": "mixed", "correct_rate": 0.0})
        assert start.status_code == 202
        status_body = _wait_for_completion(client, course_id, start.json()["job_id"])
    finally:
        app.dependency_overrides.clear()

    assert status_body["state"] == "completed"
    results = {result["concept_slug"]: result for result in status_body["results"]}
    # The displayed stats reflect the simulated first attempt (the whole point of "mixed").
    assert results["quiz-concept"]["quiz_items_correct"] == 0
    assert results["quiz-concept"]["quiz_items_incorrect"] == 2
    # But every item ends up answered correctly too, and the lab ends up passing --
    # otherwise this course could never earn a certificate.
    assert results["lab-concept"]["lab_passed"] is True
    assert repository.lab_submissions == [False, True]
    wrong_then_right = [correct for _item_id, correct in repository.quiz_responses]
    assert wrong_then_right.count(False) == 2
    assert wrong_then_right.count(True) == 2


def test_auto_complete_skips_already_correct_and_attempt_exhausted_items() -> None:
    repository = DemoRepository()
    # Pre-seed: mcq-1 already correct, sa-1 already used all 3 attempts (still wrong).
    repository.quiz_responses = [("mcq-1", True), ("sa-1", False), ("sa-1", False), ("sa-1", False)]
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(f"/api/v1/courses/{course_id}/demo/auto-complete", json={"target": "mastered"})
        assert start.status_code == 202
        status_body = _wait_for_completion(client, course_id, start.json()["job_id"])
    finally:
        app.dependency_overrides.clear()

    results = {result["concept_slug"]: result for result in status_body["results"]}
    # Both items are already resolved (correct, or attempts exhausted) -- neither gets a new attempt.
    assert results["quiz-concept"]["quiz_items_correct"] == 0
    assert results["quiz-concept"]["quiz_items_incorrect"] == 0
    assert results["quiz-concept"]["quiz_items_skipped"] == 2
    assert repository.quiz_responses == [("mcq-1", True), ("sa-1", False), ("sa-1", False), ("sa-1", False)]


def test_auto_complete_respects_concept_slugs_scope() -> None:
    repository = DemoRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(
            f"/api/v1/courses/{course_id}/demo/auto-complete",
            json={"target": "mastered", "concept_slugs": ["lab-concept"]},
        )
        assert start.status_code == 202
        assert start.json()["total"] == 1
        status_body = _wait_for_completion(client, course_id, start.json()["job_id"])
    finally:
        app.dependency_overrides.clear()

    slugs = [result["concept_slug"] for result in status_body["results"]]
    assert slugs == ["lab-concept"]
    assert repository.lab_submissions == [True]
    assert repository.quiz_responses == []


def test_auto_complete_can_exclude_quizzes_or_labs() -> None:
    repository = DemoRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(
            f"/api/v1/courses/{course_id}/demo/auto-complete",
            json={"target": "mastered", "include_quizzes": False, "include_labs": False},
        )
        assert start.status_code == 202
        status_body = _wait_for_completion(client, course_id, start.json()["job_id"])
    finally:
        app.dependency_overrides.clear()

    results = {result["concept_slug"]: result for result in status_body["results"]}
    # Both concepts are still visited (in scope), but neither quizzes nor labs run.
    assert results["quiz-concept"]["quiz_items_correct"] == 0
    assert results["quiz-concept"]["quiz_items_incorrect"] == 0
    assert results["quiz-concept"]["quiz_items_skipped"] == 0
    assert results["lab-concept"]["lab_passed"] is None
    assert repository.lab_submissions == []
    assert repository.quiz_responses == []


def test_auto_complete_status_shows_live_progress_while_running() -> None:
    repository = DemoRepository()
    gate = threading.Event()
    grader = GatedGrader(gate)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: grader
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(f"/api/v1/courses/{course_id}/demo/auto-complete", json={"target": "mastered"})
        assert start.status_code == 202
        job_id = start.json()["job_id"]

        # The first concept's short-answer item is blocked mid-flight -- the job must be
        # visibly "running" on the concept it's actually working on, not a black box.
        assert grader.reached_gate.wait(timeout=5)
        mid_run = client.get(f"/api/v1/courses/{course_id}/demo/auto-complete/{job_id}").json()
        assert mid_run["state"] == "running"
        assert mid_run["current_concept_title"] == "Quiz Concept"
        assert mid_run["completed"] == 0

        gate.set()
        status_body = _wait_for_completion(client, course_id, job_id)
    finally:
        app.dependency_overrides.clear()

    assert status_body["state"] == "completed"
    assert status_body["current_concept_title"] is None


def test_auto_complete_cancel_stops_before_the_next_concept() -> None:
    repository = DemoRepository()
    gate = threading.Event()
    grader = GatedGrader(gate)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: grader
    client = TestClient(app)
    course_id = uuid4()
    try:
        start = client.post(f"/api/v1/courses/{course_id}/demo/auto-complete", json={"target": "mastered"})
        assert start.status_code == 202
        job_id = start.json()["job_id"]

        # Catch it mid-way through the first (quiz) concept, cancel, then let that one
        # concept finish -- cancellation is only honored before the *next* concept starts.
        assert grader.reached_gate.wait(timeout=5)
        cancel = client.post(f"/api/v1/courses/{course_id}/demo/auto-complete/{job_id}/cancel")
        assert cancel.status_code == 204
        gate.set()

        status_body = _wait_for_completion(client, course_id, job_id)
    finally:
        app.dependency_overrides.clear()

    assert status_body["state"] == "cancelled"
    assert status_body["total"] == 2
    assert [result["concept_slug"] for result in status_body["results"]] == ["quiz-concept"]
    assert repository.lab_submissions == []


def test_auto_complete_status_404s_for_an_unknown_job() -> None:
    repository = DemoRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: DemoSandbox()
    app.dependency_overrides[get_quiz_grader] = lambda: DemoGrader()
    try:
        response = TestClient(app).get(f"/api/v1/courses/{uuid4()}/demo/auto-complete/does-not-exist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
