-- A learner-chosen display name for the profile (the auth flow is passwordless magic-link
-- email only, so there's never a name to seed this from) -- lets a certificate show a real
-- name instead of a bare email address.
alter table public.profiles add column display_name text;

-- One durable row per (course, learner) the first time their certificate is issued, so:
--  1. "Issued <date>" is a fixed historical fact, not "today" recomputed on every view.
--  2. The row's own id is a stable, unguessable token for a public, no-auth verification
--     link -- the same trust model course sharing already uses for its course id links.
create table public.certificates (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses (id) on delete cascade,
  owner_id uuid not null references public.profiles (id) on delete cascade,
  issued_at timestamptz not null default now(),
  unique (course_id, owner_id)
);

alter table public.certificates enable row level security;

create policy "certificates are readable by their owner"
  on public.certificates for select
  using (auth.uid() = owner_id);

-- No public SELECT policy: the verification page is served by the API using the service
-- role key (bypassing RLS) after looking up by the unguessable row id, exactly like course
-- sharing already resolves a shared course id without granting a broad public policy.
