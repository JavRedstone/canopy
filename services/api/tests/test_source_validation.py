from fastapi.testclient import TestClient

from app.main import app


def test_source_rejects_a_file_larger_than_signed_upload_limit() -> None:
    response = TestClient(app).post(
        "/api/v1/sources",
        json={"filename": "large.pdf", "mime_type": "application/pdf", "byte_size": 6 * 1024 * 1024 + 1},
    )

    assert response.status_code == 422


def test_source_rejects_an_unsupported_mime_type() -> None:
    response = TestClient(app).post(
        "/api/v1/sources",
        json={"filename": "malware.exe", "mime_type": "application/octet-stream", "byte_size": 128},
    )

    assert response.status_code == 422
