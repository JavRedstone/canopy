import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, Protocol

import docker
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from sandbox_runner.runner import DockerSandboxRunner, SandboxError, SandboxFile, SandboxRunResult, get_environment, validate_file_suffix, validate_workspace_file

EnvironmentId = Literal["python-basic", "javascript-basic", "go-basic"]
from sandbox_runner.settings import SandboxRunnerSettings, get_settings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings().require_runtime_configuration()
    yield


app = FastAPI(title="Adaptive Source Learning Sandbox Runner", version="0.1.0", lifespan=lifespan)


class SandboxBackend(Protocol):
    def run_pytest(self, *, environment_id: str, files: list[SandboxFile]) -> SandboxRunResult: ...

    def run_script(self, *, environment_id: str, entry_path: str, files: list[SandboxFile]) -> SandboxRunResult: ...


class RunFile(BaseModel):
    path: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def is_safe_workspace_file(self) -> "RunFile":
        validate_workspace_file(SandboxFile(path=self.path, content=self.content))
        return self


class RunRequest(BaseModel):
    profile: Literal["content_validation", "learner_visible"]
    environment_id: EnvironmentId
    files: list[RunFile] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def file_paths_are_unique(self) -> "RunRequest":
        if len({file.path for file in self.files}) != len(self.files):
            raise ValueError("Sandbox file paths must be unique.")
        return self

    @model_validator(mode="after")
    def files_match_the_environment(self) -> "RunRequest":
        environment = get_environment(self.environment_id)
        if environment is None:
            raise ValueError("The requested sandbox environment is not registered.")
        for file in self.files:
            validate_file_suffix(SandboxFile(path=file.path, content=file.content), environment)
        return self


class RunResponse(BaseModel):
    passed: bool
    exit_code: int
    output: str
    timed_out: bool


class RunScriptRequest(BaseModel):
    environment_id: EnvironmentId
    entry_path: str = Field(min_length=1, max_length=255)
    files: list[RunFile] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def file_paths_are_unique_and_include_entry(self) -> "RunScriptRequest":
        paths = {file.path for file in self.files}
        if len(paths) != len(self.files):
            raise ValueError("Sandbox file paths must be unique.")
        if self.entry_path not in paths:
            raise ValueError("The script entry path must be one of the submitted files.")
        return self

    @model_validator(mode="after")
    def files_match_the_environment(self) -> "RunScriptRequest":
        environment = get_environment(self.environment_id)
        if environment is None:
            raise ValueError("The requested sandbox environment is not registered.")
        for file in self.files:
            validate_file_suffix(SandboxFile(path=file.path, content=file.content), environment)
        return self


class RunScriptResponse(BaseModel):
    exit_code: int
    output: str
    timed_out: bool


def _backend(settings: SandboxRunnerSettings = Depends(get_settings)) -> SandboxBackend:
    return DockerSandboxRunner(docker.from_env(), timeout_seconds=settings.sandbox_timeout_seconds)


def _internal_request_allowed(
    x_internal_service_token: str | None = Header(default=None),
    settings: SandboxRunnerSettings = Depends(get_settings),
) -> None:
    expected = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    if expected and x_internal_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal service token.")
    if not expected and settings.environment != "development":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal authentication is not configured.")


@app.get("/health", dependencies=[Depends(_internal_request_allowed)])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/v1/runs", response_model=RunResponse, dependencies=[Depends(_internal_request_allowed)])
def run_pytest(request: RunRequest, backend: SandboxBackend = Depends(_backend)) -> RunResponse:
    try:
        result = backend.run_pytest(
            environment_id=request.environment_id,
            files=[SandboxFile(path=file.path, content=file.content) for file in request.files],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except SandboxError as exc:
        logger.exception("Sandbox execution failed", extra={"profile": request.profile})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The exercise runner is unavailable.") from exc
    return RunResponse(passed=result.passed, exit_code=result.exit_code, output=result.output, timed_out=result.timed_out)


@app.post("/internal/v1/scripts", response_model=RunScriptResponse, dependencies=[Depends(_internal_request_allowed)])
def run_script(request: RunScriptRequest, backend: SandboxBackend = Depends(_backend)) -> RunScriptResponse:
    try:
        result = backend.run_script(
            environment_id=request.environment_id,
            entry_path=request.entry_path,
            files=[SandboxFile(path=file.path, content=file.content) for file in request.files],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except SandboxError as exc:
        logger.exception("Sandbox script execution failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The exercise runner is unavailable.") from exc
    return RunScriptResponse(exit_code=result.exit_code, output=result.output, timed_out=result.timed_out)
