-- A builder can fail before its internal repair loop runs (for example, because a
-- model response cannot be parsed). Previously the worker archived that job and the
-- course remained permanently "building". Persist a small retry budget and atomically
-- enqueue the next attempt before the worker archives the failed message.
alter table public.lesson_definitions
  add column if not exists build_retry_count integer not null default 0
  check (build_retry_count >= 0);

create or replace function public.retry_lesson_build(
  p_lesson_definition_id uuid,
  p_max_retries integer default 2
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_retry_count integer;
begin
  update public.lesson_definitions
  set build_retry_count = build_retry_count + 1
  where id = p_lesson_definition_id
    and build_status in ('building', 'failed')
  returning build_retry_count into v_retry_count;

  if v_retry_count is null or v_retry_count > greatest(p_max_retries, 0) then
    return false;
  end if;

  update public.lesson_definitions
  set build_status = 'pending', build_claimed_at = null
  where id = p_lesson_definition_id;

  perform pgmq.send(
    'generation_jobs',
    jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', p_lesson_definition_id)
  );
  return true;
end;
$$;

revoke all on function public.retry_lesson_build(uuid, integer) from public, anon, authenticated;
grant execute on function public.retry_lesson_build(uuid, integer) to service_role;

-- An explicit user resume is a new recovery attempt, so restore its bounded retry
-- budget as well as reclaiming stale claims. Completed lessons remain untouched.
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
  set build_status = 'pending', build_claimed_at = null, build_retry_count = 0
  where course_version_id = v_version_id
    and kind = 'lesson'
    and (
      build_status = 'failed'
      or (build_status = 'building' and (
        build_claimed_at is null
        or build_claimed_at < now() - interval '5 minutes'
      ))
    );

  return public.enqueue_lesson_builds(v_version_id);
end;
$$;

revoke all on function public.resume_course_lesson_builds(uuid, uuid) from public, anon, authenticated;
grant execute on function public.resume_course_lesson_builds(uuid, uuid) to service_role;
