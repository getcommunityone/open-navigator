---
pr: 1226
branch: fix/1221-search-org-types
title: "fix(search): search pickers offer Organizations with real sub-types, Places and Grant Opportunities"
author: johncbowyer
reviewed_at: 2026-11-26
reviewer: read-only reviewer subagent (general-purpose) and coordinator
verdict: approve
---

# PR Review: fix(search): search pickers offer Organizations with real sub-types, Places and Grant Opportunities

## Summary
Organization search used to inner-join `mdm_organization_nonprofit`, so "Organizations" could only return nonprofits, and the home picker labelled it "Nonprofits". This PR left-joins the satellite and returns every searchable `mdm_organization.org_type`. It adds a whitelisted `?org_type=` sub-type filter and a `facets=org_type` facet with real counts, and drives the home picker and /search from one shared category list. Places and Grant Opportunities become selectable. The private-trust `other` type is excluded by design. The reviewer found three Important and four Minor issues. All seven are fixed in `feb97f26` and pinned by tests, and the UI was re-verified in Playwright at both sizes. Verdict: approve.

## Scope of Change
- Files changed: 9 (+1,167 / -137 incl. the follow-up commit; no generated files)
- Areas touched: api / web_app / web_docs / dbt_project
- Commits:
  - 2878e148 fix(search): search pickers offer Organizations with real sub-types, Places and Grant Opportunities
  - feb97f26 fix(search): gate the org facet on surviving filters and keep the pager reachable
- Range reviewed: `0589f029..feb97f26`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success on 2878e148; re-run pending on feb97f26 |
| Documentation Build (Docusaurus) | success on 2878e148; re-run pending on feb97f26 |
| Backend Tests (Python) | success on 2878e148; re-run pending on feb97f26 |
| API Types (OpenAPI -> TypeScript) | success on 2878e148; re-run pending on feb97f26 |
| PR conventions | success |
| Docker Build Test | skipped (no Docker changes; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. The worktree `.env` copy is gitignored and not committed.
- **Fabricated data:** clean. Every count comes from a SQL COUNT. On a facet timeout the facet is omitted and the UI shows no badge. No fallback constants, and fixtures exist only in tests.
- **Personal data and privacy:** clean, and stronger than before. `org_type = 'other'` (39,787 rows) is excluded from search and facets because sampled rows are private family and living trusts from property records. Tests pin the exclusion. No new storage or logging of user data.
- **Destructive or bulky data changes:** clean. The dbt change only adds an index through the `indexes` config. No warehouse writes were made outside dbt; the live index will land on the next build.

## Strengths
- The org-type vocabulary maps to static SQL predicates, and unknown values return 400. The values are whitelisted, so no SQL can be injected.
- One `_org_filter_where` serves the count and the facet, so totals and facets agree.
- The URL is the authority for the sub-type (`?org_type=`). The chip, tab, pager and API query all read it, which satisfies the scope-label rule.
- The catch-all `except Exception` no longer turns 4xx into 500, which also fixes unknown `cause_id` (#578's intent).
- Rare sub-type browse goes from ~6s to ~0.4s with a planner fence, until the new `(org_type, org_name_norm)` index lands.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All three are fixed in feb97f26:
1. `api/routes/search.py`: the facet ran, and overwrote the org total, even after a topic, cause or question filter had dropped `organizations`. The reviewer reproduced it with stubs (`filters.types=['decisions']` while `type_totals.organizations=999999`). Fix: the facet task now re-checks `'organizations' in requested_types` after the narrowing. Test: `test_facet_skipped_when_cause_filter_drops_organizations`.
2. `api/routes/search.py`: with a text query, the exact facet total offered pager pages beyond `ORG_CANDIDATE_CAP` that could never load. Fix: the pager total is the exact total in browse mode and `min(exact, ORG_CANDIDATE_CAP)` with `q`. The full count is returned separately as `organizations_total`. Tests: `test_text_query_keeps_reachable_pager_total` and `test_text_query_small_match_set_gets_exact_pager_total`.
3. The cold facet ran concurrently in two calls. Verified: the /search active-tab call only starts after the tab-counts call returns, because its tab comes from that response, so its facet is a cache hit. Home now runs the cheap facet call before the heavy all-types call. Timeouts are cached for 60s.

### 🔵 Nits / suggestions (Minor)
All four are fixed in feb97f26:
4. `UnifiedSearch.tsx`: the chip and `org_type` outlived an unticked Organizations type. They are now ignored unless Organizations is selected. Verified in Playwright: `/search?types=decisions&org_type=church` shows no chip.
5. Tests did not pin the endpoint wiring. Endpoint tests were added for the override, the clamp, timeout omission, the cause and ein skips, the unknown `cause_id` 400 and the `jurisdiction_id` count.
6. `HomeV9.tsx`: sub-type rows were indented only visually. They now carry `aria-label="Organizations: <sub-type>[, count]"`.
7. Facet timeouts were not cached. They now get a 60s negative cache (`test_facet_timeout_is_negatively_cached`).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #1221 has all four parts; branch `fix/1221-search-org-types`; `Closes #1221`; follow-ups filed as #1225 and #1227 (action-item) |
| Conventional Commits | Yes | Both commits carry the co-author trailer |
| No fabricated data | Yes | See scans |
| New Python in `packages/` | N/A | API route changes only |
| dbt for transformations | Yes | No SQL logic moved into Python; the index goes through dbt config |
| Naming | Yes | `state_code` and `state` unchanged |
| Keys | N/A | No model or column change; `dbt ls --select mdm_organization+` lists 33 downstream models, none affected |
| Calendar years | N/A | |
| Scope label matches filter | Yes | Chip, tab and pager name the sub-type, read from the URL; a filter that applies to nothing is hidden |
| Match evidence on filtered tiles | N/A | Org name FTS, unchanged |
| Docs | Yes | `web_docs/docs/guides/unified-search.md` updated in the same PR |
| Telemetry and logging | Yes | New spans `search.count_organization_types` and org_types attributes; loguru |
| Tests | Yes | 23 new tests in `tests/test_api_search_org_types.py`; `searchCategories.test.ts` |
| Shared libraries | N/A | No `packages/` change |

## Test Coverage
- Run locally: `pytest tests/test_api_search_org_types.py tests/test_api_cause_id_resolve.py tests/test_api_topics.py` (46 passed); `npx tsc --noEmit` clean; `npx vitest run` (684 passed); `npm run build` (web_app) and the docs build both pass. Ruff shows no new rule categories beyond the file's existing `Optional`/`List` style.
- Live checks against the local warehouse (worktree API on :8011): every `org_type` returns rows and real counts. Rare-type browse takes 0.4s in SQL and about 1.4s end to end.
- Playwright (own Vite on :5199) at 1440x900 and on iPhone 13, for "health":
  - Home picker counts: Organizations 38,381; Nonprofits 37,194; Foundations 557; Places of worship 168; Government bodies 173; Companies & businesses 7; Healthcare 837; Schools & education 2; Political groups 0.
  - Picking a sub-type goes to `/search?...&org_type=church`, where the pager reads "Showing 1–20 of 168 places of worship".
- Not covered: the non-org home counts depend on the all-types call, which takes about 20s on a common word locally, the same as on main. Tracked in #1225.

## Verdict
**approve.** Nothing is blocking, and all Important and Minor findings are fixed and tested. Merge once required CI is green on feb97f26 (or the review commit on top of it).
