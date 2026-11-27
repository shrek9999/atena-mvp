# ATENA — Frontend/Backend contract for selective guided movement learning

**Status:** implementation contract for the current selective-learning design.
**Date:** 27 November 2026.
**Applies to:** `tiny-figolla-016703` (Cloudflare Pages frontend) and `atena-mvp` (Render coaching backend).

## 1. Non-negotiable movement semantics

The six foundational learning patterns are squat, hinge, horizontal push, horizontal pull, vertical push and lunge.

**Vertical push is the actual overhead press, performed with a very light, equipment-appropriate load.** It is both the learning exercise and the movement test. It is not a one-repetition maximum or maximal-strength test. The control points cover tempo, press path, natural upward scapular rotation, trunk control, bilateral coordination, and tolerated load/range.

**Unloaded overhead arm raise is only an optional camera observation.** It is not the vertical-push learning task, does not replace the overhead press and does not establish readiness for loaded pressing.

Camera observations are coarse technical context only. They do not diagnose, certify mastery, decide safety/readiness or independently unlock loaded work.

## 2. Sparse six-pattern contract

The six patterns are available, but a user may learn one pattern or any selected subset. The API carries **only patterns the user has started or explicitly excluded**. An absent pattern means **not selected, not assessed, and omitted from the current programme**. Do not require a manual skip action for untouched patterns, and do not introduce a synthetic `not_started` key.

| Saved state | Meaning | Included in current programme? |
|---|---|---|
| `in_progress` | The user has begun learning and has saved partial criteria | No; retain for later |
| `completed` | The user has confirmed all six task-specific learning criteria | Yes, as a learning-stage pattern only |
| `excluded` | The user explicitly deferred or excluded the pattern, with a reason | No |

A saved checklist is user-confirmed practice progress only. It is **not** objective technique certification and must never be converted to `READY` by itself.

For every supplied pattern, the criteria object must contain exactly the six IDs registered for that pattern, each with a boolean value. `completed` requires all six values to be true. `in_progress` retains the actual partial values. `excluded` requires a valid exclusion reason and may preserve the existing criteria values.

## 3. Programme-request contract

The frontend builds two sparse objects:

- `learning_progress.patterns`: only completed patterns and explicitly excluded patterns for the current programme request. Partially completed learning remains saved in the profile but is not sent as eligible programme work.
- `movement_decisions`: the same pattern keys as `learning_progress.patterns`.

The backend requires those two key sets to match exactly. It then internally represents every absent foundational pattern as `UNASSESSABLE` with omission reason `not_selected_for_current_programme`. Such patterns must not be filled from a generic goal template.

A completed pattern maps to `LEARN`, not `READY`. The user may receive a low-load learning-stage programme only for patterns whose learning task is complete. Exercise-specific capacity development still requires the existing repeatable training evidence and progression rules.

A pain-related regression is accepted only through the existing pattern-specific regression validation. Other selected patterns remain independent.

## 4. API and persistence boundaries

- Cloudflare `POST /api/plan` proxies to Render `/coach/program`.
- Cloudflare `PUT /api/profile/{profile_id}/learning-progress` proxies to Render `/coach/profile/{profile_id}/learning-progress`.
- The save endpoint accepts a sparse subset of patterns and preserves partial `in_progress` progress.
- The programme endpoint accepts only completed or explicitly excluded patterns; unfinished patterns are not sent as programme inputs.
- Profile learning progress is distinct from optional health-data storage/consent. Keep existing profile authentication and consent gates.
- Learning progress is stored under the reserved internal key `_atena_learning_progress` inside `atena_profiles.profile_json`; profile reads strip this key from the public profile payload.
- Profile updates preserve the internal learning-progress value. Health-data consent withdrawal does not erase it; profile deletion does.
- No separate learning-progress table or production migration is required. PostgreSQL request handlers perform no DDL; hosted schema changes remain migration-managed.
- English remains the default product language; Slovenian remains the pilot language via `?lang=sl`.

## 5. Required cross-stack alignment

### Frontend repository
1. Preserve the sparse behaviour in `guidedLearningPayload()`: only started/partial or explicitly excluded patterns are saved.
2. Preserve the plan snapshot in `guidedLearningProgramPayload()`: only completed and explicitly excluded patterns are sent.
3. Keep `readProgramMovementPatternValues()` and `movement_decisions` keys aligned with that exact subset.
4. A missing pattern must remain unassessed; do not manufacture an exclusion or a user action.
5. Canonical vertical-push method ID must be `light_overhead_press`. The frontend currently emits the legacy ID `light_implement_press`; update the decision mapper, proxy allow-list and method-label mapping together.
6. Keep the camera protocol's unloaded overhead arm raise explicitly separate.

### Backend repository
1. Preserve `allow_partial=True` for sparse learning-progress validation.
2. Continue requiring exact key equality between learning progress and movement decisions.
3. Continue filling absent patterns internally as `UNASSESSABLE` with `not_selected_for_current_programme`; do not expose absent patterns as errors.
4. Permit a valid focused programme containing fewer than three exercises when a structured selective-learning request contains only one or two eligible patterns. Do not add unrelated or unassessed exercises merely to reach a count threshold. Requests with zero compatible exercises must still fail safely.
5. Normalize the frontend's legacy `light_implement_press` ID to canonical `light_overhead_press` at the backend boundary until the frontend sends the canonical ID.
6. Keep the rule that checklist completion alone does not create `READY`.

## 6. Acceptance scenarios

1. A user begins squat only. The saved payload contains squat only; the other five patterns are absent and are treated as unassessed.
2. The user confirms all six squat criteria. The programme request contains squat only; the other five patterns receive internal unassessed omission records and contribute no exercises.
3. A user has three criteria checked for hinge. The profile stores hinge as `in_progress`; the current programme omits hinge without losing those three checks.
4. A user explicitly defers lunge. Lunge is saved as `excluded` with a reason; it remains distinguishable from an absent/untouched pattern.
5. A user reports pain in one pattern. Existing symptom-specific safety and regression rules apply only to that pattern.
6. The vertical-push learning task and backend registry use `light_overhead_press`; the camera continues to label its separate observation as unloaded overhead arm raise.
7. One selected pattern can produce a focused programme if at least one safe catalogue exercise is available. The engine must not require three unrelated exercises or invent work for unassessed patterns.
8. No checklist-only path sets a pattern to `READY` or starts capacity development without the existing repeatable training evidence.

## 7. Validation and release boundary

Required before the integration PRs can be marked ready:
- frontend and backend contract tests for sparse save/restore and matching key sets;
- complete offline suites in both repositories;
- Preview smoke for save, restore, one-pattern programme generation and explicit exclusion;
- real-browser click-through and coach-led review;
- confirmation of the existing production/Preview configuration.

No merge, deployment, production configuration change or database migration is authorised by this document.
