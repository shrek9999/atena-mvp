# ATENA Coach — data model and operational boundaries

## Purpose

ATENA Coach needs to explain not only what it prescribed, but what the athlete actually did, how the athlete responded, and why the next decision changed. This document records the current storage contract and the safe rollout sequence.

ATENA Coach (the end-user training product) and ATENA Decision Engine (the separate agent/API product) share selected decision logic, but they are separate product tracks. The Coach owns the athlete profile, training history, programme versions, consent and user experience. The Decision Engine exposes a narrow decision capability to external agents; it must not become the owner of Coach user records.

## Current tables

| Table | Purpose | Current representation |
|---|---|---|
| `atena_profiles` | Authenticated athlete profile, canonical athlete state, privacy acknowledgement and health-data consent | Profile fields in JSONB; access token stored only as a SHA-256 hash |
| `atena_training_sessions` | Actual completed or interrupted training sessions and exercise/set outcomes | Session envelope in JSONB; linked to the exact programme version attempted |
| `atena_program_versions` | Immutable, numbered snapshots of every generated programme | Full JSONB snapshot, profile-scoped version number and operational/health-sensitive classification |
| `atena_decision_events` | Longitudinal audit trail of profile, assessment, session, feedback and consent changes | Typed event envelope plus JSONB payload |

The event envelope is versioned independently from the athlete-state schema. Event payloads are strict JSON objects, have a bounded serialized size, use timezone-aware timestamps, and reject unknown fields and event types.

## Event write rules

- Profile creation, profile updates, movement assessments, training logs and consent changes are written in the same database transaction as their source record.
- If an event cannot be validated or persisted, the corresponding profile/session change is rolled back.
- Every read requires the profile access token; the event endpoint is read-only and bounded.
- Event source and data classification are explicit. Movement assessment, symptom context and referral events must be classified as health-sensitive.
- Health-sensitive events require consent verified by the server against the stored profile, not a client-supplied flag.
- Withdrawing health-data consent deletes health-sensitive events and removes stored movement/symptom observations and session discomfort flags. The operational consent-change event remains.
- Deleting a profile cascades to its sessions, programme versions and events.
- A training session may reference the exact immutable programme version it followed. Deleting a health-sensitive programme on consent withdrawal sets the session reference to null but preserves the non-sensitive training record.
- Programme versions are immutable through the application role; only creation, retrieval and privacy-driven deletion are supported.
- Programme version numbers are serialized per profile using a profile-row lock in PostgreSQL (and an immediate write transaction in SQLite).
- The user export includes the profile, sessions and decision-event history.

## Database access boundary

- Browser clients must never receive the database connection string or a service-role key.
- Public Supabase API roles `anon` and `authenticated` have no direct table grants.
- RLS is enabled on all Coach tables.
- The reviewed migration creates `atena_app`, a NOLOGIN, NOBYPASSRLS role with only CRUD access to the Coach tables. The server-side connection switches to this role transaction-locally using `SET LOCAL ROLE`.
- The app role has an RLS policy allowing its server-side queries across Coach rows. Per-athlete isolation is enforced by the server's profile-token check. This is a deliberate server-owned access model, not a claim that the database policy independently authenticates each athlete.
- Runtime requests do not create tables, alter schema or change grants. Hosted PostgreSQL schema changes are migrations only. SQLite schema setup remains limited to local/test use.

## Migration and deployment order

1. Review the checked-in baseline migration against the already-recorded Supabase migration `20261101141750`.
2. Apply the new event-storage migration to a non-production/test database first.
3. Verify the new table, constraints, indexes, RLS policies, grants and `atena_app` role; run Supabase security and performance advisors.
4. Verify a server connection can `SET LOCAL ROLE atena_app`, read/write an authorized profile, and cannot access tables as `anon` or `authenticated`.
5. Verify consent withdrawal and profile deletion against disposable test records.
6. Only then apply the reviewed migration to the live project and deploy matching application code in the same controlled release window.

**Do not deploy the Phase 23/24 application code before its required migration exists.** The application intentionally no longer performs runtime schema creation.

## What is not yet complete

- Session records are still JSONB envelopes; a separate relational set-result model may be justified after the programme-version link and user workflow are validated.
- Programme-generation and session links now provide the prescribed-versus-performed anchor, but the frontend still needs to present programme history and submit the selected `program_version_id` when a session is logged.
- Adaptation-decision events are not yet emitted by every decision path. Read-only GET requests do not create events.
- Database backup configuration, point-in-time recovery and a real restoration drill have not been verified.
- The production application connection has not yet been tested with the new `atena_app` role because the migration has not been applied.
- No production migration or deployment has been performed as part of this phase.

## Product-quality principle

Passing tests verifies software behavior, not coaching quality. Programme quality still requires expert review against goal, experience, equipment, movement competence, symptom context, dose, tempo, range of motion, recovery and the athlete's actual response over multiple weeks.
