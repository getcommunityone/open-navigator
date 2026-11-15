---
description: Review a PR or branch against this repo's rules and write pull_requests/pr-<n>-review.md
argument-hint: "[PR number | branch] (default: current branch)"
---

Review `$ARGUMENTS` (a PR number, a branch, or empty for the current branch) using `.claude/review-rubric.md`. Read
the rubric first and follow it exactly.

1. Resolve the target. For a PR number, read it with the GitHub tools: title, author, base, head SHA, check runs and
   the linked issue. For a branch, use `git merge-base origin/main <branch>` as `BASE_SHA`.
2. Run the four scans (secrets, fabricated data in a served path, personal data, destructive data changes) on the
   full diff.
3. Read the range with a read-only reviewer (a subagent: Superpowers `requesting-code-review` where installed,
   otherwise the specialist in `.claude/agents/` for the area touched), with the rubric, `AGENTS.md` and `CLAUDE.md`
   as the requirements. Then verify each finding against the code. Keep only verified findings.
4. Run the local checks for the areas touched (rubric, step 5) and read CI on the head commit.
5. Write `pull_requests/pr-<n>-review.md` in the rubric's format. Print the verdict, the count per severity and the
   path. Don't post to GitHub unless asked.
