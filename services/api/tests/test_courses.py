from fastapi.testclient import TestClient

from app.main import app


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
    assert len(course_map.json()["concepts"]) == 3

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
