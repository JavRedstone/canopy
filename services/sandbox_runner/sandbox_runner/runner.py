import io
import tarfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import docker
import docker.errors
from requests.exceptions import ReadTimeout


_SANDBOX_IMAGE_DIR = Path(__file__).resolve().parent.parent / "sandbox_image"


@dataclass(frozen=True)
class SandboxFile:
    path: str
    content: str


@dataclass(frozen=True)
class SandboxEnvironment:
    """One registered, hardened execution environment. Every field here is curated by
    us at review time -- there is no path for a caller to run an unregistered image or
    toolchain, which is the point (see docs/architecture/SECURITY.md on why arbitrary images are a
    real risk given this service's docker.sock access)."""

    image: str
    dockerfile_dir: Path
    file_suffix: str
    test_command: list[str]
    script_command: list[str]  # entry_path is appended at call time
    extra_env: dict[str, str] = field(default_factory=dict)
    # Server-authored files injected ahead of the caller's own, skipped if the caller
    # already submitted that exact path. Not user input, so not suffix/traversal checked.
    bootstrap_files: dict[str, str] = field(default_factory=dict)


_ENVIRONMENTS: dict[str, SandboxEnvironment] = {
    "python-basic": SandboxEnvironment(
        image="canopy-lesson-sandbox:python-basic",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "python-basic",
        file_suffix=".py",
        # -v (not -q) prints one "path::test_name PASSED/FAILED" line per test, which the
        # API/frontend parse into a per-test-case list instead of a single pass/fail blob.
        test_command=["pytest", "-v", "-p", "no:cacheprovider", "."],
        script_command=["python", "-u"],
        extra_env={"PYTHONDONTWRITEBYTECODE": "1"},
    ),
    "javascript-basic": SandboxEnvironment(
        image="canopy-lesson-sandbox:javascript-basic",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "javascript-basic",
        file_suffix=".js",
        # Node's built-in test runner auto-discovers **/*.test.js -- no framework install needed.
        test_command=["node", "--test"],
        script_command=["node"],
    ),
    "go-basic": SandboxEnvironment(
        image="canopy-lesson-sandbox:go-basic",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "go-basic",
        file_suffix=".go",
        test_command=["go", "test", "./..."],
        script_command=["go", "run"],
        # The container runs as the non-root, homeless UID 65534, so Go's toolchain needs
        # its cache/module dirs redirected to a path that UID can actually write to.
        extra_env={"GOCACHE": "/tmp/go-cache", "GOPATH": "/tmp/go-path", "GOFLAGS": "-mod=mod"},
        # go test requires a go.mod; submitted lesson/demo content won't include one.
        bootstrap_files={"go.mod": "module sandbox\n\ngo 1.22\n"},
    ),
}


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


def get_environment(environment_id: str) -> SandboxEnvironment | None:
    return _ENVIRONMENTS.get(environment_id)


def validate_workspace_file(file: SandboxFile) -> None:
    path = PurePosixPath(file.path)
    if path.is_absolute() or ".." in path.parts or len(path.parts) > 8:
        raise ValueError("Sandbox files must be relative files without path traversal.")
    if not file.content:
        raise ValueError("Sandbox files may not be empty.")
    if len(file.content.encode("utf-8")) > 20_000:
        raise ValueError("A sandbox file exceeds the maximum size.")


def validate_file_suffix(file: SandboxFile, environment: SandboxEnvironment) -> None:
    # Bootstrap paths (e.g. go.mod) are project scaffold, not source files -- a caller
    # overriding one (see files_to_tar) is exempt from the primary source-file suffix.
    if file.path in environment.bootstrap_files:
        return
    if PurePosixPath(file.path).suffix != environment.file_suffix:
        raise ValueError(f"Sandbox files for this environment must be {environment.file_suffix} files.")


def files_to_tar(files: list[SandboxFile], environment: SandboxEnvironment) -> bytes:
    for file in files:
        validate_workspace_file(file)
        validate_file_suffix(file, environment)
    submitted_paths = {file.path for file in files}
    bootstrap = [
        SandboxFile(path=path, content=content)
        for path, content in environment.bootstrap_files.items()
        if path not in submitted_paths
    ]
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for file in [*bootstrap, *files]:
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
        self._ready_images: set[str] = set()

    def run_pytest(self, *, environment_id: str, files: list[SandboxFile]) -> SandboxRunResult:
        environment = self._environment(environment_id)
        return self._run(environment=environment, files=files, command=environment.test_command)

    def run_script(self, *, environment_id: str, entry_path: str, files: list[SandboxFile]) -> SandboxRunResult:
        if not any(file.path == entry_path for file in files):
            raise ValueError("The script entry path must be one of the submitted files.")
        environment = self._environment(environment_id)
        return self._run(environment=environment, files=files, command=[*environment.script_command, entry_path])

    def _environment(self, environment_id: str) -> SandboxEnvironment:
        environment = get_environment(environment_id)
        if environment is None:
            raise ValueError("The requested sandbox environment is not registered.")
        return environment

    def _run(self, *, environment: SandboxEnvironment, files: list[SandboxFile], command: list[str]) -> SandboxRunResult:
        if not files or len(files) > 20:
            raise ValueError("Sandbox runs must contain between 1 and 20 files.")
        if sum(len(file.content.encode("utf-8")) for file in files) > 128_000:
            raise ValueError("The sandbox workspace is too large.")

        self._ensure_image(environment)
        container = None
        try:
            # No read-only rootfs or workspace tmpfs: the Docker archive API rejects
            # put_archive outright on read-only-rootfs containers, and a tmpfs would
            # shadow files copied in before start. The non-root user cannot write
            # anywhere meaningful on the rootfs, and pytest is configured not to write.
            container = self.client.containers.create(
                image=environment.image,
                command=command,
                working_dir="/workspace",
                environment=environment.extra_env,
                network_disabled=True,
                # Not read-only: Docker's put_archive rejects writes outright on a read-only rootfs, and even
                # when writable, a tmpfs mount at the target path silently shadows archive-extracted files
                # (verified against the local daemon). The container is single-use and force-removed in
                # `finally`, and network/capabilities/user/resources are still fully locked down below.
                read_only=False,
                user="65534:65534",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit="256m",
                nano_cpus=1_000_000_000,
                pids_limit=64,
                detach=True,
            )
            container.put_archive("/workspace", files_to_tar(files, environment))
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

    def _ensure_image(self, environment: SandboxEnvironment) -> None:
        if environment.image in self._ready_images:
            return
        try:
            self.client.images.get(environment.image)
        except docker.errors.ImageNotFound:
            try:
                self.client.images.build(path=str(environment.dockerfile_dir), tag=environment.image, rm=True)
            except docker.errors.APIError as exc:
                raise SandboxError(str(exc)) from exc
        self._ready_images.add(environment.image)
