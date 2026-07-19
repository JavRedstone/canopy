-- Pilot: a course can target C++ labs instead of just Python. `language` is a
-- course-level setting (same shape as quiz_max_attempts) fixed at creation time --
-- changing it after generation would leave a course with mixed-language labs, so it's
-- not exposed on update_course, only create_course. The lesson builder reads it via
-- claim_lesson_build to pick the right generation prompt and sandbox environment for
-- every coding lab in the course.

alter table public.courses
  add column if not exists language text not null default 'python'
  check (language in ('python', 'cpp'));

-- The return row type gains `language`, which "create or replace" cannot do.
drop function if exists public.claim_lesson_build(uuid, integer);

create or replace function public.claim_lesson_build(p_lesson_definition_id uuid, p_stale_seconds integer default 300)
returns table(
  lesson_definition_id uuid,
  course_version_id uuid,
  concept_id uuid,
  concept_slug text,
  concept_kind text,
  concept_title text,
  summary_markdown text,
  citations_json jsonb,
  next_revision integer,
  pending_content_json jsonb,
  language text
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  return query
  update public.lesson_definitions as ld
  set build_status = 'building', build_claimed_at = now(), build_error = null
  from public.concepts as c
  left join public.concept_summaries as cs on cs.concept_id = c.id
  join public.course_versions as cv on cv.id = ld.course_version_id
  join public.courses as co on co.id = cv.course_id
  where ld.id = p_lesson_definition_id
    and ld.concept_id = c.id
    and (
      ld.build_status in ('pending', 'failed')
      or (ld.build_status = 'building' and ld.build_claimed_at < now() - make_interval(secs => greatest(p_stale_seconds, 1)))
    )
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
    ) + 1,
    ld.pending_content_json,
    co.language;
end;
$$;

revoke all on function public.claim_lesson_build(uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_lesson_build(uuid, integer) to service_role;
