from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SandboxFile:
    path: str
    content: str


@dataclass(frozen=True)
class SandboxRunResult:
    exit_code: int
    output: str
    timed_out: bool

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SandboxError(Exception):
    """The private sandbox runner could not accept or complete a run."""


class SandboxRunnerClient:
    """Runs content-validation jobs through the isolated sandbox service."""

    def __init__(
        self,
        base_url: str,
        *,
        internal_service_token: str | None,
        timeout_seconds: int,
        http_client: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_service_token = internal_service_token
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds + 5)

    def run_pytest(self, files: list[SandboxFile], *, environment_id: str = "python-basic") -> SandboxRunResult:
        headers = {"X-Internal-Service-Token": self.internal_service_token} if self.internal_service_token else {}
        try:
            response = self.http_client.post(
                f"{self.base_url}/internal/v1/runs",
                headers=headers,
                json={
                    "profile": "content_validation",
                    "environment_id": environment_id,
                    "files": [{"path": file.path, "content": file.content} for file in files],
                },
            )
            response.raise_for_status()
            result = response.json()
            return SandboxRunResult(
                exit_code=int(result["exit_code"]),
                output=str(result["output"]),
                timed_out=bool(result["timed_out"]),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise SandboxError("The sandbox runner request failed.") from exc
