alter table public.lesson_definitions
  add column build_status text not null default 'pending'
  check (build_status in ('pending', 'building', 'built', 'failed'));

create or replace function public.enqueue_lesson_builds(p_course_version_id uuid)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_lesson_definition_id uuid;
  v_count integer := 0;
begin
  for v_lesson_definition_id in
    select ld.id
    from public.lesson_definitions as ld
    join public.concepts as c on c.id = ld.concept_id
    where ld.course_version_id = p_course_version_id
      and ld.kind = 'lesson'
      and c.kind = 'coding'
      and ld.build_status in ('pending', 'failed')
  loop
    perform pgmq.send(
      'generation_jobs',
      jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', v_lesson_definition_id)
    );
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;

create or replace function public.claim_lesson_build(p_lesson_definition_id uuid)
returns table(
  lesson_definition_id uuid,
  course_version_id uuid,
  concept_id uuid,
  concept_slug text,
  concept_title text,
  summary_markdown text,
  citations_json jsonb,
  next_revision integer
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  return query
  update public.lesson_definitions as ld
  set build_status = 'building'
  from public.concepts as c
  left join public.concept_summaries as cs on cs.concept_id = c.id
  where ld.id = p_lesson_definition_id
    and ld.concept_id = c.id
    and ld.build_status in ('pending', 'failed')
  returning
    ld.id,
    ld.course_version_id,
    c.id,
    c.slug,
    c.title,
    coalesce(cs.summary_markdown, ''),
    coalesce(cs.citations_json, '[]'::jsonb),
    coalesce(
      (select max(lr.revision) from public.lesson_revisions as lr where lr.lesson_definition_id = ld.id), 0
    ) + 1;
end;
$$;

create or replace function public.apply_lesson_bundle(
  p_lesson_definition_id uuid,
  p_revision integer,
  p_bundle jsonb,
  p_validation_status text
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_revision_id uuid;
begin
  if p_validation_status not in ('validated', 'failed') then
    raise exception 'Invalid validation status' using errcode = '22000';
  end if;

  if not exists (
    select 1 from public.lesson_definitions
    where id = p_lesson_definition_id and build_status = 'building'
  ) then
    raise exception 'Lesson definition is not claimed for build' using errcode = 'P0002';
  end if;

  insert into public.lesson_revisions (lesson_definition_id, revision, bundle_json, validation_status)
  values (p_lesson_definition_id, p_revision, p_bundle, p_validation_status)
  returning id into v_revision_id;

  update public.lesson_definitions
  set build_status = case when p_validation_status = 'validated' then 'built' else 'failed' end
  where id = p_lesson_definition_id;

  return v_revision_id;
end;
$$;

revoke all on function public.enqueue_lesson_builds(uuid) from public, anon, authenticated;
revoke all on function public.claim_lesson_build(uuid) from public, anon, authenticated;
revoke all on function public.apply_lesson_bundle(uuid, integer, jsonb, text) from public, anon, authenticated;

grant execute on function public.enqueue_lesson_builds(uuid) to service_role;
grant execute on function public.claim_lesson_build(uuid) to service_role;
grant execute on function public.apply_lesson_bundle(uuid, integer, jsonb, text) to service_role;

-- Extend apply_course_plan (originally defined in 20260716003000_ingestion_and_planning_jobs.sql)
-- with one added line that auto-queues a lesson_build job for every coding-concept lesson slot
-- the moment a course finishes planning, in the same transaction.
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

  perform public.enqueue_lesson_builds(p_course_version_id);

  update public.course_versions
  set status = 'ready'
  where id = p_course_version_id;

  update public.courses
  set status = 'ready', updated_at = now()
  where id = v_course_id;
end;
$$;
