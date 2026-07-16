alter table public.source_documents
  add constraint source_documents_allowed_mime_type
  check (mime_type in ('application/pdf', 'text/markdown', 'text/plain')),
  add constraint source_documents_byte_size_limit
  check (byte_size > 0 and byte_size <= 6291456);

update storage.buckets
set
  file_size_limit = 6291456,
  allowed_mime_types = array['application/pdf', 'text/markdown', 'text/plain']::text[]
where id = 'sources';
