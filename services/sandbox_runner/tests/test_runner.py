import io
import tarfile

import pytest
from fastapi import HTTPException

from sandbox_runner import main
from sandbox_runner.main import RunFile, RunRequest
from sandbox_runner.runner import SandboxFile, files_to_tar, get_environment


def test_workspace_archive_contains_only_validated_relative_python_files() -> None:
    environment = get_environment("python-basic")
    assert environment is not None
    files = [
        SandboxFile(path="solution.py", content="x = 1\n"),
        SandboxFile(path="tests/test_solution.py", content="from solution import x\n"),
    ]

    archive = tarfile.open(fileobj=io.BytesIO(files_to_tar(files, environment)), mode="r")
    members = {member.name: archive.extractfile(member).read().decode() for member in archive.getmembers()}

    assert members == {file.path: file.content for file in files}


def test_path_traversal_is_rejected_even_when_it_matches_the_basic_file_pattern() -> None:
    with pytest.raises(ValueError, match="path traversal"):
        RunFile(path="src/../escape.py", content="x = 1\n")


def test_javascript_environment_accepts_js_files() -> None:
    environment = get_environment("javascript-basic")
    assert environment is not None
    files = [SandboxFile(path="solution.test.js", content="require('node:test');\n")]

    archive = tarfile.open(fileobj=io.BytesIO(files_to_tar(files, environment)), mode="r")
    assert {member.name for member in archive.getmembers()} == {"solution.test.js"}


def test_go_environment_injects_a_go_mod_when_the_caller_did_not_submit_one() -> None:
    environment = get_environment("go-basic")
    assert environment is not None
    files = [SandboxFile(path="solution_test.go", content="package sandbox\n")]

    archive = tarfile.open(fileobj=io.BytesIO(files_to_tar(files, environment)), mode="r")
    members = {member.name: archive.extractfile(member).read().decode() for member in archive.getmembers()}

    assert members["solution_test.go"] == "package sandbox\n"
    assert members["go.mod"] == "module sandbox\n\ngo 1.22\n"


def test_go_environment_does_not_override_a_caller_submitted_go_mod() -> None:
    environment = get_environment("go-basic")
    assert environment is not None
    files = [
        SandboxFile(path="solution_test.go", content="package sandbox\n"),
        SandboxFile(path="go.mod", content="module custom\n\ngo 1.22\n"),
    ]

    archive = tarfile.open(fileobj=io.BytesIO(files_to_tar(files, environment)), mode="r")
    members = {member.name: archive.extractfile(member).read().decode() for member in archive.getmembers()}

    assert members["go.mod"] == "module custom\n\ngo 1.22\n"


def test_files_to_tar_rejects_a_suffix_that_does_not_match_the_environment() -> None:
    environment = get_environment("javascript-basic")
    assert environment is not None
    with pytest.raises(ValueError, match=r"\.js files"):
        files_to_tar([SandboxFile(path="solution.py", content="x = 1\n")], environment)


def test_run_request_rejects_files_whose_suffix_does_not_match_the_environment() -> None:
    with pytest.raises(ValueError, match=r"\.js files"):
        RunRequest(
            profile="learner_visible",
            environment_id="javascript-basic",
            files=[RunFile(path="solution.py", content="x = 1\n")],
        )


def test_docker_readiness_has_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnavailableDocker:
        def ping(self) -> None:
            raise main.docker.errors.DockerException("connection refused")

    monkeypatch.setattr(main.docker, "from_env", lambda: UnavailableDocker())

    with pytest.raises(HTTPException, match="Start Docker Desktop") as exc_info:
        main.health()

    assert exc_info.value.status_code == 503
