# ATENA coach response quality fixtures

The cases in `coach_quality_cases.json` are synthetic, hand-written examples. They are not outputs from Gemini or another model. The tests run a small deterministic heuristic against these examples and a few obviously unsafe counterexamples. A passing run proves only that the fixtures satisfy those declared checks and that the heuristic catches those counterexamples. It does **not** prove that the live coach responds safely, accurately, naturally, or consistently.

## Automated coverage

| Requirement area | What CI checks | What CI does not establish |
|---|---|---|
| Safety | Presence/absence of selected Slovenian phrases; clearly unsafe counterexamples are rejected; critical cases are tagged | Clinical adequacy, completeness of red-flag triage, whether an unlisted diagnosis is implied |
| Individualization | Fixture contains expected context terms and has a declared maximum number of question marks | Whether the question is the best next question or the plan truly fits a person |
| Timing | One structured synthetic example sums warm-up, work/rest, transitions, and cool-down to 20 minutes; required timing phrases appear in its fixture reply | Parsing arbitrary free-form model output or verifying that the actual performed session lasts that long |
| Feedback and history | Fixture refers to supplied prior context; selected claims of durable memory are rejected | Whether a model correctly used every relevant prior turn |
| Slovenian | Selected examples include required plain-language terms and exclude a small list of common English jargon | Grammar, idiom, terminology quality, readability, or regional suitability |

The timing arithmetic is test metadata, with work/rest intervals checked separately from transitions. The sentence checks are literal substring checks, not semantic interpretation.

## Human review still required

Every case has a `human_review` list. A Slovenian-speaking exercise professional should review:

- clinical and training appropriateness, including when to stop or refer;
- whether progressions and modifications fit the actual exercise and user context;
- the accuracy of Slovenian grammar and exercise terminology;
- whether instructions are understandable and internally consistent.

These checks are a preparatory offline harness. No production or staging endpoint, external model, personal data, or real secret is used.

## Adding cases

1. Use fictional details only and mark each case `synthetic_handwritten`.
2. State the linked validation-plan requirement and severity; critical safety cases must remain explicit.
3. Keep automated criteria narrow and observable. Use a negative counterexample to show that an important forbidden phrase is detected.
4. List remaining expert judgments under `human_review`.
5. Never describe fixture-level success as a model quality or safety pass.
