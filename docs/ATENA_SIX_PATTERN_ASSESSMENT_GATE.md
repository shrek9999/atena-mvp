# ATENA – six-pattern assessment gate (pilot API)

## Purpose

A profile-based individual programme must not be generated from training goals, experience and equipment alone. The user can complete the six short guided movement checks independently, in any order. A programme may use the patterns already assessed; it must omit patterns that are missing, unclear or not ready. This is a coaching self-report, not a clinical screen, diagnosis or proof of objective movement quality.

## Six foundational checks

| API pattern key | User-facing movement |
|---|---|
| `squat` | Počep |
| `hinge` | Predklon v kolkih (hip hinge) |
| `horizontal_push` | Horizontalni potisk |
| `horizontal_pull` | Horizontalni poteg / veslanje |
| `vertical_push` | Vertikalni potisk |
| `lunge` | Izpadni korak |

A pull-up / zgib is a **vertical pull**, not a horizontal row. Vertical pull remains a supplementary programming pattern and is not one of these six assessment checks.

## Consent and persistence

The six-pattern result is health-related movement information. It is persisted only when the profile has separate `health_data_consent=true`. With consent withdrawn, the existing storage layer erases the movement assessment and programme decision history.

## Save endpoint

`PUT /coach/profile/{profile_id}/movement-assessment`

Header: `X-Profile-Token: <profile access token>`

Body must contain `movement_assessment_consent: true` and at least one known pattern key. Send only the pattern being assessed or retested. The API merges it with previously saved decisions, so earlier results are preserved:

```json
{
  "movement_assessment_consent": true,
  "movement_patterns": {
    "squat": {"status": "comfortable"},
    "hinge": {"status": "needs_support"}
  }
}
```

Allowed statuses and deterministic mapping:

| User report | Structured decision | Programme behaviour |
|---|---|---|
| `comfortable` | `LEARN` | Confirm repeatable pattern-specific control before a READY decision |
| `needs_support` | `LEARN` | Select a verified learning / easier variation |
| `uncertain` | `UNASSESSABLE` | Omit the pattern pending reassessment |
| `not_assessed` | `UNASSESSABLE` | Omit the pattern pending reassessment |
| `symptoms_reported` | `UNASSESSABLE` | Omit only the affected pattern pending clarification |

The service accepts a non-empty subset of known patterns and rejects unknown keys. It preserves earlier decisions when one pattern is retested. It does not infer readiness from experience level, goals, equipment or conversation history. A comfortable basic check remains LEARN until the user confirms all pattern-specific control criteria and repeatability. READY is still capped at a conservative low/moderate-loading starting variation; exercise-specific progression requires recorded training evidence. The response includes `missing_patterns` so the interface can show what remains optional.

## Programme gate

`POST /coach/profile/{profile_id}/program` still requires the current safety confirmation. It requires at least one saved, assessable pattern in the current schema version. Missing patterns are not a blocker: they are omitted from the programme until assessed. If no pattern is assessable, the endpoint returns HTTP 409 with `assessment_required=true`.

Whenever structured movement decisions are supplied, the deterministic programme engine uses strict pattern scope: only explicitly assessed patterns can contribute exercises or learning tasks. `UNASSESSABLE`, `uncertain`, `not_assessed`, and entirely missing patterns are omitted. A missing assessment is never treated as READY. Symptoms are kept distinct from movement-quality observations; ATENA does not diagnose or automatically substitute a different exercise.

## Optional camera coordination contribution

The browser camera may contribute only a positive, low-dose skill emphasis. The backend accepts the coordination proxy as usable for this purpose only when status is `observed`, quality is `adequate`, at least six frames are valid, both cross-body directions are represented, and at least two alternating transitions are observed. When all conditions are met, the programme may add one 10-second set of the beginner-level, bodyweight **controlled lateral step** to the warm-up.

This is not a coordination score or a general movement-quality finding. It does not establish readiness, safety, absence of symptoms, or competence in other tasks. It never changes main exercise selection, load, progression, or the six self-reported movement decisions. If the task is skipped, unclear, insufficient-quality or not observed, no camera-based change is made and no deficit is inferred. Camera data remains transient and is not stored or uploaded.

## Current implementation boundary

The backend contract now supports independent pattern assessment, cumulative persistence and strict per-pattern programme inclusion. The Cloudflare Pages interface must present each check independently, submit only the pattern being assessed, show the remaining optional checks, and allow retesting without erasing prior results. The profile-program action should be available once at least one pattern has a valid assessable decision.
