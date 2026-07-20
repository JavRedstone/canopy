"""Coverage for the practice endpoints. The contract that matters here is how sharply this
path differs from the graded quiz one: nothing withheld, no attempt cap, no quiz_responses
row, and positive-only mastery credit."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.repository import get_repository
from app.routers.courses import get_quiz_grader
from app.schemas import PracticeQuestion, PracticeSessionResponse


COURSE_ID = uuid4()
ITEM_ID = uuid4()

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

CONCEPT = {"id": "concept-id", "slug": "token-expiry", "title": "Token expiry", "kind": "conceptual"}


class FakeGrader:
    """Never reached for choice items, which grade deterministically."""


class PracticeRepository:
    name = "practice"

    def __init__(self, p_understand: float | None = 0.62) -> None:
        self.p_understand = p_understand
        self.sessions: list[tuple] = []
        self.answers: list[tuple[UUID, bool]] = []
        self.top_ups: list[list[str]] = []

    def practice_session(self, owner_id, course_id, scope, ids, count, order, filter, seed):
        self.sessions.append((scope, tuple(ids), count, order, filter, seed))
        return PracticeSessionResponse(
            course_id=course_id,
            questions=[
                PracticeQuestion(
                    id=ITEM_ID,
                    concept_slug="token-expiry",
                    concept_title="Token expiry",
                    kind="mcq",
                    prompt_markdown="What happens to an expired token?",
                    options=[{"text": "It is rejected."}, {"text": "It is accepted."}],
                )
            ],
            concepts_low_on_questions=["token-expiry"],
        )

    def practice_item(self, owner_id, course_id, item_id):
        return MCQ_ITEM, CONCEPT

    def record_practice_answer(self, owner_id, course_id, item_id, concept, correct):
        self.answers.append((item_id, correct))
        return self.p_understand if correct else None

    def request_practice_top_up(self, owner_id, course_id, concept_slugs):
        self.top_ups.append(list(concept_slugs))
        return list(concept_slugs)


def _client(repository: PracticeRepository) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_quiz_grader] = lambda: FakeGrader()
    return TestClient(app)


def test_session_returns_answer_stripped_questions() -> None:
    repository = PracticeRepository()
    try:
        response = _client(repository).get(f"/api/v1/courses/{COURSE_ID}/practice")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    question = response.json()["questions"][0]
    assert question["prompt_markdown"] == "What happens to an expired token?"
    # The learner sees option text and nothing that reveals which one is right.
    assert question["options"] == [{"text": "It is rejected."}, {"text": "It is accepted."}]
    assert "correct_option_index" not in question
    assert "explanation_markdown" not in question


def test_session_defaults_to_everything_started_unseen_and_shuffled() -> None:
    repository = PracticeRepository()
    try:
        _client(repository).get(f"/api/v1/courses/{COURSE_ID}/practice")
    finally:
        app.dependency_overrides.clear()

    scope, ids, count, order, filter, _seed = repository.sessions[0]
    assert (scope, ids, count, order, filter) == ("done", (), 10, "shuffle", "unseen")


def test_session_passes_through_the_learners_chosen_options() -> None:
    repository = PracticeRepository()
    try:
        _client(repository).get(
            f"/api/v1/courses/{COURSE_ID}/practice",
            params={"scope": "concepts", "ids": "token-expiry, clock-skew", "count": 5, "order": "weakest", "filter": "missed"},
        )
    finally:
        app.dependency_overrides.clear()

    scope, ids, count, order, filter, _seed = repository.sessions[0]
    assert (scope, count, order, filter) == ("concepts", 5, "weakest", "missed")
    # Whitespace around a comma-separated id must not become part of the slug.
    assert ids == ("token-expiry", "clock-skew")


def test_sessions_vary_between_requests_but_a_pinned_seed_reproduces_one() -> None:
    repository = PracticeRepository()
    try:
        client = _client(repository)
        client.get(f"/api/v1/courses/{COURSE_ID}/practice")
        client.get(f"/api/v1/courses/{COURSE_ID}/practice")
        client.get(f"/api/v1/courses/{COURSE_ID}/practice", params={"seed": 7})
    finally:
        app.dependency_overrides.clear()

    seeds = [session[-1] for session in repository.sessions]
    assert seeds[0] != seeds[1]
    assert seeds[2] == 7


def test_session_rejects_a_count_beyond_the_allowed_range() -> None:
    repository = PracticeRepository()
    try:
        response = _client(repository).get(f"/api/v1/courses/{COURSE_ID}/practice", params={"count": 500})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_a_correct_answer_reveals_everything_immediately() -> None:
    repository = PracticeRepository()
    try:
        response = _client(repository).post(
            f"/api/v1/courses/{COURSE_ID}/practice/{ITEM_ID}/answer",
            json={"selected_option_index": 0},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True
    assert body["item_id"] == str(ITEM_ID)
    assert body["concept_slug"] == "token-expiry"
    assert body["explanation_markdown"] == "Expired tokens must never validate."
    assert [option["correct"] for option in body["options"]] == [True, False]


def test_a_wrong_answer_still_reveals_everything_and_costs_no_mastery() -> None:
    # The whole point of low-stakes practice: nothing is withheld to preserve a later
    # attempt, because there is no attempt cap to preserve it for.
    repository = PracticeRepository()
    try:
        response = _client(repository).post(
            f"/api/v1/courses/{COURSE_ID}/practice/{ITEM_ID}/answer",
            json={"selected_option_index": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is False
    assert body["explanation_markdown"] == "Expired tokens must never validate."
    assert [option["correct"] for option in body["options"]] == [True, False]
    # No mastery movement is reported, so the meter cannot fall on a miss.
    assert body["p_understand"] is None


def test_a_correct_answer_reports_the_refreshed_estimate_for_the_meter() -> None:
    repository = PracticeRepository(p_understand=0.71)
    try:
        response = _client(repository).post(
            f"/api/v1/courses/{COURSE_ID}/practice/{ITEM_ID}/answer",
            json={"selected_option_index": 0},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.json()["p_understand"] == 0.71


def test_every_answer_is_logged_right_or_wrong() -> None:
    repository = PracticeRepository()
    try:
        client = _client(repository)
        client.post(f"/api/v1/courses/{COURSE_ID}/practice/{ITEM_ID}/answer", json={"selected_option_index": 0})
        client.post(f"/api/v1/courses/{COURSE_ID}/practice/{ITEM_ID}/answer", json={"selected_option_index": 1})
    finally:
        app.dependency_overrides.clear()

    assert repository.answers == [(ITEM_ID, True), (ITEM_ID, False)]


def test_answering_the_same_question_repeatedly_is_never_capped() -> None:
    # The graded path 403s once attempts run out; practice has no such ceiling.
    repository = PracticeRepository()
    try:
        client = _client(repository)
        codes = [
            client.post(
                f"/api/v1/courses/{COURSE_ID}/practice/{ITEM_ID}/answer",
                json={"selected_option_index": 1},
            ).status_code
            for _ in range(6)
        ]
    finally:
        app.dependency_overrides.clear()

    assert codes == [200] * 6


def test_top_up_queues_the_named_concepts() -> None:
    repository = PracticeRepository()
    try:
        response = _client(repository).post(
            f"/api/v1/courses/{COURSE_ID}/practice/top-up",
            json={"concept_slugs": ["token-expiry"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["concepts_queued"] == ["token-expiry"]
    assert repository.top_ups == [["token-expiry"]]


def test_session_tells_the_client_which_concepts_are_running_low() -> None:
    repository = PracticeRepository()
    try:
        response = _client(repository).get(f"/api/v1/courses/{COURSE_ID}/practice")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["concepts_low_on_questions"] == ["token-expiry"]
