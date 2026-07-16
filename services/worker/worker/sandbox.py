import io
import tarfile
from dataclasses import dataclass
from pathlib import Path

import docker
import docker.errors
from requests.exceptions import ReadTimeout

_SANDBOX_IMAGE_DIR = Path(__file__).resolve().parent.parent / "sandbox_image"


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
    """A Docker/daemon-level failure, distinct from a failing test run inside the sandbox."""


def _files_to_tar(files: list[SandboxFile]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for file in files:
            data = file.content.encode("utf-8")
            info = tarfile.TarInfo(name=file.path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class DockerSandbox:
    """Runs generated lesson code inside a disposable, network-isolated container.

    This validates content the worker itself asked an LLM to generate, not
    arbitrary untrusted student input; containment here is about preventing a
    runaway process, not defending against an adversarial actor.
    """

    IMAGE_TAG = "canopy-lesson-sandbox:python-basic"

    def __init__(self, client: docker.DockerClient, timeout_seconds: int = 20) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds
        self._image_ready = False

    def ensure_image(self) -> None:
        if self._image_ready:
            return
        try:
            self.client.images.get(self.IMAGE_TAG)
        except docker.errors.ImageNotFound:
            self.client.images.build(path=str(_SANDBOX_IMAGE_DIR), tag=self.IMAGE_TAG, rm=True)
        self._image_ready = True

    def run_pytest(self, files: list[SandboxFile]) -> SandboxRunResult:
        self.ensure_image()
        try:
            container = self.client.containers.create(
                image=self.IMAGE_TAG,
                command=["pytest", "-q", "."],
                working_dir="/workspace",
                network_disabled=True,
                mem_limit="256m",
                nano_cpus=1_000_000_000,
                pids_limit=128,
                detach=True,
            )
        except docker.errors.APIError as exc:
            raise SandboxError(str(exc)) from exc

        try:
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
            return SandboxRunResult(exit_code=exit_code, output=output, timed_out=timed_out)
        except docker.errors.APIError as exc:
            raise SandboxError(str(exc)) from exc
        finally:
            container.remove(force=True)
