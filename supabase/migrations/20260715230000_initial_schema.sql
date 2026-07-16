create extension if not exists pgcrypto;
create extension if not exists vector;
create extension if not exists pgmq;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do update set email = excluded.email;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

create table public.source_documents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles (id) on delete cascade,
  filename text not null,
  mime_type text not null,
  byte_size bigint not null check (byte_size >= 0),
  storage_path text not null unique,
  sha256 text,
  status text not null default 'uploading'
    check (status in ('uploading', 'uploaded', 'ingesting', 'ready', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.source_document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.source_documents (id) on delete cascade,
  parser_version text not null,
  parsed_storage_path text,
  created_at timestamptz not null default now()
);

create table public.source_chunks (
  id uuid primary key default gen_random_uuid(),
  document_version_id uuid not null references public.source_document_versions (id) on delete cascade,
  content text not null,
  embedding vector(1536),
  page_number integer,
  section text,
  char_start integer,
  char_end integer,
  created_at timestamptz not null default now()
);

create index source_chunks_embedding_idx
  on public.source_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create table public.courses (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles (id) on delete cascade,
  title text not null,
  goal text not null,
  source_set_hash text not null,
  status text not null default 'draft'
    check (status in ('draft', 'ready', 'archived')),
  active_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.course_versions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses (id) on delete cascade,
  version integer not null check (version > 0),
  status text not null default 'planning'
    check (status in ('planning', 'ready', 'failed', 'archived')),
  planner_schema_version text not null default 'v1',
  created_at timestamptz not null default now(),
  unique (course_id, version)
);

alter table public.courses
  add constraint courses_active_version_fk
  foreign key (active_version_id) references public.course_versions (id) on delete set null;

create table public.concepts (
  id uuid primary key default gen_random_uuid(),
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  slug text not null,
  title text not null,
  kind text not null check (kind in ('conceptual', 'coding')),
  created_at timestamptz not null default now(),
  unique (course_version_id, slug)
);

create table public.concept_summaries (
  concept_id uuid primary key references public.concepts (id) on delete cascade,
  summary_markdown text not null,
  citations_json jsonb not null default '[]'::jsonb,
  revision integer not null default 1,
  created_at timestamptz not null default now()
);

create table public.concept_prerequisites (
  concept_id uuid not null references public.concepts (id) on delete cascade,
  prerequisite_concept_id uuid not null references public.concepts (id) on delete cascade,
  primary key (concept_id, prerequisite_concept_id),
  check (concept_id <> prerequisite_concept_id)
);

create table public.modules (
  id uuid primary key default gen_random_uuid(),
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  position integer not null check (position > 0),
  title text not null,
  unique (course_version_id, position)
);

create table public.lesson_definitions (
  id uuid primary key default gen_random_uuid(),
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  module_id uuid references public.modules (id) on delete set null,
  concept_id uuid not null references public.concepts (id) on delete cascade,
  kind text not null check (kind in ('lesson', 'transfer_check')),
  created_at timestamptz not null default now()
);

create table public.lesson_revisions (
  id uuid primary key default gen_random_uuid(),
  lesson_definition_id uuid not null references public.lesson_definitions (id) on delete cascade,
  revision integer not null check (revision > 0),
  bundle_json jsonb not null,
  validation_status text not null default 'pending'
    check (validation_status in ('pending', 'validated', 'failed')),
  created_at timestamptz not null default now(),
  unique (lesson_definition_id, revision)
);

create table public.support_lesson_artifacts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  target_concept_id uuid references public.concepts (id) on delete set null,
  triggering_event_id uuid,
  kind text not null check (kind in ('remediation', 'extra_examples', 'concise_variant')),
  bundle_json jsonb not null,
  validation_status text not null default 'pending'
    check (validation_status in ('pending', 'validated', 'failed')),
  created_at timestamptz not null default now()
);

create table public.learner_lesson_assignments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  lesson_revision_id uuid references public.lesson_revisions (id) on delete restrict,
  support_artifact_id uuid references public.support_lesson_artifacts (id) on delete restrict,
  route_kind text not null check (route_kind in ('canonical', 'remediation', 'support', 'transfer')),
  status text not null default 'assigned'
    check (status in ('assigned', 'active', 'completed', 'skipped')),
  created_at timestamptz not null default now(),
  check (num_nonnulls(lesson_revision_id, support_artifact_id) = 1)
);

create table public.quiz_responses (
  id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references public.learner_lesson_assignments (id) on delete cascade,
  quiz_item_id text not null,
  idempotency_key text not null,
  response_json jsonb not null,
  result text not null check (result in ('correct', 'incorrect')),
  created_at timestamptz not null default now(),
  unique (assignment_id, quiz_item_id, idempotency_key)
);

create table public.submissions (
  id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references public.learner_lesson_assignments (id) on delete cascade,
  snapshot_path text not null,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'failed')),
  submitted_at timestamptz not null default now()
);

create table public.observations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  concept_id uuid not null references public.concepts (id) on delete cascade,
  track text not null check (track in ('understand', 'apply')),
  assessment_kind text not null check (assessment_kind in ('quiz_mcq', 'quiz_fill', 'coding_submission', 'transfer_exercise')),
  result text not null check (result in ('correct', 'incorrect')),
  support_level text not null default 'independent',
  evidence_id uuid,
  created_at timestamptz not null default now()
);

create table public.mastery (
  user_id uuid not null references public.profiles (id) on delete cascade,
  concept_id uuid not null references public.concepts (id) on delete cascade,
  track text not null check (track in ('understand', 'apply')),
  p_l double precision not null default 0.2 check (p_l >= 0 and p_l <= 1),
  opportunities integer not null default 0 check (opportunities >= 0),
  last_update timestamptz not null default now(),
  primary key (user_id, concept_id, track)
);

create table public.mastery_parameters (
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  concept_id uuid references public.concepts (id) on delete cascade,
  track text not null check (track in ('understand', 'apply')),
  assessment_kind text not null check (assessment_kind in ('quiz_mcq', 'quiz_fill', 'coding_submission', 'transfer_exercise')),
  p_l0 double precision not null check (p_l0 >= 0 and p_l0 <= 1),
  p_t double precision not null check (p_t >= 0 and p_t <= 1),
  p_g double precision not null check (p_g >= 0 and p_g <= 1),
  p_s double precision not null check (p_s >= 0 and p_s <= 1),
  primary key (course_version_id, concept_id, track, assessment_kind)
);

create table public.adaptation_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  event_type text not null,
  reason_json jsonb not null default '{}'::jsonb,
  decision text not null default 'proposed'
    check (decision in ('proposed', 'accepted', 'deferred', 'declined')),
  created_at timestamptz not null default now()
);

alter table public.support_lesson_artifacts
  add constraint support_artifact_event_fk
  foreign key (triggering_event_id) references public.adaptation_events (id) on delete set null;

insert into storage.buckets (id, name, public)
values ('sources', 'sources', false), ('submissions', 'submissions', false)
on conflict (id) do nothing;

select pgmq.create('ingestion_jobs');
select pgmq.create('generation_jobs');
select pgmq.create('evaluation_jobs');

alter table public.profiles enable row level security;
alter table public.source_documents enable row level security;
alter table public.source_document_versions enable row level security;
alter table public.source_chunks enable row level security;
alter table public.courses enable row level security;
alter table public.course_versions enable row level security;
alter table public.concepts enable row level security;
alter table public.concept_summaries enable row level security;
alter table public.concept_prerequisites enable row level security;
alter table public.modules enable row level security;
alter table public.lesson_definitions enable row level security;
alter table public.lesson_revisions enable row level security;
alter table public.support_lesson_artifacts enable row level security;
alter table public.learner_lesson_assignments enable row level security;
alter table public.quiz_responses enable row level security;
alter table public.submissions enable row level security;
alter table public.observations enable row level security;
alter table public.mastery enable row level security;
alter table public.mastery_parameters enable row level security;
alter table public.adaptation_events enable row level security;

create policy "profiles are self readable" on public.profiles
  for select to authenticated using (id = auth.uid());

create policy "sources belong to owner" on public.source_documents
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());

create policy "courses belong to owner" on public.courses
  for all to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());

create policy "course versions visible to owner" on public.course_versions
  for select to authenticated using (
    exists (select 1 from public.courses c where c.id = course_id and c.owner_id = auth.uid())
  );

create policy "concepts visible to course owner" on public.concepts
  for select to authenticated using (
    exists (
      select 1 from public.course_versions cv
      join public.courses c on c.id = cv.course_id
      where cv.id = course_version_id and c.owner_id = auth.uid()
    )
  );

create policy "concept summaries visible to course owner" on public.concept_summaries
  for select to authenticated using (
    exists (
      select 1 from public.concepts co
      join public.course_versions cv on cv.id = co.course_version_id
      join public.courses c on c.id = cv.course_id
      where co.id = concept_id and c.owner_id = auth.uid()
    )
  );

create policy "support artifacts belong to learner" on public.support_lesson_artifacts
  for select to authenticated using (user_id = auth.uid());

create policy "assignments belong to learner" on public.learner_lesson_assignments
  for select to authenticated using (user_id = auth.uid());

create policy "quiz responses through own assignment" on public.quiz_responses
  for select to authenticated using (
    exists (select 1 from public.learner_lesson_assignments a where a.id = assignment_id and a.user_id = auth.uid())
  );

create policy "submissions through own assignment" on public.submissions
  for select to authenticated using (
    exists (select 1 from public.learner_lesson_assignments a where a.id = assignment_id and a.user_id = auth.uid())
  );

create policy "observations belong to learner" on public.observations
  for select to authenticated using (user_id = auth.uid());

create policy "mastery belongs to learner" on public.mastery
  for select to authenticated using (user_id = auth.uid());

create policy "adaptation events belong to learner" on public.adaptation_events
  for select to authenticated using (user_id = auth.uid());

create policy "source uploads in own folder" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'sources' and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "source reads in own folder" on storage.objects
  for select to authenticated using (
    bucket_id = 'sources' and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "submission reads in own folder" on storage.objects
  for select to authenticated using (
    bucket_id = 'submissions' and (storage.foldername(name))[1] = auth.uid()::text
  );
