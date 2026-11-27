# ATENA Phase 3 — taxonomy-driven programme selection

## Objective

Make the structured exercise taxonomy operational in the deterministic programme generator. Existing legacy exercise IDs, goal tags and pattern templates remain compatible; the new metadata now constrains eligibility and improves explanation.

## Goal-to-purpose rules

- Strength: `strength`
- Hypertrophy: `hypertrophy`
- Combined strength/hypertrophy: union of the two purposes, subject to the existing advanced-user emphasis rules
- Fat loss / weight management: resistance purposes plus general fitness and cardiorespiratory conditioning; resistance work remains foundational
- Functional fitness: functional fitness, strength, general fitness, balance, coordination, mobility and cardiorespiratory conditioning
- General fitness: general fitness plus relevant strength, mobility, balance, coordination and cardiorespiratory purposes
- Power: power and strength
- Endurance: cardiorespiratory conditioning, muscular endurance and general fitness
- Mobility: mobility plus relevant strength, general fitness, balance and coordination

Purpose tags are eligibility metadata, not a substitute for the existing movement-pattern template, experience, equipment, time, loading potential or exercise-specific selection rules.

## Stability

Every exercise with a primary or supporting stability role must also carry the `stability` training purpose. Stability work is added only when the current feedback/assessment indicates a relevant need. When included, the selector may retrieve compatible stability-purpose exercises even if their legacy goal tags would otherwise exclude them.

The returned exercise object exposes:
- `movement_pattern`
- `training_purposes`
- `stability_role`
- `stability_focus`

This lets ATENA explain whether stability is primary, supporting or incidental. It must not imply that every exercise with incidental trunk control is a dedicated stability exercise.

## Reaching squat

The reaching squat remains eligible for mobility/general/functional contexts but is excluded as a primary hypertrophy stimulus because its purpose metadata does not include hypertrophy. The legacy goal tag is retained for backwards compatibility, but the programme generator now respects the more specific purpose tag.

## Compatibility and safety

- Existing exercise IDs and legacy pattern labels remain unchanged.
- No exercise is invented by the language model.
- Equipment and experience constraints remain active.
- Landing/braking readiness is not inferred from training experience.
- Stability is not inserted automatically into every programme.
- The frontend and questionnaire are unchanged.

## Tests

Regression tests cover purpose filtering, reaching-squat eligibility, functional capacity tags, endurance conditioning tags, stability role/purpose consistency and semantic metadata in generated programmes.
