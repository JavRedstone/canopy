from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser
from app.sandbox import SandboxError, SandboxFile, SandboxRunnerClient
from app.schemas import LessonWorkspaceFile, RunLessonResponse
from app.settings import get_settings

router = APIRouter(prefix="/playground", tags=["playground"])


def get_playground_sandbox() -> SandboxRunnerClient:
    settings = get_settings()
    token = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    return SandboxRunnerClient(
        settings.sandbox_runner_url,
        internal_service_token=token,
        timeout_seconds=settings.sandbox_timeout_seconds,
    )


Sandbox = Annotated[SandboxRunnerClient, Depends(get_playground_sandbox)]


class PlaygroundRunRequest(BaseModel):
    """Course-independent test execution -- nothing here is persisted. Exists to prove
    the sandbox's multi-language, multi-framework execution live in the product,
    separate from the Python-only AI course-generation pipeline (see docs/architecture/SECURITY.md
    and the sandbox runner's own curated environment registry for why languages are
    not arbitrary). Each environment's test command auto-discovers test files by its
    own convention (pytest: test_*.py, node --test: *.test.js, go test: *_test.go,
    doctest: any *.cpp file)."""

    environment_id: Literal["python-basic", "javascript-basic", "go-basic", "cpp-basic"]
    files: list[LessonWorkspaceFile] = Field(min_length=1, max_length=20)


@router.post("/run", response_model=RunLessonResponse)
def run_playground(request: PlaygroundRunRequest, current_user: CurrentUser, sandbox: Sandbox) -> RunLessonResponse:
    del current_user  # auth only -- this endpoint doesn't touch any owned resource
    try:
        result = sandbox.run_pytest(
            [SandboxFile(path=file.path, content=file.content) for file in request.files],
            environment_id=request.environment_id,
        )
    except SandboxError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The sandbox is unavailable.") from exc
    return RunLessonResponse(passed=result.passed, output=result.output, timed_out=result.timed_out)
