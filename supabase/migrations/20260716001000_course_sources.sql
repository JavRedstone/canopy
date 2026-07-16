create table public.course_sources (
  course_id uuid not null references public.courses (id) on delete cascade,
  source_document_id uuid not null references public.source_documents (id) on delete restrict,
  position integer not null check (position > 0),
  created_at timestamptz not null default now(),
  primary key (course_id, source_document_id),
  unique (course_id, position)
);

alter table public.course_sources enable row level security;

create policy "course sources visible to course owner" on public.course_sources
  for select to authenticated using (
    exists (
      select 1 from public.courses c
      where c.id = course_id and c.owner_id = auth.uid()
    )
  );
