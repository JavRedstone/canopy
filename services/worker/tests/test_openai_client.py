from types import SimpleNamespace

from pydantic import SecretStr

from worker.ingestion import IngestionWorker
from worker.llm import LLMGatewayClient
from worker.main import _build_llm_client
from worker.planner import CourseSkeleton, ModuleConcepts


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


class FakePlanningClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def rpc(self, function: str, arguments: dict[str, object]) -> FakeRequest:
        self.calls.append((function, arguments))
        if function == "claim_course_planning":
            return FakeRequest(
                [
                    {
                        "course_version_id": "version-id",
                        "goal": "Learn authentication",
                        "source_set_hash": "source-hash",
                    }
                ]
            )
        if function == "apply_course_skeleton":
            modules = arguments["p_modules"]
            return FakeRequest([{"module_id": f"module-{index}", "module_position": index + 1} for index in range(len(modules))])
        return FakeRequest([])


def test_build_llm_client_uses_internal_gateway_configuration() -> None:
    settings = SimpleNamespace(
        llm_gateway_url="http://llm-gateway:8010/",
        internal_service_token=SecretStr("internal-token"),
    )

    client = _build_llm_client(settings)

    assert client.base_url == "http://llm-gateway:8010"
    assert client.internal_service_token == "internal-token"


def test_gateway_client_sends_schema_and_validates_structured_output() -> None:
    http = FakeHttpClient(
        [
            FakeResponse(
                {
                    "output": {
                        "course_title": "Authentication",
                        "source_set_hash": "source-hash",
                        "modules": [{"id": "basics", "title": "Basics"}],
                    }
                }
            )
        ]
    )
    client = LLMGatewayClient("http://gateway", internal_service_token="secret", http_client=http)

    result = client.responses.parse(
        model="course_planning",
        input=[{"role": "user", "content": "Build a course."}],
        text_format=CourseSkeleton,
    )

    assert result.output_parsed.course_title == "Authentication"
    assert http.calls == [
        {
            "url": "http://gateway/internal/v1/structured",
            "headers": {"X-Internal-Service-Token": "secret"},
            "json": {
                "task": "course_planning",
                "input": [{"role": "user", "content": "Build a course."}],
                "schema_name": "CourseSkeleton",
                "schema": CourseSkeleton.model_json_schema(),
            },
        }
    ]


def test_embedding_request_uses_gateway_task() -> None:
    embeddings = FakeEmbeddings()
    worker = IngestionWorker.__new__(IngestionWorker)
    worker.settings = SimpleNamespace(embedding_batch_size=2, embedding_model="embedding", embedding_dimensions=3)
    worker.openai = SimpleNamespace(embeddings=embeddings)

    result = worker._embed(["first", "second", "third"])

    assert [call["model"] for call in embeddings.calls] == ["embedding", "embedding"]
    assert [call["input"] for call in embeddings.calls] == [["first", "second"], ["third"]]
    assert result == [[0.0, 0.5, 0.25], [1.0, 0.5, 0.25], [0.0, 0.5, 0.25]]


def test_planner_request_uses_course_planning_task() -> None:
    skeleton = CourseSkeleton.model_validate(
        {"course_title": "Authentication", "source_set_hash": "source-hash", "modules": [{"id": "basics", "title": "Basics"}]}
    )
    module_concepts = ModuleConcepts.model_validate(
        {
            "concepts": [
                {
                    "id": "tokens",
                    "title": "Tokens",
                    "kind": "conceptual",
                    "summary_markdown": "Tokens identify requests.",
                    "prerequisites": [],
                    "citations": ["chunk-id"],
                }
            ]
        }
    )
    responses = FakeResponses([skeleton, module_concepts])
    worker = IngestionWorker.__new__(IngestionWorker)
    worker.settings = SimpleNamespace(planner_model="course_planning")
    worker.client = FakePlanningClient()
    worker.openai = SimpleNamespace(responses=responses)
    worker._course_context = lambda _course_id: [{"id": "chunk-id", "content": "Source content."}]

    worker.plan_course("course-id")

    assert [call["model"] for call in responses.calls] == ["course_planning", "course_planning"]
    assert [call[0] for call in worker.client.calls] == [
        "claim_course_planning",
        "reset_course_planning",
        "apply_course_skeleton",
        "apply_module_concepts",
        "finalize_course_plan",
    ]


def test_goal_only_planner_request_requires_empty_citations() -> None:
    skeleton = CourseSkeleton.model_validate(
        {"course_title": "Python foundations", "source_set_hash": "source-hash", "modules": [{"id": "basics", "title": "Basics"}]}
    )
    module_concepts = ModuleConcepts.model_validate(
        {
            "concepts": [
                {
                    "id": "variables",
                    "title": "Variables",
                    "kind": "coding",
                    "summary_markdown": "Store and reuse values with variables.",
                    "prerequisites": [],
                    "citations": [],
                }
            ]
        }
    )
    responses = FakeResponses([skeleton, module_concepts])
    worker = IngestionWorker.__new__(IngestionWorker)
    worker.settings = SimpleNamespace(planner_model="course_planning")
    worker.client = FakePlanningClient()
    worker.openai = SimpleNamespace(responses=responses)
    worker._course_context = lambda _course_id: []

    worker.plan_course("course-id")

    system_prompt = responses.calls[0]["input"][0]["content"]
    assert "empty citations list" in system_prompt
    assert worker.client.calls[-1][0] == "finalize_course_plan"
