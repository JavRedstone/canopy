create or replace function public.cancel_course_lesson_generation(
  p_course_id uuid,
  p_owner_id uuid
)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_version_id uuid;
  v_deleted integer;
begin
  select active_version_id into v_version_id
  from public.courses
  where id = p_course_id and owner_id = p_owner_id;

  if v_version_id is null then
    raise exception 'Course not found' using errcode = 'P0002';
  end if;

  -- Prevent a job already leased by a worker from applying a stale bundle.
  update public.lesson_definitions
  set build_status = 'failed'
  where course_version_id = v_version_id and kind = 'lesson';

  delete from pgmq.q_generation_jobs as job
  where job.message ->> 'lesson_definition_id' in (
    select id::text
    from public.lesson_definitions
    where course_version_id = v_version_id and kind = 'lesson'
  );
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;

revoke all on function public.cancel_course_lesson_generation(uuid, uuid) from public, anon, authenticated;
grant execute on function public.cancel_course_lesson_generation(uuid, uuid) to service_role;
