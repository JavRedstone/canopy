-- The ivfflat index on source_chunks.embedding silently broke relevance retrieval.
--
-- match_source_chunks restricts chunks to a course's document versions and then orders
-- by cosine distance. ivfflat is an APPROXIMATE index that probes only a single list by
-- default and returns the globally-nearest candidates *before* the document_version_id
-- filter is applied. With lists = 100 over a small, multi-document table (and centroids
-- built while the table was empty at migration time), the one probed list usually holds
-- none of the target version's chunks -- so the function returned a fragment or, more
-- often, zero rows. The planner then saw an empty source context and built every
-- source-backed course ungrounded, ignoring the uploaded documents entirely.
--
-- At this scale a per-course chunk set is small, so exact nearest-neighbour search is
-- both correct and fast. Drop the approximate index and add a btree on
-- document_version_id so the version filter stays cheap; the ORDER BY distance in
-- match_source_chunks then sorts only the matched rows, exactly.

drop index if exists public.source_chunks_embedding_idx;

create index if not exists source_chunks_document_version_id_idx
  on public.source_chunks (document_version_id);
