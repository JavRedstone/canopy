from types import SimpleNamespace

from pydantic import SecretStr

from worker.ingestion import IngestionWorker
from worker.main import _build_openai_client
from worker.planner import CoursePlan


class FakeOpenAI:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(index), 0.5, 0.25]) for index in range(len(kwargs["input"]))]
        )


class FakeResponses:
    def __init__(self, plan: CoursePlan) -> None:
        self.plan = plan
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.plan)


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
        return FakeRequest([])


def test_build_openai_client_uses_default_api_endpoint(monkeypatch: object) -> None:
    FakeOpenAI.calls = []
    monkeypatch.setattr("worker.main.OpenAI", FakeOpenAI)
    settings = SimpleNamespace(openai_api_key=SecretStr("test-key"), openai_provider="openai")

    _build_openai_client(settings)

    assert FakeOpenAI.calls == [{"api_key": "test-key"}]


def test_build_openai_client_uses_azure_v1_endpoint(monkeypatch: object) -> None:
    FakeOpenAI.calls = []
    monkeypatch.setattr("worker.main.OpenAI", FakeOpenAI)
    settings = SimpleNamespace(
        openai_api_key=SecretStr("test-key"),
        openai_provider="azure",
        azure_openai_endpoint="https://example.openai.azure.com/",
    )

    _build_openai_client(settings)

    assert FakeOpenAI.calls == [
        {"api_key": "test-key", "base_url": "https://example.openai.azure.com/openai/v1/"}
    ]


def test_embedding_request_uses_resolved_provider_model() -> None:
    embeddings = FakeEmbeddings()
    worker = IngestionWorker.__new__(IngestionWorker)
    worker.settings = SimpleNamespace(embedding_batch_size=2, embedding_model="azure-embedding", embedding_dimensions=3)
    worker.openai = SimpleNamespace(embeddings=embeddings)

    result = worker._embed(["first", "second", "third"])

    assert [call["model"] for call in embeddings.calls] == ["azure-embedding", "azure-embedding"]
    assert [call["input"] for call in embeddings.calls] == [["first", "second"], ["third"]]
    assert result == [[0.0, 0.5, 0.25], [1.0, 0.5, 0.25], [0.0, 0.5, 0.25]]


def test_planner_request_uses_resolved_provider_model() -> None:
    plan = CoursePlan.model_validate(
        {
            "course_title": "Authentication",
            "source_set_hash": "source-hash",
            "concepts": [
                {
                    "id": "tokens",
                    "title": "Tokens",
                    "kind": "conceptual",
                    "summary_markdown": "Tokens identify requests.",
                    "prerequisites": [],
                    "citations": ["chunk-id"],
                }
            ],
            "modules": [{"id": "basics", "title": "Basics", "concept_ids": ["tokens"]}],
        }
    )
    responses = FakeResponses(plan)
    worker = IngestionWorker.__new__(IngestionWorker)
    worker.settings = SimpleNamespace(planner_model="azure-planner")
    worker.client = FakePlanningClient()
    worker.openai = SimpleNamespace(responses=responses)
    worker._course_context = lambda _course_id: [{"id": "chunk-id", "content": "Source content."}]

    worker.plan_course("course-id")

    assert responses.calls[0]["model"] == "azure-planner"
    assert worker.client.calls[-1][0] == "apply_course_plan"
