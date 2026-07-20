import io
import json

from llm_gateway.providers import (
    AzureOpenAIProvider,
    BedrockConverseProvider,
    BedrockOpenAIProvider,
    OpenAIProvider,
    build_provider,
)
from llm_gateway.settings import GatewaySettings


class FakeBedrockClient:
    def __init__(self, converse_response: dict | None = None) -> None:
        self.converse_calls: list[dict] = []
        self.invoke_calls: list[dict] = []
        self.converse_response = converse_response or {"output": {"message": {"role": "assistant", "content": []}}}

    def converse(self, **kwargs):
        self.converse_calls.append(kwargs)
        return self.converse_response

    def invoke_model(self, **kwargs):
        self.invoke_calls.append(kwargs)
        return {"body": io.BytesIO(json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode())}


def _settings(**overrides) -> GatewaySettings:
    return GatewaySettings(_env_file=None, **overrides)


def test_build_provider_selects_adapter_per_provider_setting() -> None:
    assert type(build_provider(_settings(openai_api_key="test-key"))) is OpenAIProvider
    assert type(
        build_provider(
            _settings(
                llm_provider="azure",
                openai_api_key="test-key",
                azure_openai_endpoint="https://example.openai.azure.com/",
            )
        )
    ) is AzureOpenAIProvider
    assert type(
        build_provider(_settings(llm_provider="aws_openai", aws_region="us-east-1", aws_bedrock_api_key="test-key"))
    ) is BedrockOpenAIProvider


def test_settings_accept_legacy_openai_provider_env_alias(monkeypatch) -> None:
    monkeypatch.setenv("APP_OPENAI_PROVIDER", "openai")
    assert GatewaySettings(_env_file=None).llm_provider == "openai"
    monkeypatch.setenv("APP_LLM_PROVIDER", "aws")
    assert GatewaySettings(_env_file=None).llm_provider == "aws"


def test_settings_model_for_splits_openai_generation_and_repair() -> None:
    settings = _settings(openai_api_key="test-key")
    # Assert routing to each *tier*, not literal model names -- which model backs a given
    # tier is a free-to-change product/cost decision, not something a test should pin.
    # The outline is the one planning call promoted to the Sol reasoning tier; per-module
    # concepts and every generation task share the cheaper builder (Luna) tier.
    assert settings.model_for("course_outline") == settings.openai_outline_model
    assert settings.model_for("module_concepts") == settings.openai_builder_model
    assert settings.model_for("lesson_build") == settings.openai_builder_model
    assert settings.model_for("concept_regeneration") == settings.openai_builder_model
    assert settings.model_for("quiz_grading") == settings.openai_builder_model
    # Repair is the other Sol task: the last line of defense before a lab is declared failed.
    assert settings.model_for("lesson_repair") == settings.openai_repair_model
    assert settings.model_for("lesson_helper") == settings.openai_helper_model
    # The practice pool is builder-tier work behind its own task, so it can be dialled up on
    # answer-key quality without dragging lesson generation with it.
    assert settings.model_for("practice_pool") == settings.openai_practice_pool_model
    # The tiers are genuinely distinct models, or this test would pass by coincidence.
    assert settings.openai_outline_model != settings.openai_builder_model


def test_settings_model_for_uses_bedrock_models_when_aws() -> None:
    settings = _settings(
        llm_provider="aws",
        aws_region="us-east-1",
        aws_bedrock_planner_model="planner-bedrock",
        aws_bedrock_builder_model="builder-bedrock",
        aws_bedrock_embedding_model="embed-bedrock",
    )
    assert settings.model_for("course_outline") == "planner-bedrock"
    assert settings.model_for("module_concepts") == "builder-bedrock"
    # Bedrock has no dedicated repair tier, so repair falls back to the builder model.
    assert settings.model_for("lesson_repair") == "builder-bedrock"
    assert settings.model_for("lesson_helper") == "builder-bedrock"
    assert settings.model_for("embedding") == "embed-bedrock"
    # An explicit repair model overrides that fallback.
    assert settings.model_copy(update={"aws_bedrock_repair_model": "repair-bedrock"}).model_for("lesson_repair") == "repair-bedrock"
    assert settings.model_copy(update={"aws_bedrock_helper_model": "helper-bedrock"}).model_for("lesson_helper") == "helper-bedrock"
    # The practice pool follows the same fallback-then-override shape on every provider.
    assert settings.model_for("practice_pool") == "builder-bedrock"
    assert settings.model_copy(update={"aws_bedrock_practice_pool_model": "pool-bedrock"}).model_for("practice_pool") == "pool-bedrock"


def test_bedrock_openai_targets_mantle_endpoint_and_uses_titan_for_embeddings() -> None:
    settings = _settings(
        llm_provider="aws_openai",
        aws_region="us-west-2",
        aws_bedrock_api_key="bedrock-key",
    )
    provider = BedrockOpenAIProvider(settings, bedrock_client=FakeBedrockClient())

    assert str(provider.client.base_url).startswith("https://bedrock-mantle.us-west-2.api.aws/openai/v1")
    assert settings.model_for("course_outline") == settings.aws_openai_planner_model
    assert settings.model_for("embedding") == settings.aws_bedrock_embedding_model
    assert provider.embed(model="amazon.titan-embed-text-v2:0", texts=["a"], dimensions=None) == [[0.1, 0.2, 0.3]]


def test_bedrock_structured_forces_tool_choice_and_returns_tool_input() -> None:
    client = FakeBedrockClient(
        converse_response={
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"toolUse": {"toolUseId": "t1", "name": "CoursePlan", "input": {"title": "Generated"}}}],
                }
            }
        }
    )
    provider = BedrockConverseProvider(_settings(llm_provider="aws", aws_region="us-east-1"), client=client)

    output = provider.structured(
        model="model-id",
        input=[
            {"role": "system", "content": "Plan courses."},
            {"role": "user", "content": "Build a course."},
        ],
        schema_name="CoursePlan",
        schema={"type": "object", "properties": {"title": {"type": "string"}}},
    )

    assert output == {"title": "Generated"}
    call = client.converse_calls[0]
    assert call["modelId"] == "model-id"
    assert call["system"] == [{"text": "Plan courses."}]
    assert call["messages"] == [{"role": "user", "content": [{"text": "Build a course."}]}]
    assert call["toolConfig"]["toolChoice"] == {"tool": {"name": "CoursePlan"}}


def test_bedrock_respond_translates_tools_and_output_items() -> None:
    client = FakeBedrockClient(
        converse_response={
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Fixing the file."},
                        {"toolUse": {"toolUseId": "call-1", "name": "read_file", "input": {"path": "main.py"}}},
                    ],
                }
            }
        }
    )
    provider = BedrockConverseProvider(_settings(llm_provider="aws", aws_region="us-east-1"), client=client)

    output = provider.respond(
        model="model-id",
        input=[{"role": "user", "content": "Fix the tests."}],
        tools=[
            {
                "type": "function",
                "name": "read_file",
                "description": "Read a file.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ],
    )

    call = client.converse_calls[0]
    assert call["toolConfig"]["tools"][0]["toolSpec"]["name"] == "read_file"
    assert output[0]["type"] == "message"
    assert output[0]["content"][0] == {"type": "output_text", "text": "Fixing the file.", "annotations": []}
    assert output[1]["type"] == "function_call"
    assert output[1]["call_id"] == "call-1"
    assert json.loads(output[1]["arguments"]) == {"path": "main.py"}


def test_bedrock_respond_round_trips_function_calls_from_previous_turns() -> None:
    client = FakeBedrockClient()
    provider = BedrockConverseProvider(_settings(llm_provider="aws", aws_region="us-east-1"), client=client)

    provider.respond(
        model="model-id",
        input=[
            {"role": "user", "content": "Fix the tests."},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Reading the file.", "annotations": []}],
                "status": "completed",
            },
            {"type": "function_call", "call_id": "call-1", "name": "read_file", "arguments": '{"path": "main.py"}'},
            {"type": "function_call_output", "call_id": "call-1", "output": "print('hi')"},
        ],
        tools=None,
    )

    messages = client.converse_calls[0]["messages"]
    assert messages == [
        {"role": "user", "content": [{"text": "Fix the tests."}]},
        {
            "role": "assistant",
            "content": [
                {"text": "Reading the file."},
                {"toolUse": {"toolUseId": "call-1", "name": "read_file", "input": {"path": "main.py"}}},
            ],
        },
        {"role": "user", "content": [{"toolResult": {"toolUseId": "call-1", "content": [{"text": "print('hi')"}]}}]},
    ]


def test_bedrock_embed_uses_titan_invoke_model_per_text() -> None:
    client = FakeBedrockClient()
    provider = BedrockConverseProvider(_settings(llm_provider="aws", aws_region="us-east-1"), client=client)

    embeddings = provider.embed(model="amazon.titan-embed-text-v2:0", texts=["a", "b"], dimensions=256)

    assert embeddings == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert len(client.invoke_calls) == 2
    assert json.loads(client.invoke_calls[0]["body"]) == {"inputText": "a", "dimensions": 256}
