"""Verifies the citation-excerpt lookup: source_chunks -> source_document_versions ->
course_sources, with the course_sources match being what actually proves a citation
belongs to the requested course (not merely to a source the caller owns elsewhere)."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.repository import MemoryCourseRepository, SupabaseCourseRepository
from app.schemas import CreateCourseRequest


class FakeQuery:
    def __init__(self, table: "FakeTable") -> None:
        self._table = table

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def eq(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def execute(self) -> "FakeQuery":
        return self

    @property
    def data(self) -> list[dict]:
        return self._table.select_rows


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


def _client(*, course_sources: list[dict]) -> FakeClient:
    return FakeClient(
        {
            "courses": [{"id": "course-1"}],
            "source_chunks": [
                {"id": "chunk-1", "content": "def validate_hold(...): ...", "section": "authorization.py", "page_number": None, "document_version_id": "version-1"}
            ],
            "source_document_versions": [{"document_id": "document-1"}],
            "course_sources": course_sources,
        }
    )


def test_citation_excerpt_returns_the_chunk_content_and_source_filename() -> None:
    client = _client(course_sources=[{"source_documents": {"filename": "authorization.py"}}])
    repo = SupabaseCourseRepository(client)

    result = repo.citation_excerpt(uuid4(), uuid4(), uuid4())

    assert result.filename == "authorization.py"
    assert result.section == "authorization.py"
    assert result.content == "def validate_hold(...): ..."


def test_citation_excerpt_404s_when_the_source_is_not_attached_to_this_course() -> None:
    # The chunk and its source exist, but course_sources has no row for this course --
    # i.e. the caller owns the source elsewhere but it isn't part of this course.
    client = _client(course_sources=[])
    repo = SupabaseCourseRepository(client)

    with pytest.raises(HTTPException) as exc_info:
        repo.citation_excerpt(uuid4(), uuid4(), uuid4())
    assert exc_info.value.status_code == 404


def test_memory_repository_citation_excerpt_always_404s() -> None:
    repo = MemoryCourseRepository()
    owner = uuid4()
    created = repo.create_course(owner, CreateCourseRequest(title="Test", goal="Test goal"))

    with pytest.raises(HTTPException) as exc_info:
        repo.citation_excerpt(owner, created.id, uuid4())
    assert exc_info.value.status_code == 404
