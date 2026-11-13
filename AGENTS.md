# AGENTS.md

Rules for every coding agent working in this repository (Claude Code, Codex, Cursor, Copilot and others), and for
people too. `CLAUDE.md` imports this file. Read `CLAUDE.md` as well: it holds the architecture, data, UX,
documentation and commit rules, and they apply to every agent.

## Issues first: log the work before you start

Every change starts from a GitHub issue, and agents open it themselves. Don't wait to be asked.

1. **Search open issues first.** If one already covers the work, use it. If not, open one before the first commit.
2. **Title:** `<type>(<scope>): <what changes>`, in the Conventional Commit style used for commits
   (for example `fix(census): Connecticut counties render blank on the county map`).
3. **Labels:** `bug`, `enhancement`, `documentation`, or the feedback labels (`ux-friction`, `copy/content`,
   `feature-request`, `validated`). Follow-ups get `action-item`.
4. **One issue, one pull request.** A larger story is split into issues, and each PR closes one.

## What an issue says

Write all four parts, as headings, before the first commit. The template is `.github/ISSUE_TEMPLATE/work-item.md`.

- **Problem:** what is wrong or missing, and who it affects, with the evidence linked (a failing test, a log line,
  a screenshot, a feedback issue).
- **Done when:** one line per check a test or reviewer will make.
- **Contract:** every name a test or another layer will use that isn't in the repository yet. For an API, that's
  the path, parameters and response fields. For data, it's the dbt model or table, its grain (one row per what), its
  typed columns, its primary key and its foreign keys (see `CLAUDE.md`, "Data Pipeline Standards"). For the UI, it's
  the route and the URL parameters it reads.
- **Read first:** the files to change, and the rules and docs that govern them.

If a name has to change later, add a dated line to the issue. Never rewrite the original text: it records what was
asked.

## Log what you find, as you go

- **Follow-ups become issues, not notes.** Anything out of scope that you notice (a bug, a missing test, a stale doc)
  gets its own issue, labelled `action-item`, with the four parts and the evidence. Link it from your PR. Never leave
  it only in a TODO comment or a line of PR text.
- **Failures become issues.** When CI, a data load or a run fails for a reason your change doesn't fix, open a
  `bug` issue with the failing command, the error line and where it ran. Then carry on with your own work.
- **Feedback becomes issues.** A reviewer's or user's feedback gets one issue per concrete item (as #137 to #151
  were), each linked to the feedback issue it came from.
- **Decisions are written down.** A choice and its reason go in a page under `web_docs/docs/development/`, linked
  from the issue. Never leave a decision only in an issue or PR thread.

## Branches and pull requests

- **Branch:** `<type>/<issue>-<slug>`, for example `fix/71-ct-county-map`. The type is a Conventional Commit type
  (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`, `build`, `revert`), then the issue number, then
  a lowercase slug of at most 40 characters. Branches a tool names (`dependabot/*`, `renovate/*`) stay as they are.
- **Pull request:** the description says `Closes #<issue>` (or `Refs #<issue>` for one part of a larger issue), so
  merging closes it.
- **The `PR conventions` check** (`.github/scripts/pr_conventions.py`) enforces both on every pull request opened from
  November 14, 2026. It also checks that the linked issue has the four parts.
- Everything in `CLAUDE.md`, "Branch & PR Workflow" still applies: never push to `main`, never force-push, required
  checks green before merge.
