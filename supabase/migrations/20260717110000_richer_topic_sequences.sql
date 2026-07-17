-- A topic should be a sequence of small, purposeful activities instead of one
-- oversized lecture and a single lab.
alter table public.courses drop constraint if exists courses_lesson_min_check;
alter table public.courses drop constraint if exists courses_lesson_max_check;
update public.courses set lesson_max = greatest(lesson_max, lesson_min, 6) where lesson_max < 6;
update public.courses set lesson_min = 6 where lesson_min < 6;
alter table public.courses alter column lesson_min set default 12;
alter table public.courses alter column lesson_max set default 20;
alter table public.courses add constraint courses_lesson_min_check check (lesson_min between 6 and 24);
alter table public.courses add constraint courses_lesson_max_check check (lesson_max between lesson_min and 24);
