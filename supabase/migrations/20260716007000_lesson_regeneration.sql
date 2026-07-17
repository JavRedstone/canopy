alter table public.lesson_definitions
  add column if not exists generation_requested_at timestamptz;

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
  v_concept_id uuid;
  v_concept_kind text;
  v_message_id bigint;
begin
  select lesson.id, concept.id, concept.kind into v_lesson_definition_id, v_concept_id, v_concept_kind
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

  if v_concept_kind = 'coding' then
    update public.lesson_definitions set build_status = 'pending' where id = v_lesson_definition_id;
    select * into v_message_id from pgmq.send(
      'generation_jobs', jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', v_lesson_definition_id)
    );
  else
    update public.lesson_definitions
    set build_status = 'pending', generation_requested_at = now()
    where id = v_lesson_definition_id;
    select * into v_message_id from pgmq.send(
      'generation_jobs', jsonb_build_object(
        'type', 'concept_regeneration', 'concept_id', v_concept_id, 'lesson_definition_id', v_lesson_definition_id
      )
    );
  end if;
  return v_message_id;
end;
$$;

revoke all on function public.regenerate_lesson_build(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.regenerate_lesson_build(uuid, uuid, text) to service_role;
