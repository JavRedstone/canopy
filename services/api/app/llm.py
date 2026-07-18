"""Minimal structured-output client for the private LLM gateway.

The API holds no model-provider credential; short-answer quiz grading is the only
LLM-backed API feature, so this client supports exactly one operation: a structured
generation call validated against a Pydantic model, with one feedback retry.
"""

import json
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class LLMGatewayError(Exception):
    """The private LLM gateway could not accept or complete a model request."""


_STRUCTURED_ATTEMPTS = 3

T = TypeVar("T", bound=BaseModel)


class LLMGatewayClient:
    def __init__(
        self,
        base_url: str,
        *,
        internal_service_token: str | None,
        timeout_seconds: int = 30,
        http_client: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_service_token = internal_service_token
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def structured(self, *, task: str, input: list[dict[str, Any]], output_model: type[T]) -> T:
        items = list(input)
        last_error: ValidationError | None = None
        for attempt in range(1, _STRUCTURED_ATTEMPTS + 1):
            payload = {
                "task": task,
                "input": items,
                "schema_name": output_model.__name__,
                "schema": output_model.model_json_schema(),
            }
            headers = {"X-Internal-Service-Token": self.internal_service_token} if self.internal_service_token else {}
            try:
                response = self.http_client.post(f"{self.base_url}/internal/v1/structured", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise LLMGatewayError("The LLM gateway request failed.") from exc
            if not isinstance(data, dict) or "output" not in data:
                raise LLMGatewayError("The gateway returned an invalid structured response.")
            try:
                return output_model.model_validate(data["output"])
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "Structured output for task %s failed validation (attempt %d/%d): %s",
                    task, attempt, _STRUCTURED_ATTEMPTS, exc,
                )
                items = items + [
                    {"role": "assistant", "content": json.dumps(data["output"])},
                    {"role": "user", "content": f"Your previous response was rejected by validation:\n{exc}\nReturn a corrected response."},
                ]
        logger.warning("Structured output for task %s still failed validation after %d attempts.", task, _STRUCTURED_ATTEMPTS)
        raise LLMGatewayError("The model output failed validation repeatedly.") from last_error
