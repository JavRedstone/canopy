-- Resume only incomplete lesson jobs for a course. This deliberately preserves
-- built lesson definitions and revisions; full course regeneration remains a
-- separate, explicit operation.
create or replace function public.resume_course_lesson_builds(p_course_id uuid, p_owner_id uuid)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_version_id uuid;
begin
  select active_version_id into v_version_id
  from public.courses
  where id = p_course_id and owner_id = p_owner_id;

  if v_version_id is null then
    raise exception 'Course not found' using errcode = 'P0002';
  end if;

  -- `enqueue_lesson_builds` targets pending and failed definitions only. It
  -- never touches built definitions, so a resume cannot discard good work.
  return public.enqueue_lesson_builds(v_version_id);
end;
$$;

revoke all on function public.resume_course_lesson_builds(uuid, uuid) from public, anon, authenticated;
grant execute on function public.resume_course_lesson_builds(uuid, uuid) to service_role;
