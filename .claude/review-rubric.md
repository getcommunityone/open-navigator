# PR review rubric (shared by /create-pr and /pr-review)

Adapted from the review flow of the health-transformation-lab-nlp repository (a read-only reviewer, verified findings
only, mandatory scans), with this repository's rules from `CLAUDE.md` and `AGENTS.md`.

## How the review runs

1. **Range.** `BASE_SHA` = merge base with `main`; `HEAD_SHA` = the branch head. Review only `BASE_SHA..HEAD_SHA`.
   Leave generated files (`web_app/src/lib/api.types.ts`, lock files, build output) out of the line counts, but scan
   them (step 2).
2. **Scans, before reading for style.** Run all four on the whole diff:
   - **Secrets:** API keys (Gemini, YouTube, OpenStates, Hugging Face), database passwords, tokens, credentialed URLs,
     `.env` content, real cookies (`eboard_cookies.json`; only `*.example` belongs in git). Any real credential is
     🔴 Blocking.
   - **Fabricated data in a served path:** made-up, placeholder or hard-coded numbers (dollar amounts, budgets,
     contributions, vote counts, statistics) in `api/` or `web_app/src/` outside tests, fixtures used as defaults, or
     fallback constants that look real (`CLAUDE.md`, "No Fabricated Data"). 🔴 Blocking. Missing data must show an
     explicit empty state. An input's placeholder hint ("Try 123 Main St") isn't data.
   - **Personal data:** a user's address, location or other personal data stored or logged when the feature only
     needs it for the moment (the "no data stored" promise), or private personal information added to the
     warehouse. 🔴 Blocking. Public records (officials, meetings, votes) are fine.
   - **Destructive or bulky data changes:** anything deleting `data/cache/`, large raw files committed (logs, parquet
     dumps, caches), or warehouse tables changed outside dbt. 🔴 Blocking for deletions, 🟡 for bulk.
3. **Reviewer.** A read-only reviewer reads the range with this rubric, `AGENTS.md` and `CLAUDE.md` as the
   requirements: a reviewer subagent (Superpowers `requesting-code-review` where installed, otherwise the matching
   specialist in `.claude/agents/`: api, data-dbt, frontend, python-packages) or, without subagents, the coordinator
   itself.
4. **Verify.** Reproduce or trace each finding in the code before writing it down (Superpowers
   `receiving-code-review` where installed). Drop what doesn't survive. Severity: Critical → 🔴 Blocking, Important
   → 🟡 Should fix, Minor → 🔵 Nit.
5. **Checks.** Read CI on `HEAD_SHA`: Frontend Build, Documentation Build, Backend Tests and API Types (required),
   and PR conventions. Run locally what CI can't show: `pytest` for each touched package and its dependents
   (`CLAUDE.md`, "Explicit Development Guidelines"), `ruff check` on changed Python, `cd web_app && npx tsc --noEmit`
   for frontend changes, and `dbt ls --select <model>+` for changed dbt models when the warehouse is reachable (say
   so when it isn't).

## Repo rules (the compliance table)

| Rule | What to check |
|---|---|
| Issue first | Branch `<type>/<issue>-<slug>`; description says `Closes #<issue>`; the issue has Problem, Done when, Contract, Read first (`AGENTS.md`); follow-ups found are their own issues |
| Conventional Commits | `<type>(<scope>): <description>` on every commit; co-author trailer when an agent wrote it |
| No fabricated data | Scan result above |
| New Python in `packages/` | Nothing new in `scripts/`; new entry points are `python -m <lib>.<module>` CLIs |
| dbt for transformations | No SQL logic or JSONB extraction in Python; medallion layers `bronze → staging → intermediate → marts` |
| Naming | `state_code` and `state` both present; `website_url`; no `dim_`/`fact_` names |
| Keys | Every model exposed in `public` declares a primary key and its foreign keys in `schema.yml` |
| Calendar years | Integer in storage from staging on; a string on the wire (`calendar_year_label()`) |
| Scope label matches filter | The label, the URL parameters and the API query move together; filters carry across navigation |
| Match evidence on filtered tiles | A real highlighted passage (`ts_headline` → `highlightSnippet`), never invented; no `dangerouslySetInnerHTML` |
| Docs | New docs under `web_docs/docs/`, kebab-case, frontmatter; no new root `.md` beyond README, LICENSE, CONTRIBUTING, AGENTS.md, CLAUDE.md |
| Telemetry and logging | FastAPI work traced with OpenTelemetry spans; scripts and packages log with `loguru` |
| Tests | Every behaviour change has a test that would have failed before it; a bug fix has a regression test |
| Shared libraries | A change in `packages/` ran that package's tests and its dependents' |

## Output

Write `pull_requests/pr-<n>-review.md` (or `pull_requests/<branch-slug>-review.md` before a PR exists), overwriting
any earlier review of the same PR:

```markdown
---
pr: <n>
branch: <branch>
title: "<PR title>"
author: <login>
reviewed_at: <YYYY-MM-DD>
reviewer: <who reviewed: subagent and coordinator, or coordinator>
verdict: approve | approve-with-nits | request-changes
---

# PR Review: <title>

## Summary
<3-6 sentences: what it does, whether it works, the verdict and why>

## Scope of Change
- Files changed: N (+A / -D, excluding generated files)
- Areas touched: api / web_app / web_docs / dbt_project / packages / ci / agents
- Commits: <sha> <subject>, one per line
- Range reviewed: `BASE..HEAD`

## CI Status
| Check | Status |
|---|---|

## Scans (secrets, fabricated data, personal data, destructive data changes)
<each scan: "clean" or the findings>

## Strengths

## Findings
### 🔴 Blocking (Critical)
### 🟡 Should fix (Important, non-blocking)
### 🔵 Nits / suggestions (Minor)
<each: file:line, what's wrong, how it was verified, the fix>

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|

## Test Coverage
<what's tested, what isn't, what was run locally>

## Verdict
<approve / approve-with-nits / request-changes, and what must change first>
```

Commit the review file to the PR's branch so the record stays in git. Don't post it to GitHub as a comment unless
asked. It must pass the same scans: no secrets or personal data in it.
