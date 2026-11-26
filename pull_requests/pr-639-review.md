---
pr: 639
branch: chore/632-site-belt-agenda-scoreboard
title: "chore(dc): site-belt agenda coverage scoreboard (#632)"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator
verdict: approve
---

# PR Review: chore(dc): site-belt agenda coverage scoreboard (#632)

## Summary

Adds a regenerable warehouse scoreboard CLI in `packages/scrapers` (`python -m scrapers.discovery.data_center_agenda_scoreboard`), unit tests, an agenda-first design doc, and a committed scoreboard report with real Neon-derived counts. The work correctly lives in `packages/` rather than `scripts/`, uses loguru, and documents that figures are warehouse-only. Required CI is green; scans found no credentials in the diff (only env var names) and no api/web_app served-path fabrication. **Approve** for merge.

## Scope of Change
- Files changed: 4 (+991 / -0)
- Areas touched: packages/scrapers, web_docs
- Commits: ef51fe40 chore(dc): site-belt agenda coverage scoreboard (#632)
- Range reviewed: merge-base..ef51fe40

## CI Status
| Check | Status |
|---|---|
| Frontend Build | pass |
| Documentation Build | pass |
| Backend Tests | pass |
| API Types | pass |
| PR conventions | pass |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: clean (env var names only)
- Fabricated data (api/web_app served paths): clean
- Personal data: clean
- Destructive/bulky data: clean

## Strengths
- Scoreboard markdown is explicitly regenerable and labeled as warehouse counts.
- Classification helpers are covered by five unit tests.

## Findings
### 🔴 Blocking (Critical)
None.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | Closes #632 |
| New Python in packages/ | Yes | CLI under scrapers.discovery |

## Test Coverage
`test_data_center_agenda_scoreboard.py` (5 tests); Backend Tests CI pass.

## Verdict
**Approve** — planning artifact and tooling with green CI and clean scans.