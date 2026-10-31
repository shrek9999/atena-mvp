# ATENA exercise system — Phase 4

## Purpose

The catalogue is the source of truth for exercise selection. The generator must select an exercise because its movement pattern, training role, loading potential, available equipment and intended stimulus match the user's goal—not merely because the exercise name contains a familiar movement.

The catalogue currently contains 107 curated entries. It is a controlled pilot library, not an exhaustive encyclopaedia. New exercises should be added only with a defined purpose, equipment contract, coaching cues, common errors, regression, progression and safety notes.

## Movement architecture

| Pattern / family | Purpose and examples |
|---|---|
| Squat | Reaching squat, air squat, goblet squat, back squat, front squat, dumbbell squat, single-leg box squat |
| Lunge | Split squat, forward/reverse lunge, walking lunge, Bulgarian split squat, ATG split squat, lateral lunge, step-up |
| Hinge | Deadlift, Romanian deadlift, dumbbell deadlift, single-leg RDL; unloaded hip hinge is a skill drill |
| Hip extension | Glute bridge, long-lever bridge, elevated heel hip lift, hip thrust |
| Knee flexion | Sliding leg curl, Nordic curl |
| Horizontal push | Wall/incline/standard/decline push-up ladder, dumbbell press, parallel-bar dips and band-assisted dips |
| Vertical push | Pike push-up, dumbbell/barbell overhead press, band press |
| Horizontal pull | One-arm dumbbell/kettlebell row, barbell row, TRX/ring/table row, band row |
| Vertical pull | Pull-up, chin-up, band-assisted and foot-assisted variants |
| Carry / trunk | Farmer carry, suitcase carry, front-rack carry, overhead carry, Pallof press, dead bug, Copenhagen plank |
| Locomotion / conditioning | Walk, run, cycle, row, SkiErg, air bike, jump rope, burpee, shuttle run, sled push and backward sled drag, step-up intervals, box-jump intervals, bear crawl |
| Mobility / loaded range / stretching | 90/90 transitions and hip IR isometrics, shinbox get-up, Cossack squat, ankle rocks, dead hang, crab reach, elevated pigeon hinge, straight-leg hip hinge, shoulder CARs, wall slides, wall butterfly, stick pass-through, couch and hamstring stretches, deep squat hold, loaded full-range squat |

The main movement patterns remain squat, lunge, hinge, push, pull, carry and locomotion. Mobility, conditioning, power and stability describe training roles or qualities and complement—not replace—the movement-pattern map. Joint targets (ankle, hip, shoulder, thoracic spine) and physiological targets (cardiorespiratory system) are stored separately from anatomical muscle groups.

## Goals are not interchangeable

- **Strength:** build force production. Use appropriately challenging external resistance or scalable unilateral/bodyweight variants, lower rep ranges where suitable, sufficient rest and technically sound execution.
- **Hypertrophy:** accumulate sufficient hard, repeatable work for the target musculature. Compound movements are prioritised. Single-joint accessories are opt-in for advanced trainees and longer sessions. A low-load skill drill must not be used as the main stimulus when a more scalable option exists.
- **Endurance:** a distinct goal with aerobic locomotion and interval/mixed-modal conditioning. Aerobic work is primarily prescribed by duration and talk-test effort; intervals by work/rest, exercise type and repeatability. Box-jump intervals are an advanced optional modality, not the default conditioning choice. Muscular endurance can be supported by carries, lunges and circuits. “Kondicija” is a broad everyday term, not a precise physiological category. Endurance is a specific training quality; distinguish cardiorespiratory, local muscular and repeated high-intensity effort.
- **Mobility:** combines active range exploration, controlled articular movement, transitions, end-range strength, loaded exercises through the individual's available range and selected static stretches. Static stretches complement—but do not replace—active mobility and strength through range. It is not synonymous with passive stretching.
- **Power:** prioritises intent and movement quality. Stop sets when speed or landing quality materially deteriorates.
- **Functional / general fitness:** combine foundational movement patterns and physical qualities according to the person's context. “Functional” is not a separate anatomical movement pattern.

## Loading potential

Each exercise has a `loading_potential` value:

- `low`: useful for skill, preparation, accessible movement or mobility; not normally a strong primary hypertrophy option for a trained person.
- `moderate`: scalable through range, leverage, unilateral work, tempo, external load or exercise difficulty.
- `high`: readily loadable or progressively demanding when appropriate equipment and technique are available.

This is a selection aid, not a universal ranking. The same push-up or split squat can be too easy for one person and challenging for another. The coach must consider training age, actual performance, target RIR, range, leverage and feedback.

For hypertrophy without weights, ATENA should prefer challenging, controlled variants. Preserve the hip-extension/knee-flexion posterior-chain substitute when the available time is short; do not drop it as optional accessory work. For the posterior chain it can use long-lever/elevated hip extension or sliding/Nordic knee flexion when appropriate. The unloaded hip hinge remains available to teach the pattern, but is not selected as the primary hypertrophy hinge.

## Equipment semantics

“Without equipment” means **without dedicated weights or gym apparatus**, not without ordinary household supports.

- Universal: bodyweight, floor and wall.
- Common household support: a stable chair, couch, step, table, towel or light stick/broom handle.
- Household load: a securely closed backpack or another safely gripped object.
- Dedicated equipment: dumbbells, kettlebells, barbells, racks, pull-up bars, resistance bands, suspension trainers/TRX, gymnastic rings, dip bars, sleds and cardio machines.

Household items are not assumed to be safe anchors. Table rows, elevated heel bridges, Bulgarian split squats and dips are allowed only when the support is stable, non-slip and suitable for the direction of force. Do not improvise a pull-up or Nordic anchor. If the safety of a support cannot be established, select another exercise.

## Progression

Progression is goal-specific and is not synonymous with adding weight.

- Strength / hypertrophy: meet the target rep range at the intended RIR and with consistent technique; then add a small load when available or use a harder variation, longer lever, unilateral version or greater controlled range.
- Endurance: gradually increase duration or total work, then intensity or density; change one main variable at a time.
- Mobility: improve active control, tolerable range and force production in that range. Repetition-based drills stay rep-prescribed; sustained positions are time-prescribed. Do not force end positions.
- Power: preserve speed, coordination and landing quality; do not chase fatigue.

Tempo is chosen by purpose: controlled lowering for resistance work, fast intent for power, rhythmic pacing for endurance and slow active control for mobility.

## Stability and carries

Carries are valuable loaded tasks for grip, trunk control, gait and postural endurance. They are programmed as purposeful work, not as a generic filler in every hypertrophy session. Anti-rotation and trunk-control exercises are included when the goal or observed movement-control feedback supports them. Pain or new discomfort blocks automatic adaptation and requires clarification rather than an automatic exercise substitution.

## Safety and limitations

- The system does not diagnose injuries or prescribe rehabilitation as a medical treatment.
- “Full range” means the individual's largest controlled, tolerable range—not a forced universal depth.
- Pain, instability, unsafe equipment or loss of control override the planned progression.
- A missing movement pattern or equipment option should be reported honestly; the generator must not invent a safe anchor or substitute an unrelated exercise.
- Exercise selection still needs professional review and live testing with representative profiles before production use.


## Push-up scaling

The horizontal-push ladder is explicit: wall push-up → incline push-up (higher support is easier; lower support is harder) → floor push-up → decline push-up. The selected support must be stable and non-slip. Progress by lowering the hand support gradually while preserving trunk position and range.

## Carries and stability

Loaded carries are included in strength, general-fitness and functional plans when time and equipment permit. They train grip, trunk control and gait under load. Carries complement—not replace—direct trunk-control exercises. Specific trunk-control drills remain feedback-led when a movement-control issue is identified.


## Additional movement options

The library includes optional mobility work inspired by Strength Side's published mobility programme: 90/90 transitions and internal-rotation isometrics, deep squat practice, couch stretch, dead hangs, elevated pigeon hinge, straight-leg hinge, crab reach and wall butterfly. These are examples to adapt—not a fixed routine to copy. Their published programme pairs strength and mobility sessions and uses holds, repetitions and isometrics in one plan.

ATG-inspired additions include Patrick step, ATG split squat, tibialis and full-range calf work, reverse Nordic curl, loaded squat through an individual's controlled range, and backward sled drag. These are coaching choices and optional progressions, not universal requirements or claims of injury prevention. Backward sled work and knee-over-toes loading must be introduced at a tolerable level and only where equipment, surface and movement control are appropriate.

## Evidence versus coaching philosophy

The 2026 ACSM position stand summarizes 137 systematic reviews involving more than 30,000 participants. It supports progressive resistance training for strength, hypertrophy, power and physical function; highlights heavy loads and complete range of motion for strength, higher weekly volume for hypertrophy, and fast concentric intent for power. It also notes that momentary failure, equipment type and complex periodisation did not consistently change outcomes in the reviewed evidence. Evidence on the optimal ROM for hypertrophy was insufficient to establish a single universal answer. ATENA therefore uses individualised, controlled ROM rather than forcing a universal depth.

WHO describes aerobic activity as rhythmic movement of large muscle groups over a sustained period and equates this with endurance activity; it distinguishes this from brief high-intensity anaerobic efforts and muscle-strengthening activity.

Reference reading:
- ACSM 2026 Position Stand: https://pubmed.ncbi.nlm.nih.gov/41843416/
- ACSM official summary: https://acsm.org/resistance-training-guidelines-update-2026/
- WHO glossary: https://www.ncbi.nlm.nih.gov/books/NBK566047/
- Strength Side mobility programme: https://strengthside.com/pages/free-program
- Strength Side 90/90 and hip mobility example: https://www.youtube.com/watch?v=RhbUw_hiR3U
- ATG Knee Ability series: https://app.atgonlinecoaching.com/articles/article-knee-ability-series-2-of-10
- ATG backward-walking and sled-work discussion: https://www.atgonlinecoaching.com/articles/does-walking-backward-on-a-treadmill-work-for-knee-ability

The ATG and Strength Side materials are used as sources of exercise ideas and coaching philosophy, not as independent clinical proof. Their claims about pain relief or injury prevention are not adopted as ATENA guarantees.
