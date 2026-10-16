# ATENA Gemini Free-Tier Pilot

This is a separate, manually triggered experimental runner. It does not change the production ATENA API or the existing OpenAI pilot.

## Cost and safety guardrails

- **No automatic runs:** the workflow only runs via manual `workflow_dispatch`.
- **Explicit gate:** the operator must type `I_CONFIRM_FREE_TIER` before the job starts.
- **Small limit:** defaults to one paired case and has a hard maximum of five.
- **No retries after quota/auth errors:** HTTP 429, 401 and 403 stop the run.
- **No Google Search grounding or other optional paid tools.**
- **No API key in code:** the key is read only from the GitHub Actions secret `GEMINI_API_KEY`.
- The workflow does not itself enable billing or create a billing account. Nevertheless, the operator must verify the project is still on Free Tier immediately before each run; if a billing account is linked, do not run this workflow.

Google states that the Free Tier allows access to selected Gemini API models within model-specific limits. Confirm the selected model and its quota in AI Studio before running:
https://ai.google.dev/gemini-api/docs/billing
https://ai.google.dev/gemini-api/docs/rate-limits
https://ai.google.dev/gemini-api/docs/pricing

## Setup

1. In the GitHub repository, open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named `GEMINI_API_KEY` and paste the key directly into GitHub's secret form. Never put the key in a file, workflow input, issue, pull request, or chat.
3. Confirm the Gemini API project remains on Free Tier and has no linked billing account.
4. Open **Actions → ATENA Gemini Free-Tier Pilot → Run workflow**.
5. Keep the default case limit at `1`. Keep the default `gemini-3.8-flash` unless AI Studio shows it is unavailable on your project. Confirm that the model is Free Tier for this project and that no billing account is linked.
6. Type `I_CONFIRM_FREE_TIER` and run only if the above checks are true.

## Interpretation

One case only checks that the pipeline works; it does not establish incremental value. Review the saved paired outputs blind and score them with the existing evaluation rubric before expanding to more cases. The result artifact contains model output and token counts; it does not contain the API key.

This pilot is experimental and is not clinical validation.
