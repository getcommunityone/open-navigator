---
pr: 320
branch: fix/252-unsupported-platform-gap
title: "fix(scrapers): report a meeting platform with no adapter as a gap, not no meetings"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve-with-nits
---

# PR Review: fix(scrapers): report a meeting platform with no adapter as a gap, not no meetings

## Summary

`get_scraper_class()` returned `None` for every platform, and both helpers pointed unknown platforms at a
`GenericScraper` that doesn't exist. So unsupported councils looked like councils with no meetings. The PR makes
`get_scraper_class()` defer to `ingestion.meetings.adapter_for()` and makes `get_platform_capabilities()` raise for
platforms it doesn't describe. The discovery run now logs `coverage_report()` and counts platforms without an adapter
in its summary CSV. Closes #252. Approve, with one nit.

## Scope of Change

- Files changed: 3 (`platform_detector.py`, `comprehensive_discovery_pipeline.py`, new test file)
- Areas touched: packages (scrapers)
- Commits: 61e516fa fix(scrapers): report a meeting platform with no adapter as a gap, not no meetings

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: none. The new CSV column is a count computed from detected platforms, not a stand-in value.
- Personal data: none.
- Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- `platform_detector.py`: the capabilities table still lists `scraper_class` strings for Legistar, Granicus and
  CivicPlus that point to modules that don't exist. They're kept because `scripts/examples/integration_demo.py`
  prints them. When that demo is ported off `scripts/`, the key can name the registered adapter instead.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #252 has all four parts and its Attributes table (epic #235, story #242), repeated in the PR. The two new names are recorded as a dated line on the issue |
| Conventional Commits | Yes | `fix(scrapers): ...` with the co-author trailer |
| New Python in `packages/` | Yes | Library changes only; nothing added to `scripts/` |
| Tests | Yes | All 4 new tests failed before the change and pass after |
| Shared libraries | Yes | The meeting-model tests (15) and the root test importing these modules pass |

## Verdict

Approve with one nit, once the required checks are green.
