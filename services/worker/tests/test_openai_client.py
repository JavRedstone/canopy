from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from worker.ingestion import SourceIngestor
from worker.llm import LLMGatewayClient, LLMValidationError
from worker.main import _build_llm_client
from worker.planner import CourseOutline, ModuleConcepts
from worker.planning import PLAN_VALIDATION_ATTEMPTS, CoursePlanner


def _outline_dict(modules: list[dict] | None = None) -> dict:
    return {
        "course_title": "Authentication",
        "source_set_hash": "source-hash",
        "audience": "Developers new to authentication.",
        "objectives": ["Understand tokens", "Validate requests safely"],
        "language": "python",
        "modules": modules or [{"id": "basics", "title": "Basics", "focus": "Token fundamentals.", "lesson_count": 6}],
    }


def _module_concept_entries(citations: list[str] | None = None) -> list[dict]:
    """Six concepts (3 lectures, 2 labs, 1 assessment, in that order) -- the shape the
    planner prompt guides toward (not a hard requirement), matching the default
    six-lesson module from _outline_dict()."""
    cites = ["chunk-id"] if citations is None else citations
    kinds = ["conceptual", "conceptual", "conceptual", "coding", "coding", "assessment"]
    return [
        {
            "id": f"concept-{index}",
            "title": f"Concept {index}",
            "kind": kind,
            "summary_markdown": f"Concept {index} summary.",
            "prerequisites": [],
            "citations": list(cites),
        }
        for index, kind in enumerate(kinds)
    ]


class FakeResponse:
    def __init__(self, data: dict[str, object]) -> None:
        self.data = data
        self.raised = False

    def raise_for_status(self) -> None:
        self.raised = True

    def json(self) -> dict[str, object]:
        return self.data


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(index), 0.5, 0.25]) for index in range(len(kwargs["input"]))]
        )


class FakeResponses:
    """Returns one queued parsed output per `.parse()` call, in order."""

    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.outputs.pop(0))


class FakeRequest:
    def __init__(self, data: list[dict[str, object]]) -> None:
        self.data = data

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class FakeTable:
    """Accepts the status-update chain plan_course runs when a plan fails."""

    def update(self, *args: object, **kwargs: object) -> "FakeTable":
        return self

    def eq(self, *args: object, **kwargs: object) -> "FakeTable":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[])


class FakePlanningClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def table(self, name: str) -> FakeTable:
        return FakeTable()

    def rpc(self, function: str, arguments: dict[str, object]) -> FakeRequest:
        self.calls.append((function, arguments))
        if function == "claim_course_planning":
            return FakeRequest(
                [
                    {
                        "course_version_id": "version-id",
                        "goal": "Learn authentication",
                        "source_set_hash": "source-hash",
                        "lesson_min": 1,
                        "lesson_max": 6,
                    }
                ]
            )
        if function == "apply_course_skeleton":
            modules = arguments["p_modules"]
            return FakeRequest([{"module_id": f"module-{index}", "module_position": index + 1} for index in range(len(modules))])
        return FakeRequest([])


def _planner_with(responses: "FakeResponses", chunks: list[dict[str, object]]) -> CoursePlanner:
    """A CoursePlanner whose retrieval is stubbed to return ``chunks`` for every query.

    An empty ``chunks`` list stands in for a course with no sources (goal-only planning).
    """
    worker = CoursePlanner.__new__(CoursePlanner)
    worker.settings = SimpleNamespace(
        outline_model="course_outline",
        module_concepts_model="module_concepts",
        embedding_model="embedding",
        embedding_dimensions=3,
        planner_context_chunk_limit=40,
        planner_module_context_chunk_limit=16,
        queue_visibility_seconds=300,
    )
    worker.client = FakePlanningClient()
    worker.openai = SimpleNamespace(responses=responses)
    worker._source_version_ids = lambda _course_id: (["version-a"] if chunks else [])
    worker._retrieve = lambda _version_ids, _query, _limit: list(chunks)
    return worker


def test_build_llm_client_uses_internal_gateway_configuration() -> None:
    settings = SimpleNamespace(
        llm_gateway_url="http://llm-gateway:8010/",
        internal_service_token=SecretStr("internal-token"),
    )

    client = _build_llm_client(settings)

    assert client.base_url == "http://llm-gateway:8010"
    assert client.internal_service_token == "internal-token"


def test_gateway_client_sends_schema_and_validates_structured_output() -> None:
    http = FakeHttpClient([FakeResponse({"output": _outline_dict()})])
    client = LLMGatewayClient("http://gateway", internal_service_token="secret", http_client=http)

    result = client.responses.parse(
        model="course_outline",
        input=[{"role": "user", "content": "Build a course."}],
        text_format=CourseOutline,
    )

    assert result.output_parsed.course_title == "Authentication"
    assert http.calls == [
        {
            "url": "http://gateway/internal/v1/structured",
            "headers": {"X-Internal-Service-Token": "secret"},
            "json": {
                "task": "course_outline",
                "input": [{"role": "user", "content": "Build a course."}],
                "schema_name": "CourseOutline",
                "schema": CourseOutline.model_json_schema(),
            },
        }
    ]


def test_structured_output_failing_validation_is_retried_with_feedback() -> None:
    invalid = {**_outline_dict(), "modules": []}
    valid = _outline_dict()
    http = FakeHttpClient([FakeResponse({"output": invalid}), FakeResponse({"output": valid})])
    client = LLMGatewayClient("http://gateway", internal_service_token=None, http_client=http)

    result = client.responses.parse(
        model="course_outline",
        input=[{"role": "user", "content": "Build a course."}],
        text_format=CourseOutline,
    )

    assert result.output_parsed.modules[0].id == "basics"
    assert len(http.calls) == 2
    retry_input = http.calls[1]["json"]["input"]
    assert retry_input[0] == {"role": "user", "content": "Build a course."}
    assert retry_input[1]["role"] == "assistant"
    assert retry_input[2]["role"] == "user"
    assert "rejected by validation" in retry_input[2]["content"]


def test_structured_output_failing_validation_repeatedly_is_not_retryable() -> None:
    invalid = {**_outline_dict(), "modules": []}
    http = FakeHttpClient([FakeResponse({"output": invalid}) for _ in range(3)])
    client = LLMGatewayClient("http://gateway", internal_service_token=None, http_client=http)

    with pytest.raises(LLMValidationError):
        client.responses.parse(
            model="course_outline",
            input=[{"role": "user", "content": "Build a course."}],
            text_format=CourseOutline,
        )

    assert len(http.calls) == 3


def test_embedding_request_uses_gateway_task() -> None:
    embeddings = FakeEmbeddings()
    ingestor = SourceIngestor.__new__(SourceIngestor)
    ingestor.settings = SimpleNamespace(embedding_batch_size=2, embedding_model="embedding", embedding_dimensions=3)
    ingestor.openai = SimpleNamespace(embeddings=embeddings)

    result = ingestor._embed(["first", "second", "third"])

    assert [call["model"] for call in embeddings.calls] == ["embedding", "embedding"]
    assert [call["input"] for call in embeddings.calls] == [["first", "second"], ["third"]]
    assert result == [[0.0, 0.5, 0.25], [1.0, 0.5, 0.25], [0.0, 0.5, 0.25]]


def test_planner_requests_use_outline_then_concepts_tasks() -> None:
    outline = CourseOutline.model_validate(_outline_dict())
    module_concepts = ModuleConcepts.model_validate({"concepts": _module_concept_entries()})
    responses = FakeResponses([outline, module_concepts])
    worker = _planner_with(responses, [{"id": "chunk-id", "content": "Source content."}])

    worker.plan_course("course-id")

    assert [call["model"] for call in responses.calls] == ["course_outline", "module_concepts"]
    assert [call[0] for call in worker.client.calls] == [
        "claim_course_planning",
        "reset_course_planning",
        "apply_course_skeleton",
        "apply_module_concepts",
        "finalize_course_plan",
    ]


def test_module_concepts_citing_unknown_chunk_are_regenerated_with_feedback() -> None:
    outline = CourseOutline.model_validate(_outline_dict())
    bad_concepts = ModuleConcepts.model_validate({"concepts": _module_concept_entries(citations=["bogus-chunk"])})
    good_concepts = ModuleConcepts.model_validate({"concepts": _module_concept_entries(citations=["chunk-id"])})
    responses = FakeResponses([outline, bad_concepts, good_concepts])
    worker = _planner_with(responses, [{"id": "chunk-id", "content": "Source content."}])

    worker.plan_course("course-id")

    assert len(responses.calls) == 3
    feedback_message = responses.calls[2]["input"][-1]
    assert feedback_message["role"] == "user"
    assert "rejected" in feedback_message["content"]
    assert "outside the source context" in feedback_message["content"]
    assert worker.client.calls[-1][0] == "finalize_course_plan"


def test_plan_fails_when_concepts_never_pass_validation() -> None:
    outline = CourseOutline.model_validate(_outline_dict())
    bad_concepts = ModuleConcepts.model_validate({"concepts": _module_concept_entries(citations=["bogus-chunk"])})
    responses = FakeResponses([outline] + [bad_concepts] * PLAN_VALIDATION_ATTEMPTS)
    worker = _planner_with(responses, [{"id": "chunk-id", "content": "Source content."}])

    with pytest.raises(ValueError, match="failed validation after"):
        worker.plan_course("course-id")

    assert len(responses.calls) == 1 + PLAN_VALIDATION_ATTEMPTS


def test_module_concepts_cite_by_ordinal_label_resolved_to_real_chunk_ids() -> None:
    """The model is shown short numeric labels ([1], [2], ...), not raw chunk UUIDs, since a
    UUID is easy for a model to mis-copy -- exactly the failure this guards against. Citing
    the label the excerpt was shown under must resolve to the real chunk id in what gets
    persisted, without needing a retry."""
    outline = CourseOutline.model_validate(_outline_dict())
    module_concepts = ModuleConcepts.model_validate({"concepts": _module_concept_entries(citations=["2"])})
    responses = FakeResponses([outline, module_concepts])
    chunks = [
        {"id": "5968e028-f96f-4776-91f7-eccad2741378", "content": "First chunk."},
        {"id": "aa11bb22-cc33-dd44-ee55-ff6677889900", "content": "Second chunk."},
    ]
    worker = _planner_with(responses, chunks)

    worker.plan_course("course-id")

    module_context = responses.calls[1]["input"][1]["content"]
    assert "[1]" in module_context and "[2]" in module_context
    assert "5968e028-f96f-4776-91f7-eccad2741378" not in module_context
    persisted_concepts = worker.client.calls[-2][1]["p_concepts"]
    assert all(concept["citations"] == ["aa11bb22-cc33-dd44-ee55-ff6677889900"] for concept in persisted_concepts)


def test_goal_only_planner_request_requires_empty_citations() -> None:
    outline = CourseOutline.model_validate(_outline_dict())
    module_concepts = ModuleConcepts.model_validate({"concepts": _module_concept_entries(citations=[])})
    responses = FakeResponses([outline, module_concepts])
    worker = _planner_with(responses, [])

    worker.plan_course("course-id")

    system_prompt = responses.calls[0]["input"][0]["content"]
    assert "empty citations list" in system_prompt
    assert worker.client.calls[-1][0] == "finalize_course_plan"
