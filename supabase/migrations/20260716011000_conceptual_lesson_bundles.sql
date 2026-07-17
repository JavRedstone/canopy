-- Conceptual lessons become v2 bundles built through the same lesson_build pipeline as
-- coding lessons: enqueue at plan time, claim with the concept kind, store revisions in
-- lesson_revisions. concept_summaries stays the short course-map summary and is no
-- longer overwritten by regeneration. The concept_regeneration job type is retired
-- (workers map any in-flight message onto lesson_build).

create or replace function public.enqueue_lesson_builds(p_course_version_id uuid)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_lesson record;
  v_count integer := 0;
begin
  for v_lesson in
    select ld.id, c.kind
    from public.lesson_definitions as ld
    join public.concepts as c on c.id = ld.concept_id
    where ld.course_version_id = p_course_version_id
      and ld.kind = 'lesson'
      and ld.build_status in ('pending', 'failed')
  loop
    -- The API uses generation_requested_at to distinguish "a build is really queued"
    -- from legacy conceptual definitions that never had one.
    if v_lesson.kind = 'conceptual' then
      update public.lesson_definitions
      set generation_requested_at = now()
      where id = v_lesson.id;
    end if;
    perform pgmq.send(
      'generation_jobs',
      jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', v_lesson.id)
    );
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;

-- The return row type gains concept_kind, which "create or replace" cannot do.
drop function if exists public.claim_lesson_build(uuid);

create or replace function public.claim_lesson_build(p_lesson_definition_id uuid)
returns table(
  lesson_definition_id uuid,
  course_version_id uuid,
  concept_id uuid,
  concept_slug text,
  concept_kind text,
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
    c.kind,
    c.title,
    coalesce(cs.summary_markdown, ''),
    coalesce(cs.citations_json, '[]'::jsonb),
    coalesce(
      (select max(lr.revision) from public.lesson_revisions as lr where lr.lesson_definition_id = ld.id), 0
    ) + 1;
end;
$$;

create or replace function public.regenerate_lesson_build(
  p_course_id uuid,
  p_owner_id uuid,
  p_concept_slug text
)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_lesson_definition_id uuid;
  v_concept_kind text;
  v_message_id bigint;
begin
  select lesson.id, concept.kind into v_lesson_definition_id, v_concept_kind
  from public.lesson_definitions as lesson
  join public.concepts as concept on concept.id = lesson.concept_id
  join public.course_versions as version on version.id = lesson.course_version_id
  join public.courses as course on course.id = version.course_id
  where course.id = p_course_id
    and course.owner_id = p_owner_id
    and version.id = course.active_version_id
    and lesson.kind = 'lesson'
    and concept.slug = p_concept_slug;

  if v_lesson_definition_id is null then
    raise exception 'Lesson not found' using errcode = 'P0002';
  end if;

  update public.lesson_definitions
  set build_status = 'pending',
      generation_requested_at = case when v_concept_kind = 'conceptual' then now() else generation_requested_at end
  where id = v_lesson_definition_id;

  select * into v_message_id from pgmq.send(
    'generation_jobs', jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', v_lesson_definition_id)
  );
  return v_message_id;
end;
$$;

revoke all on function public.enqueue_lesson_builds(uuid) from public, anon, authenticated;
revoke all on function public.claim_lesson_build(uuid) from public, anon, authenticated;
revoke all on function public.regenerate_lesson_build(uuid, uuid, text) from public, anon, authenticated;

grant execute on function public.enqueue_lesson_builds(uuid) to service_role;
grant execute on function public.claim_lesson_build(uuid) to service_role;
grant execute on function public.regenerate_lesson_build(uuid, uuid, text) to service_role;

-- Backfill: existing ready courses get their conceptual lessons (and any failed coding
-- builds) queued so they upgrade to full bundles without a manual regeneration.
select public.enqueue_lesson_builds(cv.id)
from public.course_versions as cv
where cv.status = 'ready';
