---
pr: 1439
issue: 1428
verdict: approve-with-nits
---

# PR #1439 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `fix/1428-dc-over-time-all-sites`, `Closes #1428`. The issue has all four parts.
- **Scans:** no secrets and no personal data. No Neon writes; the publish set is listed in the PR. No fabricated data:
  - every count comes from the mart or the API's SQL;
  - `listed_by` comes only from real dates (`first_seen_on`, `status_as_of`) and is labelled as an upper bound, never as an opening;
  - a site with no date at all (`none`) enters only at today.
- **Data:**
  - The PK and FK on `data_center_site_timeline` are unchanged. `appear_basis` is now `not_null`, with accepted values.
  - `listed_by` applies only when a site has neither an announced date nor an Epoch timeline. A real start date is never overridden.
  - The dbt build of the model and its tests passed (20 of 20), and the public view picks up the new columns.
- **Correctness:**
  - `PHASE_SQL` is unchanged. `build_years_sql` coalesces a `none` site to this year, so today's row totals every site.
  - The pytest suite runs the route's SQL against the real mart (national and FL). Each year's total equals the running count, and today equals every site.
  - The front end mirrors this with `enterYear(site, today)`.
  - The legend counts what the map can draw, so 9 territory sites (PR, GU, MP, VI) outside the Albers USA projection are "Not mapped". The legend states this.
  - The box summary used to add running totals across years ("8,598 dated sites"). It now boxes today's row.
- **Contract:** `appear_basis` value `first_report` is renamed `epoch_first_report`. The only consumers are the timeline utils, which are updated, and `api.types.ts` is regenerated.
- **Verification:**
  - pytest: 8 passed.
  - vitest `src/utils`: passed.
  - Playwright `over-time-all-sites.check.mjs`: 36 of 36 at Pixel 7 and 1440, national and FL.
  - The phone-fit check was run against the branch.
- **Docs:** `web_docs/docs/guides/data-stories.md` covers the bases, the coverage table and the drawing rules.

Nits (not blocking):
- The response is now 1.6 MB raw (190 KB gzipped) with all 2,379 sites. A slimmer site projection for the map could come later.
- `screenBoxes.ts` belongs to the story-boxes work. The change there is limited to which year row it reads.

No blocking findings.
