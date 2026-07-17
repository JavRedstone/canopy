"""Model provider adapters for the LLM gateway.

Each adapter implements the ModelProvider protocol. Requests and responses use
the OpenAI Responses API shapes as the gateway's internal lingua franca; the
Bedrock adapter translates to and from the AWS Converse API.
"""

import json
from collections.abc import Sequence
from typing import Any, Protocol

from openai import OpenAI

from llm_gateway.settings import GatewaySettings


class ModelProvider(Protocol):
    def structured(self, *, model: str, input: list[dict[str, Any]], schema_name: str, schema: dict[str, Any]) -> dict[str, Any]: ...

    def respond(self, *, model: str, input: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]: ...

    def embed(self, *, model: str, texts: list[str], dimensions: int | None) -> list[list[float]]: ...


class OpenAIProvider:
    def __init__(self, settings: GatewaySettings) -> None:
        self.client = self._build_client(settings)

    def _build_client(self, settings: GatewaySettings) -> OpenAI:
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        return OpenAI(api_key=api_key)

    def structured(self, *, model: str, input: list[dict[str, Any]], schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=model,
            input=input,
            text={"format": {"type": "json_schema", "name": schema_name, "schema": _strict_schema(schema), "strict": True}},
        )
        try:
            return json.loads(response.output_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Model did not return a JSON value matching the requested schema.") from exc

    def respond(self, *, model: str, input: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        response = self.client.responses.create(model=model, input=input, tools=tools or [])
        return [item.model_dump(mode="json") for item in response.output]

    def embed(self, *, model: str, texts: list[str], dimensions: int | None) -> list[list[float]]:
        kwargs: dict[str, Any] = {"model": model, "input": texts}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        response = self.client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]


class AzureOpenAIProvider(OpenAIProvider):
    def _build_client(self, settings: GatewaySettings) -> OpenAI:
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        assert settings.azure_openai_endpoint is not None
        return OpenAI(api_key=api_key, base_url=settings.azure_openai_endpoint.rstrip("/") + "/openai/v1/")


class BedrockOpenAIProvider(OpenAIProvider):
    """OpenAI GPT models served by AWS Bedrock's bedrock-mantle endpoint.

    The endpoint implements the OpenAI Responses API, so chat and structured
    generation reuse the OpenAI adapter verbatim; only the base URL and the
    Bedrock API key differ. bedrock-mantle serves no embedding models, so
    embeddings fall back to Amazon Titan through the Converse adapter's
    bedrock-runtime client.
    """

    def __init__(self, settings: GatewaySettings, bedrock_client: Any | None = None) -> None:
        super().__init__(settings)
        self._settings = settings
        self._bedrock_client = bedrock_client
        self._embedder: BedrockConverseProvider | None = None

    def _build_client(self, settings: GatewaySettings) -> OpenAI:
        api_key = settings.aws_bedrock_api_key.get_secret_value() if settings.aws_bedrock_api_key else ""
        assert settings.aws_region is not None
        return OpenAI(api_key=api_key, base_url=f"https://bedrock-mantle.{settings.aws_region}.api.aws/openai/v1")

    def embed(self, *, model: str, texts: list[str], dimensions: int | None) -> list[list[float]]:
        if self._embedder is None:
            self._embedder = BedrockConverseProvider(self._settings, client=self._bedrock_client)
        return self._embedder.embed(model=model, texts=texts, dimensions=dimensions)


class BedrockConverseProvider:
    """Adapter for the AWS Bedrock Converse API (plus InvokeModel for embeddings).

    Credentials come from the standard boto3 chain (env vars, shared config,
    instance role); only the region is configured through gateway settings.
    Structured generation is implemented as a forced tool call, so the chat
    models must support Converse toolChoice (Anthropic Claude, Amazon Nova,
    Mistral Large). Embeddings assume the Amazon Titan request/response shape.
    """

    def __init__(self, settings: GatewaySettings, client: Any | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self.client = client

    def structured(self, *, model: str, input: list[dict[str, Any]], schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
        system, messages = _to_converse_messages(input)
        response = self.client.converse(
            modelId=model,
            messages=messages,
            **({"system": system} if system else {}),
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": schema_name,
                            "description": "Record the structured result matching the requested schema.",
                            "inputSchema": {"json": schema},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": schema_name}},
            },
        )
        for block in response["output"]["message"].get("content", []):
            tool_use = block.get("toolUse")
            if tool_use and tool_use.get("name") == schema_name and isinstance(tool_use.get("input"), dict):
                return tool_use["input"]
        raise ValueError("Model did not return a JSON value matching the requested schema.")

    def respond(self, *, model: str, input: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        system, messages = _to_converse_messages(input)
        kwargs: dict[str, Any] = {"modelId": model, "messages": messages}
        if system:
            kwargs["system"] = system
        tool_config = _to_converse_tool_config(tools or [])
        if tool_config:
            kwargs["toolConfig"] = tool_config
        response = self.client.converse(**kwargs)
        return _from_converse_output(response["output"]["message"])

    def embed(self, *, model: str, texts: list[str], dimensions: int | None) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            body: dict[str, Any] = {"inputText": text}
            if dimensions is not None:
                body["dimensions"] = dimensions
            response = self.client.invoke_model(modelId=model, body=json.dumps(body))
            payload = json.loads(response["body"].read())
            embeddings.append(payload["embedding"])
        return embeddings


def build_provider(settings: GatewaySettings) -> ModelProvider:
    if settings.llm_provider == "aws":
        return BedrockConverseProvider(settings)
    if settings.llm_provider == "aws_openai":
        return BedrockOpenAIProvider(settings)
    if settings.llm_provider == "azure":
        return AzureOpenAIProvider(settings)
    return OpenAIProvider(settings)


def _to_converse_messages(input: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Translate OpenAI Responses input items into Converse system + messages.

    Handles plain role/content messages, assistant output items fed back into
    the conversation, and the function_call / function_call_output pairs the
    lesson-repair loop appends between turns. Converse requires toolUse blocks
    on assistant messages and toolResult blocks on user messages, and rejects
    consecutive same-role messages for Anthropic models, so blocks are merged.
    """
    system: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []

    def append_block(role: str, block: dict[str, Any]) -> None:
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].append(block)
        else:
            messages.append({"role": role, "content": [block]})

    for item in input:
        role = item.get("role")
        item_type = item.get("type")
        if role in {"system", "developer"}:
            system.append({"text": _item_text(item.get("content"))})
        elif role in {"user", "assistant"} and (item_type is None or item_type == "message"):
            text = _item_text(item.get("content"))
            if text:
                append_block(role, {"text": text})
        elif item_type == "function_call":
            arguments = item.get("arguments") or "{}"
            append_block(
                "assistant",
                {
                    "toolUse": {
                        "toolUseId": item["call_id"],
                        "name": item["name"],
                        "input": json.loads(arguments) if isinstance(arguments, str) else arguments,
                    }
                },
            )
        elif item_type == "function_call_output":
            append_block(
                "user",
                {
                    "toolResult": {
                        "toolUseId": item["call_id"],
                        "content": [{"text": str(item.get("output", ""))}],
                    }
                },
            )
    return system, messages


def _item_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def _to_converse_tool_config(tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    specs = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        specs.append(
            {
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool.get("description") or tool["name"],
                    "inputSchema": {"json": tool.get("parameters") or {"type": "object", "properties": {}}},
                }
            }
        )
    return {"tools": specs} if specs else None


def _from_converse_output(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate a Converse output message into OpenAI Responses output items."""
    items: list[dict[str, Any]] = []
    text_parts: list[dict[str, Any]] = []
    for block in message.get("content", []):
        if isinstance(block.get("text"), str):
            text_parts.append({"type": "output_text", "text": block["text"], "annotations": []})
        elif block.get("toolUse"):
            tool_use = block["toolUse"]
            items.append(
                {
                    "type": "function_call",
                    "id": tool_use["toolUseId"],
                    "call_id": tool_use["toolUseId"],
                    "name": tool_use["name"],
                    "arguments": json.dumps(tool_use.get("input") or {}),
                    "status": "completed",
                }
            )
    if text_parts:
        items.insert(0, {"type": "message", "role": "assistant", "content": text_parts, "status": "completed"})
    return items


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make Pydantic's JSON schema compatible with strict Structured Outputs.

    Strict schemas require every object property to be listed in `required` and
    prohibit undeclared properties. The caller still validates the returned
    payload with its local Pydantic domain model.
    """
    normalized = json.loads(json.dumps(schema))

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["required"] = list(properties)
                value["additionalProperties"] = False
            for child in value.values():
                visit(child)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            for child in value:
                visit(child)

    visit(normalized)
    return normalized
