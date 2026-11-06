# ATENA implementation architecture audit — 6 November 2026

**Scope:** read-only review of `phase-3/archetype-benchmarks` at commit `b4126d8ca72f36b0afbaf9ec0c00bbc8de90e8c0`.  
**Purpose:** identify concrete refactoring priorities before changing user-visible coaching behaviour.  
**Important:** this is a source-code review, not a live production test. The separate Cloudflare Pages frontend source is not part of this repository tree, so this audit does not claim to have inspected or changed the live questionnaire UI.

## 1. What already exists

| Capability | Current implementation | Assessment |
|---|---|---|
| Exercise knowledge | `training/catalogue.py`, `training/exercises.json` | Useful structured foundation; audit metadata and progression relationships need to be made consistently explicit. |
| Programme generation | `training/program.py` | Deterministic catalogue-backed generator with equipment, goal, experience and quality checks. Preserve it; do not replace with free-form LLM exercise selection. |
| Movement intake | `training/movement_assessment.py` | Conservative self-report model; current task set and terminology do not match the newly agreed assessment. |
| Pain/load policy | `training/PAIN_AND_LOAD_MANAGEMENT.md` and route prompt rules | Good nuanced principles exist, but the structured session API currently captures only a broad discomfort boolean. |
| Exercise progression | `training/exercise_progression.py` | Exercise-specific progression evidence exists. |
| Programme-level decisions | `training/adaptive_decision.py` | Explainable decision proposals with narrow scopes and no silent programme rewrite. |
| Other adaptation signal | `training/adaptation.py` | A second adaptation path with overlapping concepts; must be reconciled to avoid conflicting decisions. |
| Longitudinal summaries | `training/longitudinal_progression.py`, `training/conditioning_progression.py`, `training/periodization.py` | Useful evidence streams; should inform one decision service. |
| Persistent profile/history | `coach_store.py` | Opt-in PostgreSQL storage and structured session records. The JSON profile has no explicit schema-version/migration contract visible in this implementation. |
| Conversation | `coach_routes.py` | Contextual Slovenian prompt and many good guardrails, but route module has become a large mixed-responsibility file. |
| Quality checks | `training/quality_gate.py` and extensive tests | Strong existing automated coverage. Need additional end-to-end tests for the full closed-loop coaching behaviour. |

## 2. Specific mismatches to resolve

### 2.1 Movement assessment

Current `training/movement_assessment.py` exposes eight tasks:
- squat currently displayed as “vstajanje s stola”;
- hinge as “pobiranje lahkega predmeta s tal”;
- lunge;
- generic push and pull;
- overhead reach;
- single-leg balance;
- locomotion.

This does not match the agreed methodology:
- five core tasks: počep, izpadni korak, predklon z nevtralnim položajem hrbtenice, skleca, potisk nad glavo;
- two complementary positions: globok čep and klečanje s sedenjem na petah;
- dowel/broomstick feedback for the neutral-spine forward bend;
- no separate pull assessment in the initial basic screen, while pulling remains a required programme pattern.

The change must preserve old API/profile compatibility. Historical assessment records should not be reinterpreted as if they were collected under the new protocol. Add an assessment version and explicit mapping only where meaning is genuinely equivalent.

### 2.2 Goal taxonomy

`training/program.py` currently supports nine values:
`strength`, `hypertrophy`, `strength_hypertrophy`, `fat_loss`, `general_fitness`, `functional`, `power`, `endurance`, and `mobility`.

The goal/experience matrix describes five user-facing goals, but tests still exercise the nine internal goals. This is a mismatch between user-facing product taxonomy and backend taxonomy.

Target user-facing goals:
1. `strength_muscle` (combined strength + muscle development);
2. `functional_fitness` (integrated strength, endurance, power, mobility, balance and coordination);
3. `body_weight_management` (resistance training, appropriate endurance/circuit work and general nutrition support).

Do not simply delete old goal values. Introduce canonical values, map legacy values explicitly, preserve old profiles, and test every migration path. Keep advanced strength/hypertrophy emphasis as a secondary programme priority, not as two default user-facing goals.

### 2.3 Pain and symptoms

The written pain policy is substantially more nuanced than a binary injury/no-injury model. However:
- the session API stores `discomfort_reported` as a boolean;
- the profile programme endpoint requires a global `no_current_pain_or_restrictions=true` confirmation;
- `_build_profile_adaptation` treats a past discomfort record conservatively and creates a synthetic “discomfort=no” feedback only after the separate confirmation flow;
- the programme generator can omit a movement pattern on `symptoms_reported`, but does not itself have the richer symptom context needed to choose a well-matched alternative.

The desired direction is a structured symptom context with explicit unknown/unanswered/present/resolved states, location/task/timing/trend/function impact, and the user's response to modification. Keep appropriate red-flag gating. For ordinary local symptoms, decisions should be specific to the provoking task and dose, and should preserve unaffected training when appropriate.

Do not remove safety controls until the richer structured path is implemented and tested. A migration must not convert an old `false` or missing field into proof that the user is currently symptom-free.

### 2.4 Decision authority is fragmented

`coach_routes.py` imports and uses:
- `assess_next_step` from `training/adaptation.py`;
- `decide_adaptation` from `training/adaptive_decision.py`;
- exercise progression;
- longitudinal progression;
- conditioning progression;
- periodization and proactive check-ins.

The route helper `_build_adaptive_decision` already aggregates several signals, which is a useful start. But another helper, `_build_profile_adaptation`, independently derives a feedback object and invokes the separate `assess_next_step` path. The profile-program route then generates a plan and applies exercise progression, while broader decisions remain advisory.

Target: one coaching orchestration service owns the final next-step decision. Existing modules become evidence providers/specialist evaluators. The programme generator remains deterministic and is called only with a validated, scoped decision. Preserve the current conservative behaviour until equivalence tests prove the new engine is at least as safe.

### 2.5 Conversation route is carrying too much policy

`coach_routes.py` is over 2,100 lines and contains profile/storage routes, chat context, many natural-language safety and coaching rules, session validation, and programme/adaptation orchestration.

Target: progressively extract policy and services into dedicated modules, leaving route handlers to validate HTTP input, call application services and format responses. Do not attempt a risky one-shot rewrite. Extract in small steps with unchanged endpoint contracts and focused regression tests.

### 2.6 Profile and event history

`coach_store.py` stores a JSON profile and structured training sessions. That is a useful starting point, but the current visible storage schema does not define a versioned canonical athlete-state contract or a complete decision timeline.

Target: version profile and assessment payloads; record which facts are user-reported, observed, session-logged or inferred; distinguish planned work from actual work; and retain adaptation proposal/outcome links. Implement migrations only after reviewing actual stored data shape and existing export/import behaviour.

## 3. Recommended implementation order

1. Add versioned canonical goal and assessment contracts without changing the frontend.
2. Add compatibility adapters and tests for existing profiles, API payloads and historical session records.
3. Replace the old movement-assessment task schema behind a versioned endpoint; preserve legacy reads.
4. Create one coaching orchestration service that wraps the current evidence modules and returns a typed decision.
5. Route existing progress/adaptation endpoints through the new service while keeping response fields backward compatible.
6. Introduce richer symptom feedback with consent-aware storage and an explicit migration plan.
7. Extract responsibilities from `coach_routes.py` one module at a time.
8. Update the frontend questionnaire only after its source repository and deployment path are confirmed.
9. Run full offline CI and multi-turn Slovenian benchmarks. Live pilot testing is a separate quality check, not a substitute for automated tests.

## 4. Non-negotiable compatibility and safety rules

- No existing profile is silently discarded or reinterpreted.
- No missing answer is treated as a negative answer.
- No symptom is converted to a diagnosis.
- No pain flag is cleared merely to let a programme generator proceed.
- No old goal is dropped without a tested mapping or an explicit user clarification.
- No equipment is inferred from the goal or from common gym availability.
- No programme is silently rewritten by a chat response.
- No production deployment, model change, paid usage or data-storage setting is changed as part of this audit.

## 5. Conclusion

The current implementation is not a dead end. It has substantial reusable coaching logic and test coverage. The best path is a controlled architectural consolidation: canonical state, a single decision authority, a deterministic programme compiler and a structured closed feedback loop. The most urgent technical risks are the mismatch between the new coaching methodology and the legacy movement/goal schemas, and the gap between nuanced pain policy and the binary structured feedback currently stored.
