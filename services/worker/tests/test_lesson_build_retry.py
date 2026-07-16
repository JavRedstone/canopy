from types import SimpleNamespace

from httpx import HTTPError

from worker.ingestion import IngestionWorker, QueueMessage


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


def _worker() -> tuple[IngestionWorker, FakeClient, FakeQueue]:
    worker = IngestionWorker.__new__(IngestionWorker)
    client = FakeClient()
    queue = FakeQueue()
    worker.client = client
    worker.queue = queue
    return worker, client, queue


def test_transient_lesson_build_error_resets_status_and_leaves_job_queued(monkeypatch: object) -> None:
    worker, client, queue = _worker()
    monkeypatch.setattr(worker, "build_lesson", lambda lesson_definition_id: (_ for _ in ()).throw(HTTPError("temporary outage")))

    worker._handle_generation(
        QueueMessage(message_id=1, payload={"type": "lesson_build", "lesson_definition_id": "11111111-1111-1111-1111-111111111111"})
    )

    assert queue.archived == []
    assert client.update_calls == []


def test_permanent_lesson_build_error_archives(monkeypatch: object) -> None:
    worker, client, queue = _worker()
    monkeypatch.setattr(worker, "build_lesson", lambda lesson_definition_id: (_ for _ in ()).throw(ValueError("bad bundle")))

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


def test_build_lesson_resets_build_status_to_pending_on_retryable_error(monkeypatch: object) -> None:
    import worker.ingestion as ingestion_module

    worker = IngestionWorker.__new__(IngestionWorker)
    worker.settings = SimpleNamespace(builder_model="test-model")
    worker.openai = SimpleNamespace()
    worker.sandbox = SimpleNamespace()
    worker.client = ClaimingClient()

    def _raise_transient(*_args: object, **_kwargs: object) -> None:
        raise HTTPError("temporary outage")

    monkeypatch.setattr(ingestion_module, "generate_lesson_bundle", _raise_transient)

    try:
        worker.build_lesson("lesson-id")
    except HTTPError:
        pass

    assert worker.client.update_calls == [("lesson_definitions", {"build_status": "pending"})]
