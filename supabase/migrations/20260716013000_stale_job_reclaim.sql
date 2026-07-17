-- A worker that dies between claiming a job (course planning -> 'generating',
-- lesson build -> 'building') and finishing it leaves the row stuck in that
-- in-progress status forever: claim_course_planning/claim_lesson_build only match
-- pending/failed rows, so once the underlying pgmq message is redelivered after its
-- visibility timeout, the claim silently matches nothing, no exception is raised, and
-- the worker archives the message anyway -- discarding the only remaining retry.
--
-- Track when each claim happened and let both claim functions also reclaim rows whose
-- claim is older than the caller's own queue visibility window: by then, a live worker
-- would already have finished or reset the row, so it's provably abandoned.

alter table public.course_versions
  add column if not exists claimed_at timestamptz;

alter table public.lesson_definitions
  add column if not exists build_claimed_at timestamptz;

drop function if exists public.claim_course_planning(uuid);

create or replace function public.claim_course_planning(p_course_id uuid, p_stale_seconds integer default 300)
returns table(course_version_id uuid, course_id uuid, goal text, source_set_hash text, lesson_min integer, lesson_max integer)
language plpgsql security definer set search_path = pg_catalog, public
as $$
begin
  return query
  update public.course_versions as version
  set status = 'generating', claimed_at = now()
  from public.courses as course
  where course.id = p_course_id
    and version.id = course.active_version_id
    and (
      version.status = 'planning'
      or (version.status = 'generating' and version.claimed_at < now() - make_interval(secs => greatest(p_stale_seconds, 1)))
    )
    and not exists (
      select 1
      from public.course_sources cs
      join public.source_documents s on s.id = cs.source_document_id
      where cs.course_id = course.id and s.status <> 'ready'
    )
  returning version.id, course.id, course.goal, course.source_set_hash, course.lesson_min, course.lesson_max;
end;
$$;

revoke all on function public.claim_course_planning(uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_course_planning(uuid, integer) to service_role;

drop function if exists public.claim_lesson_build(uuid);

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
  next_revision integer
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  return query
  update public.lesson_definitions as ld
  set build_status = 'building', build_claimed_at = now()
  from public.concepts as c
  left join public.concept_summaries as cs on cs.concept_id = c.id
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
    ) + 1;
end;
$$;

revoke all on function public.claim_lesson_build(uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_lesson_build(uuid, integer) to service_role;
