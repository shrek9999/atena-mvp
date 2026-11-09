-- Phase 25: immutable programme snapshots and exact session linkage.
-- This migration upgrades both a fresh schema and the earlier Phase 17
-- atena_program_versions table (program_json + decision_json).
-- Apply only after the Phase 23/24 decision-event migration.

create table if not exists public.atena_program_versions (
  program_version_id text primary key,
  profile_id text not null references public.atena_profiles(profile_id) on delete cascade,
  version_number integer,
  goal text,
  experience text,
  data_classification text,
  program_json jsonb not null check (jsonb_typeof(program_json) = 'object'),
  generation_context_json jsonb not null default '{}'::jsonb
    check (jsonb_typeof(generation_context_json) = 'object'),
  created_at timestamptz not null default now()
);

-- Phase 17 already created this table with a narrower schema. Add the new
-- fields explicitly; CREATE TABLE IF NOT EXISTS does not evolve old tables.
alter table public.atena_program_versions
  add column if not exists version_number integer;
alter table public.atena_program_versions
  add column if not exists goal text;
alter table public.atena_program_versions
  add column if not exists experience text;
alter table public.atena_program_versions
  add column if not exists data_classification text;
alter table public.atena_program_versions
  add column if not exists generation_context_json jsonb not null default '{}'::jsonb;
alter table public.atena_training_sessions
  add column if not exists program_version_id text;

-- Preserve the legacy decision_json column if it exists, while allowing the
-- new writer to use generation_context_json instead.
do $$
begin
  if exists (
    select 1 from information_schema.columns
     where table_schema = 'public'
       and table_name = 'atena_program_versions'
       and column_name = 'decision_json'
  ) then
    alter table public.atena_program_versions
      alter column decision_json set default '{}'::jsonb;
  end if;
end
$$;

-- Backfill legacy rows deterministically. Unknown legacy provenance is
-- classified as health-sensitive (fail closed), not silently exposed as
-- ordinary training data. Current production table is empty, but this also
-- makes the upgrade safe if legacy rows exist in another environment.
with existing_max as (
  select profile_id, coalesce(max(version_number), 0) as max_version
    from public.atena_program_versions
   group by profile_id
),
ranked_missing as (
  select pv.program_version_id,
         existing_max.max_version
         + row_number() over (
             partition by pv.profile_id
             order by pv.created_at asc, pv.program_version_id asc
           ) as assigned_version
    from public.atena_program_versions as pv
    join existing_max using (profile_id)
   where pv.version_number is null
)
update public.atena_program_versions as pv
   set version_number = ranked_missing.assigned_version
  from ranked_missing
 where pv.program_version_id = ranked_missing.program_version_id;

update public.atena_program_versions as pv
   set goal = coalesce(nullif(pv.program_json ->> 'goal', ''),
                       nullif(p.profile_json ->> 'goal', ''),
                       'unknown'),
       experience = coalesce(nullif(p.profile_json ->> 'experience', ''),
                             nullif(pv.program_json ->> 'experience', ''),
                             'unknown'),
       data_classification = coalesce(pv.data_classification, 'health_sensitive'),
       generation_context_json = coalesce(pv.generation_context_json, '{}'::jsonb)
  from public.atena_profiles as p
 where p.profile_id = pv.profile_id
   and (pv.goal is null or pv.experience is null
        or pv.data_classification is null
        or pv.generation_context_json is null);

update public.atena_program_versions
   set goal = coalesce(goal, 'unknown'),
       experience = coalesce(experience, 'unknown'),
       data_classification = coalesce(data_classification, 'health_sensitive'),
       generation_context_json = coalesce(generation_context_json, '{}'::jsonb)
 where goal is null or experience is null
    or data_classification is null or generation_context_json is null;

alter table public.atena_program_versions
  alter column version_number set not null,
  alter column goal set not null,
  alter column experience set not null,
  alter column data_classification set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.atena_program_versions'::regclass
       and conname = 'atena_program_versions_profile_id_version_number_key'
  ) then
    alter table public.atena_program_versions
      add constraint atena_program_versions_profile_id_version_number_key
      unique (profile_id, version_number);
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.atena_program_versions'::regclass
       and conname = 'atena_program_versions_data_classification_check'
  ) then
    alter table public.atena_program_versions
      add constraint atena_program_versions_data_classification_check
      check (data_classification in ('operational', 'health_sensitive'));
  end if;

  -- Phase 18 already installed this relationship under the name
  -- atena_training_sessions_program_version_fk. Do not add a duplicate FK.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.atena_training_sessions'::regclass
       and confrelid = 'public.atena_program_versions'::regclass
       and contype = 'f'
       and pg_get_constraintdef(oid) like
           'FOREIGN KEY (program_version_id) REFERENCES atena_program_versions%'
  ) then
    alter table public.atena_training_sessions
      add constraint atena_training_sessions_program_version_fk
      foreign key (program_version_id)
      references public.atena_program_versions(program_version_id)
      on delete set null;
  end if;

  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.atena_decision_events'::regclass
       and confrelid = 'public.atena_program_versions'::regclass
       and contype = 'f'
       and pg_get_constraintdef(oid) like
           'FOREIGN KEY (program_version_id) REFERENCES atena_program_versions%'
  ) then
    alter table public.atena_decision_events
      add constraint atena_decision_events_program_version_fk
      foreign key (program_version_id)
      references public.atena_program_versions(program_version_id)
      on delete set null;
  end if;
end
$$;

create index if not exists atena_program_versions_profile_created
  on public.atena_program_versions(profile_id, created_at desc, version_number desc);
create index if not exists atena_sessions_program_version
  on public.atena_training_sessions(program_version_id);
create index if not exists atena_events_program_version
  on public.atena_decision_events(program_version_id);

alter table public.atena_program_versions enable row level security;
revoke all privileges on table public.atena_program_versions from public, anon, authenticated;
grant select, insert, delete on table public.atena_program_versions to atena_app;

do $$
begin
  if not exists (
    select 1 from pg_policies
     where schemaname = 'public'
       and tablename = 'atena_program_versions'
       and policyname = 'atena_app_server_access'
  ) then
    create policy atena_app_server_access on public.atena_program_versions
      for all to atena_app using (true) with check (true);
  end if;
end
$$;
