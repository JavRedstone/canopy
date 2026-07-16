create or replace function public.reset_course_planning(p_course_version_id uuid)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  delete from public.lesson_definitions where course_version_id = p_course_version_id;
  delete from public.concept_prerequisites
  where concept_id in (select id from public.concepts where course_version_id = p_course_version_id)
     or prerequisite_concept_id in (select id from public.concepts where course_version_id = p_course_version_id);
  delete from public.concept_summaries
  where concept_id in (select id from public.concepts where course_version_id = p_course_version_id);
  delete from public.concepts where course_version_id = p_course_version_id;
  delete from public.modules where course_version_id = p_course_version_id;
end;
$$;

create or replace function public.apply_course_skeleton(p_course_version_id uuid, p_modules jsonb)
returns table(module_id uuid, module_position integer)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  return query
  with module_entries as (
    select value as entry, ordinality as entry_position
    from jsonb_array_elements(p_modules) with ordinality
  )
  insert into public.modules (course_version_id, position, title)
  select p_course_version_id, module_entries.entry_position, entry ->> 'title'
  from module_entries
  returning id, modules.position;
end;
$$;

create or replace function public.apply_module_concepts(p_course_version_id uuid, p_module_id uuid, p_concepts jsonb)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_concepts)
  )
  insert into public.concepts (course_version_id, slug, title, kind)
  select p_course_version_id, entry ->> 'id', entry ->> 'title', entry ->> 'kind'
  from concept_entries;

  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_concepts)
  )
  insert into public.concept_summaries (concept_id, summary_markdown, citations_json)
  select concept.id, entry ->> 'summary_markdown', coalesce(entry -> 'citations', '[]'::jsonb)
  from concept_entries
  join public.concepts as concept
    on concept.course_version_id = p_course_version_id
    and concept.slug = concept_entries.entry ->> 'id';

  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_concepts)
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

  with concept_entries as (
    select value as entry
    from jsonb_array_elements(p_concepts)
  )
  insert into public.lesson_definitions (course_version_id, module_id, concept_id, kind)
  select p_course_version_id, p_module_id, concept.id, 'lesson'
  from concept_entries
  join public.concepts as concept
    on concept.course_version_id = p_course_version_id
    and concept.slug = concept_entries.entry ->> 'id';
end;
$$;

create or replace function public.finalize_course_plan(p_course_version_id uuid)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_course_id uuid;
begin
  select course_id into v_course_id from public.course_versions where id = p_course_version_id;
  if v_course_id is null then
    raise exception 'Course version not found' using errcode = 'P0002';
  end if;

  update public.course_versions set status = 'ready' where id = p_course_version_id;
  update public.courses set status = 'ready', updated_at = now() where id = v_course_id;

  perform public.enqueue_lesson_builds(p_course_version_id);
end;
$$;

revoke all on function public.reset_course_planning(uuid) from public, anon, authenticated;
revoke all on function public.apply_course_skeleton(uuid, jsonb) from public, anon, authenticated;
revoke all on function public.apply_module_concepts(uuid, uuid, jsonb) from public, anon, authenticated;
revoke all on function public.finalize_course_plan(uuid) from public, anon, authenticated;

grant execute on function public.reset_course_planning(uuid) to service_role;
grant execute on function public.apply_course_skeleton(uuid, jsonb) to service_role;
grant execute on function public.apply_module_concepts(uuid, uuid, jsonb) to service_role;
grant execute on function public.finalize_course_plan(uuid) to service_role;
