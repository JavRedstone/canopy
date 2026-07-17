-- A course topic is a small textbook unit: lectures introduce it, labs apply it,
-- and a final assessment checks that the learner can connect the pieces.
alter table public.concepts drop constraint if exists concepts_kind_check;
alter table public.concepts add constraint concepts_kind_check check (kind in ('conceptual', 'coding', 'assessment'));

alter table public.courses drop constraint if exists courses_lesson_min_check;
alter table public.courses drop constraint if exists courses_lesson_max_check;
update public.courses set lesson_max = greatest(lesson_max, lesson_min, 4) where lesson_max < 4;
update public.courses set lesson_min = 4 where lesson_min < 4;
alter table public.courses alter column lesson_min set default 8;
alter table public.courses alter column lesson_max set default 16;
alter table public.courses add constraint courses_lesson_min_check check (lesson_min between 4 and 24);
alter table public.courses add constraint courses_lesson_max_check check (lesson_max between lesson_min and 24);

-- Generate in the exact order the learner sees: all lectures for topic one, its
-- labs, its assessment, then topic two. This replaces the former all-lectures,
-- then all-labs ordering.
create or replace function public.enqueue_lesson_builds(p_course_version_id uuid)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public, pgmq
as $$
declare
  v_lesson record;
  v_count integer := 0;
begin
  for v_lesson in
    select ld.id, c.kind
    from public.lesson_definitions as ld
    join public.concepts as c on c.id = ld.concept_id
    left join public.modules as m on m.id = ld.module_id
    where ld.course_version_id = p_course_version_id
      and ld.kind = 'lesson'
      and ld.build_status in ('pending', 'failed')
    order by m.position nulls last,
      case c.kind when 'conceptual' then 0 when 'coding' then 1 else 2 end,
      c.slug
  loop
    if v_lesson.kind <> 'coding' then
      update public.lesson_definitions set generation_requested_at = now() where id = v_lesson.id;
    end if;
    perform pgmq.send('generation_jobs', jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', v_lesson.id));
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;
