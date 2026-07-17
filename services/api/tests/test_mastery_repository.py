"""Verifies the Supabase repository's observation write path -- the read-modify-write that
turns a graded result into a BKT observation + a rolled-forward mastery estimate -- against
a fake fluent client, so the glue is checked without a live database."""

from uuid import uuid4

from postgrest.exceptions import APIError

from app.mastery import DEFAULT_PARAMS, bkt_update
from app.repository import SupabaseCourseRepository


class FakeQuery:
    """A chainable stand-in for postgrest's query builder. select/eq return self; execute
    yields the pre-seeded rows. insert/upsert record their payload for assertions."""

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
        if self._table.raise_on_write:
            raise self._table.raise_on_write
        self._table.inserted.append(payload)
        return self

    def upsert(self, payload: dict, **kwargs) -> "FakeQuery":
        if self._table.raise_on_write:
            raise self._table.raise_on_write
        self._table.upserted.append((payload, kwargs))
        return self

    def execute(self) -> "FakeQuery":
        return self

    @property
    def data(self) -> list[dict]:
        return self._rows


class FakeTable:
    def __init__(self) -> None:
        self.select_rows: list[dict] = []
        self.inserted: list[dict] = []
        self.upserted: list[tuple[dict, dict]] = []
        self.raise_on_write: Exception | None = None

    def query(self) -> FakeQuery:
        return FakeQuery(self)


class FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeQuery:
        return self.tables.setdefault(name, FakeTable()).query()


def _api_error() -> APIError:
    return APIError({"message": "boom", "code": "500"})


def test_first_observation_seeds_mastery_from_the_prior_and_updates_it() -> None:
    client = FakeClient()
    repo = SupabaseCourseRepository(client)
    owner, concept = uuid4(), str(uuid4())

    repo._record_observation(owner, concept, "quiz_mcq", correct=True)

    observation = client.tables["observations"].inserted[0]
    assert observation["user_id"] == str(owner)
    assert observation["concept_id"] == concept
    assert observation["track"] == "understand"
    assert observation["assessment_kind"] == "quiz_mcq"
    assert observation["result"] == "correct"

    upsert_payload, upsert_kwargs = client.tables["mastery"].upserted[0]
    expected = bkt_update(DEFAULT_PARAMS["quiz_mcq"].p_l0, correct=True, params=DEFAULT_PARAMS["quiz_mcq"])
    assert upsert_payload["p_l"] == expected
    assert upsert_payload["opportunities"] == 1
    assert upsert_payload["track"] == "understand"
    # Must upsert on the mastery primary key, not blindly insert a duplicate row.
    assert upsert_kwargs["on_conflict"] == "user_id,concept_id,track"


def test_subsequent_observation_advances_from_the_stored_estimate() -> None:
    client = FakeClient()
    client.tables["mastery"] = FakeTable()
    client.tables["mastery"].select_rows = [{"p_l": 0.5, "opportunities": 2}]
    repo = SupabaseCourseRepository(client)

    repo._record_observation(uuid4(), str(uuid4()), "coding_submission", correct=False)

    upsert_payload, _ = client.tables["mastery"].upserted[0]
    expected = bkt_update(0.5, correct=False, params=DEFAULT_PARAMS["coding_submission"])
    assert upsert_payload["p_l"] == expected
    assert upsert_payload["opportunities"] == 3
    assert client.tables["observations"].inserted[0]["track"] == "apply"


def test_observation_write_failure_is_swallowed_not_raised() -> None:
    client = FakeClient()
    observations = FakeTable()
    observations.raise_on_write = _api_error()
    client.tables["observations"] = observations
    repo = SupabaseCourseRepository(client)

    # Best-effort: the derived answer is already durable, so a mastery hiccup must not raise.
    repo._record_observation(uuid4(), str(uuid4()), "quiz_fill", correct=True)
    assert observations.inserted == []


def test_prerequisite_concept_maps_mastery_and_flags_a_shaky_prereq() -> None:
    concept = {"id": "c1", "slug": "headers", "title": "HTTP headers", "kind": "conceptual"}
    mastery = {("c1", "understand"): {"p_l": 0.4, "opportunities": 3}}

    entry = SupabaseCourseRepository._prerequisite_concept(concept, mastery)

    assert entry.slug == "headers"
    assert entry.p_understand == 0.4
    assert entry.needs_review is True  # practiced (3 obs) and below the review bar
    assert entry.mastered is False


def test_prerequisite_concept_does_not_flag_a_mastered_prereq() -> None:
    concept = {"id": "c2", "slug": "token-shape", "title": "Token shape", "kind": "coding"}
    mastery = {("c2", "apply"): {"p_l": 0.97, "opportunities": 4}}

    entry = SupabaseCourseRepository._prerequisite_concept(concept, mastery)

    assert entry.p_apply == 0.97
    assert entry.mastered is True
    assert entry.needs_review is False


def test_prerequisite_concept_with_no_observations_is_not_flagged() -> None:
    concept = {"id": "c3", "slug": "intro", "title": "Intro", "kind": "conceptual"}

    entry = SupabaseCourseRepository._prerequisite_concept(concept, {})

    assert entry.p_understand is None
    assert entry.needs_review is False
    assert entry.mastered is False
