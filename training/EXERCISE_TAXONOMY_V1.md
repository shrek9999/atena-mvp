# ATENA exercise taxonomy v1

## Why this exists

The existing catalogue fields remain backward compatible. This taxonomy adds a stable semantic layer so the programme engine can distinguish a movement pattern from a training purpose, a quality being trained, and the stability contribution of an exercise. Do not collapse these concepts into one label.

## Canonical movement pattern

Every exercise receives `movement_pattern`, one of:

- `squat`, `lunge`, `hinge`: lower-body foundational patterns. A hinge exercise is described in Slovenian as **predklon** or **predklon z nevtralnim hrbtom** where appropriate; avoid the phrase “kolčni pregib” as the user-facing name.
- `push`, `pull`: upper-body push/pull patterns, independent of horizontal or vertical direction (the existing `pattern` retains that detail).
- `carry`: loaded carries and object transport.
- `trunk_control`: direct trunk-control patterns, including anti-rotation and trunk-stability work.
- `locomotion`: gait, running, jumping and related movement tasks.
- `conditioning`: cyclical or mixed-modal conditioning not better represented as locomotion.
- `mobility`: active mobility, transitions and stretching.
- `balance`, `coordination`: exercises whose primary movement identity is these qualities.
- `accessory`: local or supplementary exercises that do not fit the foundational patterns.

The legacy `pattern` and `movement_family` remain intact for current filtering and are not to be removed in this phase.

## Training purposes

Each record has a list `training_purposes`. Allowed values:

- `strength`, `hypertrophy`, `mobility`, `stability`, `trunk_bracing`, `balance`, `coordination`, `power`, `cardiorespiratory_conditioning`, `muscular_endurance`, `general_fitness`, `functional_fitness`, `weight_management`, `skill`.

An exercise may serve multiple purposes. Its catalogue `goals` remain the existing high-level programme eligibility tags; purposes explain the specific qualities the exercise can contribute. A purpose tag does not make an exercise automatically suitable as the main stimulus for that goal. Consider loading potential, training experience, range, dose and feedback.

## Stability semantics

Every exercise has:

- `stability_role`: `primary`, `supporting`, `incidental` or `none`.
- `stability_focus`: zero or more of `trunk_control`, `trunk_bracing`, `balance`, `joint_control`.

Interpretation:

- `primary`: stability/control is the main intended training stimulus (e.g. anti-rotation or direct trunk-control exercise).
- `supporting`: the exercise deliberately facilitates or reinforces stability, bracing, balance or coordination while serving another movement purpose.
- `incidental`: stability is required during execution but is not the reason the exercise is selected.
- `none`: no meaningful stability purpose is claimed.

Stability work must not be inserted automatically into every programme. Use it when the goal, movement assessment or user feedback supports it. A movement may train trunk stability without being a conventional “core exercise”.

## Special coaching interpretation: reaching squat

`reaching_squat` is a supported, accessible squat-pattern option. Reaching the arms forward/up and optionally holding a light bumper plate (for example 5 kg) as a counterbalance can make the movement easier to coordinate and balance, and can help the person establish trunk bracing/stabilization. The plate is a positional aid, not a loading target. This is why its metadata marks stability as `supporting`, with trunk bracing, balance and coordination as focuses. Do not classify it as a demanding balance test or a heavy hypertrophy squat merely because an external plate is held.

## Naming convention: hinge

Use **predklon** or **predklon z nevtralnim hrbtom** in user-facing Slovenian labels and coaching cues. “Predklon z nevtralnim hrbtom (lastna teža)” is the canonical label for the unloaded pattern-learning drill. Loaded variants retain their established exercise names (e.g. romunski mrtvi dvig).

## Selection principles

1. Select by the user's goal, experience, movement competency, available equipment, time and feedback—not by a single tag.
2. Prefer multi-joint foundational patterns for strength and hypertrophy; add single-joint accessories when experience, volume and time justify them.
3. Mobility includes active movement, strength/control at end range, transitions and selected stretching—not stretching alone.
4. Conditioning distinguishes aerobic work, intervals, muscular-endurance circuits and high-intensity mixed-modal work.
5. Functional fitness combines strength, conditioning, balance, coordination, carries, trunk control and movement competency; it is not a synonym for conditioning.
6. Stability is an explicit purpose and can be primary, supporting or incidental. Add dedicated work only when warranted.
7. A purpose tag never overrides pain, safety, prerequisites, or the individual's controllable range of motion.

## Compatibility

The additions are additive. Existing `pattern`, `training_role`, `goals`, equipment rules, and exercise IDs remain stable except the user-facing Slovenian label and cue wording for the unloaded hinge drill. Keep the existing ID `bodyweight_hip_hinge` to preserve stored programme references.
