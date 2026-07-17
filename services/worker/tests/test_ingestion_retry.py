from types import SimpleNamespace

from httpx import HTTPError

from worker.ingestion import SourceIngestor, _batches_by_payload_size
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


def test_transient_ingestion_error_leaves_job_queued_for_retry() -> None:
    worker, client, queue = _worker()
    worker.ingestor = SimpleNamespace(ingest_source=_raiser(HTTPError("temporary outage")))

    worker._handle_ingestion(QueueMessage(message_id=1, payload={"source_id": "11111111-1111-1111-1111-111111111111"}))

    assert queue.archived == []
    assert client.update_calls == []


def test_permanent_ingestion_error_archives_and_marks_failed() -> None:
    worker, client, queue = _worker()
    worker.ingestor = SimpleNamespace(ingest_source=_raiser(ValueError("bad state")))

    worker._handle_ingestion(QueueMessage(message_id=2, payload={"source_id": "22222222-2222-2222-2222-222222222222"}))

    assert queue.archived == [("ingestion", 2)]
    assert client.update_calls == [("source_documents", {"status": "failed"})]


def test_chunk_insert_batches_stay_under_the_payload_size_cap() -> None:
    rows = [{"id": str(index), "embedding": "x" * 40_000} for index in range(10)]

    batches = _batches_by_payload_size(rows, max_bytes=100_000)

    assert [row for batch in batches for row in batch] == rows
    assert all(len(batch) <= 2 for batch in batches)
    assert len(batches) == 5


def test_chunk_insert_retries_transport_errors_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("worker.ingestion.time.sleep", lambda _seconds: None)
    ingestor = SourceIngestor.__new__(SourceIngestor)
    attempts: list[int] = []

    class FlakyInsert:
        def insert(self, _batch: list) -> "FlakyInsert":
            return self

        def execute(self) -> SimpleNamespace:
            attempts.append(1)
            if len(attempts) < 3:
                raise HTTPError("bad record mac")
            return SimpleNamespace(data=[])

    ingestor.client = SimpleNamespace(table=lambda _name: FlakyInsert())

    ingestor._insert_chunk_batch([{"id": "chunk"}])

    assert len(attempts) == 3


def test_transient_generation_error_leaves_job_queued_for_retry() -> None:
    worker, client, queue = _worker()
    worker.planner = SimpleNamespace(plan_course=_raiser(HTTPError("temporary outage")))

    worker._handle_generation(
        QueueMessage(message_id=3, payload={"type": "course_planning", "course_id": "33333333-3333-3333-3333-333333333333"})
    )

    assert queue.archived == []


def test_permanent_generation_error_archives() -> None:
    worker, client, queue = _worker()
    worker.planner = SimpleNamespace(plan_course=_raiser(ValueError("bad plan")))

    worker._handle_generation(
        QueueMessage(message_id=4, payload={"type": "course_planning", "course_id": "44444444-4444-4444-4444-444444444444"})
    )

    assert queue.archived == [("generation", 4)]
