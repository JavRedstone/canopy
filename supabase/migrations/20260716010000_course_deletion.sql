create or replace function public.delete_course(p_course_id uuid, p_owner_id uuid)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
begin
  if not exists (
    select 1 from public.courses where id = p_course_id and owner_id = p_owner_id
  ) then
    raise exception 'Course not found' using errcode = 'P0002';
  end if;

  -- Drop queued lesson builds so workers do not pick up jobs for deleted rows.
  delete from pgmq.q_generation_jobs as job
  where job.message ->> 'lesson_definition_id' in (
    select ld.id::text
    from public.lesson_definitions ld
    join public.course_versions cv on cv.id = ld.course_version_id
    where cv.course_id = p_course_id
  );

  -- Assignments hold ON DELETE RESTRICT references to lesson revisions and
  -- support artifacts, so they must go before the course cascade can run.
  delete from public.learner_lesson_assignments a
  where a.lesson_revision_id in (
      select lr.id
      from public.lesson_revisions lr
      join public.lesson_definitions ld on ld.id = lr.lesson_definition_id
      join public.course_versions cv on cv.id = ld.course_version_id
      where cv.course_id = p_course_id
    )
    or a.support_artifact_id in (
      select sa.id
      from public.support_lesson_artifacts sa
      join public.course_versions cv on cv.id = sa.course_version_id
      where cv.course_id = p_course_id
    );

  delete from public.courses
  where id = p_course_id and owner_id = p_owner_id;
end;
$$;

revoke all on function public.delete_course(uuid, uuid) from public, anon, authenticated;
grant execute on function public.delete_course(uuid, uuid) to service_role;
