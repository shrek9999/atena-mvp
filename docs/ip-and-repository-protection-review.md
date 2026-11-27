# ATENA — repository, licence and IP protection review

**Review date:** 6 November 2026  
**Repository:** https://github.com/shrek9999/atena-mvp  
**Scope:** visible GitHub repository metadata, root licence, current file tree and a limited search for common credential patterns. This is an operational review, not legal advice or a full security audit.

## Findings

### 1. Repository is public

The GitHub repository API currently reports:

- `private: false` / visibility `public`;
- default branch: `main`;
- GitHub-reported forks: `0`;
- GitHub Actions and pull requests are enabled.

Anyone can view public source code and public activity, and public repositories can be forked. GitHub's guidance says that changing a public repository to private does not make existing public forks private; they are detached from the original repository and remain public. Local copies cannot be enumerated by the repository owner.

Official guidance: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility

### 2. Root licence is MIT

The root `LICENSE` file contains the MIT License and names Grega Jenko as copyright holder, copyright year 2026. MIT is a permissive licence that allows people who obtain a copy to use, copy, modify, distribute, sublicense and sell copies, subject to the licence notice and conditions.

This is not compatible with an assumption that the repository source is confidential or that downstream recipients are prohibited from commercial reuse. Making the repository private now would stop ordinary new public access to the original repository, but it does not erase copies already obtained or retroactively withdraw rights granted under the MIT licence. The legal effect of changing licensing for future releases and the ownership of all contributions should be reviewed with a qualified lawyer before any relicensing strategy is adopted.

Official GitHub guidance: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository

### 3. Limited credential scan

The current file tree reviewed on the pilot branch did not show a committed `.env` file. A limited GitHub code search on the default branch for common literal patterns and environment-variable names (including `AIza`, `sk-`, `GEMINI_API_KEY`, `AI_COACH_TEST_TOKEN`, `SUPABASE_SERVICE_ROLE_KEY` and `DATABASE_URL`) returned no matching results.

This is **not** a complete secret audit: code search is not a substitute for scanning all branches, commit history, workflow artifacts, deployment logs and connected service settings. Secret values should remain in Render/GitHub/Cloudflare secret stores, never in source, prompts, screenshots or logs. If a real credential was ever committed, rotate it; deleting it from the latest file is not enough.

### 4. Product IP is broader than source code

The defensible product assets include:

- original exercise catalogue records, cues, setup requirements and progression relationships;
- Grega Jenko's original coaching methodology, rules and training content;
- original program-quality criteria and evaluation scenarios;
- software implementation, brand identity, domain and product experience;
- accumulated user feedback and training data, subject to privacy and lawful processing.

The generic idea of an AI fitness coach is not, by itself, an exclusive asset. Avoid copying competitors' source code, videos, text, branding, interface artwork or confidential algorithms.

## Recommended decision

**Do not change repository visibility or licence automatically as part of this documentation-only phase.** The change is consequential and the current MIT licence requires care.

Before a visibility change, confirm:
1. whether Cloudflare Pages, Render, GitHub Actions and any external registry/integration can continue to access a private repository;
2. whether the GitHub plan and Actions minutes/features remain sufficient;
3. who needs repository access and what least-privilege permissions they require;
4. whether any third-party contributions or dependencies impose obligations;
5. whether the desired strategy is private proprietary software, open-source core plus proprietary service, or a dual-licence model.

If the immediate objective is to reduce further casual copying, changing the repository to private may be a useful forward-looking step after the operational checks. It is not a substitute for legal review and does not make previously distributed MIT copies disappear.

## Practical protection checklist

- [ ] Decide repository visibility after checking deployment integrations and GitHub plan implications.
- [ ] Obtain legal advice on MIT licensing, ownership, future releases and any possible relicensing.
- [ ] Review every collaborator and connected GitHub App; use least privilege.
- [ ] Enable appropriate branch protection and required checks before production merges.
- [ ] Run a full secret scan across all branches and Git history; rotate any exposed credential.
- [ ] Keep production credentials in secret stores and rotate pilot tokens periodically.
- [ ] Keep user health-related information out of free-tier model tests; document consent, retention and deletion.
- [ ] Keep original coaching content, catalogue and evaluation data versioned and attributable.
- [ ] Protect the ATENA brand and domain separately from the source-code licence.

## Actions taken in this review

- No repository visibility, licence, branch protection, secret, deployment, paid service or production setting was changed.
- This review records the current public/MIT state and the consequences to resolve before a protection change.
