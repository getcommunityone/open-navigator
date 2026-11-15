---
pr: 384
branch: feat/249-pipeline-sites
title: "feat(dc): DC-4.1 data center sites from Epoch AI with status, source, and dropped sites kept"
author: coordinator (Claude Code)
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve-with-nits
---

# PR Review: DC-4.1 data center sites (#384)

## Summary
Loads Epoch AI's data center files (CC BY 4.0) into bronze, shapes them in dbt into `data_center_site` (public), and serves them on `/data-centers` with status, source credit, and dropped sites kept and labeled. It meets #249's "Done when": sites load with status and source, a dropped site stays visible, and unlicensed sources (the Brockovich map's own layers) are excluded. The code path ran end to end on local PostgreSQL with a made-up test file. Epoch's real files couldn't be fetched from the sandbox, so one dry run on a reachable machine is still needed. Approve with nits.

## Scope of Change
- Package: `ingestion.data_centers.epoch_sites` (+ tests).
- dbt: two bronze sources, `stg_epoch_data_center`, `stg_epoch_data_center_timeline`, mart `data_center_site` (enforced contract, ODCS generated), `epoch_data_centers.sql` macros, `publish_public_serving` served list.
- API: `GET /api/data-centers/sites` in `api/routes/data_centers.py` (+ tests).
- Web: Sites section on `DataCenters.tsx`, `fetchDataCenterSites`, `siteStatusLabel` (+ tests), `api.types.ts` (additions only).
- Docs: `data-center-sites.md`.

## CI Status
Checked on the head commit before merge; see the PR's Checks tab.

## Scans (secrets, fabricated data, personal data, destructive data changes)
- Secrets: none.
- Fabricated data: none in any served path. The four-site test file lives only in `/tmp` and in test strings. Status is derived only from Epoch's rows; there is no "cancelled" label, because the source has no such flag; unknown values are null ("Status not published").
- Personal data: none (sites, companies, addresses of facilities).
- Destructive changes: none. New tables; bronze inserts are `ON CONFLICT DO NOTHING`.

## Strengths
- Licensing handled honestly: the credit is on every row and the page; unlicensed layers stay out, and the reason is recorded.
- Raw-JSONB bronze plus a header check means an upstream rename fails loudly instead of quietly producing nulls.
- The scope label rule is respected: the Sites section carries its own scope and says when a city filter can't apply.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **Fixed on this branch.** A running site with a blank "Buildings operational" but IT power above zero would have shown as "under construction". It now counts as operating; the rule is in the model header and the docs.
### 🔵 Nits / suggestions (Minor)
- The column names come from Epoch's published field list, not a downloaded file. The loader's header check covers the required three; optional columns (`Owner`, `Address`, `IT power (MW)`, `Buildings operational`) would come through as null if renamed. Check them on the first real dry run.
- The loader isn't scheduled. Epoch updates roughly weekly; a weekly run keeps "no longer listed" accurate.
- The address-to-state parse covers addresses ending in a state code or name. A site whose address ends with a county or city only has no state, so it appears nationally but not under a state filter.

## Repo-Rule Compliance
| Rule | Status |
|---|---|
| Issue first, four parts, Contract before first commit (+ dated addendum) | ✅ #249 |
| Branch `<type>/<issue>-<slug>`, `Closes #249` | ✅ |
| Conventional Commits | ✅ |
| New Python in `packages/`, CLI as `python -m` | ✅ |
| Transformations in dbt; Python only for ingestion | ✅ JSONB extraction in staging |
| PK on public relation; FK where a relationship exists | ✅ PK `data_center_site_id`; no relationship (no jurisdiction in the source), recorded |
| `state_code` and `state` both | ✅ |
| No fabricated data | ✅ |
| Scope label rule | ✅ |
| Decisions written down | ✅ `data-center-sites.md` |

## Test Coverage
- API: 5 tests (scope and counts, status filter, bad status 422, missing mart, 500).
- Loader: 4 tests (BOM, blank rows, header mismatch, bronze rows, idempotent SQL).
- dbt: an end-to-end run on PostgreSQL covering all four statuses, the blank-count fallback, state parsing and confidence tags.
- Web: `siteStatusLabel` tests; `tsc` and eslint clean.
- Not covered: Epoch's real files (blocked from the sandbox).

## Verdict
**approve-with-nits.**
