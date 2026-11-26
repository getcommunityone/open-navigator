# pull_requests/

One review per pull request: `pr-<n>-review.md` (or `<branch-slug>-review.md` before a PR number exists).
Each file records what was checked, findings, and a YAML `verdict:` of `approve`, `approve-with-nits`, or
`request-changes`.

## How a review gets written

1. **Automated (default, #648).** On every same-repo pull request `opened` / `synchronize` / `reopened`, the
   **PR conventions** workflow runs `auto_pr_review.py` first. It scans the diff with rubric heuristics (secrets,
   credential shapes, hard-coded money in served paths), optionally adds a short Gemini summary when
   `GEMINI_API_KEY` / `GOOGLE_API_KEY` is set, and commits `pull_requests/pr-<n>-review.md` onto the head branch
   with `[skip review]` so it does not loop. Fork PRs cannot receive that push; they still fail the existence
   check until a review is committed another way.
2. **Agent / human.** `/pr-review` (`.claude/commands/pr-review.md`) against `.claude/review-rubric.md`, also run
   by `/create-pr`. A non-bot review is left alone by the auto writer.

## Enforcement

From **2026-11-22**, the same workflow’s **PR conventions** job fails when the review file is missing or has no
`verdict:` line (tool branches `dependabot/`, `renovate/`, `kaggle-results/` are exempt). Loop guards: only
review-file changes, `[skip review]` in the commit message, or tool branches skip the writer.

Agents that aren't Claude Code follow the same two prompts (see `AGENTS.md`, "Branches and pull requests").
