alter table public.courses add column lesson_min integer not null default 3 check (lesson_min between 1 and 24);
alter table public.courses add column lesson_max integer not null default 6 check (lesson_max between 1 and 24 and lesson_max >= lesson_min);

create or replace function public.claim_course_planning(p_course_id uuid)
returns table(course_version_id uuid, course_id uuid, goal text, source_set_hash text, lesson_min integer, lesson_max integer)
language plpgsql security definer set search_path = pg_catalog, public
as $$
begin
  return query update public.course_versions as version set status = 'generating' from public.courses as course
  where course.id = p_course_id and version.id = course.active_version_id and version.status = 'planning'
    and not exists (select 1 from public.course_sources cs join public.source_documents s on s.id = cs.source_document_id where cs.course_id = course.id and s.status <> 'ready')
  returning version.id, course.id, course.goal, course.source_set_hash, course.lesson_min, course.lesson_max;
end;
$$;
