"""Endpoint coverage for the course-level prerequisite-review recommendations surface -- listing
open recommendations and recording the learner's accept/defer/decline verdict -- against a fake
repository, so the routing and request validation are checked without a live database."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.repository import get_repository
from app.schemas import PrerequisiteConcept, RecommendationSummary, RecommendationsResponse


class RecommendationRepository:
    def __init__(self) -> None:
        self.decided: tuple[object, object, object, str] | None = None
        self.event_id = uuid4()

    def list_recommendations(self, owner_id: object, course_id: object) -> RecommendationsResponse:
        return RecommendationsResponse(
            course_id=course_id,
            recommendations=[
                RecommendationSummary(
                    id=self.event_id,
                    concept_slug="closures",
                    concept_title="Closures",
                    prerequisites=[
                        PrerequisiteConcept(
                            slug="scope", title="Variable scope", kind="conceptual",
                            p_understand=0.4, p_apply=None, mastered=False, needs_review=True,
                        )
                    ],
                    created_at="2026-07-18T00:00:00Z",
                )
            ],
        )

    def decide_recommendation(self, owner_id: object, course_id: object, event_id: object, decision: str) -> None:
        self.decided = (owner_id, course_id, event_id, decision)


def test_recommendations_endpoint_lists_open_recommendations() -> None:
    repository = RecommendationRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    try:
        response = TestClient(app).get(f"/api/v1/courses/{uuid4()}/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert len(recommendations) == 1
    assert recommendations[0]["concept_slug"] == "closures"
    assert recommendations[0]["prerequisites"][0]["needs_review"] is True


def test_decision_endpoint_records_the_verdict() -> None:
    repository = RecommendationRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    course_id = uuid4()
    event_id = uuid4()
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{course_id}/recommendations/{event_id}/decision",
            json={"decision": "accepted"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert repository.decided is not None
    assert repository.decided[1:] == (course_id, event_id, "accepted")


def test_decision_endpoint_rejects_an_unknown_verdict() -> None:
    repository = RecommendationRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/recommendations/{uuid4()}/decision",
            json={"decision": "maybe"},
        )
    finally:
        app.dependency_overrides.clear()

    # 'maybe' isn't one of accepted/deferred/declined -> schema validation rejects it.
    assert response.status_code == 422
    assert repository.decided is None
