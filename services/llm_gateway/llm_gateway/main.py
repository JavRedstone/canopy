import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from llm_gateway.providers import ModelProvider, build_provider
from llm_gateway.settings import GatewaySettings, GatewayTask, get_settings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings().require_runtime_configuration()
    yield


app = FastAPI(title="Adaptive Source Learning LLM Gateway", version="0.1.0", lifespan=lifespan)


class StructuredGenerationRequest(BaseModel):
    task: GatewayTask
    input: list[dict[str, Any]] = Field(min_length=1, max_length=32)
    schema_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    schema_: dict[str, Any] = Field(alias="schema")


class StructuredGenerationResponse(BaseModel):
    output: dict[str, Any]


class ResponseRequest(BaseModel):
    task: Literal["lesson_repair", "concept_regeneration"]
    input: list[dict[str, Any]] = Field(min_length=1, max_length=64)
    tools: list[dict[str, Any]] = Field(default_factory=list, max_length=8)


class ResponseResponse(BaseModel):
    output: list[dict[str, Any]]


class EmbeddingRequest(BaseModel):
    task: Literal["embedding"]
    texts: list[str] = Field(min_length=1, max_length=128)
    dimensions: int | None = Field(default=None, ge=1, le=4096)


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]


def _provider(settings: GatewaySettings = Depends(get_settings)) -> ModelProvider:
    return build_provider(settings)


def _internal_request_allowed(
    x_internal_service_token: str | None = Header(default=None),
    settings: GatewaySettings = Depends(get_settings),
) -> None:
    expected = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    if expected and x_internal_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal service token.")
    if not expected and settings.environment != "development":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal authentication is not configured.")


@app.get("/health", dependencies=[Depends(_internal_request_allowed)])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/v1/structured", response_model=StructuredGenerationResponse, dependencies=[Depends(_internal_request_allowed)])
def structured_generation(
    request: StructuredGenerationRequest,
    settings: GatewaySettings = Depends(get_settings),
    provider: ModelProvider = Depends(_provider),
) -> StructuredGenerationResponse:
    try:
        output = provider.structured(
            model=settings.model_for(request.task),
            input=request.input,
            schema_name=request.schema_name,
            schema=request.schema_,
        )
    except Exception as exc:
        logger.exception("LLM structured generation failed", extra={"task": request.task})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The LLM gateway is unavailable.") from exc
    return StructuredGenerationResponse(output=output)


@app.post("/internal/v1/responses", response_model=ResponseResponse, dependencies=[Depends(_internal_request_allowed)])
def response_generation(
    request: ResponseRequest,
    settings: GatewaySettings = Depends(get_settings),
    provider: ModelProvider = Depends(_provider),
) -> ResponseResponse:
    try:
        output = provider.respond(model=settings.model_for(request.task), input=request.input, tools=request.tools)
    except Exception as exc:
        logger.exception("LLM response generation failed", extra={"task": request.task})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The LLM gateway is unavailable.") from exc
    return ResponseResponse(output=output)


@app.post("/internal/v1/embeddings", response_model=EmbeddingResponse, dependencies=[Depends(_internal_request_allowed)])
def embeddings(
    request: EmbeddingRequest,
    settings: GatewaySettings = Depends(get_settings),
    provider: ModelProvider = Depends(_provider),
) -> EmbeddingResponse:
    try:
        result = provider.embed(
            model=settings.model_for(request.task), texts=request.texts, dimensions=request.dimensions
        )
    except Exception as exc:
        logger.exception("LLM embedding generation failed", extra={"task": request.task, "text_count": len(request.texts)})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The LLM gateway is unavailable.") from exc
    return EmbeddingResponse(embeddings=result)
