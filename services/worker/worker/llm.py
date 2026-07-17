import json
from types import SimpleNamespace
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError


class LLMGatewayError(Exception):
    """The private LLM gateway could not accept or complete a model request."""


class LLMValidationError(Exception):
    """The model repeatedly returned output that failed domain validation.

    Deliberately not an LLMGatewayError: transport errors are transient and the
    job should stay queued, but a model that failed validation even after being
    shown the errors will not fix itself on a queue retry.
    """


_STRUCTURED_ATTEMPTS = 3


class GatewayOutputItem(dict[str, Any]):
    """A JSON-safe response item that preserves the OpenAI SDK's attribute access shape."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _ResponsesClient:
    def __init__(self, gateway: "LLMGatewayClient") -> None:
        self.gateway = gateway

    def parse(self, *, model: str, input: list[dict[str, Any]], text_format: type[BaseModel]) -> SimpleNamespace:
        items = list(input)
        last_error: ValidationError | None = None
        for _ in range(_STRUCTURED_ATTEMPTS):
            result = self.gateway._post(
                "/internal/v1/structured",
                {
                    "task": model,
                    "input": items,
                    "schema_name": text_format.__name__,
                    "schema": text_format.model_json_schema(),
                },
            )
            if "output" not in result:
                raise LLMGatewayError("The gateway returned an invalid structured response.")
            try:
                return SimpleNamespace(output_parsed=text_format.model_validate(result["output"]))
            except ValidationError as exc:
                last_error = exc
                items = items + [
                    {"role": "assistant", "content": json.dumps(result["output"])},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was rejected by validation:\n"
                            f"{exc}\n"
                            "Return a corrected response that fixes every violation and still follows all "
                            "of the original instructions."
                        ),
                    },
                ]
        raise LLMValidationError(
            f"The model output still failed validation after {_STRUCTURED_ATTEMPTS} attempts."
        ) from last_error

    def create(
        self,
        *,
        model: str,
        input: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> SimpleNamespace:
        result = self.gateway._post(
            "/internal/v1/responses",
            {"task": model, "input": input, "tools": tools or []},
        )
        try:
            return SimpleNamespace(output=[GatewayOutputItem(item) for item in result["output"]])
        except (KeyError, TypeError) as exc:
            raise LLMGatewayError("The gateway returned an invalid response.") from exc


class _EmbeddingsClient:
    def __init__(self, gateway: "LLMGatewayClient") -> None:
        self.gateway = gateway

    def create(self, *, model: str, input: list[str], dimensions: int | None = None) -> SimpleNamespace:
        result = self.gateway._post(
            "/internal/v1/embeddings",
            {"task": model, "texts": input, "dimensions": dimensions},
        )
        try:
            return SimpleNamespace(data=[SimpleNamespace(embedding=embedding) for embedding in result["embeddings"]])
        except (KeyError, TypeError) as exc:
            raise LLMGatewayError("The gateway returned invalid embeddings.") from exc


class LLMGatewayClient:
    """Provider-neutral client. The worker holds no model-provider credential."""

    def __init__(
        self,
        base_url: str,
        *,
        internal_service_token: str | None,
        timeout_seconds: int = 120,
        http_client: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_service_token = internal_service_token
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self.responses = _ResponsesClient(self)
        self.embeddings = _EmbeddingsClient(self)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"X-Internal-Service-Token": self.internal_service_token} if self.internal_service_token else {}
        try:
            response = self.http_client.post(f"{self.base_url}{path}", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise TypeError("Gateway response must be an object.")
            return data
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise LLMGatewayError("The LLM gateway request failed.") from exc
