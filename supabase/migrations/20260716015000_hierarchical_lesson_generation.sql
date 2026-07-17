-- enqueue_lesson_builds fanned jobs out in arbitrary (insertion) order, so a coding lab
-- could finish building before the conceptual lesson that introduces it, leaving a
-- learner reading module 2 material while module 1's own conceptual lessons were still
-- queued behind labs elsewhere in the course. The worker processes generation_jobs
-- strictly FIFO (one message at a time), so ordering the enqueue is enough to get
-- hierarchical generation: every conceptual lesson (in module order) before any coding
-- lab, matching the order a learner actually walks through the course.

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
    order by (case when c.kind = 'conceptual' then 0 else 1 end), m.position nulls last, c.slug
  loop
    -- The API uses generation_requested_at to distinguish "a build is really queued"
    -- from legacy conceptual definitions that never had one.
    if v_lesson.kind = 'conceptual' then
      update public.lesson_definitions
      set generation_requested_at = now()
      where id = v_lesson.id;
    end if;
    perform pgmq.send(
      'generation_jobs',
      jsonb_build_object('type', 'lesson_build', 'lesson_definition_id', v_lesson.id)
    );
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;
