import json
import logging
import time
from typing import Any
from uuid import uuid4

from httpx import HTTPError
from supabase import Client

from worker.db import one
from worker.embeddings import embed_texts, to_pgvector
from worker.llm import LLMGatewayClient
from worker.parsing import ParsedChunk, parse_source_document
from worker.queues import QueueAdapter
from worker.settings import WorkerSettings


logger = logging.getLogger(__name__)


def _batches_by_payload_size(rows: list[dict[str, Any]], max_bytes: int) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for row in rows:
        row_size = len(json.dumps(row))
        if current and current_size + row_size > max_bytes:
            batches.append(current)
            current, current_size = [], 0
        current.append(row)
        current_size += row_size
    if current:
        batches.append(current)
    return batches


# Multi-hundred-KB TLS uploads are intermittently corrupted on some local network
# paths (surfacing as SSL bad_record_mac), so chunk inserts are capped well below
# that threshold and the odd residual transport failure is retried in place
# instead of restarting the whole ingestion (which would re-bill the embeddings).
_INSERT_MAX_BYTES = 200_000
_INSERT_ATTEMPTS = 3


class SourceIngestor:
    """Downloads, parses, chunks, and embeds uploaded source documents."""

    def __init__(self, settings: WorkerSettings, client: Client, openai: LLMGatewayClient, queue: QueueAdapter) -> None:
        self.settings = settings
        self.client = client
        self.openai = openai
        self.queue = queue

    def ingest_source(self, source_id: str) -> None:
        source = one(
            self.client.table("source_documents")
            .select("id,owner_id,mime_type,storage_path,status")
            .eq("id", source_id)
            .execute()
            .data,
            "Source",
        )
        if source["status"] == "ready":
            return
        if source["status"] != "ingesting":
            raise ValueError("Source is not claimed for ingestion.")

        raw_content = self.client.storage.from_("sources").download(source["storage_path"])
        parsed_chunks = parse_source_document(
            raw_content,
            source["mime_type"],
            self.settings.chunk_characters,
            self.settings.chunk_overlap_characters,
        )
        document_version_id = self._replace_document_version(source_id)
        embeddings = self._embed([chunk.content for chunk in parsed_chunks])
        chunk_rows = [
            self._chunk_row(document_version_id, chunk, embedding)
            for chunk, embedding in zip(parsed_chunks, embeddings, strict=True)
        ]
        for batch in _batches_by_payload_size(chunk_rows, _INSERT_MAX_BYTES):
            self._insert_chunk_batch(batch)

        self.client.table("source_documents").update({"status": "ready"}).eq("id", source_id).execute()
        self._enqueue_attached_course_plans(source_id)

    def _insert_chunk_batch(self, batch: list[dict[str, Any]]) -> None:
        for attempt in range(1, _INSERT_ATTEMPTS + 1):
            try:
                self.client.table("source_chunks").insert(batch).execute()
                return
            except HTTPError:
                if attempt == _INSERT_ATTEMPTS:
                    raise
                logger.warning(
                    "Chunk insert hit a transport error (attempt %d/%d); retrying on a fresh connection",
                    attempt,
                    _INSERT_ATTEMPTS,
                )
                time.sleep(attempt)

    def _replace_document_version(self, source_id: str) -> str:
        existing = (
            self.client.table("source_document_versions")
            .select("id")
            .eq("document_id", source_id)
            .eq("parser_version", "v1")
            .execute()
            .data
            or []
        )
        for version in existing:
            self.client.table("source_document_versions").delete().eq("id", version["id"]).execute()
        document_version_id = str(uuid4())
        self.client.table("source_document_versions").insert(
            {"id": document_version_id, "document_id": source_id, "parser_version": "v1"}
        ).execute()
        return document_version_id

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return embed_texts(
            self.openai,
            self.settings.embedding_model,
            self.settings.embedding_dimensions,
            texts,
            self.settings.embedding_batch_size,
        )

    def _chunk_row(self, document_version_id: str, chunk: ParsedChunk, embedding: list[float]) -> dict[str, Any]:
        return {
            "id": str(uuid4()),
            "document_version_id": document_version_id,
            "content": chunk.content,
            "embedding": to_pgvector(embedding),
            "page_number": chunk.page_number,
            "section": chunk.section,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }

    def _enqueue_attached_course_plans(self, source_id: str) -> None:
        course_sources = self.client.table("course_sources").select("course_id").eq("source_document_id", source_id).execute().data or []
        for course_source in course_sources:
            course = one(
                self.client.table("courses")
                .select("id,owner_id")
                .eq("id", course_source["course_id"])
                .execute()
                .data,
                "Course",
            )
            self.queue.enqueue_course_planning(course["id"], course["owner_id"])
