# pull_requests/

One review per pull request, written by the `/pr-review` prompt (`.claude/commands/pr-review.md`, also run by
`/create-pr`) against `.claude/review-rubric.md`: `pr-<n>-review.md`, or `<branch-slug>-review.md` before a PR exists.
Reviews are committed with the PR's branch, so each change keeps its record: what was checked, what was found and
the verdict. Agents that aren't Claude Code follow the same two prompts (see `AGENTS.md`, "Branches and pull
requests").
