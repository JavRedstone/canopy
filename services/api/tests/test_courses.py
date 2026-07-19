from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.repository import get_repository
from app.schemas import CertificateResponse


def test_course_vertical_slice() -> None:
    client = TestClient(app)
    source = client.post(
        "/api/v1/sources",
        json={"filename": "auth.md", "mime_type": "text/markdown", "byte_size": 123},
    )
    assert source.status_code == 201
    assert source.json()["upload_token"] == "development-upload-token"
    source_id = source.json()["id"]

    complete = client.post(f"/api/v1/sources/{source_id}/complete")
    assert complete.status_code == 200

    course = client.post(
        "/api/v1/courses",
        json={"title": "API auth", "goal": "Learn JWT validation", "source_ids": [source_id]},
    )
    assert course.status_code == 201

    courses = client.get("/api/v1/courses")
    assert courses.status_code == 200
    assert courses.json()[0]["title"] == "API auth"

    course_id = course.json()["id"]
    course_map = client.get(f"/api/v1/courses/{course_id}/map")
    assert course_map.status_code == 200
    assert len(course_map.json()["modules"]) == 1
    assert len(course_map.json()["modules"][0]["concepts"]) == 4

    coursebook = client.get(f"/api/v1/courses/{course_id}/export/coursebook")
    assert coursebook.status_code == 200
    assert coursebook.headers["content-type"].startswith("application/pdf")
    assert coursebook.content.startswith(b"%PDF-")
    assert "attachment;" in coursebook.headers["content-disposition"]

    sources = client.get(f"/api/v1/courses/{course_id}/sources")
    assert sources.status_code == 200
    assert sources.json() == [
        {"id": source_id, "filename": "auth.md", "mime_type": "text/markdown", "byte_size": 123, "status": "uploaded", "position": 1}
    ]

    download = client.get(f"/api/v1/courses/{course_id}/sources/{source_id}/download")
    assert download.status_code == 200
    assert download.json()["filename"] == "auth.md"
    assert download.json()["download_url"]

    other_user_sources = client.get(
        f"/api/v1/courses/{course_id}/sources",
        headers={"X-Demo-User-Id": "00000000-0000-0000-0000-000000000002"},
    )
    assert other_user_sources.status_code == 404

    single_course = client.get(f"/api/v1/courses/{course_id}")
    assert single_course.status_code == 200
    assert single_course.json()["title"] == "API auth"

    other_user_courses = client.get(
        "/api/v1/courses",
        headers={"X-Demo-User-Id": "00000000-0000-0000-0000-000000000002"},
    )
    assert other_user_courses.status_code == 200
    assert other_user_courses.json() == []

    other_user_single_course = client.get(
        f"/api/v1/courses/{course_id}",
        headers={"X-Demo-User-Id": "00000000-0000-0000-0000-000000000002"},
    )
    assert other_user_single_course.status_code == 404

    progress = client.get(f"/api/v1/courses/{course_id}/progress")
    assert progress.status_code == 200
    assert progress.json()["stage"] == "ready"

    regenerated = client.post(f"/api/v1/courses/{course_id}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()["id"] == course_id

    concept = client.get(f"/api/v1/courses/{course_id}/concepts/core-pattern")
    assert concept.status_code == 200
    assert concept.json()["kind"] == "coding"

    missing_concept = client.get(f"/api/v1/courses/{course_id}/concepts/not-a-real-slug")
    assert missing_concept.status_code == 404


def test_course_mastery_endpoint_returns_the_threshold_and_concepts() -> None:
    client = TestClient(app)
    course = client.post(
        "/api/v1/courses",
        json={"title": "Mastery", "goal": "Track it", "source_ids": []},
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    mastery = client.get(f"/api/v1/courses/{course_id}/mastery")
    assert mastery.status_code == 200
    body = mastery.json()
    assert body["course_id"] == course_id
    assert body["threshold"] == 0.95
    assert isinstance(body["concepts"], list)

    prerequisites = client.get(f"/api/v1/courses/{course_id}/concepts/core-pattern/prerequisites")
    assert prerequisites.status_code == 200
    prereq_body = prerequisites.json()
    assert prereq_body["slug"] == "core-pattern"
    assert prereq_body["review_threshold"] == 0.6
    assert prereq_body["review_recommended"] is False
    assert isinstance(prereq_body["prerequisites"], list)


def test_course_deletion() -> None:
    client = TestClient(app)
    owner = {"X-Demo-User-Id": "00000000-0000-0000-0000-000000000004"}
    other_user = {"X-Demo-User-Id": "00000000-0000-0000-0000-000000000005"}
    course = client.post(
        "/api/v1/courses",
        headers=owner,
        json={"title": "Disposable course", "goal": "Learn deletion"},
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    forbidden = client.delete(f"/api/v1/courses/{course_id}", headers=other_user)
    assert forbidden.status_code == 404

    deleted = client.delete(f"/api/v1/courses/{course_id}", headers=owner)
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/courses/{course_id}", headers=owner)
    assert missing.status_code == 404

    repeat = client.delete(f"/api/v1/courses/{course_id}", headers=owner)
    assert repeat.status_code == 404


def test_goal_only_course_does_not_require_sources() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/courses",
        headers={"X-Demo-User-Id": "00000000-0000-0000-0000-000000000003"},
        json={"title": "Python foundations", "goal": "Learn Python from first principles"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Python foundations"


def test_course_map_rejects_a_malformed_course_id() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/courses/not-a-uuid/map")

    assert response.status_code == 422


def test_import_shared_course_gates_on_sharing_and_clones_to_importer() -> None:
    client = TestClient(app)
    owner = {"X-Demo-User-Id": "00000000-0000-0000-0000-000000000001"}
    other = {"X-Demo-User-Id": "00000000-0000-0000-0000-000000000002"}

    course = client.post(
        "/api/v1/courses",
        headers=owner,
        json={"title": "Sharing 101", "goal": "Hand a course to a friend"},
    )
    assert course.status_code == 201
    course_id = course.json()["id"]
    assert course.json()["is_shared"] is False

    # Not shared yet -> indistinguishable from a course that does not exist.
    blocked = client.post("/api/v1/courses/import", headers=other, json={"course_id": course_id})
    assert blocked.status_code == 404

    shared = client.patch(f"/api/v1/courses/{course_id}", headers=owner, json={"is_shared": True})
    assert shared.status_code == 200
    assert shared.json()["is_shared"] is True

    imported = client.post("/api/v1/courses/import", headers=other, json={"course_id": course_id})
    assert imported.status_code == 201
    body = imported.json()
    assert body["title"] == "Sharing 101"
    assert body["id"] != course_id
    # The importer's copy is private by default -- sharing does not cascade.
    assert body["is_shared"] is False

    # The copy lands in the importer's library, and not in the owner's.
    other_ids = [row["id"] for row in client.get("/api/v1/courses", headers=other).json()]
    assert other_ids == [body["id"]]
    owner_ids = [row["id"] for row in client.get("/api/v1/courses", headers=owner).json()]
    assert body["id"] not in owner_ids


def test_certificate_is_refused_until_the_course_is_fully_completed() -> None:
    client = TestClient(app)
    course = client.post(
        "/api/v1/courses",
        json={"title": "Unfinished", "goal": "Not done yet"},
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    # The memory-backed repository used by default in tests never tracks real
    # lesson completion, so a course here can never be "done".
    certificate = client.get(f"/api/v1/courses/{course_id}/certificate")
    assert certificate.status_code == 409

    export = client.get(f"/api/v1/courses/{course_id}/export/certificate")
    assert export.status_code == 409


class _CompletedCourseRepository:
    """Fakes just enough of CourseRepository for a fully completed course."""

    def certificate(self, owner_id: UUID, course_id: UUID) -> CertificateResponse:
        return CertificateResponse(
            course_id=course_id,
            course_title="API auth",
            learner_email="learner@example.com",
            issued_at="2026-07-19T00:00:00Z",
            certificate_id="ABC123DEF456",
        )


def test_certificate_is_issued_once_a_course_is_fully_completed() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_repository] = lambda: _CompletedCourseRepository()
    try:
        course_id = "00000000-0000-0000-0000-0000000000aa"

        certificate = client.get(f"/api/v1/courses/{course_id}/certificate")
        assert certificate.status_code == 200
        body = certificate.json()
        assert body["course_title"] == "API auth"
        assert body["learner_email"] == "learner@example.com"
        assert body["certificate_id"] == "ABC123DEF456"

        export = client.get(f"/api/v1/courses/{course_id}/export/certificate")
        assert export.status_code == 200
        assert export.headers["content-type"].startswith("application/pdf")
        assert export.content.startswith(b"%PDF-")
        assert "attachment;" in export.headers["content-disposition"]
        assert "API-auth-certificate.pdf" in export.headers["content-disposition"]
    finally:
        app.dependency_overrides.clear()
