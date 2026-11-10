create table if not exists public.atena_profiles (
  profile_id text primary key,
  token_hash text not null,
  profile_json jsonb not null,
  privacy_notice_version text not null,
  privacy_acknowledged boolean not null default true,
  health_data_consent boolean not null default false,
  health_data_consent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.atena_training_sessions (
  session_id text primary key,
  profile_id text not null references public.atena_profiles(profile_id) on delete cascade,
  session_date date not null,
  session_json jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists atena_sessions_profile_date
  on public.atena_training_sessions(profile_id, session_date desc);
alter table public.atena_profiles enable row level security;
alter table public.atena_training_sessions enable row level security;
