-- Quiz grading has been stateless: answers were graded against the bundle's server-side
-- key but nothing was ever written to quiz_responses, so attempts/completion never
-- survived a reload and there was no way to enforce a per-course attempt cap. The
-- learner_lesson_assignments / quiz_responses tables already exist for exactly this
-- (see 20260715230000_initial_schema.sql) but nothing ever created an assignment row.
-- This wires that up: a course-level attempt cap, and a uniqueness guarantee so the API
-- can safely upsert one assignment per (learner, lesson revision) without racing itself.

alter table public.courses
  add column if not exists quiz_max_attempts integer not null default 3
  check (quiz_max_attempts > 0 and quiz_max_attempts <= 10);

alter table public.learner_lesson_assignments
  add constraint learner_lesson_assignments_user_revision_key unique (user_id, lesson_revision_id);
