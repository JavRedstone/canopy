-- Relevance retrieval over source_chunks. The planner previously read the first N
-- chunks by insertion order, ignoring the embeddings entirely; this returns the chunks
-- nearest a query embedding (cosine distance) within a course's document versions, so
-- planning is grounded in the material that actually matches the goal or module.
--
-- p_query_embedding arrives as pgvector's text form (e.g. '[0.1,0.2,...]') and is cast
-- to vector, which avoids depending on postgREST coercion of array params to vector.

create or replace function public.match_source_chunks(
  p_version_ids uuid[],
  p_query_embedding text,
  p_limit integer
)
returns table(id uuid, content text, similarity double precision)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select
    chunk.id,
    chunk.content,
    1 - (chunk.embedding <=> p_query_embedding::vector) as similarity
  from public.source_chunks as chunk
  where chunk.document_version_id = any(p_version_ids)
    and chunk.embedding is not null
  order by chunk.embedding <=> p_query_embedding::vector
  limit greatest(p_limit, 1);
$$;

revoke all on function public.match_source_chunks(uuid[], text, integer) from public, anon, authenticated;
grant execute on function public.match_source_chunks(uuid[], text, integer) to service_role;
