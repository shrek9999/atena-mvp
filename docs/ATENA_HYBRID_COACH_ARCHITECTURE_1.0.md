# ATENA Hybrid Coaching Architecture 1.0

**Status:** proposed target architecture for Phase 3  
**Decision:** evolve the current Flask application into a modular monolith with a deterministic coaching core and an LLM conversation layer. Do not rebuild the product or introduce a multi-agent swarm.

## Executive decision

ATENA should not be designed as a chatbot that writes workouts, nor as a collection of independent AI agents. It should be a **stateful coaching system** with one authoritative athlete profile, one explainable decision engine, a curated exercise knowledge base, a programme compiler, and a conversational interface.

The current repository already contains useful foundations: a catalogue-backed programme generator, profile and session storage, movement-assessment code, exercise progression, longitudinal summaries, adaptive decisions, pain/load guidance, and quality gates. The main architectural problem is orchestration and consistency: rules and coaching behaviour are spread across route-level prompt text and separate modules. The correct next move is to consolidate decision-making and data contracts, not discard the working system.

## 1. Target architecture

Use a modular monolith initially. Keep the current Flask deployment and database approach unless a measured technical requirement justifies a change.

### Layer A — Conversation and intake interface

Responsibilities:
- Understand natural-language requests and answer in Slovenian.
- Ask one high-value follow-up at a time.
- Extract facts from user messages into a proposed structured update.
- Explain coaching decisions in natural language.
- Never claim that a profile, workout or programme has been saved unless the storage workflow confirms it.

The language model may interpret ambiguity and formulate questions. It must not independently bypass safety rules, invent profile facts, select unverified equipment or write arbitrary programme changes.

### Layer B — Canonical Athlete State

Create one versioned, validated representation of the person. It is the source of truth for coaching decisions.

Suggested domains:
- identity and consent metadata (minimum necessary);
- goals and priority (combined strength + muscle development, functional fitness, body-weight management);
- training experience and history;
- schedule and flexible session duration;
- equipment and setup constraints;
- movement observations and assessment provenance;
- symptom/pain context, status and last update;
- actual completed training records;
- exercise-specific performance and RIR;
- recovery, adherence and user preferences;
- current programme version and prior adaptation decisions.

Every fact should carry provenance and freshness where appropriate: user-reported, observed in a task, logged from a session, inferred with confidence, or not known. Missing information must remain unknown. Do not store a model guess as a user fact.

Use schema versions and explicit migrations. Do not silently reinterpret old profiles when the goal taxonomy changes.

### Layer C — Coaching Decision Engine (the core)

This is the single place that determines what ATENA should do next. It receives a canonical state and returns a typed, explainable decision.

Decision order:
1. safety and urgent warning-sign gate;
2. symptom/pain-specific interpretation and whether ordinary coaching can continue;
3. goal and user-priority resolution;
4. movement/task and equipment constraints;
5. training response, recovery and adherence;
6. exercise-level progression or regression;
7. session/programme-level changes only when justified;
8. reassessment or clarification when evidence is insufficient.

The engine must return:
- decision type;
- scope (one set, one exercise, one session, whole programme, or no change);
- evidence and reason codes;
- uncertainty / missing information;
- proposed action;
- expected response to monitor;
- whether user confirmation is required;
- rules that blocked progression.

No other module should make a competing programme-level decision. Existing adaptation modules should be reconciled behind this engine, not called independently by routes with overlapping authority.

### Layer D — Exercise Knowledge Base

Maintain a curated catalogue as structured coaching knowledge, not just a list of exercise names.

Each exercise record should include:
- stable exercise ID and accurate Slovenian display name;
- movement pattern and training purpose;
- equipment and safe setup requirements;
- primary and secondary muscles/capacities where useful;
- experience suitability;
- required competence and constraints;
- dosage options and coaching cues;
- clear regression and progression links;
- acceptable alternatives for the same intended stimulus;
- symptom-related caution notes without diagnostic claims;
- source/review metadata.

Regression/progression should be explicit and directional. A regression is not merely a different exercise with fewer repetitions. It should reduce a relevant demand (load, range, leverage, balance, coordination, speed or complexity) while preserving as much of the intended training effect as possible.

### Layer E — Programme Compiler

The compiler converts the engine's approved training intent into a concrete plan. It must not invent coaching policy.

Inputs:
- canonical athlete state;
- primary goal and secondary priorities;
- approved decision output;
- exercise catalogue;
- available equipment and realistic session time.

Outputs:
- weekly distribution;
- sessions and exercise order;
- exercise IDs and variations;
- sets, repetitions/time, tempo, rest and effort target;
- concise unique coaching cues;
- regression/progression options;
- explicit rationale for key selections.

A deterministic quality gate checks every generated programme before delivery: equipment, safe setup, goal fit, experience, weekly balance, dose, RIR, realistic duration, exercise validity, symptom constraints and alternatives. If validation fails, regenerate or return a clear limitation; do not silently pass it.

### Layer F — Session execution and feedback

Treat the completed session as evidence, not as a copy of the prescribed plan.

Capture with minimal friction:
- completed / partly completed / not completed;
- actual exercise, sets, reps, load or duration where relevant;
- RIR or perceived effort;
- technique/control and confidence;
- pain or discomfort, location and timing;
- recovery and next-day response when relevant;
- reason for missed or modified work (time, difficulty, recovery, external interruption, other).

A short conversational summary may be enough for most users. Detailed per-set logging should remain optional, with structured logging available for users who want it.

### Layer G — Longitudinal coaching memory

Store meaningful changes as a timeline:
- what was prescribed;
- what was actually done;
- what the user reported;
- what ATENA decided and why;
- what change was proposed/applied;
- what happened after that change.

This enables ATENA to learn from the person's response without pretending that one session establishes a trend. Keep explicit distinctions between planned, completed, user-reported and inferred data.

### Layer H — Evaluation and governance

Quality assurance must test the whole coaching loop, not only whether the API returns valid text.

Maintain:
- deterministic unit tests for rules and programme validation;
- profile migration tests;
- multi-turn Slovenian conversation scenarios;
- adversarial cases (missing pain answer, contradictory equipment, new symptoms, ambiguous goal, incomplete session);
- expert-reviewed programme quality rubric;
- longitudinal tests that check whether the next decision uses actual previous outcomes;
- live model evaluations on the free pilot only, with cost and privacy constraints respected.

Report technical reliability separately from coaching quality. A successful API response is not evidence of a good coaching decision.

## 2. The decision loop

The central workflow should be explicit and repeatable:

1. **Understand:** interpret the user's request and identify missing facts.
2. **Update state:** validate any proposed profile or session facts; preserve provenance.
3. **Check constraints:** safety, symptoms, equipment, experience and time.
4. **Decide:** produce one typed coaching decision with evidence and uncertainty.
5. **Plan:** compile or revise only the affected part of the programme.
6. **Validate:** run the quality gate before presenting the plan.
7. **Explain:** tell the user what changed and why, in concise Slovenian.
8. **Observe:** collect actual performance and response.
9. **Review:** compare the observed response with the expected signal.
10. **Adapt or hold:** change only what the evidence justifies.

This loop applies at three timescales:
- **in-session:** exercise-level adjustment;
- **between sessions:** dose, progression and recovery decisions;
- **between blocks:** programme structure, priorities and reassessment.

## 3. Specific intelligence: use context, not a larger prompt

ATENA becomes specifically intelligent when it can connect facts to consequences.

Examples:
- If a user has only a wall and bodyweight, it must choose exercises that can actually be performed safely with those resources; it must not suggest a row requiring an unverified table or anchor.
- If a user is a beginner, a technically complex exercise does not become appropriate merely because it matches the goal. Choose a learnable variation and dose.
- If the user reports pain during one variation, investigate that task and its dose, test a tolerable alternative when appropriate, and preserve unrelated training where possible.
- If a session was missed because of time, restructure the session rather than automatically reducing training load.
- If a user completes a set with high effort or deteriorating technique, do not progress it merely because all prescribed repetitions were completed.
- If the user has two easy sessions, do not progress every exercise globally; identify which exercise and which variable have evidence for progression.
- If the user wants fat loss, keep resistance training central, add appropriate endurance/circuit work, and provide safe, sustainable general nutrition guidance.
- If a user selects functional fitness, integrate strength, endurance, power, mobility, balance and coordination according to their level and priorities rather than generating random MetCons.

## 4. Pain is a first-class coaching signal

Pain/symptom context must be represented as structured state and processed before routine progression. It should include location, side, provoking task, onset/timing, intensity as reported, trend, functional effect, response to modification and next-day response.

The engine should distinguish:
- symptom not asked;
- asked but unanswered;
- explicitly denied for the relevant context;
- present and stable/familiar;
- new, worsening or function-changing;
- concerning / requires professional assessment.

Do not collapse these states into a single boolean such as `pain: true/false`. Do not infer no pain from silence. Do not diagnose. Red flags and urgent symptoms override routine programme decisions. For non-urgent symptoms, use task- and dose-specific modification, monitor the response and preserve tolerable unrelated work.

## 5. Architecture choices: what not to do

### Do not rebuild the whole product now
A rewrite would discard tested behaviour and create new integration risks. First consolidate contracts and decision authority around existing modules.

### Do not introduce multiple autonomous agents
Separate agents for anatomy, programming, nutrition, pain and motivation may sound sophisticated but add coordination overhead, contradictory outputs, latency, cost and debugging complexity. Use clear internal modules and one controlled orchestration path. A specialist model/tool can be considered later only if an evaluation demonstrates a real gap.

### Do not let the LLM directly own exercise prescription
LLMs are useful for interpreting natural language, asking questions and explaining decisions. They are not a reliable sole source of exercise catalogue facts, equipment validation, dose arithmetic or safety gating. Those must be structured and testable.

### Do not add wearables or computer vision as a prerequisite
The product should deliver useful coaching with ordinary user feedback first. Integrate wearables/video only when there is a clear decision benefit, consent, privacy controls and evidence that the signal is reliable enough.

### Do not use fine-tuning as the first solution
First improve the state model, structured knowledge, deterministic rules, prompts and evaluation set. Fine-tuning is worth considering only after a sufficiently large, high-quality, consented dataset demonstrates a repeatable failure that cannot be addressed more simply.

## 6. Recommended implementation sequence

### Step 1 — Architecture and behaviour inventory
Map every current route, prompt rule, profile field, storage operation, training module and decision output. Identify duplicate/conflicting decision paths and define one canonical schema. No production behaviour change in this step.

### Step 2 — Canonical state and decision contracts
Introduce typed, versioned schemas for athlete state, symptom context, session evidence and coaching decisions. Add migration/compatibility tests. Do not break existing profiles or API contracts.

### Step 3 — One decision engine
Move overlapping progression/adaptation decisions behind a single orchestration service. Existing modules become specialised evaluators called by that service. Return structured reasons, uncertainty, scope and confirmation requirements.

### Step 4 — Programme compiler integration
Feed only validated decisions into the existing catalogue-backed generator. Add a goal migration path: strength and muscle development combined by default; functional fitness integrated; body-weight management with resistance training and nutrition support. Keep advanced specialisation conditional.

### Step 5 — Assessment and symptom integration
Implement the agreed five movement tasks plus two complementary positions, with observed/self-reported provenance. Integrate symptom context as a first-class constraint without turning the movement assessment into diagnosis.

### Step 6 — Closed-loop session review
Connect actual completed work and user response to exercise-level and programme-level decisions. Ensure the next plan reflects only confirmed, justified changes.

### Step 7 — Quality evaluation
Build end-to-end scenarios across beginner/intermediate/advanced users, equipment profiles, all goals, pain contexts, schedule constraints and multi-week histories. Require expert review of generated plans, not only automated pass/fail tests.

### Step 8 — Controlled pilot
Run offline tests, then the existing free-tier pilot. Compare repeatable scenarios and human-rated coaching quality. No paid model, billing change, production deployment or external data integration without explicit approval.

## 7. Success criteria

ATENA is ready for a wider pilot only when it consistently:
- builds a programme that is specific to the person's goal, experience, equipment, capacity and time;
- explains why each main exercise and variation was selected;
- provides safe, meaningful regressions and progressions;
- notices and responds correctly to pain and incomplete information;
- distinguishes session non-completion due to time, difficulty and recovery;
- uses actual training history without inventing missing data;
- changes only the appropriate exercise/session/programme scope;
- preserves a coherent coaching conversation across multiple weeks;
- passes expert-reviewed Slovenian scenarios with no critical safety or prescription failures.

## Final recommendation

Keep the current repository, deployment and free-tier model for now. Refactor toward a **hybrid, stateful coaching architecture**: LLM for conversation and contextual interpretation; deterministic coaching engine for decisions; curated exercise knowledge for prescription; validated programme compiler for plans; persistent session evidence for learning; and expert-reviewed evaluations for quality.

This is the most efficient and proportionate path for ATENA at its current stage. It preserves the work already done while directly addressing the central weakness: the parts need to behave like one coherent coach.
