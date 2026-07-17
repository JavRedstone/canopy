import io
import tarfile

import pytest

from sandbox_runner.main import RunFile
from sandbox_runner.runner import SandboxFile, files_to_tar


def test_workspace_archive_contains_only_validated_relative_python_files() -> None:
    files = [
        SandboxFile(path="solution.py", content="x = 1\n"),
        SandboxFile(path="tests/test_solution.py", content="from solution import x\n"),
    ]

    archive = tarfile.open(fileobj=io.BytesIO(files_to_tar(files)), mode="r")
    members = {member.name: archive.extractfile(member).read().decode() for member in archive.getmembers()}

    assert members == {file.path: file.content for file in files}


def test_path_traversal_is_rejected_even_when_it_matches_the_basic_file_pattern() -> None:
    with pytest.raises(ValueError, match="path traversal"):
        RunFile(path="src/../escape.py", content="x = 1\n")
