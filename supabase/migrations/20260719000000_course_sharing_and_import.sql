-- Course sharing + import-by-ID.
--
-- Sharing is a Google-Docs-style capability: an owner flips `is_shared` on (via the
-- normal update-course path), which turns the course's UUID into a share token. Anyone
-- who has that id can import a *copy* of the course content into their own account.
--
-- Import is pure content cloning -- no LLM/worker involvement. `import_shared_course`
-- reads the source course's active version and re-inserts its modules, concepts,
-- summaries, prerequisites, lesson definitions, latest validated lesson revisions,
-- mastery parameters, and source attachments under the importing user with fresh UUIDs.
-- Progress tables (observations, mastery, assignments, quiz responses, submissions,
-- adaptation events, support artifacts) are deliberately NOT copied -- content only.
--
-- Citations survive because we copy the `course_sources` rows verbatim (same
-- source_document_ids): citation_excerpt() authorizes on the course_sources link, not on
-- source ownership, and the API reads through the service role, so an imported course's
-- citation chips resolve against the original author's chunks with no RLS changes.

alter table public.courses
  add column if not exists is_shared boolean not null default false;

-- Runs as the definer so it can read across owners: the whole point of import-by-id is
-- that the importer does not own the source course. The `is_shared` gate below is what
-- authorizes the cross-owner read -- an unshared course cannot be imported.
create or replace function public.import_shared_course(p_source_course_id uuid, p_new_owner_id uuid)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_src public.courses%rowtype;
  v_src_version_id uuid;
  v_new_course_id uuid;
  v_new_version_id uuid;
begin
  select * into v_src from public.courses where id = p_source_course_id;
  if v_src.id is null then
    raise exception 'Course not found' using errcode = 'P0002';
  end if;
  if not v_src.is_shared then
    -- Not a leak: same error the API maps to 404 for a nonexistent id, so an unshared
    -- course is indistinguishable from one that does not exist.
    raise exception 'Course not found' using errcode = 'P0002';
  end if;
  if v_src.status <> 'ready' or v_src.active_version_id is null then
    raise exception 'Course is not ready to import' using errcode = 'P0001';
  end if;
  v_src_version_id := v_src.active_version_id;

  -- New course + its single active version, owned by the importer, never shared by default.
  insert into public.courses
    (owner_id, title, goal, source_set_hash, status, lesson_min, lesson_max, quiz_max_attempts, language, is_shared)
  values
    (p_new_owner_id, v_src.title, v_src.goal, v_src.source_set_hash, 'ready',
     v_src.lesson_min, v_src.lesson_max, v_src.quiz_max_attempts, v_src.language, false)
  returning id into v_new_course_id;

  insert into public.course_versions (course_id, version, status, planner_schema_version)
  select v_new_course_id, 1, 'ready', planner_schema_version
  from public.course_versions where id = v_src_version_id
  returning id into v_new_version_id;

  update public.courses set active_version_id = v_new_version_id where id = v_new_course_id;

  -- Keep citations resolvable: same source_document_ids, so the original author's chunks
  -- still back this copy's citation markers.
  insert into public.course_sources (course_id, source_document_id, position)
  select v_new_course_id, source_document_id, position
  from public.course_sources where course_id = p_source_course_id;

  -- Modules and concepts are remapped by their natural keys (module.position,
  -- concept.slug), both unique per version -- no id-to-id table needed.
  insert into public.modules (course_version_id, position, title)
  select v_new_version_id, position, title
  from public.modules where course_version_id = v_src_version_id;

  insert into public.concepts (course_version_id, slug, title, kind)
  select v_new_version_id, slug, title, kind
  from public.concepts where course_version_id = v_src_version_id;

  insert into public.concept_summaries (concept_id, summary_markdown, citations_json, revision)
  select c_new.id, cs.summary_markdown, cs.citations_json, cs.revision
  from public.concept_summaries cs
  join public.concepts c_src on c_src.id = cs.concept_id and c_src.course_version_id = v_src_version_id
  join public.concepts c_new on c_new.course_version_id = v_new_version_id and c_new.slug = c_src.slug;

  insert into public.concept_prerequisites (concept_id, prerequisite_concept_id)
  select c_new.id, p_new.id
  from public.concept_prerequisites cp
  join public.concepts c_src on c_src.id = cp.concept_id and c_src.course_version_id = v_src_version_id
  join public.concepts p_src on p_src.id = cp.prerequisite_concept_id
  join public.concepts c_new on c_new.course_version_id = v_new_version_id and c_new.slug = c_src.slug
  join public.concepts p_new on p_new.course_version_id = v_new_version_id and p_new.slug = p_src.slug;

  -- Lesson definitions carry over build_status verbatim (a ready course's are 'built'),
  -- mapping module by position and concept by slug. generation_requested_at is stamped so
  -- pre-conceptual-bundle visibility rules treat these as generated.
  insert into public.lesson_definitions
    (course_version_id, module_id, concept_id, kind, build_status, generation_requested_at)
  select v_new_version_id, m_new.id, c_new.id, ld_src.kind, ld_src.build_status, now()
  from public.lesson_definitions ld_src
  join public.concepts c_src on c_src.id = ld_src.concept_id
  join public.concepts c_new on c_new.course_version_id = v_new_version_id and c_new.slug = c_src.slug
  left join public.modules m_src on m_src.id = ld_src.module_id
  left join public.modules m_new on m_new.course_version_id = v_new_version_id and m_new.position = m_src.position
  where ld_src.course_version_id = v_src_version_id;

  -- One revision per definition: the source's latest *validated* bundle, re-numbered to 1.
  -- Definitions without a validated bundle (still building / failed on the source) simply
  -- get none, matching how a freshly built course looks.
  insert into public.lesson_revisions (lesson_definition_id, revision, bundle_json, validation_status)
  select ld_new.id, 1, latest.bundle_json, 'validated'
  from public.lesson_definitions ld_new
  join public.concepts c_new on c_new.id = ld_new.concept_id
  join public.concepts c_src on c_src.course_version_id = v_src_version_id and c_src.slug = c_new.slug
  join public.lesson_definitions ld_src
    on ld_src.course_version_id = v_src_version_id
   and ld_src.concept_id = c_src.id
   and ld_src.kind = ld_new.kind
  join lateral (
    select lr.bundle_json
    from public.lesson_revisions lr
    where lr.lesson_definition_id = ld_src.id and lr.validation_status = 'validated'
    order by lr.revision desc
    limit 1
  ) latest on true
  where ld_new.course_version_id = v_new_version_id;

  -- Mastery/BKT parameters are content (per-concept tuning), not learner progress.
  insert into public.mastery_parameters
    (course_version_id, concept_id, track, assessment_kind, p_l0, p_t, p_g, p_s)
  select v_new_version_id, c_new.id, mp.track, mp.assessment_kind, mp.p_l0, mp.p_t, mp.p_g, mp.p_s
  from public.mastery_parameters mp
  join public.concepts c_src on c_src.id = mp.concept_id and c_src.course_version_id = v_src_version_id
  join public.concepts c_new on c_new.course_version_id = v_new_version_id and c_new.slug = c_src.slug
  where mp.course_version_id = v_src_version_id;

  return v_new_course_id;
end;
$$;

revoke all on function public.import_shared_course(uuid, uuid) from public, anon, authenticated;
grant execute on function public.import_shared_course(uuid, uuid) to service_role;
