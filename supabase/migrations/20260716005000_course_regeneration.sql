create or replace function public.regenerate_course_planning(p_course_id uuid, p_owner_id uuid)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_next_version integer;
  v_new_version_id uuid;
  v_message_id bigint;
begin
  if not exists (
    select 1 from public.courses where id = p_course_id and owner_id = p_owner_id
  ) then
    raise exception 'Course not found' using errcode = 'P0002';
  end if;

  select coalesce(max(version), 0) + 1 into v_next_version
  from public.course_versions
  where course_id = p_course_id;

  insert into public.course_versions (course_id, version, status)
  values (p_course_id, v_next_version, 'planning')
  returning id into v_new_version_id;

  update public.courses
  set status = 'draft', active_version_id = v_new_version_id, updated_at = now()
  where id = p_course_id and owner_id = p_owner_id;

  v_message_id := public.enqueue_course_planning(p_course_id, p_owner_id);
  return v_message_id;
end;
$$;

revoke all on function public.regenerate_course_planning(uuid, uuid) from public, anon, authenticated;
grant execute on function public.regenerate_course_planning(uuid, uuid) to service_role;
