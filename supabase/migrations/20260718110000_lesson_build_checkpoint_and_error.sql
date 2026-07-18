-- Two independent lesson-build reliability improvements:
-- 1. pending_content_json checkpoints the validated lesson content once generated, so a
--    worker restart mid-build (crash, redeploy) during the coding-artifacts/repair phase
--    doesn't also have to pay for regenerating the (already-good) content. Cleared on
--    every terminal outcome (apply_lesson_bundle), so it can only resume a single
--    interrupted attempt, never serve stale content across a genuinely new build cycle.
-- 2. build_error records why a build failed -- an exception message or an unresolved
--    sandbox failure -- queryable without worker log access.

alter table public.lesson_definitions
  add column if not exists pending_content_json jsonb,
  add column if not exists build_error text;

-- The return row type gains pending_content_json, which "create or replace" cannot do.
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
  pending_content_json jsonb
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
    ld.pending_content_json;
end;
$$;

revoke all on function public.claim_lesson_build(uuid, integer) from public, anon, authenticated;
grant execute on function public.claim_lesson_build(uuid, integer) to service_role;

create or replace function public.save_lesson_content_checkpoint(p_lesson_definition_id uuid, p_content jsonb)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  update public.lesson_definitions
  set pending_content_json = p_content
  where id = p_lesson_definition_id and build_status = 'building';
end;
$$;

revoke all on function public.save_lesson_content_checkpoint(uuid, jsonb) from public, anon, authenticated;
grant execute on function public.save_lesson_content_checkpoint(uuid, jsonb) to service_role;

-- The signature gains p_build_error, so "create or replace" alone would create a second
-- overload rather than replacing this one -- drop the old 4-arg signature first.
drop function if exists public.apply_lesson_bundle(uuid, integer, jsonb, text);

create or replace function public.apply_lesson_bundle(
  p_lesson_definition_id uuid,
  p_revision integer,
  p_bundle jsonb,
  p_validation_status text,
  p_build_error text default null
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_revision_id uuid;
begin
  if p_validation_status not in ('validated', 'failed') then
    raise exception 'Invalid validation status' using errcode = '22000';
  end if;

  if not exists (
    select 1 from public.lesson_definitions
    where id = p_lesson_definition_id and build_status = 'building'
  ) then
    raise exception 'Lesson definition is not claimed for build' using errcode = 'P0002';
  end if;

  insert into public.lesson_revisions (lesson_definition_id, revision, bundle_json, validation_status)
  values (p_lesson_definition_id, p_revision, p_bundle, p_validation_status)
  returning id into v_revision_id;

  update public.lesson_definitions
  set build_status = case when p_validation_status = 'validated' then 'built' else 'failed' end,
      build_error = case when p_validation_status = 'failed' then p_build_error else null end,
      pending_content_json = null
  where id = p_lesson_definition_id;

  return v_revision_id;
end;
$$;

revoke all on function public.apply_lesson_bundle(uuid, integer, jsonb, text, text) from public, anon, authenticated;
grant execute on function public.apply_lesson_bundle(uuid, integer, jsonb, text, text) to service_role;
