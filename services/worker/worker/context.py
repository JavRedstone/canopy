"""Source-chunk retrieval and prompt-context formatting.

Every LLM call that grounds itself in uploaded sources goes through this module, so the
retrieval strategy lives in one place. Planning retrieves by relevance: it embeds a
query (the goal, or a module's focus) and asks pgvector for the nearest chunks within
the course's document versions, rather than reading a fixed prefix of the corpus.
"""

from typing import Any

from supabase import Client

from worker.embeddings import embed_query, to_pgvector
from worker.llm import LLMGatewayClient

NO_SOURCES_CONTEXT = "No source documents were provided."


def format_chunk_context(chunks: list[dict[str, Any]]) -> str:
    """Render chunks as a `[chunk-id]` header over content — the shape every prompt cites."""
    return "\n\n".join(f"[{chunk['id']}]\n{chunk['content']}" for chunk in chunks) or NO_SOURCES_CONTEXT


def citation_chunks(client: Client, citation_ids: list[str]) -> list[dict[str, Any]]:
    """Load the exact chunks a concept cited when it was planned."""
    if not citation_ids:
        return []
    return (
        client.table("source_chunks")
        .select("id,content")
        .in_("id", citation_ids)
        .execute()
        .data
        or []
    )


def course_version_ids(client: Client, course_id: str) -> list[str]:
    """The latest parsed version of each source attached to the course."""
    source_rows = client.table("course_sources").select("source_document_id").eq("course_id", course_id).execute().data or []
    source_ids = [row["source_document_id"] for row in source_rows]
    if not source_ids:
        return []
    versions = (
        client.table("source_document_versions")
        .select("id,document_id,created_at")
        .in_("document_id", source_ids)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    version_ids_by_source: dict[str, str] = {}
    for version in versions:
        version_ids_by_source.setdefault(version["document_id"], version["id"])
    return list(version_ids_by_source.values())


def retrieve_relevant_chunks(
    client: Client,
    openai: LLMGatewayClient,
    embedding_model: str,
    embedding_dimensions: int,
    version_ids: list[str],
    query_text: str,
    limit: int,
) -> list[dict[str, Any]]:
    """The chunks most relevant to ``query_text`` within the given document versions."""
    if not version_ids or limit <= 0:
        return []
    embedding = embed_query(openai, embedding_model, embedding_dimensions, query_text)
    rows = client.rpc(
        "match_source_chunks",
        {
            "p_version_ids": list(version_ids),
            "p_query_embedding": to_pgvector(embedding),
            "p_limit": limit,
        },
    ).execute().data or []
    return [{"id": row["id"], "content": row["content"]} for row in rows]
