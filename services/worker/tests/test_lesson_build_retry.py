import json
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


def _valid_content() -> dict:
    return {
        "lesson_content": {
            "title": "Reject expired tokens",
            "explanation_markdown": "Tokens carry an expiry claim that must be checked.",
            "citations": ["chunk-a"],
            "worked_examples": [],
        },
        "quiz_items": [],
        "hints": [],
    }


def _valid_artifacts() -> dict:
    return {
        "workspace": {
            "environment_id": "python-basic",
            "files": [
                {"path": "solution.py", "content": "def is_expired(token):\n    ...\n", "visibility": "visible", "editable_regions": None}
            ],
        },
        "visible_tests": [
            {"path": "test_basic.py", "content": "from solution import is_expired\n\ndef test_it():\n    assert is_expired({'exp': 0})\n"}
        ],
        "hidden_tests": [
            {"path": "test_more.py", "content": "from solution import is_expired\n\ndef test_more():\n    assert is_expired({'exp': 0})\n"}
        ],
        "reference_solution_files": [
            {"path": "solution.py", "content": "def is_expired(token):\n    return token['exp'] < 1\n"}
        ],
    }


class BuildFlowClient(FakeClient):
    def __init__(self, pending_content_json: dict | None = None) -> None:
        super().__init__()
        self.rpc_calls: list[tuple[str, dict]] = []
        self.pending_content_json = pending_content_json

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
                    "pending_content_json": self.pending_content_json,
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


def _tool_call(name: str, call_id: str, **arguments: object) -> SimpleNamespace:
    return SimpleNamespace(type="function_call", name=name, call_id=call_id, arguments=json.dumps(arguments))


class FakeToolResponses:
    """Scripted responses for the strip_starter_solution tool loop specifically."""

    def __init__(self, outputs: list[list[SimpleNamespace]]) -> None:
        self._outputs = list(outputs)
        self.calls = 0

    def create(self, **_kwargs: object) -> SimpleNamespace:
        self.calls += 1
        output = self._outputs.pop(0) if self._outputs else []
        return SimpleNamespace(output=output)


def test_solutioned_starter_is_stripped_by_a_targeted_repair_loop(monkeypatch: object) -> None:
    import worker.lesson_build as lesson_build_module
    from worker.lesson_schema import CodingArtifactsBundle, LessonContentBundle

    def fake_content(*_args: object, **_kwargs: object) -> LessonContentBundle:
        return LessonContentBundle.model_validate(_valid_content())

    def fake_artifacts(*_args: object, **_kwargs: object) -> CodingArtifactsBundle:
        return CodingArtifactsBundle.model_validate(_valid_artifacts())

    monkeypatch.setattr(lesson_build_module, "generate_lesson_content", fake_content)
    monkeypatch.setattr(lesson_build_module, "generate_coding_artifacts", fake_artifacts)

    tool_responses = FakeToolResponses(
        outputs=[
            [_tool_call("write_file", "c1", path="solution.py", content="def is_expired(token):\n    ...\n")],
            [],  # model stops calling tools after one patch
        ]
    )

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(
        builder_model="test-model", lesson_build_max_attempts=3, lesson_build_max_tool_calls=8, queue_visibility_seconds=300
    )
    builder.openai = SimpleNamespace(responses=tool_responses)
    # Starter passes on the generated artifacts (solutioned); the targeted strip loop's
    # final re-verification then fails (correctly stubby again); the reference solution
    # passes its own validation run with no repair needed.
    builder.sandbox = ScriptedSandbox([True, False, True])
    builder.client = BuildFlowClient()

    builder.build_lesson("33333333-3333-3333-3333-333333333333")

    assert tool_responses.calls == 2
    assert builder.sandbox.calls == 3
    applied = [arguments for function, arguments in builder.client.rpc_calls if function == "apply_lesson_bundle"]
    assert len(applied) == 1
    assert applied[0]["p_validation_status"] == "validated"
    assert applied[0]["p_build_error"] is None


def test_checkpointed_content_is_reused_without_regenerating(monkeypatch: object) -> None:
    # Simulates resuming after a worker restart mid-build: the claim carries content
    # generated (and checkpointed) by the previous, interrupted attempt.
    import worker.lesson_build as lesson_build_module
    from worker.lesson_schema import CodingArtifactsBundle, LessonContentBundle

    content_calls = 0

    def fake_content(*_args: object, **_kwargs: object) -> LessonContentBundle:
        nonlocal content_calls
        content_calls += 1
        return LessonContentBundle.model_validate(_valid_content())

    def fake_artifacts(*_args: object, **_kwargs: object) -> CodingArtifactsBundle:
        return CodingArtifactsBundle.model_validate(_valid_artifacts())

    monkeypatch.setattr(lesson_build_module, "generate_lesson_content", fake_content)
    monkeypatch.setattr(lesson_build_module, "generate_coding_artifacts", fake_artifacts)

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(
        builder_model="test-model", lesson_build_max_attempts=3, lesson_build_max_tool_calls=8, queue_visibility_seconds=300
    )
    builder.openai = SimpleNamespace()
    builder.sandbox = ScriptedSandbox([False, True])  # starter correctly fails; reference solution passes
    builder.client = BuildFlowClient(pending_content_json=_valid_content())

    builder.build_lesson("55555555-5555-5555-5555-555555555555")

    assert content_calls == 0  # the checkpoint was used instead of calling generate_lesson_content
    checkpoint_saves = [f for f, _ in builder.client.rpc_calls if f == "save_lesson_content_checkpoint"]
    assert checkpoint_saves == []  # re-saving an already-checkpointed value would be pointless
    applied = [arguments for function, arguments in builder.client.rpc_calls if function == "apply_lesson_bundle"]
    assert applied[0]["p_validation_status"] == "validated"


def test_content_is_checkpointed_after_generating_when_no_checkpoint_exists(monkeypatch: object) -> None:
    import worker.lesson_build as lesson_build_module
    from worker.lesson_schema import CodingArtifactsBundle, LessonContentBundle

    def fake_content(*_args: object, **_kwargs: object) -> LessonContentBundle:
        return LessonContentBundle.model_validate(_valid_content())

    def fake_artifacts(*_args: object, **_kwargs: object) -> CodingArtifactsBundle:
        return CodingArtifactsBundle.model_validate(_valid_artifacts())

    monkeypatch.setattr(lesson_build_module, "generate_lesson_content", fake_content)
    monkeypatch.setattr(lesson_build_module, "generate_coding_artifacts", fake_artifacts)

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(
        builder_model="test-model", lesson_build_max_attempts=3, lesson_build_max_tool_calls=8, queue_visibility_seconds=300
    )
    builder.openai = SimpleNamespace()
    builder.sandbox = ScriptedSandbox([False, True])  # starter correctly fails; reference solution passes
    builder.client = BuildFlowClient()  # no pending_content_json

    builder.build_lesson("66666666-6666-6666-6666-666666666666")

    checkpoint_saves = [arguments for function, arguments in builder.client.rpc_calls if function == "save_lesson_content_checkpoint"]
    assert len(checkpoint_saves) == 1
    assert checkpoint_saves[0]["p_lesson_definition_id"] == "66666666-6666-6666-6666-666666666666"
    assert checkpoint_saves[0]["p_content"]["lesson_content"]["title"] == _valid_content()["lesson_content"]["title"]


def test_starter_strip_loop_cannot_touch_the_reference_solution_or_tests(monkeypatch: object) -> None:
    # The model tries to cheat by rewriting the hidden test instead of the starter --
    # the write must be rejected, and since nothing legitimate changed, the starter still
    # passes after exhausting every attempt, so the build should raise rather than ship a
    # lesson whose starter has nothing left to implement.
    import worker.lesson_build as lesson_build_module
    from worker.lesson_schema import CodingArtifactsBundle, LessonContentBundle

    def fake_content(*_args: object, **_kwargs: object) -> LessonContentBundle:
        return LessonContentBundle.model_validate(_valid_content())

    def fake_artifacts(*_args: object, **_kwargs: object) -> CodingArtifactsBundle:
        return CodingArtifactsBundle.model_validate(_valid_artifacts())

    monkeypatch.setattr(lesson_build_module, "generate_lesson_content", fake_content)
    monkeypatch.setattr(lesson_build_module, "generate_coding_artifacts", fake_artifacts)

    cheat_attempt = [_tool_call("write_file", "c1", path="test_basic.py", content="def test_it():\n    pass\n")]
    tool_responses = FakeToolResponses(outputs=[cheat_attempt, []] * 3)

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(
        builder_model="test-model", lesson_build_max_attempts=3, lesson_build_max_tool_calls=8, queue_visibility_seconds=300
    )
    builder.openai = SimpleNamespace(responses=tool_responses)
    # Starter always passes: the generated artifacts pass once, and every re-verification
    # after a rejected write still passes since nothing legitimate ever changed.
    builder.sandbox = ScriptedSandbox([True, True, True])
    builder.client = BuildFlowClient()

    try:
        builder.build_lesson("44444444-4444-4444-4444-444444444444")
        raised = False
    except ValueError:
        raised = True

    assert raised
    applied = [arguments for function, arguments in builder.client.rpc_calls if function == "apply_lesson_bundle"]
    assert applied == []  # never reached storage -- the exception path handled it instead
    failed_updates = [payload for table, payload in builder.client.update_calls if table == "lesson_definitions"]
    assert failed_updates[-1]["build_status"] == "failed"
    assert "targeted repair attempts" in failed_updates[-1]["build_error"]


def test_build_lesson_resets_build_status_to_pending_on_retryable_error(monkeypatch: object) -> None:
    import worker.lesson_build as lesson_build_module

    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(builder_model="test-model", queue_visibility_seconds=300)
    builder.openai = SimpleNamespace()
    builder.sandbox = SimpleNamespace()
    builder.client = ClaimingClient()

    def _raise_transient(*_args: object, **_kwargs: object) -> None:
        raise HTTPError("temporary outage")

    monkeypatch.setattr(lesson_build_module, "generate_lesson_content", _raise_transient)

    try:
        builder.build_lesson("lesson-id")
    except HTTPError:
        pass

    assert builder.client.update_calls == [("lesson_definitions", {"build_status": "pending"})]


class StatusQuery:
    def __init__(self, build_status: str) -> None:
        self.build_status = build_status

    def select(self, *_args: object, **_kwargs: object) -> "StatusQuery":
        return self

    def eq(self, *_args: object, **_kwargs: object) -> "StatusQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[{"build_status": self.build_status}])


class ClaimEmptyClient:
    """A claim that never matches (the row is already 'building' or 'built'), as happens
    when a redelivered queue message arrives for a job someone else already claimed."""

    def __init__(self, build_status: str) -> None:
        self.build_status = build_status

    def rpc(self, function: str, _arguments: dict) -> SimpleNamespace:
        assert function == "claim_lesson_build"
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))

    def table(self, name: str) -> StatusQuery:
        assert name == "lesson_definitions"
        return StatusQuery(self.build_status)


def test_build_lesson_reports_unresolved_when_another_attempt_still_holds_the_claim() -> None:
    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(queue_visibility_seconds=300)
    builder.client = ClaimEmptyClient("building")

    assert builder.build_lesson("lesson-id") is False


def test_build_lesson_reports_resolved_when_another_attempt_already_finished() -> None:
    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(queue_visibility_seconds=300)
    builder.client = ClaimEmptyClient("built")

    assert builder.build_lesson("lesson-id") is True


def test_lesson_build_still_in_flight_leaves_job_queued() -> None:
    worker, _client, queue = _worker()
    worker.lesson_builder = SimpleNamespace(build_lesson=lambda _id: False)

    worker._handle_generation(
        QueueMessage(message_id=5, payload={"type": "lesson_build", "lesson_definition_id": "55555555-5555-5555-5555-555555555555"})
    )

    assert queue.archived == []


def test_lesson_build_resolved_elsewhere_archives() -> None:
    worker, _client, queue = _worker()
    worker.lesson_builder = SimpleNamespace(build_lesson=lambda _id: True)

    worker._handle_generation(
        QueueMessage(message_id=6, payload={"type": "lesson_build", "lesson_definition_id": "66666666-6666-6666-6666-666666666666"})
    )

    assert queue.archived == [("generation", 6)]
