import io
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import docker
import docker.errors
from requests.exceptions import ReadTimeout


_SANDBOX_IMAGE_DIR = Path(__file__).resolve().parent.parent / "sandbox_image"
_ENVIRONMENT_IMAGES = {"python-basic": "canopy-lesson-sandbox:python-basic"}


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
    """The isolated execution backend could not accept or complete a run."""


def validate_workspace_file(file: SandboxFile) -> None:
    path = PurePosixPath(file.path)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py" or len(path.parts) > 8:
        raise ValueError("Sandbox files must be relative Python files without path traversal.")
    if not file.content:
        raise ValueError("Sandbox files may not be empty.")
    if len(file.content.encode("utf-8")) > 20_000:
        raise ValueError("A sandbox file exceeds the maximum size.")


def files_to_tar(files: list[SandboxFile]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for file in files:
            validate_workspace_file(file)
            data = file.content.encode("utf-8")
            info = tarfile.TarInfo(name=file.path)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class DockerSandboxRunner:
    """Development execution backend. Only this service receives Docker access."""

    def __init__(self, client: docker.DockerClient, timeout_seconds: int = 20) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds
        self._ready_environments: set[str] = set()

    def run_pytest(self, *, environment_id: str, files: list[SandboxFile]) -> SandboxRunResult:
        if environment_id not in _ENVIRONMENT_IMAGES:
            raise ValueError("The requested sandbox environment is not registered.")
        if not files or len(files) > 15:
            raise ValueError("Sandbox runs must contain between 1 and 15 files.")
        if sum(len(file.content.encode("utf-8")) for file in files) > 128_000:
            raise ValueError("The sandbox workspace is too large.")

        image = _ENVIRONMENT_IMAGES[environment_id]
        self._ensure_image(environment_id, image)
        container = None
        try:
            container = self.client.containers.create(
                image=image,
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
            container.put_archive("/workspace", files_to_tar(files))
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
            if container is not None:
                container.remove(force=True)

    def _ensure_image(self, environment_id: str, image: str) -> None:
        if environment_id in self._ready_environments:
            return
        try:
            self.client.images.get(image)
        except docker.errors.ImageNotFound:
            try:
                self.client.images.build(path=str(_SANDBOX_IMAGE_DIR), tag=image, rm=True)
            except docker.errors.APIError as exc:
                raise SandboxError(str(exc)) from exc
        self._ready_environments.add(environment_id)
