from types import SimpleNamespace

from httpx import HTTPError

from worker.lesson_build import LessonBuilder
from worker.queues import QueueMessage
from worker.runner import Worker


class FakeTableQuery:
    def __init__(self, calls: list, table: str) -> None:
        self.calls = calls
        self.table = table
        self.payload: dict | None = None

    def update(self, payload: dict) -> "FakeTableQuery":
        self.payload = payload
        return self

    def select(self, *_args, **_kwargs) -> "FakeTableQuery":
        return self

    def eq(self, *_args, **_kwargs) -> "FakeTableQuery":
        return self

    def in_(self, *_args, **_kwargs) -> "FakeTableQuery":
        return self

    def execute(self) -> SimpleNamespace:
        if self.payload is not None:
            self.calls.append((self.table, self.payload))
        return SimpleNamespace(data=[])


class FakeClient:
    def __init__(self) -> None:
        self.update_calls: list[tuple[str, dict | None]] = []

    def table(self, name: str) -> FakeTableQuery:
        return FakeTableQuery(self.update_calls, name)


class FakeQueue:
    def __init__(self) -> None:
        self.archived: list[tuple[str, int]] = []

    def archive(self, queue: str, message_id: int) -> None:
        self.archived.append((queue, message_id))


def _raiser(error: Exception):
    def raise_error(*_args: object, **_kwargs: object) -> None:
        raise error

    return raise_error


def _worker() -> tuple[Worker, FakeClient, FakeQueue]:
    worker = Worker.__new__(Worker)
    client = FakeClient()
    queue = FakeQueue()
    worker.client = client
    worker.queue = queue
    return worker, client, queue


def test_transient_lesson_build_error_resets_status_and_leaves_job_queued() -> None:
    worker, client, queue = _worker()
    worker.lesson_builder = SimpleNamespace(build_lesson=_raiser(HTTPError("temporary outage")))

    worker._handle_generation(
        QueueMessage(message_id=1, payload={"type": "lesson_build", "lesson_definition_id": "11111111-1111-1111-1111-111111111111"})
    )

    assert queue.archived == []
    assert client.update_calls == []


def test_permanent_lesson_build_error_archives() -> None:
    worker, client, queue = _worker()
    worker.lesson_builder = SimpleNamespace(build_lesson=_raiser(ValueError("bad bundle")))

    worker._handle_generation(
        QueueMessage(message_id=2, payload={"type": "lesson_build", "lesson_definition_id": "22222222-2222-2222-2222-222222222222"})
    )

    assert queue.archived == [("generation", 2)]


class ClaimingClient(FakeClient):
    def rpc(self, function: str, arguments: dict) -> SimpleNamespace:
        assert function == "claim_lesson_build"
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(
                data=[
                    {
                        "lesson_definition_id": arguments["p_lesson_definition_id"],
                        "course_version_id": "version-id",
                        "concept_id": "concept-id",
                        "concept_slug": "jwt-expiry",
                        "concept_title": "JWT expiry",
                        "summary_markdown": "Tokens expire.",
                        "citations_json": ["chunk-a"],
                        "next_revision": 1,
                    }
                ]
            )
        )


def _valid_coding_bundle() -> dict:
    return {
        "schema_version": 2,
        "lesson_content": {
            "title": "Reject expired tokens",
            "explanation_markdown": "Tokens carry an expiry claim that must be checked.",
            "citations": ["chunk-a"],
            "worked_examples": [],
        },
        "workspace": {
            "environment_id": "python-basic",
            "files": [
                {"path": "solution.py", "content": "def is_expired(token):\n    ...\n", "visibility": "visible", "editable_regions": None}
            ],
        },
        "assessment": {
            "visible_tests": [
                {"path": "test_basic.py", "content": "from solution import is_expired\n\ndef test_it():\n    assert is_expired({'exp': 0})\n"}
            ],
            "hidden_tests": [
                {"path": "test_more.py", "content": "from solution import is_expired\n\ndef test_more():\n    assert is_expired({'exp': 0})\n"}
            ],
            "quiz_items": [],
            "hints": [],
            "reference_solution_files": [
                {"path": "solution.py", "content": "def is_expired(token):\n    return token['exp'] < 1\n"}
            ],
        },
    }


class BuildFlowClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.rpc_calls: list[tuple[str, dict]] = []

    def rpc(self, function: str, arguments: dict) -> SimpleNamespace:
        self.rpc_calls.append((function, arguments))
        data = (
            [
                {
                    "lesson_definition_id": arguments["p_lesson_definition_id"],
                    "course_version_id": "version-id",
                    "concept_id": "concept-id",
                    "concept_kind": "coding",
                    "concept_slug": "jwt-expiry",
                    "concept_title": "JWT expiry",
                    "summary_markdown": "Tokens expire.",
                    "citations_json": ["chunk-a"],
                    "next_revision": 1,
                }
            ]
            if function == "claim_lesson_build"
            else []
        )
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))


class ScriptedSandbox:
    """Returns one scripted pass/fail verdict per run_pytest call, in order."""

    def __init__(self, verdicts: list[bool]) -> None:
        self.verdicts = list(verdicts)
        self.calls = 0

    def run_pytest(self, _files: list) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(passed=self.verdicts.pop(0), exit_code=0, output="", timed_out=False)


def test_solutioned_starter_is_regenerated_until_it_fails_the_tests(monkeypatch: object) -> None:
    import worker.lesson_build as lesson_build_module
    from worker.lesson_schema import LessonBundle

    generate_calls: list[str | None] = []

    def fake_generate(*_args: object, feedback: str | None = None, **_kwargs: object) -> LessonBundle:
        generate_calls.append(feedback)
        return LessonBundle.model_validate(_valid_coding_bundle())

    monkeypatch.setattr(lesson_build_module, "generate_lesson_bundle", fake_generate)

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(builder_model="test-model", lesson_build_max_attempts=3, lesson_build_max_tool_calls=8)
    builder.openai = SimpleNamespace()
    # Starter passes on the first bundle (solutioned), fails on the regenerated one,
    # then the reference solution passes its own validation run.
    builder.sandbox = ScriptedSandbox([True, False, True])
    builder.client = BuildFlowClient()

    builder.build_lesson("33333333-3333-3333-3333-333333333333")

    assert len(generate_calls) == 2
    assert generate_calls[0] is None
    assert "already pass every test" in (generate_calls[1] or "")
    assert builder.sandbox.calls == 3
    applied = [arguments for function, arguments in builder.client.rpc_calls if function == "apply_lesson_bundle"]
    assert len(applied) == 1
    assert applied[0]["p_validation_status"] == "validated"


def test_build_lesson_resets_build_status_to_pending_on_retryable_error(monkeypatch: object) -> None:
    import worker.lesson_build as lesson_build_module

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(builder_model="test-model")
    builder.openai = SimpleNamespace()
    builder.sandbox = SimpleNamespace()
    builder.client = ClaimingClient()

    def _raise_transient(*_args: object, **_kwargs: object) -> None:
        raise HTTPError("temporary outage")

    monkeypatch.setattr(lesson_build_module, "generate_lesson_bundle", _raise_transient)

    try:
        builder.build_lesson("lesson-id")
    except HTTPError:
        pass

    assert builder.client.update_calls == [("lesson_definitions", {"build_status": "pending"})]
