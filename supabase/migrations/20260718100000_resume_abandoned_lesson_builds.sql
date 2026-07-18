-- Resume previously skipped abandoned `building` lessons because
-- enqueue_lesson_builds only selects pending/failed rows. Reclaim only claims
-- older than the worker's default five-minute queue lease; a fresh build may
-- still be performing its model, sandbox, or repair work.
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

  update public.lesson_definitions
  set build_status = 'pending', build_claimed_at = null
  where course_version_id = v_version_id
    and kind = 'lesson'
    and build_status = 'building'
    and (
      build_claimed_at is null
      or build_claimed_at < now() - interval '5 minutes'
    );

  return public.enqueue_lesson_builds(v_version_id);
end;
$$;

revoke all on function public.resume_course_lesson_builds(uuid, uuid) from public, anon, authenticated;
grant execute on function public.resume_course_lesson_builds(uuid, uuid) to service_role;
