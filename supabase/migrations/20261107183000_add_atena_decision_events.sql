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
