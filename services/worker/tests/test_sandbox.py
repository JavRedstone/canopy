import httpx
import pytest

from worker.sandbox import SandboxError, SandboxFile, SandboxRunnerClient


class FakeResponse:
    def __init__(self, data: dict[str, object], error: Exception | None = None) -> None:
        self.data = data
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self) -> dict[str, object]:
        return self.data


class FakeHttpClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_client_submits_only_fixed_content_validation_profile() -> None:
    http = FakeHttpClient(FakeResponse({"passed": True, "exit_code": 0, "output": "1 passed", "timed_out": False}))
    client = SandboxRunnerClient("http://sandbox/", internal_service_token="secret", timeout_seconds=20, http_client=http)

    result = client.run_pytest([SandboxFile(path="solution.py", content="x = 1\n")])

    assert result.passed
    assert http.calls == [
        {
            "url": "http://sandbox/internal/v1/runs",
            "headers": {"X-Internal-Service-Token": "secret"},
            "json": {
                "profile": "content_validation",
                "environment_id": "python-basic",
                "files": [{"path": "solution.py", "content": "x = 1\n"}],
            },
        }
    ]


def test_client_hides_transport_errors_as_sandbox_error() -> None:
    http = FakeHttpClient(FakeResponse({}, error=httpx.ConnectError("offline")))
    client = SandboxRunnerClient("http://sandbox", internal_service_token=None, timeout_seconds=20, http_client=http)

    with pytest.raises(SandboxError):
        client.run_pytest([SandboxFile(path="solution.py", content="x = 1\n")])
