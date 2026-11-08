-- Phase 18: connect each performed session to the exact generated programme.
-- Existing training history remains valid with a NULL programme reference.
ALTER TABLE public.atena_training_sessions
    ADD COLUMN IF NOT EXISTS program_version_id text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'atena_training_sessions_program_version_fk'
           AND conrelid = 'public.atena_training_sessions'::regclass
    ) THEN
        ALTER TABLE public.atena_training_sessions
            ADD CONSTRAINT atena_training_sessions_program_version_fk
            FOREIGN KEY (program_version_id)
            REFERENCES public.atena_program_versions(program_version_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS atena_sessions_program_version
    ON public.atena_training_sessions(program_version_id);
