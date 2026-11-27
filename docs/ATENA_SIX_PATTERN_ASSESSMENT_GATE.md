# ATENA — six guided movement patterns and selective programme gate

## Purpose

ATENA offers six foundational movement-learning tasks before prescribing loaded work for those patterns. The user does **not** have to complete all six before receiving a first programme. They may begin with one pattern or any selected subset; untouched patterns wait.

A user-confirmed checklist records completion of the learning task. It does not certify objective technique mastery or automatically mark a pattern READY for high-load training.

## Six available learning tasks

| API pattern key | Learning / movement test |
|---|---|
| \`squat\` | Air squat |
| \`hinge\` | Hip hinge with dowel |
| \`horizontal_push\` | Incline or floor push-up, as appropriate |
| \`horizontal_pull\` | Bent-over row / scapular coordination |
| \`vertical_push\` | Actual overhead press with a very light, equipment-appropriate load |
| \`lunge\` | Supported reverse lunge / split squat |

Vertical pull remains a separate supplementary training pattern, not one of the six learning or camera tasks.

**Vertical push:** the learning task and movement test is the actual overhead press with a very light load. The unloaded overhead arm raise is only an optional camera observation and never replaces the press task.

## Selective learning contract

- Each task contains six pattern-specific control criteria.
- Progress can be saved for a subset of patterns. Untouched patterns are omitted from the saved progress object.
- A partially completed checklist remains \`in_progress\`; it can be saved and resumed but is not yet eligible for the current programme.
- A completed checklist (\`completed\`) can be included in a programme.
- A user may explicitly mark a started pattern as temporarily excluded (\`excluded\` with a reason).
- The first programme requires at least one completed selected pattern. It includes only completed selected patterns; explicitly excluded patterns are omitted.
- Any foundational pattern absent from the request remains unassessed. The backend treats it as \`UNASSESSABLE\` for this programme and never selects its exercises from a generic goal template.
- The keys in \`learning_progress.patterns\` and \`movement_decisions\` must match exactly. Unknown or mismatched keys are rejected.

## Endpoints

### Save or restore learning progress

\`GET /coach/profile/{profile_id}/learning-progress\`

\`PUT /coach/profile/{profile_id}/learning-progress\`

Header: \`X-Profile-Token: <profile access token>\`

The body contains only the patterns the user has started or explicitly excluded:

\`\`\`json
{
  "patterns": {
    "squat": {
      "status": "in_progress",
      "criteria": {
        "tempo": true,
        "balance": false
      }
    }
  }
}
\`\`\`

The example is illustrative: the actual criteria object must contain all six criterion IDs for that movement pattern, each with a boolean value. Partial progress is valid for saving. The storage endpoint stores only the supplied patterns and does not require optional health-data consent.

### Generate programme

\`POST /coach/program\`

The request includes:
- the structured training profile;
- the existing current-safety confirmation and explicit programme-use consent;
- \`learning_progress.patterns\` containing only completed or explicitly excluded selected patterns;
- \`movement_decisions\` with exactly the same pattern keys;
- optional camera observations, separately consented.

At least one selected pattern must be completed and eligible for learning / a conservative starting variation. In-progress and untouched patterns are not included in this request. If no eligible pattern exists, the backend returns a clear validation response.

## Decision and loading boundaries

- A completed checklist remains a user confirmation, not objective evidence of mastery.
- Selected patterns begin with verified learning or conservative starter variations.
- A camera observation cannot determine safety, diagnose, certify mastery, or grant permission for external load.
- New or worsening symptoms remain a separate safety concern and are not converted into automatic progression.
- Never replace an unsuitable pattern with a harder exercise from a different pattern.

## Optional camera observation

The camera may observe broad features from nine views across six tests. Video and frames remain on the device; transmitted observations are transient technical context only. The camera cannot replace a learning task, including the overhead press.

## Retired contract

The standalone \`/coach/movement-assessment\` and profile \`/coach/profile/{profile_id}/movement-assessment\` routes are retired. Use the guided \`learning-progress\` route for learning progress and send current movement decisions only with the programme request.
