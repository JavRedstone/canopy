import shutil
import tarfile
import io

import docker
import pytest

from worker.sandbox import DockerSandbox, SandboxFile, _files_to_tar


def test_files_to_tar_round_trips_paths_and_contents() -> None:
    files = [
        SandboxFile(path="solution.py", content="def f():\n    return 1\n"),
        SandboxFile(path="test_solution.py", content="from solution import f\n"),
    ]

    archive = tarfile.open(fileobj=io.BytesIO(_files_to_tar(files)), mode="r")
    members = {member.name: archive.extractfile(member).read().decode() for member in archive.getmembers()}

    assert members == {file.path: file.content for file in files}


@pytest.mark.skipif(shutil.which("docker") is None, reason="requires a local Docker daemon")
def test_run_pytest_reports_pass_and_fail_against_a_real_daemon() -> None:
    client = docker.from_env()
    sandbox = DockerSandbox(client, timeout_seconds=30)

    passing = sandbox.run_pytest(
        [
            SandboxFile("solution.py", "def add(a, b):\n    return a + b\n"),
            SandboxFile("test_solution.py", "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"),
        ]
    )
    assert passing.passed

    failing = sandbox.run_pytest(
        [
            SandboxFile("solution.py", "def add(a, b):\n    return a - b\n"),
            SandboxFile("test_solution.py", "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"),
        ]
    )
    assert not failing.passed
    assert failing.exit_code != 0
