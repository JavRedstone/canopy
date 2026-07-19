-- Fix: claim_lesson_build was unclaimable, so no lesson ever built.
--
-- 20260718130000_course_language.sql redefined claim_lesson_build to also return the
-- course's `language`, adding `join public.courses co on co.id = cv.course_id` and, before
-- it, `join public.course_versions cv on cv.id = ld.course_version_id`. That second join's
-- ON clause references `ld` -- the UPDATE target table -- from inside an explicit JOIN in
-- the UPDATE ... FROM list. Postgres forbids that: the update target is only visible at the
-- top level of FROM/WHERE, not inside a nested JOIN's ON. Every call raised
--   42P01  invalid reference to FROM-clause entry for table "ld"
-- which PostgREST surfaces as a 404, which the worker misreads as a transient error and
-- requeues forever -- leaving all lesson_definitions stuck at build_status = 'pending'.
--
-- Same query, made legal: course_versions and courses move out of explicit JOINs into the
-- comma-separated FROM list, and their join predicates move into WHERE, where referencing
-- the update target `ld` is allowed. concept_summaries stays a LEFT JOIN on concepts (it is
-- genuinely optional and never references ld). Return type is unchanged, so create-or-replace
-- suffices -- no drop needed.

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
  left join public.concept_summaries as cs on cs.concept_id = c.id,
       public.course_versions as cv,
       public.courses as co
  where ld.id = p_lesson_definition_id
    and ld.concept_id = c.id
    and cv.id = ld.course_version_id
    and co.id = cv.course_id
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
