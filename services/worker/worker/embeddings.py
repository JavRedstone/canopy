"""Embedding generation and pgvector serialization.

Shared by ingestion (embedding source chunks for storage) and planning (embedding a
query to retrieve relevant chunks), so both paths agree on batching, dimension
validation, and the pgvector text encoding.
"""

from typing import Any


def batched(items: list[Any], size: int) -> list[list[Any]]:
    if size <= 0:
        raise ValueError("Batch size must be positive.")
    return [items[index : index + size] for index in range(0, len(items), size)]


def embed_texts(openai: Any, model: str, dimensions: int, texts: list[str], batch_size: int) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for batch in batched(texts, batch_size):
        response = openai.embeddings.create(model=model, input=batch, dimensions=dimensions)
        embeddings.extend(item.embedding for item in response.data)
    if any(len(embedding) != dimensions for embedding in embeddings):
        raise ValueError("Embedding dimensions do not match the configured pgvector column.")
    return embeddings


def embed_query(openai: Any, model: str, dimensions: int, text: str) -> list[float]:
    return embed_texts(openai, model, dimensions, [text], batch_size=1)[0]


def to_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(format(value, ".8g") for value in embedding) + "]"
