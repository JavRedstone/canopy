alter table public.course_versions
  drop constraint if exists course_versions_status_check;

alter table public.course_versions
  add constraint course_versions_status_check
  check (status in ('planning', 'generating', 'ready', 'failed', 'archived'));

create or replace function public.enqueue_source_ingestion(p_source_id uuid, p_owner_id uuid)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_message_id bigint;
begin
  update public.source_documents
  set status = 'ingesting', updated_at = now()
  where id = p_source_id
    and owner_id = p_owner_id
    and status = 'uploaded';

  if not found then
    raise exception 'Source is not ready to enqueue for ingestion' using errcode = 'P0002';
  end if;

  select * into v_message_id
  from pgmq.send('ingestion_jobs', jsonb_build_object('source_id', p_source_id));
  return v_message_id;
end;
$$;

create or replace function public.enqueue_course_planning(p_course_id uuid, p_owner_id uuid)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_message_id bigint;
begin
  if not exists (
    select 1
    from public.courses
    where id = p_course_id
      and owner_id = p_owner_id
      and status = 'draft'
  ) then
    raise exception 'Course is not available for planning' using errcode = 'P0002';
  end if;

  select * into v_message_id
  from pgmq.send(
    'generation_jobs',
    jsonb_build_object('type', 'course_planning', 'course_id', p_course_id)
  );
  return v_message_id;
end;
$$;

create or replace function public.read_ingestion_jobs(p_visibility_seconds integer, p_limit integer)
returns table(message_id bigint, message jsonb)
language sql
security definer
set search_path = pg_catalog, pgmq
as $$
  select record.msg_id, record.message
  from pgmq.read('ingestion_jobs', greatest(p_visibility_seconds, 1), greatest(p_limit, 1)) as record;
$$;

create or replace function public.read_generation_jobs(p_visibility_seconds integer, p_limit integer)
returns table(message_id bigint, message jsonb)
language sql
security definer
set search_path = pg_catalog, pgmq
as $$
  select record.msg_id, record.message
  from pgmq.read('generation_jobs', greatest(p_visibility_seconds, 1), greatest(p_limit, 1)) as record;
$$;

create or replace function public.archive_ingestion_job(p_message_id bigint)
returns boolean
language sql
security definer
set search_path = pg_catalog, pgmq
as $$
  select pgmq.archive('ingestion_jobs', p_message_id);
$$;

create or replace function public.archive_generation_job(p_message_id bigint)
returns boolean
language sql
security definer
set search_path = pg_catalog, pgmq
as $$
  select pgmq.archive('generation_jobs', p_message_id);
$$;

create or replace function public.claim_course_planning(p_course_id uuid)
returns table(course_version_id uuid, course_id uuid, goal text, source_set_hash text)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  return query
  update public.course_versions as version
  set status = 'generating'
  from public.courses as course
  where course.id = p_course_id
    and version.id = course.active_version_id
    and version.status = 'planning'
    and not exists (
      select 1
      from public.course_sources as course_source
      join public.source_documents as source on source.id = course_source.source_document_id
      where course_source.course_id = course.id
        and source.status <> 'ready'
    )
  returning version.id, course.id, course.goal, course.source_set_hash;
end;
$$;

create or replace function public.apply_course_plan(p_course_version_id uuid, p_plan jsonb)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_course_id uuid;
  v_source_set_hash text;
begin
  select version.course_id, course.source_set_hash
  into v_course_id, v_source_set_hash
  from public.course_versions as version
  join public.courses as course on course.id = version.course_id
  where version.id = p_course_version_id
    and version.status = 'generating'
  for update of version;

  if not found then
    raise exception 'Course version is not claimed for planning' using errcode = 'P0002';
  end if;

  if p_plan ->> 'source_set_hash' <> v_source_set_hash then
    raise exception 'Planner source set does not match the course' using errcode = '22000';
  end if;

  with module_entries as (
    select value as entry, ordinality as position
    from jsonb_array_elements(p_plan -> 'modules') with ordinality
  )
  insert into public.modules (course_version_id, position, title)
  select p_course_version_id, position, entry ->> 'title'
  from module_entries;

  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_plan -> 'concepts')
  )
  insert into public.concepts (course_version_id, slug, title, kind)
  select
    p_course_version_id,
    entry ->> 'id',
    entry ->> 'title',
    entry ->> 'kind'
  from concept_entries;

  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_plan -> 'concepts')
  )
  insert into public.concept_summaries (concept_id, summary_markdown, citations_json)
  select
    concept.id,
    entry ->> 'summary_markdown',
    coalesce(entry -> 'citations', '[]'::jsonb)
  from concept_entries
  join public.concepts as concept
    on concept.course_version_id = p_course_version_id
    and concept.slug = concept_entries.entry ->> 'id';

  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_plan -> 'concepts')
  )
  insert into public.concept_prerequisites (concept_id, prerequisite_concept_id)
  select concept.id, prerequisite.id
  from concept_entries
  cross join lateral jsonb_array_elements_text(
    coalesce(concept_entries.entry -> 'prerequisites', '[]'::jsonb)
  ) as prerequisite_slug(slug)
  join public.concepts as concept
    on concept.course_version_id = p_course_version_id
    and concept.slug = concept_entries.entry ->> 'id'
  join public.concepts as prerequisite
    on prerequisite.course_version_id = p_course_version_id
    and prerequisite.slug = prerequisite_slug.slug;

  with module_entries as (
    select value as entry, ordinality as position
    from jsonb_array_elements(p_plan -> 'modules') with ordinality
  )
  insert into public.lesson_definitions (course_version_id, module_id, concept_id, kind)
  select p_course_version_id, module.id, concept.id, 'lesson'
  from module_entries
  cross join lateral jsonb_array_elements_text(module_entries.entry -> 'concept_ids') as concept_slug(slug)
  join public.modules as module
    on module.course_version_id = p_course_version_id
    and module.position = module_entries.position
  join public.concepts as concept
    on concept.course_version_id = p_course_version_id
    and concept.slug = concept_slug.slug;

  update public.course_versions
  set status = 'ready'
  where id = p_course_version_id;

  update public.courses
  set status = 'ready', updated_at = now()
  where id = v_course_id;
end;
$$;

revoke all on function public.enqueue_source_ingestion(uuid, uuid) from public, anon, authenticated;
revoke all on function public.enqueue_course_planning(uuid, uuid) from public, anon, authenticated;
revoke all on function public.read_ingestion_jobs(integer, integer) from public, anon, authenticated;
revoke all on function public.read_generation_jobs(integer, integer) from public, anon, authenticated;
revoke all on function public.archive_ingestion_job(bigint) from public, anon, authenticated;
revoke all on function public.archive_generation_job(bigint) from public, anon, authenticated;
revoke all on function public.claim_course_planning(uuid) from public, anon, authenticated;
revoke all on function public.apply_course_plan(uuid, jsonb) from public, anon, authenticated;

grant execute on function public.enqueue_source_ingestion(uuid, uuid) to service_role;
grant execute on function public.enqueue_course_planning(uuid, uuid) to service_role;
grant execute on function public.read_ingestion_jobs(integer, integer) to service_role;
grant execute on function public.read_generation_jobs(integer, integer) to service_role;
grant execute on function public.archive_ingestion_job(bigint) to service_role;
grant execute on function public.archive_generation_job(bigint) to service_role;
grant execute on function public.claim_course_planning(uuid) to service_role;
grant execute on function public.apply_course_plan(uuid, jsonb) to service_role;
