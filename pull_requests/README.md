# pull_requests/

Generated PR reviews from the `/create-pr` slash command land here as
`pr-<n>-review.md` (or `<branch-slug>-review.md` for local branches).

Reviews are produced via the **superpowers** plugin's code-review skills:
`requesting-code-review` dispatches a read-only reviewer subagent over the
`BASE_SHA..HEAD_SHA` range (with this repo's CLAUDE.md rules appended to the
requirements), and `receiving-code-review` governs verification of its findings
before they are written down — only findings that survive verification are kept.
Severities map Critical → 🔴 Blocking, Important → 🟡 Should fix, Minor → 🔵 Nits.
Every review includes a mandatory secrets scan of the diff (committed keys, tokens,
passwords, credentialed URLs); any real credential is automatically 🔴 Blocking.

Files here are the latest review for that PR/branch (overwritten on re-review)
and are not committed by default.
