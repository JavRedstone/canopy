import io
import tarfile
from dataclasses import dataclass
from pathlib import PurePosixPath

import docker
import docker.errors
from requests.exceptions import ReadTimeout


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
    """A Docker daemon failure while running a learner workspace."""


def _files_to_tar(files: list[SandboxFile]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for file in files:
            path = PurePosixPath(file.path)
            if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
                raise ValueError("Learner workspaces may contain only relative Python files.")
            data = file.content.encode("utf-8")
            info = tarfile.TarInfo(name=file.path)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class DockerSandbox:
    """Run a bounded learner workspace against private generated tests."""

    IMAGE_TAG = "canopy-lesson-sandbox:python-basic"

    def __init__(self, client: docker.DockerClient, timeout_seconds: int = 20) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds

    def run_pytest(self, files: list[SandboxFile]) -> SandboxRunResult:
        if sum(len(file.content.encode("utf-8")) for file in files) > 128_000:
            raise ValueError("The exercise workspace is too large.")
        try:
            container = self.client.containers.create(
                image=self.IMAGE_TAG,
                command=["pytest", "-q", "-p", "no:cacheprovider", "."],
                working_dir="/workspace",
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
                network_disabled=True,
                read_only=True,
                user="65534:65534",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                tmpfs={"/workspace": "rw,nosuid,nodev,noexec,size=8m"},
                mem_limit="256m",
                nano_cpus=1_000_000_000,
                pids_limit=64,
                detach=True,
            )
            container.put_archive("/workspace", _files_to_tar(files))
            container.start()
            try:
                result = container.wait(timeout=self.timeout_seconds)
                exit_code = result["StatusCode"]
                timed_out = False
            except ReadTimeout:
                container.kill()
                exit_code = -1
                timed_out = True
            output = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            return SandboxRunResult(exit_code=exit_code, output=output[-16_000:], timed_out=timed_out)
        except docker.errors.APIError as exc:
            raise SandboxError(str(exc)) from exc
        finally:
            if "container" in locals():
                container.remove(force=True)
