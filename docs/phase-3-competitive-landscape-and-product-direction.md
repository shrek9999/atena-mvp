# ATENA Phase 3 — competitive landscape and product direction

**Review date:** 6 November 2026  
**Code baseline reviewed:** `pilot/coach-intelligence-stage2`, commit `c2abc54c6417474a751305b76005c80b7e22c689`  
**Purpose:** translate public competitor capabilities and the current ATENA implementation into a focused product direction. This is a desk review of public vendor information, not independent testing of competitors.

## Executive decision

Prioritize **ATENA Coach: a Slovenian-first digital personal trainer for the general population**. Its primary user is an everyday person who wants to become stronger, fitter, more enduring and more capable in daily life. It must work for beginners as well as experienced recreational trainees.

Keep the existing ATENA decision API/MCP capability as a separate technical/product line. Do not let the B2B agent-infrastructure business model determine the consumer coaching UX or near-term roadmap.

The differentiation should not be “we also generate workouts” or “we use AI”. It should be:

> A conversational coach that understands the person, selects appropriate training from a verified exercise system, explains the reasoning, adapts to real feedback over time, and knows when not to progress.

## Competitor landscape

Vendor descriptions below are based on public product pages and help documentation. Marketing claims, usage totals and proprietary algorithm descriptions are not independently verified.

| Product | Publicly described strengths | What ATENA should learn | Opportunity for ATENA |
|---|---|---|---|
| Fitbod | Exercise selection based on goal, experience, available equipment, recovery, variety and feedback; uses logged performance to adjust future recommendations. | Equipment must be a hard constraint; logged choices and training results should influence future sessions; progression needs to be evidence-led. | Stronger conversational clarification, movement competency and explicit explanation of regressions/progressions for non-athletes. |
| Freeletics | Structured training journeys; adapts sessions to profile, performance and post-workout feedback. Its Coach+ adds conversational AI; its product also describes movement-feedback features. | Good habit-forming journeys, adaptable sessions, simple user feedback and frictionless workout delivery. | A coherent strength + conditioning + mobility + functional-capacity coach, with more transparent exercise selection and individualized coaching dialogue in Slovenian. |
| Alpha Progression | Plan generation based on goal, experience, schedule, equipment and muscle priorities; weight/repetition recommendations, RIR, periodization, deloads, exercise demonstrations and progress tracking. | Excellent foundations for resistance-training logging, exercise education, progression and training analytics. | Serve broader everyday fitness goals beyond muscle/strength, while retaining strong compound-exercise programming and clear beginner pathways. |
| JuggernautAI | Highly individualized strength programming; readiness check-ins; adjustments from set-level performance through sessions, weeks, blocks and programs. | Adaptation must happen at multiple time scales; readiness and in-session performance are useful signals, not just end-of-week feedback. | Broader target population and movement/fitness goals, less powerlifting-specific language, and a more accessible conversational onboarding. |

### Public source references

- Fitbod exercise selection: https://help.fitbod.me/hc/en-us/articles/43489509474455-How-does-Fitbod-choose-which-exercises-to-give-me
- Fitbod adaptation: https://help.fitbod.me/hc/en-us/articles/43492523917207-How-does-Fitbod-adapt-as-I-get-stronger
- Freeletics Training Journeys: https://help.freeletics.com/hc/en-us/articles/360001805519-Choose-your-Freeletics-Training-Journey
- Freeletics Coach+ and privacy description: https://www.freeletics.com/en/pages/privacy/
- Alpha Progression fact sheet: https://alphaprogression.com/en/fact-sheet
- JuggernautAI product: https://www.juggernautai.app/
- JuggernautAI individualization: https://help.jtsstrength.com/en/articles/3-how-juggernautai-is-individualized-to-you

## Product implications

### 1. What ATENA must be excellent at

1. **Understanding the person:** goals, experience, available equipment, realistic time, preferences, training history, limitations and feedback.
2. **Choosing the right exercise:** the actual equipment and safe setup are hard constraints; exercise selection must reflect goal, ability, movement pattern, loading potential and user preference.
3. **Explaining the dose:** sets, repetitions, effort/RIR, tempo, rest and realistic session duration must make sense together.
4. **Regressing and progressing:** every important exercise needs a meaningful easier and harder option, with clear triggers for changing level.
5. **Adapting over time:** distinguish a one-off bad session from a repeated trend; change the smallest useful variable; stop automatic progression when symptoms appear.
6. **Coaching, not interrogating:** one useful question at a time, remember known context, be proactive without repeating intake questions.
7. **Trust and safety:** no diagnosis, no fabricated history or equipment, clear uncertainty and referral when outside the training scope.

### 2. Five user archetypes for product validation

| Archetype | Typical need | Test of product quality |
|---|---|---|
| Beginner | Confidence, simple exercises, safe learning and a manageable first plan. | Does ATENA avoid advanced exercise choices, excessive volume and unnecessarily low repetitions? |
| Home-based recreational user | Limited equipment, short/flexible sessions and practical progression. | Does every exercise genuinely fit the equipment and have a feasible alternative? |
| Regular gym user | Strength or hypertrophy with progression and sensible volume. | Does it select scalable compound exercises, use accessories selectively and manage weekly workload? |
| Conditioning / functional-fitness user | Aerobic capacity, intervals, strength, power, balance and coordination. | Does it distinguish conditioning from general fitness and avoid turning every session into a random MetCon? |
| Time-constrained user | Variable availability and inconsistent weeks. | Does it preserve the main stimulus when time is reduced rather than squeezing an unrealistic plan into a fixed duration? |

### 3. What not to copy

Use public product behavior as inspiration, not proprietary implementation. Do not copy competitor source code, protected content, exercise videos, branding, visual design or confidential algorithm details. Build original rules, catalogue content, prompts, interaction design and evaluation data around ATENA's own coaching methodology.

### 4. Positioning and business model alignment

The repository currently contains two different product narratives:

- the web-facing coaching application is a direct-to-consumer digital trainer;
- `BUSINESS_MODEL.md` positions ATENA primarily as a B2B decision-intelligence API/MCP sold to other agent developers.

These may become two products, but the immediate roadmap must prioritize the consumer coach. Keep the API/MCP stable and separate; do not divert the coaching roadmap into developer monetization until the consumer product has demonstrated repeated use and willingness to pay.

Initial market hypothesis: a Slovenian-first pilot can validate onboarding, exercise quality, adherence, feedback-driven adaptation and willingness to pay before investing in broader localization.

## Current implementation observations

Based on the reviewed code at the baseline commit:

- `training/program.py` and the curated exercise catalogue provide deterministic program generation; this is not simply a language model inventing a workout.
- `coach_routes.py` supplies the conversational system prompt, filtered catalogue context, authenticated recent training history and server-side guardrails to Gemini.
- The exercise catalogue is documented as a curated pilot library of 121 entries, with explicit exercise purpose, equipment and progression metadata.
- The repository already contains conversation-quality and phase-B scenario suites. These are useful foundations, but fixture tests and deterministic tests do not prove the live model is a high-quality coach.
- The consumer coach and the decision API/MCP have distinct jobs and should be evaluated separately.

## Prioritized roadmap

### P0 — protect and clarify the product
- Resolve repository visibility/licensing with an informed decision (see the separate IP/security review).
- Define ATENA Coach as the primary product and keep B2B decision API/MCP as a separate optional line.
- Keep production, user data, credentials and paid services untouched during this review.

### P1 — measure real coaching quality
- Run the existing multi-turn benchmark on the live model using synthetic scenarios only.
- Add coverage for the five archetypes above and for goal-specific program differences.
- Score every case against the rubric; safety-critical failures are automatic failures.
- Compare model quality, response length, latency and token cost.

### P2 — improve the coaching system
- Strengthen structured user state and explicit conversation memory boundaries.
- Keep deterministic programme constraints and safety checks outside the language model.
- Use the model for contextual reasoning, explanation, clarification and coaching dialogue.
- Make exercise substitutions preserve the intended stimulus and movement pattern.
- Improve feedback capture and next-session adaptation.

### P3 — validate product value
- Run a small pilot over several weeks.
- Measure activation, first-plan completion, workout completion, return rate, feedback quality, and retention.
- Test willingness to pay with a real offer, not only “would you pay?” survey questions.
- Do not scale acquisition before repeated use and retention are demonstrated.

## Decision

The winning strategy is not to outspend larger competitors or to imitate their interfaces. ATENA should combine a strong deterministic training engine, a capable conversational model, Grega Jenko's coaching methodology, and disciplined real-user evaluation. The product must earn trust through consistently good decisions, not through the label “AI”.
