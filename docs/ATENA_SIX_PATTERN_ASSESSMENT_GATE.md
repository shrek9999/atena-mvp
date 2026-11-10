# ATENA – six-pattern assessment gate (pilot API)

## Purpose

A profile-based individual programme must not be generated from training goals, experience and equipment alone. The user must first complete the six short guided movement checks. This is a coaching self-report, not a clinical screen, diagnosis or proof of objective movement quality.

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

Body must contain all six pattern keys, each with one status:

```json
{
  "movement_patterns": {
    "squat": {"status": "comfortable"},
    "hinge": {"status": "needs_support"},
    "horizontal_push": {"status": "uncertain"},
    "horizontal_pull": {"status": "not_assessed"},
    "vertical_push": {"status": "symptoms_reported"},
    "lunge": {"status": "comfortable"}
  }
}
```

Allowed statuses and deterministic mapping:

| User report | Structured decision | Programme behaviour |
|---|---|---|
| `comfortable` | `READY` | Normal catalogue selection; no automatic progression |
| `needs_support` | `LEARN` | Select a verified learning / easier variation |
| `uncertain` | `UNASSESSABLE` | Omit the pattern pending reassessment |
| `not_assessed` | `UNASSESSABLE` | Omit the pattern pending reassessment |
| `symptoms_reported` | `UNASSESSABLE` | Omit only the affected pattern pending clarification |

The service rejects incomplete or unknown pattern sets. It does not infer readiness from experience level, goals, equipment or conversation history.

## Programme gate

`POST /coach/profile/{profile_id}/program` still requires the current safety confirmation. It additionally requires a saved assessment with the current six-pattern schema version and all six pattern decisions. Otherwise it returns HTTP 409 with `assessment_required=true` and the missing pattern keys.

The deterministic programme engine also omits any `UNASSESSABLE`, `uncertain` or `not_assessed` pattern. A missing assessment is never treated as READY. Symptoms are kept distinct from movement-quality observations; ATENA does not diagnose or automatically substitute a different exercise.

## Current implementation boundary

This commit establishes and tests the backend contract and programme gate. The separate Cloudflare Pages onboarding interface still needs to present the six guided checks, submit this endpoint, and show users how to retry or skip a check. Do not expose the profile-program button as ready until that UI flow is connected and tested end to end.
