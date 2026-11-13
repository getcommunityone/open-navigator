---
description: Check the branch, open a PR against main that closes its issue, and review it with the shared rubric
argument-hint: "[title] (default: from the commits)"
---

Open a pull request for the current branch, then review it. Follow `AGENTS.md` and `.claude/review-rubric.md`.

## 1. Pre-flight (stop and report if any fails)

- Not on `main`; the working tree is clean; the branch is pushed (`git push -u origin <branch>`).
- **Issue first** (`AGENTS.md`): the work has an issue with the four parts (Problem, Done when, Contract, Read
  first). If there is none, search open issues, then open one with the GitHub tools before going on.
- The branch is `<type>/<issue>-<slug>`. If not, rename it (`git branch -m <type>/<issue>-<slug>`), push the new
  name, and delete the old remote branch only if no PR uses it.
- `git fetch origin main` and merge it in if the branch is behind (merge, don't rebase a branch others may use).
- Run the rubric's four scans (secrets, fabricated data in a served path, personal data, destructive data changes)
  on `origin/main..HEAD`. Any hit stops here: fix it first.
- Run the checks for the areas touched: `pytest` for each changed package and its dependents; `ruff check` on
  changed Python; `cd web_app && npx tsc --noEmit && npm run build` for frontend changes; `cd web_docs && npm run
  build` for docs; `dbt ls --select <model>+` for changed dbt models when the warehouse is reachable.

## 2. Open the PR

Title: `$ARGUMENTS`, or a Conventional Commit summary of the commits (`<type>(<scope>): <description>`). Body:

```markdown
Closes #<issue>

## Why
<the problem, in a few lines>

## What changes
<bullets by area: what and why>

## Verification
- <commands run and their results>
- <what wasn't run and why>

## Not in this PR
- <follow-ups, each with its own issue number>
```

Use `Refs #<issue>` instead of `Closes` when the PR is one part of a larger issue that stays open. End the body
with the attribution lines the session asks for. Create it with the GitHub tools.

## 3. Review it

Run the `/pr-review` flow on the new PR number, write `pull_requests/pr-<n>-review.md`, and commit it to the PR's
branch. If the verdict is request-changes, fix the 🔴 findings on the branch, push, and review again.

## 4. Merge

Report the PR link and the verdict. Merge only when the user asks, every required check (Frontend Build,
Documentation Build, Backend Tests, API Types) is green on the latest commit, and the verdict isn't
request-changes. Squash-merge (`CLAUDE.md`, "Branch & PR Workflow").
