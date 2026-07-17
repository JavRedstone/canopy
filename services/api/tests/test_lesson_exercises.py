from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.repository import get_repository
from app.routers.courses import get_lesson_sandbox
from app.sandbox import SandboxFile, SandboxRunResult
from app.schemas import LessonWorkspaceFile


class ExerciseRepository:
    def __init__(self) -> None:
        self.regenerated: tuple[object, object, str] | None = None
        self.completed: tuple[object, object, str] | None = None

    def lesson_workspace(
        self, owner_id: object, course_id: object, slug: str
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile]]:
        return (
            [LessonWorkspaceFile(path="solution.py", content="def add(a, b):\n    return 0\n")],
            [LessonWorkspaceFile(path="test_basic.py", content="from solution import add\n\ndef test_add_two_positive_numbers():\n    assert add(1, 2) == 3\n")],
            [LessonWorkspaceFile(path="test_solution.py", content="from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")],
        )

    def complete_coding_lesson(self, owner_id: object, course_id: object, slug: str) -> None:
        self.completed = (owner_id, course_id, slug)

    def regenerate_lesson(self, owner_id: object, course_id: object, slug: str) -> None:
        self.regenerated = (owner_id, course_id, slug)


class ExerciseSandbox:
    def __init__(self) -> None:
        self.files: list[SandboxFile] = []
        self.script_files: list[SandboxFile] = []
        self.entry_path: str | None = None

    def run_pytest(self, files: list[SandboxFile]) -> SandboxRunResult:
        self.files = files
        return SandboxRunResult(exit_code=0, output="1 passed", timed_out=False)

    def run_script(self, files: list[SandboxFile], entry_path: str) -> SandboxRunResult:
        self.script_files = files
        self.entry_path = entry_path
        return SandboxRunResult(exit_code=0, output="hello from scratch\n", timed_out=False)


def test_run_lesson_uses_private_tests_and_returns_result() -> None:
    repository = ExerciseRepository()
    sandbox = ExerciseSandbox()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: sandbox
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/addition/run",
            json={"files": [{"path": "solution.py", "content": "def add(a, b):\n    return a + b\n"}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"passed": True, "output": "1 passed", "timed_out": False}
    assert [(file.path, file.content) for file in sandbox.files] == [
        ("solution.py", "def add(a, b):\n    return a + b\n"),
        ("test_basic.py", "from solution import add\n\ndef test_add_two_positive_numbers():\n    assert add(1, 2) == 3\n"),
        ("test_solution.py", "from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"),
    ]
    assert repository.completed is not None


def test_run_script_executes_arbitrary_code_and_returns_console_output() -> None:
    repository = ExerciseRepository()
    sandbox = ExerciseSandbox()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: sandbox
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/addition/run-script",
            json={
                "files": [{"path": "solution.py", "content": "def add(a, b):\n    return a + b\n"}],
                "script": {"path": "scratch.py", "content": "from solution import add\nprint(add(2, 3))\n"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"output": "hello from scratch\n", "exit_code": 0, "timed_out": False}
    assert sandbox.entry_path == "scratch.py"
    assert [(file.path, file.content) for file in sandbox.script_files] == [
        ("solution.py", "def add(a, b):\n    return a + b\n"),
        ("scratch.py", "from solution import add\nprint(add(2, 3))\n"),
    ]


def test_run_script_rejects_a_path_colliding_with_a_lesson_file() -> None:
    repository = ExerciseRepository()
    sandbox = ExerciseSandbox()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: sandbox
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/addition/run-script",
            json={
                "files": [{"path": "solution.py", "content": "def add(a, b):\n    return a + b\n"}],
                "script": {"path": "solution.py", "content": "print('hi')\n"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert sandbox.script_files == []


def test_run_lesson_rejects_added_or_duplicate_files() -> None:
    repository = ExerciseRepository()
    sandbox = ExerciseSandbox()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_lesson_sandbox] = lambda: sandbox
    try:
        response = TestClient(app).post(
            f"/api/v1/courses/{uuid4()}/concepts/addition/run",
            json={"files": [
                {"path": "solution.py", "content": "first"},
                {"path": "solution.py", "content": "second"},
            ]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert sandbox.files == []


def test_regenerate_lesson_queues_only_that_lesson() -> None:
    repository = ExerciseRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    course_id = uuid4()
    try:
        response = TestClient(app).post(f"/api/v1/courses/{course_id}/concepts/addition/regenerate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert repository.regenerated is not None
    assert repository.regenerated[1:] == (course_id, "addition")
