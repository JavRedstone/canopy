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

    def eq(self, *_args, **_kwargs) -> "FakeTableQuery":
        return self

    def execute(self) -> SimpleNamespace:
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


def test_transient_ingestion_error_leaves_job_queued_for_retry(monkeypatch: object) -> None:
    worker, client, queue = _worker()
    monkeypatch.setattr(worker, "ingest_source", lambda source_id: (_ for _ in ()).throw(HTTPError("temporary outage")))

    worker._handle_ingestion(QueueMessage(message_id=1, payload={"source_id": "11111111-1111-1111-1111-111111111111"}))

    assert queue.archived == []
    assert client.update_calls == []


def test_permanent_ingestion_error_archives_and_marks_failed(monkeypatch: object) -> None:
    worker, client, queue = _worker()
    monkeypatch.setattr(worker, "ingest_source", lambda source_id: (_ for _ in ()).throw(ValueError("bad state")))

    worker._handle_ingestion(QueueMessage(message_id=2, payload={"source_id": "22222222-2222-2222-2222-222222222222"}))

    assert queue.archived == [("ingestion", 2)]
    assert client.update_calls == [("source_documents", {"status": "failed"})]


def test_transient_generation_error_leaves_job_queued_for_retry(monkeypatch: object) -> None:
    worker, client, queue = _worker()
    monkeypatch.setattr(worker, "plan_course", lambda course_id: (_ for _ in ()).throw(HTTPError("temporary outage")))

    worker._handle_generation(
        QueueMessage(message_id=3, payload={"type": "course_planning", "course_id": "33333333-3333-3333-3333-333333333333"})
    )

    assert queue.archived == []


def test_permanent_generation_error_archives(monkeypatch: object) -> None:
    worker, client, queue = _worker()
    monkeypatch.setattr(worker, "plan_course", lambda course_id: (_ for _ in ()).throw(ValueError("bad plan")))

    worker._handle_generation(
        QueueMessage(message_id=4, payload={"type": "course_planning", "course_id": "44444444-4444-4444-4444-444444444444"})
    )

    assert queue.archived == [("generation", 4)]
