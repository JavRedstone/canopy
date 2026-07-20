"""Regression test for a real bug: SupabaseCourseRepository.get_course() (the single-course
fetch used by the course detail page and by certificate()) omitted the lesson-progress query
that list_courses() already did, so lessons_completed/lessons_total silently read as (0, 0)
no matter how much of the course was actually done -- which made the completion certificate
permanently unreachable, since it 409s whenever lessons_total == 0."""

from uuid import uuid4

from app.repository import SupabaseCourseRepository


class FakeQuery:
    """A chainable stand-in for postgrest's query builder. select/eq/in_/order return self;
    execute yields the pre-seeded rows for whichever table this query was built from.
    insert() appends to the table and echoes the row back, like postgrest's default
    return=representation behavior."""

    def __init__(self, table: "FakeTable") -> None:
        self._table = table
        self._rows: list[dict] = []

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        self._rows = self._table.select_rows
        return self

    def eq(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def in_(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def order(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def insert(self, payload: dict) -> "FakeQuery":
        row = {"id": str(uuid4()), "issued_at": "2026-07-19T00:00:00Z", **payload}
        self._table.select_rows.append(row)
        self._rows = [row]
        return self

    def execute(self) -> "FakeQuery":
        return self

    @property
    def data(self) -> list[dict]:
        return self._rows


class FakeTable:
    def __init__(self, select_rows: list[dict] | None = None) -> None:
        self.select_rows = select_rows or []

    def query(self) -> FakeQuery:
        return FakeQuery(self)


class FakeClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self.tables = {name: FakeTable(rows) for name, rows in tables.items()}

    def table(self, name: str) -> FakeQuery:
        return self.tables.setdefault(name, FakeTable()).query()


def _client(*, completed_revision_ids: list[str], course_id: str) -> FakeClient:
    return FakeClient(
        {
            "courses": [
                {
                    "id": course_id, "title": "ML Basics", "goal": "Learn it", "status": "ready",
                    "active_version_id": "version-1", "updated_at": "2026-07-19T00:00:00Z",
                    "quiz_max_attempts": 3, "lesson_min": 4, "lesson_max": 8, "language": "python",
                    "is_shared": False,
                }
            ],
            "course_versions": [{"id": "version-1", "version": 1}],
            "modules": [{"id": "module-1", "position": 1, "title": "Module 1"}],
            "concepts": [
                {"id": "concept-1", "slug": "concept-1", "title": "Concept One", "kind": "conceptual"},
                {"id": "concept-2", "slug": "concept-2", "title": "Concept Two", "kind": "conceptual"},
            ],
            "lesson_definitions": [
                {"id": "def-1", "course_version_id": "version-1", "module_id": "module-1", "concept_id": "concept-1"},
                {"id": "def-2", "course_version_id": "version-1", "module_id": "module-1", "concept_id": "concept-2"},
            ],
            "lesson_revisions": [
                {"id": "rev-1", "lesson_definition_id": "def-1"},
                {"id": "rev-2", "lesson_definition_id": "def-2"},
            ],
            "learner_lesson_assignments": [
                {"lesson_revision_id": revision_id} for revision_id in completed_revision_ids
            ],
        }
    )


def test_get_course_reports_real_lesson_progress_not_always_zero() -> None:
    course_id = uuid4()
    client = _client(completed_revision_ids=["rev-1", "rev-2"], course_id=str(course_id))
    repo = SupabaseCourseRepository(client)

    summary = repo.get_course(uuid4(), course_id)

    assert summary.lessons_completed == 2
    assert summary.lessons_total == 2


def test_get_course_reports_partial_progress() -> None:
    course_id = uuid4()
    client = _client(completed_revision_ids=["rev-1"], course_id=str(course_id))
    repo = SupabaseCourseRepository(client)

    summary = repo.get_course(uuid4(), course_id)

    assert summary.lessons_completed == 1
    assert summary.lessons_total == 2


def test_certificate_is_reachable_once_get_course_reports_full_progress() -> None:
    # The bug this guards: certificate() calls get_course() and 409s whenever
    # lessons_total == 0, which is exactly what the stale get_course() always reported.
    course_id = uuid4()
    client = _client(completed_revision_ids=["rev-1", "rev-2"], course_id=str(course_id))
    client.tables["profiles"] = FakeTable([{"email": "learner@example.com", "display_name": "Ada Lovelace"}])
    repo = SupabaseCourseRepository(client)
    owner = uuid4()

    certificate = repo.certificate(owner, course_id)

    assert certificate.course_title == "ML Basics"
    assert certificate.learner_name == "Ada Lovelace"
    certificate_row_id = client.tables["certificates"].select_rows[0]["id"]
    assert certificate.verify_url.endswith(f"/certificates/{certificate_row_id}")
    assert certificate.skills == ["Module 1"]
    assert certificate.estimated_hours > 0


def test_certificate_reuses_the_same_row_and_issued_at_on_a_second_call() -> None:
    # A certificate's "Issued <date>" must be a fixed historical fact, not recomputed
    # (i.e. read as "today") on every view.
    course_id = uuid4()
    client = _client(completed_revision_ids=["rev-1", "rev-2"], course_id=str(course_id))
    client.tables["profiles"] = FakeTable([{"email": "learner@example.com", "display_name": None}])
    repo = SupabaseCourseRepository(client)
    owner = uuid4()

    first = repo.certificate(owner, course_id)
    second = repo.certificate(owner, course_id)

    assert first.verify_url == second.verify_url
    assert first.issued_at == second.issued_at
    assert len(client.tables["certificates"].select_rows) == 1
    # No display name set -- falls back to the email rather than showing nothing.
    assert first.learner_name == "learner@example.com"
