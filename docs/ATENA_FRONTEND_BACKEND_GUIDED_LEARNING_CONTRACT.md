# ATENA — Frontend/Backend contract for guided movement learning

**Status:** approved implementation contract; runtime alignment still pending.
**Date:** 27 November 2026.
**Applies to:** `tiny-figolla-016703` (Cloudflare Pages frontend) and `atena-mvp` (Render coaching backend).

## 1. Non-negotiable movement semantics

The six learning patterns are squat, hinge, horizontal push, horizontal pull, vertical push and lunge.

**Vertical push is the actual overhead press, performed with a very light, equipment-appropriate load.** It is both the learning exercise and the movement test. It is not a one-repetition maximum or maximal-strength test. The control points cover tempo, press path, natural upward scapular rotation, trunk control, bilateral coordination, and tolerated load/range.

**Unloaded overhead arm raise is only an optional camera observation.** It is not the vertical-push learning task, does not replace the overhead press and does not establish readiness for loaded pressing.

Camera observations are coarse technical context only. They do not diagnose, certify mastery, decide safety/readiness or independently unlock loaded work.

## 2. One canonical state model

Every API request concerning the six patterns carries all six canonical pattern keys. An untouched pattern is represented explicitly; the frontend must not make the user perform an extra “skip” action just to satisfy an API schema.

| State | Meaning | Included in current programme? |
|---|---|---|
| `not_started` | User has not started this pattern; all six criterion values are false | No |
| `in_progress` | User has begun learning; one or more criteria are not yet confirmed | No |
| `completed` | User confirms all six learning criteria | Yes, as a learning-stage pattern only |
| `excluded` | User has explicitly deferred or excluded this pattern, with a reason | No |

A checked learning checklist is user-confirmed practice progress only. It is **not** objective technique certification and must never be converted to `READY` by itself.

For saved progress, include all six patterns, each with the exact six criterion IDs used by the backend. For `not_started`, all six values are false. For `in_progress`, preserve the actual partial values. For `completed`, all six values must be true. For `excluded`, retain the exclusion reason and any existing criterion values without treating the pattern as mastered.

## 3. Programme-request contract

The frontend sends all six movement decisions:

- `completed` → `selected_for_learning` → backend decision `LEARN`.
- `not_started` or `in_progress` → `not_assessed` → backend decision `UNASSESSABLE`.
- `excluded` → the matching user report (for example, `not_assessed`, `uncertain` or `symptoms_reported`) and the appropriate conservative decision.
- A pain-related regression is accepted only through the existing pattern-specific regression validation.

The programme request carries exactly six learning states and six movement decisions. At least one pattern must be eligible for guided learning. Unstarted, unfinished or excluded patterns are omitted from the current programme and can be learned later. Do not relabel an untouched pattern as user-excluded merely to satisfy validation.

The plan-specific snapshot may mark an unfinished pattern as `not_started` for this request without overwriting its real saved `in_progress` state.

## 4. API and persistence boundaries

- Cloudflare `POST /api/plan` proxies to Render `/coach/program`.
- Cloudflare `PUT /api/profile/{profile_id}/learning-progress` proxies to Render `/coach/profile/{profile_id}/learning-progress`.
- The profile learning-progress record is distinct from optional health-data storage/consent.
- Keep existing profile authentication and consent gates.
- No database migration or new table is required for these JSON state values; validate the existing JSON payload and persistence path before considering schema work.
- English remains the default product language; Slovenian remains the pilot language via `?lang=sl`.

## 5. Required implementation changes

### Frontend repository
1. `guidedLearningPayload()` must emit all six patterns, using `not_started` for untouched patterns.
2. `guidedLearningProgramPayload()` must emit all six states; only `completed` and explicitly `excluded` states retain their state, while unfinished patterns are represented as `not_started` in the programme snapshot.
3. `readProgramMovementPatternValues()` must emit all six decisions, mapping unfinished patterns to `not_assessed`.
4. Restoring a `not_started` state must keep `started_by_user=false`; the UI must not display a skip action for untouched patterns.
5. The vertical-push decision method ID must be `light_overhead_press`, matching the backend method registry. Do not use `light_implement_press` or `unloaded_overhead_reach` for the learning task.
6. Keep the camera protocol's unloaded overhead arm raise explicitly separate.

### Backend repository
1. The learning-progress validator must accept `not_started` with six false criteria values, including in programme requests.
2. The profile learning-progress endpoint must preserve `not_started` distinctly from `in_progress`.
3. The programme endpoint must accept exactly six learning states and six decisions; `not_started` must pair only with an `UNASSESSABLE` / `not_assessed` decision.
4. Do not allow `in_progress` patterns into programme work; they remain excluded from that plan until complete.
5. Keep the existing rule that a completed checklist does not create `READY`.
6. Keep the vertical-push method registry and the criteria rubric consistent with the light overhead-press task.

## 6. Acceptance scenarios

1. A user starts squat only. The other five patterns remain `not_started`; no extra skip clicks are required.
2. The user confirms all six squat criteria. A programme request contains six patterns, with squat as `LEARN` and the other five as `UNASSESSABLE`.
3. A user has three criteria checked for hinge. The saved profile restores hinge as `in_progress`; hinge is omitted from the current programme, without losing those three checks.
4. A user explicitly defers lunge. Lunge remains `excluded` with its reason; it is not confused with an untouched pattern.
5. A user reports pain in one pattern. Existing symptom-specific safety and regression rules apply only to that pattern.
6. The vertical-push learning task and API use `light_overhead_press`; the camera continues to label its separate observation as unloaded overhead arm raise.
7. No checklist-only path sets a pattern to `READY` or starts loaded capacity development without the existing repeatable training evidence.

## 7. Validation and release boundary

Required before the integration PRs can be marked ready:
- frontend and backend contract tests for all six states;
- full offline suites in both repositories;
- cross-stack Preview smoke for save, restore, one-pattern plan generation and explicit exclusion;
- real-browser click-through and coach-led review;
- confirmation of the existing production/Preview configuration.

This document records the contract and acceptance criteria. It does not claim the runtime changes or the cross-stack checks are complete. No merge, deployment, production configuration change or database migration is authorised by this document.
