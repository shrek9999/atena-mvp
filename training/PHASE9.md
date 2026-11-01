# ATENA Phase 9 – opt-in profile and training history

## Scope

This phase adds a minimal, server-side profile and longitudinal training-history API. It deliberately does not store chat transcripts, names, email addresses, exact birth dates, free-text health histories or medical diagnoses.

A profile contains only:
- training goal and experience level;
- available equipment;
- weekly frequency and approximate session duration;
- optional available weekdays.

A training record contains:
- date, duration, completion and perceived difficulty;
- completed exercises selected from the verified ATENA catalogue;
- sets, repetitions, load and RIR;
- an optional binary discomfort flag, only where separate health-data consent was explicitly provided.

## Privacy and security controls

- Storage is disabled unless both `ATENA_DATA_STORAGE_ENABLED=true` and `ATENA_PRIVACY_NOTICE_APPROVED=true` are configured.
- The API requires acknowledgement of the configured `ATENA_PRIVACY_NOTICE_VERSION`.
- Profile creation requires the private pilot token.
- Every profile receives a random access token returned only once. Only its SHA-256 hash is stored.
- Profile reads, updates, session writes, history reads and deletion require the profile-specific token.
- Unknown profile/session fields and free-text notes are rejected.
- Health-related discomfort feedback is rejected unless separate `health_data_consent=true` was recorded at profile creation.
- A profile deletion removes its associated training records through the database foreign key.
- No profile or training-history endpoint writes personal values to application logs.

These are technical safeguards, not a claim that ATENA is legally GDPR-compliant. The privacy notice, lawful basis, consent wording, retention schedule, data-subject request process, controller/processor roles and cross-border processing arrangements require review before any real-user data is enabled.

## Persistence

Hosted storage supports PostgreSQL through `ATENA_DATABASE_URL` and the psycopg 3 driver. SQLite is permitted only when `ATENA_ALLOW_SQLITE_STORAGE=true` is explicitly set for local development/tests. Do not use SQLite on Render Free: its filesystem is ephemeral and local database files are lost on restarts, spin-downs and deploys.

Suggested no-cost pilot database: Supabase Free PostgreSQL. Its current free offer includes 500 MB per project and two active free projects; inactive projects can pause after a week. A paused project retains its data but must be resumed. This is suitable for a controlled pilot, not a production reliability guarantee. Re-check the provider's current terms before use.

## Environment variables

Required before enabling hosted persistence:
- `ATENA_DATABASE_URL`: PostgreSQL connection string; keep it private in the Render service environment.
- `ATENA_DATA_STORAGE_ENABLED=true`: enables the feature only after database setup.
- `ATENA_PRIVACY_NOTICE_APPROVED=true`: operator acknowledgement that the notice and processing setup have been reviewed.
- `ATENA_PRIVACY_NOTICE_VERSION`: version identifier that the client must acknowledge.

Do not enable the two flags yet. They must remain unset/false until the privacy notice and data-processing decisions have been approved. Do not commit connection strings, service-role keys or user tokens to GitHub.

## API

All endpoints are disabled (HTTP 503) until storage is enabled.

### Create profile

`POST /coach/profile`

Headers: `X-Pilot-Token`

Body:
```json
{
  "privacy_notice_acknowledged": true,
  "privacy_notice_version": "pilot-draft-1",
  "health_data_consent": false,
  "profile": {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": ["barbell", "rack", "dumbbell", "bench"],
    "sessions_per_week": 2,
    "session_minutes": 60,
    "available_days": ["monday", "thursday"]
  }
}
```

The response returns `profile_id` and `profile_access_token` once. The client must store the token securely; it cannot be retrieved later.

### Read or update profile

- `GET /coach/profile/{profile_id}`
- `PUT /coach/profile/{profile_id}` with `{"profile": {...}}`

Header: `X-Profile-Token`

### Save and read training sessions

- `POST /coach/profile/{profile_id}/sessions`
- `GET /coach/profile/{profile_id}/sessions`

The write endpoint accepts only structured session data and catalogue exercise IDs. No free-text notes are accepted.

### Delete profile and associated history

`DELETE /coach/profile/{profile_id}`

Header: `X-Profile-Token`

## Not yet implemented

- User-facing sign-in, secure token recovery/rotation and multi-device access.
- A reviewed privacy notice and complete GDPR operational process.
- Automated progression calculations from longitudinal logs.
- Export/download of a user's full history.
- Retention expiry and account recovery.
- Front-end integration and end-to-end user acceptance testing.

The next implementation step is to provision the chosen PostgreSQL free project, store its connection string privately in Render, and run a controlled end-to-end test with synthetic data before enabling any real-user storage.
