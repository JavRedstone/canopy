from fastapi.testclient import TestClient

from llm_gateway.main import _provider, app
from llm_gateway.settings import GatewaySettings, get_settings


class FakeProvider:
    def __init__(self) -> None:
        self.structured_calls: list[dict[str, object]] = []

    def structured(self, **kwargs: object) -> dict[str, object]:
        self.structured_calls.append(kwargs)
        return {"title": "Generated"}

    def respond(self, **_kwargs: object) -> list[dict[str, object]]:
        return []

    def embed(self, **_kwargs: object) -> list[list[float]]:
        return [[0.1, 0.2]]


def test_structured_generation_uses_registered_task_model_and_strict_schema() -> None:
    provider = FakeProvider()
    settings = GatewaySettings(_env_file=None, openai_api_key="test-key", openai_planner_model="planner-model")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[_provider] = lambda: provider
    try:
        response = TestClient(app).post(
            "/internal/v1/structured",
            json={
                "task": "course_planning",
                "input": [{"role": "user", "content": "Build a course."}],
                "schema_name": "CoursePlan",
                "schema": {"type": "object", "properties": {"title": {"type": "string"}}},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"output": {"title": "Generated"}}
    assert provider.structured_calls == [
        {
            "model": "planner-model",
            "input": [{"role": "user", "content": "Build a course."}],
            "schema_name": "CoursePlan",
            "schema": {"type": "object", "properties": {"title": {"type": "string"}}},
        }
    ]
