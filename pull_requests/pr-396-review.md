---
pr: 396
branch: chore/395-nightly-crawl-command
title: "chore(ops): add /nightly-crawl to run the crawl, rebuild and Neon publish from a Remote Control session"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: /nightly-crawl (#396)

## Summary
Adds a slash command that runs the crawl, rebuild and Neon publish in the session's own machine (WSL), and a doc on starting it from a phone with Remote Control. The steps match the real commands in the repo (the YouTube script and its defaults, the SuiteOne CLIs, the Epoch loader, the dbt selection, both Neon syncs and their exit codes). Approve.

## Scans
- Secrets: none. The command tells the agent to check variables exist without printing them.
- Fabricated data, personal data, destructive changes: none. It forbids stash/reset of uncommitted work, deleting `data/cache/`, and forcing past the size check.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The dbt selection builds upstream models too (`+model`); it's the safe choice after a crawl, but slower. Narrow it if runs get long.
- Step 3 runs for hours on a full state list; the command runs it in the background with a log, which keeps the phone session responsive.

## Verdict
**approve.**
