-- The practice question pool: a low-stakes, non-repeating drill bank per concept, distinct
-- from the small fixed set of graded quiz_items co-generated with each lesson. Three pieces
-- land here (see docs/architecture/PRACTICE_QUESTION_POOL.md):
--
-- 1. practice_items -- the pool itself, generated per concept by the worker in batches. It
--    holds answer keys and rubrics, so like lesson_revisions it gets RLS with NO policy:
--    service-role only, never readable through PostgREST. The API serves answer-stripped
--    previews, exactly as it does for lesson quiz items.
-- 2. practice_attempts -- one row per answered practice question, owned by the learner. Does
--    triple duty: non-repeat rotation, per-learner struggle analytics (weakest-first order,
--    "retry my misses"), and per-item difficulty in aggregate.
-- 3. A 'practice' assessment_kind, so a *correct* practice answer can write a capped,
--    positive-only mastery observation. A wrong answer writes no observation at all, so
--    practice can never lower a learner's estimate.
--
-- Generation runs as a practice_pool_build job on the existing generation_jobs queue,
-- enqueued after lesson_build succeeds so the lesson renders without waiting for the pool.

create table public.practice_items (
  id uuid primary key default gen_random_uuid(),
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  concept_id uuid not null references public.concepts (id) on delete cascade,
  -- Batch 0 is generated after the lesson builds; a top-up appends batch 1, 2, ... The
  -- batch number is what makes a redelivered queue message a no-op instead of a duplicate.
  batch integer not null default 0 check (batch >= 0),
  kind text not null check (kind in ('mcq', 'multi_select', 'fill', 'short_answer')),
  item_json jsonb not null,
  times_served integer not null default 0 check (times_served >= 0),
  times_correct integer not null default 0 check (times_correct >= 0),
  created_at timestamptz not null default now()
);

create index if not exists practice_items_concept_id_idx on public.practice_items (concept_id);
create index if not exists practice_items_course_version_id_idx on public.practice_items (course_version_id);

-- No policy on purpose: item_json carries correct answers and rubrics, so this table is
-- service-role only, the same treatment lesson_revisions gets.
alter table public.practice_items enable row level security;

create table public.practice_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  course_version_id uuid not null references public.course_versions (id) on delete cascade,
  concept_id uuid not null references public.concepts (id) on delete cascade,
  practice_item_id uuid not null references public.practice_items (id) on delete cascade,
  correct boolean not null,
  created_at timestamptz not null default now()
);

create index if not exists practice_attempts_user_id_concept_id_idx
  on public.practice_attempts (user_id, concept_id);

alter table public.practice_attempts enable row level security;

create policy "practice attempts belong to learner" on public.practice_attempts
  for select to authenticated using (user_id = auth.uid());

-- A correct practice answer feeds the understand track like a quiz answer does, but with a
-- high guess rate and a hard ceiling below the mastery bar (see services/api/app/mastery.py).
-- Both tables that constrain assessment_kind have to learn the new value.
alter table public.observations drop constraint if exists observations_assessment_kind_check;
alter table public.observations add constraint observations_assessment_kind_check
  check (assessment_kind in ('quiz_mcq', 'quiz_fill', 'coding_submission', 'transfer_exercise', 'practice'));

alter table public.mastery_parameters drop constraint if exists mastery_parameters_assessment_kind_check;
alter table public.mastery_parameters add constraint mastery_parameters_assessment_kind_check
  check (assessment_kind in ('quiz_mcq', 'quiz_fill', 'coding_submission', 'transfer_exercise', 'practice'));

-- Enqueued twice: once by the worker when a lesson finishes building, and again by the API
-- when a learner exhausts a concept's unseen questions. No batch number is passed -- the
-- worker resolves the next one at claim time, so two racing top-ups converge on the same
-- batch and the second one is discarded by apply_practice_pool rather than double-inserting.
create or replace function public.enqueue_practice_pool_build(p_lesson_definition_id uuid)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_message_id bigint;
begin
  if not exists (
    select 1
    from public.lesson_definitions
    where id = p_lesson_definition_id
      and build_status = 'built'
  ) then
    raise exception 'Lesson is not built, so it has no explanation to draw practice questions from' using errcode = 'P0002';
  end if;

  select * into v_message_id
  from pgmq.send(
    'generation_jobs',
    jsonb_build_object('type', 'practice_pool_build', 'lesson_definition_id', p_lesson_definition_id)
  );
  return v_message_id;
end;
$$;

revoke all on function public.enqueue_practice_pool_build(uuid) from public, anon, authenticated;
grant execute on function public.enqueue_practice_pool_build(uuid) to service_role;

-- Everything one generation pass needs, read in a single round trip: the concept, the
-- finalized lesson explanation the questions must test, every question the learner could
-- already have been asked on this concept (the lesson's own quiz plus earlier batches, so a
-- top-up writes around them), and the batch number this run will write.
create or replace function public.practice_pool_context(p_lesson_definition_id uuid)
returns table(
  concept_id uuid,
  course_version_id uuid,
  concept_title text,
  concept_kind text,
  summary_markdown text,
  citations_json jsonb,
  lesson_explanation text,
  existing_prompts jsonb,
  next_batch integer
)
language sql
security definer
set search_path = pg_catalog, public
as $$
  with definition as (
    select ld.id, ld.concept_id, ld.course_version_id
    from public.lesson_definitions as ld
    where ld.id = p_lesson_definition_id
      and ld.build_status = 'built'
  ),
  revision as (
    select lr.bundle_json
    from public.lesson_revisions as lr
    join definition as d on d.id = lr.lesson_definition_id
    where lr.validation_status = 'validated'
    order by lr.revision desc
    limit 1
  )
  select
    d.concept_id,
    d.course_version_id,
    c.title,
    c.kind,
    coalesce(cs.summary_markdown, ''),
    coalesce(cs.citations_json, '[]'::jsonb),
    coalesce(r.bundle_json -> 'lesson_content' ->> 'explanation_markdown', ''),
    coalesce(
      (
        select jsonb_agg(asked.prompt)
        from (
          select quiz_item ->> 'prompt_markdown' as prompt
          from jsonb_array_elements(coalesce(r.bundle_json -> 'assessment' -> 'quiz_items', '[]'::jsonb)) as quiz_item
          union all
          select pi.item_json ->> 'prompt_markdown'
          from public.practice_items as pi
          where pi.concept_id = d.concept_id
        ) as asked
        where asked.prompt is not null
      ),
      '[]'::jsonb
    ),
    coalesce((select max(pi.batch) + 1 from public.practice_items as pi where pi.concept_id = d.concept_id), 0)
  from definition as d
  join public.concepts as c on c.id = d.concept_id
  left join public.concept_summaries as cs on cs.concept_id = c.id
  left join revision as r on true;
$$;

revoke all on function public.practice_pool_context(uuid) from public, anon, authenticated;
grant execute on function public.practice_pool_context(uuid) to service_role;

-- Idempotent by (concept, batch): a redelivered queue message, or a second top-up that
-- raced the first, finds the batch already written and inserts nothing.
create or replace function public.apply_practice_pool(
  p_concept_id uuid,
  p_course_version_id uuid,
  p_batch integer,
  p_items jsonb
)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_inserted integer;
begin
  if exists (
    select 1 from public.practice_items
    where concept_id = p_concept_id and batch = p_batch
  ) then
    return 0;
  end if;

  insert into public.practice_items (course_version_id, concept_id, batch, kind, item_json)
  select p_course_version_id, p_concept_id, p_batch, item ->> 'kind', item
  from jsonb_array_elements(p_items) as item;

  get diagnostics v_inserted = row_count;
  return v_inserted;
end;
$$;

revoke all on function public.apply_practice_pool(uuid, uuid, integer, jsonb) from public, anon, authenticated;
grant execute on function public.apply_practice_pool(uuid, uuid, integer, jsonb) to service_role;
