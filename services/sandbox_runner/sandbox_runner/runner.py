import io
import logging
import tarfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import docker
import docker.errors
import docker.types
from requests.exceptions import ReadTimeout


logger = logging.getLogger(__name__)

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
    # Every other environment is a small interpreter/compiler run; ML/DL work (importing
    # torch alone, a small model or dataframe) needs meaningfully more than that, hence
    # these being overridable per environment rather than one fixed global cap.
    mem_limit: str = "256m"
    nano_cpus: int = 1_000_000_000
    pids_limit: int = 64
    # Best-effort: request a GPU device only when the environment wants one, and fall back
    # to CPU-only automatically if the host has no GPU/nvidia-container-toolkit. This is
    # what lets one image run accelerated where a GPU is available and plain CPU elsewhere,
    # without maintaining two separate images or configuring anything per host.
    gpu: bool = False
    # None means "use the runner's global default" (DockerSandboxRunner.timeout_seconds).
    # Importing torch/pandas alone eats into that default's margin before a lab even runs.
    timeout_seconds: int | None = None


_ENVIRONMENTS: dict[str, SandboxEnvironment] = {
    "python-basic": SandboxEnvironment(
        # Increment this tag whenever the Dockerfile changes. The runner only builds
        # missing images, so a versioned tag prevents an old cached environment from
        # silently surviving a dependency update.
        image="canopy-lesson-sandbox:python-basic-v2",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "python-basic",
        file_suffix=".py",
        # -v (not -q) prints one "path::test_name PASSED/FAILED" line per test, which the
        # API/frontend parse into a per-test-case list instead of a single pass/fail blob.
        test_command=["pytest", "-v", "-p", "no:cacheprovider", "."],
        script_command=["python", "-u"],
        extra_env={"PYTHONDONTWRITEBYTECODE": "1"},
    ),
    "python-ml": SandboxEnvironment(
        # See sandbox_image/python-ml/Dockerfile -- a CUDA-enabled PyTorch base image plus
        # the classical-ML/DL stack (numpy, pandas, scipy, scikit-learn, matplotlib,
        # seaborn, torch, torchvision, pytest). No TensorFlow: shipping both major DL
        # frameworks in one image roughly doubles it for no benefit when torch alone
        # covers the deep-learning track.
        image="canopy-lesson-sandbox:python-ml-v1",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "python-ml",
        file_suffix=".py",
        test_command=["pytest", "-v", "-p", "no:cacheprovider", "."],
        script_command=["python", "-u"],
        extra_env={"PYTHONDONTWRITEBYTECODE": "1"},
        # torch + CUDA runtime alone is a few hundred MB resident before a lab does
        # anything; 256m (every other environment's default) would OOM on import.
        mem_limit="3072m",
        nano_cpus=2_000_000_000,
        gpu=True,
        timeout_seconds=60,
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
    "cpp-basic": SandboxEnvironment(
        image="canopy-lesson-sandbox:cpp-basic-v1",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "cpp-basic",
        file_suffix=".cpp",
        # No single command both compiles and runs C++, so this shells out: compile every
        # .cpp in the workspace, then execute the resulting binary. A compile error trips
        # `&&`'s short-circuit and g++'s own nonzero exit code/stderr surface exactly like
        # a Python syntax error does for pytest -- no special-casing needed downstream.
        test_command=["sh", "-c", "g++ -std=c++17 -O0 -I/usr/local/include *.cpp -o /tmp/sandbox_run && /tmp/sandbox_run"],
        # `sh -c script entry_path` binds the first positional arg after the script to $0.
        script_command=["sh", "-c", "g++ -std=c++17 -O0 -I/usr/local/include \"$0\" -o /tmp/sandbox_script && /tmp/sandbox_script"],
        # doctest (a single vendored header, baked into the image -- see
        # sandbox_image/cpp-basic/Dockerfile) needs exactly one translation unit that
        # defines the runner's main(). Bootstrapping it keeps the learner's own file
        # limited to `#include "doctest.h"` plus TEST_CASE(...), the same no-entry-point
        # shape as the other environments.
        bootstrap_files={"doctest_main.cpp": "#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN\n#include \"doctest.h\"\n"},
    ),
    "c-basic": SandboxEnvironment(
        image="canopy-lesson-sandbox:c-basic-v1",
        dockerfile_dir=_SANDBOX_IMAGE_DIR / "c-basic",
        file_suffix=".c",
        # Same shell-out shape as cpp-basic: compile every .c in the workspace, then run
        # the binary. A compile error trips `&&`'s short-circuit and gcc's own nonzero
        # exit code/stderr surface exactly like a Python syntax error does for pytest.
        # -fsanitize=address instruments every run for the classic C memory bugs (buffer
        # overflow, use-after-free, stack corruption) -- it's the modern replacement for
        # valgrind here specifically because it needs no elevated container privileges
        # (valgrind's ptrace requirement doesn't fit a cap_drop=ALL, non-root sandbox).
        # ASan aborts with a nonzero exit and prints the bug straight to stdout/stderr, so
        # it surfaces exactly like any other runtime failure -- no special-casing needed.
        test_command=["sh", "-c", "gcc -std=c17 -O0 -g -fsanitize=address -fno-omit-frame-pointer -I/usr/local/include *.c -o /tmp/sandbox_run && /tmp/sandbox_run"],
        # `sh -c script entry_path` binds the first positional arg after the script to $0.
        script_command=["sh", "-c", "gcc -std=c17 -O0 -g -fsanitize=address -fno-omit-frame-pointer -I/usr/local/include \"$0\" -o /tmp/sandbox_script && /tmp/sandbox_script"],
        # LeakSanitizer (bundled with ASan) is commonly documented as needing ptrace, which
        # this sandbox's cap_drop=ALL denies -- verified empirically against this exact
        # container config (non-root, cap_drop=ALL, no-new-privileges) that it works
        # without it, so leak detection stays on rather than being disabled on a guess.
        extra_env={"ASAN_OPTIONS": "detect_leaks=1"},
        # C has no doctest-equivalent, so sandbox_test.h (a small vendored header, baked
        # into the image -- see sandbox_image/c-basic/Dockerfile) is a hand-rolled
        # TEST_CASE/CHECK framework using GCC/Clang constructor attributes to
        # self-register tests before main() runs. That self-registration needs storage
        # for the shared test/check counters defined exactly once; bootstrapping it here
        # keeps the learner's own file limited to `#include "sandbox_test.h"` plus
        # TEST_CASE(...), the same no-entry-point shape as the other environments.
        bootstrap_files={
            "sandbox_main.c": (
                "#include <stdio.h>\n"
                "#include \"sandbox_test.h\"\n\n"
                "sandbox_test_fn sandbox_tests[SANDBOX_MAX_TESTS];\n"
                "const char *sandbox_test_names[SANDBOX_MAX_TESTS];\n"
                "int sandbox_test_count = 0;\n"
                "int sandbox_checks_run = 0;\n"
                "int sandbox_checks_failed = 0;\n"
                "int sandbox_current_test_failed = 0;\n\n"
                "void sandbox_register_test(sandbox_test_fn fn, const char *name) {\n"
                "    if (sandbox_test_count < SANDBOX_MAX_TESTS) {\n"
                "        sandbox_tests[sandbox_test_count] = fn;\n"
                "        sandbox_test_names[sandbox_test_count] = name;\n"
                "        sandbox_test_count++;\n"
                "    }\n"
                "}\n\n"
                "int main(void) {\n"
                "    int failed_tests = 0;\n"
                "    for (int i = 0; i < sandbox_test_count; i++) {\n"
                "        sandbox_current_test_failed = 0;\n"
                "        printf(\"TEST %s\\n\", sandbox_test_names[i]);\n"
                "        sandbox_tests[i]();\n"
                "        if (sandbox_current_test_failed) {\n"
                "            failed_tests++;\n"
                "            printf(\"  ... FAILED\\n\");\n"
                "        } else {\n"
                "            printf(\"  ... PASSED\\n\");\n"
                "        }\n"
                "    }\n"
                "    printf(\"\\n%d checks run, %d failed | %d tests, %d failed\\n\",\n"
                "           sandbox_checks_run, sandbox_checks_failed, sandbox_test_count, failed_tests);\n"
                "    return failed_tests > 0 ? 1 : 0;\n"
                "}\n"
            ),
        },
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
            container = self._create_container(environment, command)
            container.put_archive("/workspace", files_to_tar(files, environment))
            container.start()
            try:
                timeout = environment.timeout_seconds or self.timeout_seconds
                result = container.wait(timeout=timeout)
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

    def _create_container(self, environment: SandboxEnvironment, command: list[str]):
        # No read-only rootfs or workspace tmpfs: the Docker archive API rejects
        # put_archive outright on read-only-rootfs containers, and a tmpfs would
        # shadow files copied in before start. The non-root user cannot write
        # anywhere meaningful on the rootfs, and pytest is configured not to write.
        base_kwargs = dict(
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
            mem_limit=environment.mem_limit,
            nano_cpus=environment.nano_cpus,
            pids_limit=environment.pids_limit,
            detach=True,
        )
        if environment.gpu:
            try:
                return self.client.containers.create(
                    device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])],
                    **base_kwargs,
                )
            except docker.errors.APIError:
                # No GPU / nvidia-container-toolkit on this host -- fall back to the same
                # image running CPU-only rather than failing every run outright.
                logger.warning("GPU device request failed for %s; falling back to CPU-only execution.", environment.image)
        return self.client.containers.create(**base_kwargs)

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
