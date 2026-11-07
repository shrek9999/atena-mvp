-- Append-only longitudinal event envelope for ATENA Coach.
-- The server authenticates profile tokens and checks health-data consent.
-- Browser/API roles are explicitly denied direct access; the backend uses its
-- server-side database connection. RLS remains enabled as defense in depth.

create table if not exists public.atena_decision_events (
  event_id text primary key,
  profile_id text not null references public.atena_profiles(profile_id) on delete cascade,
  schema_version integer not null check (schema_version > 0),
  event_type text not null check (event_type in (
    'profile_updated',
    'movement_assessment_recorded',
    'symptom_context_recorded',
    'consent_changed',
    'program_created',
    'program_replaced',
    'session_started',
    'session_completed',
    'session_interrupted',
    'set_result_recorded',
    'feedback_recorded',
    'adaptation_decided',
    'referral_recommended'
  )),
  occurred_at timestamptz not null,
  source text not null check (source in ('user', 'coach', 'system', 'import')),
  data_classification text not null check (data_classification in ('operational', 'health_sensitive')),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  check (event_type not in ('movement_assessment_recorded', 'symptom_context_recorded', 'referral_recommended') or data_classification = 'health_sensitive'),
  program_version_id text,
  correlation_id text,
  created_at timestamptz not null default now()
);

create index if not exists atena_events_profile_occurred
  on public.atena_decision_events(profile_id, occurred_at desc, created_at desc);
create index if not exists atena_events_profile_type_occurred
  on public.atena_decision_events(profile_id, event_type, occurred_at desc);

alter table public.atena_decision_events enable row level security;

-- Keep all three Coach tables server-only. service_role remains available to
-- trusted server-side operations; anon/authenticated receive no table grants.
revoke all privileges on table public.atena_profiles from public, anon, authenticated;
revoke all privileges on table public.atena_training_sessions from public, anon, authenticated;
revoke all privileges on table public.atena_decision_events from public, anon, authenticated;

-- The Flask service authenticates individual profile tokens before every query.
-- Give it a dedicated, non-login role that cannot bypass RLS. The postgres pooler
-- login may SET ROLE to this role, but application SQL runs with these privileges.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'atena_app') then
    create role atena_app
      nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end
$$;

alter role atena_app nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
grant atena_app to postgres;
grant usage on schema public to atena_app;
grant select, insert, update, delete on table
  public.atena_profiles,
  public.atena_training_sessions,
  public.atena_decision_events
to atena_app;

create policy atena_app_server_access on public.atena_profiles
  for all to atena_app using (true) with check (true);
create policy atena_app_server_access on public.atena_training_sessions
  for all to atena_app using (true) with check (true);
create policy atena_app_server_access on public.atena_decision_events
  for all to atena_app using (true) with check (true);
