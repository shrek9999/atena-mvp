-- Immutable, versioned programme snapshots. A training session can point
-- to the exact prescription the athlete attempted, rather than to "latest".
create table if not exists public.atena_program_versions (
  program_version_id text primary key,
  profile_id text not null references public.atena_profiles(profile_id) on delete cascade,
  version_number integer not null check (version_number > 0),
  goal text not null,
  experience text not null,
  data_classification text not null check (data_classification in ('operational', 'health_sensitive')),
  program_json jsonb not null check (jsonb_typeof(program_json) = 'object'),
  generation_context_json jsonb not null default '{}'::jsonb check (jsonb_typeof(generation_context_json) = 'object'),
  created_at timestamptz not null default now(),
  unique (profile_id, version_number)
);

create index if not exists atena_program_versions_profile_created
  on public.atena_program_versions(profile_id, created_at desc, version_number desc);
alter table public.atena_training_sessions
  add column if not exists program_version_id text;

alter table public.atena_training_sessions
  add constraint atena_training_sessions_program_version_id_fkey
  foreign key (program_version_id)
  references public.atena_program_versions(program_version_id)
  on delete set null;

alter table public.atena_decision_events
  add constraint atena_decision_events_program_version_id_fkey
  foreign key (program_version_id)
  references public.atena_program_versions(program_version_id)
  on delete set null;

create index if not exists atena_sessions_program_version
  on public.atena_training_sessions(program_version_id);
create index if not exists atena_events_program_version
  on public.atena_decision_events(program_version_id);

alter table public.atena_program_versions enable row level security;

revoke all privileges on table public.atena_program_versions from public, anon, authenticated;
grant select, insert, delete on table public.atena_program_versions to atena_app;

create policy atena_app_server_access on public.atena_program_versions
  for all to atena_app using (true) with check (true);
