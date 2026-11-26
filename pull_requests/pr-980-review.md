---
pr: 980
branch: feat/958-dc-facility-inventories
title: "feat(data-centers): import the open data center inventories"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: general-purpose subagent (read-only) and coordinator
head_sha: see branch head
verdict: approve-with-nits
---

# PR Review: import the open data center inventories

## Summary

Closes #958. The US Data Center Registry's data centers join `data_center_site`, each credited on its row. A registry
record merges with an Epoch site only on an equal normalised name in the same state, one-to-one.
`data_center_site_source` keeps every source record. Public Evidence Project records land in
`data_center_public_record` (gold) with their government URLs. The greencalculus figures stay in staging.

The independent pass said **request-changes**. Every Blocking and Should-fix finding is fixed on the branch. The
reviewer could not run dbt; the coordinator did, on the local warehouse.

## Findings and their fixes

### 🔴 Blocking (fixed)
1. **Two Python consumers read `public.data_center_site` directly.** `survey_meeting_sources.data_center_sites()` and
   `platforms/discover.py` (`dc_states`) would have taken about 2,283 more sites. **Fixed:** both read
   `source = 'epoch'`; widening is #979.

### 🟡 Should fix (fixed)
- **Deploy order:** an API deployed before `data_center_site` gains its new columns answers with an empty "not loaded"
  list, not a 500 (`UndefinedColumnError` is handled). Tested.
- **Name normalisation:** punctuation and runs of spaces are dropped before the type words ("Data-Center",
  "Data  Center"). Unit test case added. On real data the matches are unchanged (24).
- **Truncated download:** the loader refuses a file with fewer than half the records still listed (`--min-ratio`,
  `--force`). Tested.

### 🔵 Nits
- **Fixed:**
  - the recency test reads Epoch rows only;
  - the `last_seen_on` / `is_listed` descriptions name the site's own source;
  - the UI names only the sources present in the rows (`siteSourcesText`), and the hard-coded "about 2,300" is gone;
  - the city-filter reason is corrected.
- **Open:** the status mapping matches exact lower-cased words; an unknown word shows as "status not published",
  which is honest.

## Scans
- Secrets: clean. DSNs come from the environment and are never printed.
- Fabricated data: clean. Every site row carries its own source's credit and URL, and no count is invented.
- Personal data: none.
- Destructive changes: none. New bronze tables; the `data_center_site` PK is unchanged.

## Tests
- **dbt on the local warehouse:** the build of the new models plus `data_center_site+` passed (including the unit
  tests). Every downstream table that reads sites kept its row count; `data_center_project_mention` (16 → 17) changed
  because its meeting inputs changed.
- **pytest:** 13 passed (loader and sites API). ruff is clean on the changed files; `discover.py` has older findings.
- **Frontend:** vitest 385; `tsc` and eslint clean.
- **Contracts:** `models.odcs --check` current.

## Verdict

**approve-with-nits**: merge when the required checks are green.
