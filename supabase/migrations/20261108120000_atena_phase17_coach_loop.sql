-- ATENA Phase 17: persist consented movement self-assessments and immutable programme versions.
-- Apply through Supabase migrations after reviewing the matching application release.

CREATE TABLE IF NOT EXISTS public.atena_movement_assessments (
    profile_id text PRIMARY KEY REFERENCES public.atena_profiles(profile_id) ON DELETE CASCADE,
    assessment_json jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.atena_program_versions (
    program_version_id text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES public.atena_profiles(profile_id) ON DELETE CASCADE,
    program_json jsonb NOT NULL,
    decision_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS atena_program_versions_profile_created
    ON public.atena_program_versions(profile_id, created_at DESC);

ALTER TABLE public.atena_movement_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.atena_program_versions ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.atena_movement_assessments FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.atena_program_versions FROM PUBLIC, anon, authenticated;
