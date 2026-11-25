---
pr: 968
branch: docs/956-dc-sources-citations
title: "feat(data-centers): cite the hearing trackers and inventories, block the ones we may not use, feed leads from the CC BY trackers"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only, two passes) and coordinator
head_sha: see branch head (fixes in 67d4f29b and the nits commit)
verdict: approve-with-nits
---

# PR Review: cite the hearing trackers and inventories, feed leads from the CC BY trackers

## Summary

This PR cites 19 data center trackers and inventories with a dated record of each one's terms. It puts the six whose
terms forbid scraping on `BLOCKED_HOSTS`, and feeds hearing leads from the two CC BY trackers (Data Center Fights and
Siting Radar). A hearing is still shown only when the government's own page states the date with a data center word.

The first independent pass said **request-changes**. Every Blocking and Should-fix finding is fixed in `67d4f29b`, and
the second pass says **approve-with-nits**. The CI bot's auto-review (against `b13c4517`) approved before those
findings and is superseded by this file.

## Findings and their fixes

### 🔴 Blocking (both fixed)
1. **Tracker text was served.** Each tracker's topic or summary reached the card as "From the research lead".
   **Fixed:** the mart nulls `topic` for tracker leads, with a unit test. A body's name is kept, as a fact.
2. **The official-host test was loose.** Any `.us` host, `cityof*.com` and vendor hosts counted. **Fixed:** official
   now means one of:
   - a `.gov` host;
   - a locality `.us` name (`x.<state>.us`);
   - a government's own subdomain of an agenda platform (no `www.`).

   Data Center Fights' user-added records are excluded.

### 🟡 Should fix (all fixed)
- **User info in a URL:** a URL with `@` in its authority is never official.
- **Place parsing:**
  - "City of X …" stops at the first body word, case-insensitively.
  - The type word is kept ("Kansas City").
  - A "Board of …" capture is dropped.
  - The mart shows the matched jurisdiction's name.
- **Dedupe:**
  - Every lead is kept, with a `meeting_key` (counties apart from towns) and a `lead_rank`.
  - Every official URL is fetched.
  - The mart keeps one row per meeting, the verified one first.
- **Evidence:** a side is trimmed only when it was cut, so a date at the page's edge survives. Unit test added.
- **Docs:** they no longer state the #958 imports as done.
- **Run-start macro:** creates both bronze tables empty, so the served marts build before any loader has run.

### 🔵 Nits
- **Fixed:**
  - no `www.` vendor pages count as official;
  - a longer, case-insensitive body-word list;
  - only each tracker's latest file counts;
  - softened doc wording about labels.
- **Open (minor):**
  - A second date match on a page can begin mid-word (still verbatim).
  - A parish lead can't match a county jurisdiction; this predates the PR.
  - The run-start macro runs on every target, as `ensure_event_partitions` already does.

## Scans
- **Secrets:** clean. DSNs come from the environment and are never printed.
- **Fabricated data:** clean. Only verified rows are served, each quoting the official page; tracker text is not served.
- **Personal data:** none.
- **Destructive changes:** none. New bronze tables only.

## Repo rules
| Rule | Pass? |
|---|---|
| Issue first (`Closes #956`, dated contract note on the issue) | ✅ |
| New Python in `packages/` (`python -m ingestion.data_centers.load_hearing_tracker_leads`) | ✅ |
| dbt for transformations | ✅ |
| Keys (PKs/FKs on the served mart unchanged; ODCS contract regenerated) | ✅ |
| Match evidence on tiles (verbatim official text) | ✅ |
| Docs with the change | ✅ |

## Tests
- dbt on the local warehouse: 39/39, including 4 unit tests.
- pytest: 26 passed for the touched ingestion modules, 6 passed for the hearings API.
- `models.odcs --check`: current.
- Live results: 7 hearings verified, 2 of them from tracker leads (Whitley County IN, Calvert County MD).

## Verdict

**approve-with-nits**: merge when the required checks are green.
