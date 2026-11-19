---
pr: 540
branch: feat/531-dc-companies-projects
title: "feat(dc): data center companies and projects, linked to sites, governments and decisions"
author: jcbowyer
reviewed_at: 2026-11-17
reviewer: coordinator (read-only review subagent; every finding checked against the code and the local warehouse)
verdict: request-changes
---

# PR Review: feat(dc): data center companies and projects, linked to sites, governments and decisions

## Summary
The PR adds data center companies to the organization master, as the dated contract change on #531 asks. A seed
source (`stg_data_center_companies__org`) is unioned into the MDM chain, and a 1:1 satellite
`mdm_organization_data_center` holds the data center detail. It also adds five project marts (`data_center_project`,
`_company`, `_jurisdiction`, `_figure`, `_mention`) with enforced PK/FK contracts, a `master_org_id` on
`decision_company_mention`, `public` publication, the Neon `CIVIC_SERVING` entries and regenerated ODCS. The design
is sound: the curated seed rows carry a URL and a verbatim excerpt, conflicting figures each keep their source, and
the six companies the master already had kept their `master_org_id`. CI is green, and the local parse, compile,
pytest and ODCS checks pass. The verdict is **request-changes** for one reason. The Epoch IT-power excerpt drops
trailing zeros, so 7 of the 76 Epoch figure rows quote a number ten times smaller than the value they source
(Colossus 1: value 340, excerpt "…: 34"). That is a misquoted figure in a served table (No Fabricated Data). The
other findings should be fixed but don't block.

## Scope of Change
- Files changed: 33 (+2199 / -15; this includes 7 generated ODCS/ODPS contract files, about 750 lines)
- Areas touched: dbt_project (models, macros, seeds, contracts), packages (hosting), web_docs
- Commits:
  - a5a1f3b9 feat(dc): data center companies in the organization master, and projects with sourced figures
  - ffa20cc3 fix(dc): date a project's announcement only with the passage that dates it
  - d94822d8 chore(dc): untrack the dbt_packages symlink
- Range reviewed: `4ebef248..d94822d8`

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | pass |
| Documentation Build (Docusaurus) | pass |
| Backend Tests (Python) | pass |
| API Types (OpenAPI -> TypeScript) | pass |
| PR conventions (linked issue) | pass |
| Docker Build Test (Full Stack) | skipped (no Docker changes; not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. No keys, tokens, credentialed URLs or `.env` content in the diff.
- **Fabricated data in a served path:** no changes in `api/` or `web_app/src/`. The seeds were checked row by row:
  every company, project and figure row has a `source_url` and a `source_excerpt`, and Delta Forge 2's unsourced
  $3.2B, Brookwood and Kayvens details were left out rather than entered. **One finding:** the generated Epoch
  figure excerpts misquote the value (🔴 below).
- **Personal data:** clean. Only companies and public data center projects.
- **Destructive or bulky data changes:** clean. No deletions, no large files, and every warehouse change goes
  through dbt. (The PR notes that rebuilding `mdm_organization` drops the FKs that point at it. That is the existing
  table-swap behaviour, and the downstream rebuild puts them back.)

## Strengths
- The contract change is applied cleanly. Companies cluster into `mdm_organization` by normalized name. Locally,
  Google, Microsoft, Amazon, Meta, OpenAI and Anthropic all reused their master rows (`n_sources = 2`), and 9 new
  rows were created.
- Survivorship is handled carefully. The curated source is ranked below NCCS and locations and above AI-extracted
  rows. The type vote is broken toward `company` only on a tie, and the curated website only fills a null.
- The figure design is honest. The grain is one row per (project, metric, source, value). The project row shows a
  figure only when all its sources agree, and otherwise sets `has_conflicting_figures`. A unit test covers this.
- `announced_on` is gated on its own dated source passage (ffa20cc3).
- The intermediate layer (`int_data_center_project__*`) avoids an FK cycle between the project mart and its
  children.
- The contracts are enforced, with PK and FKs on all six tables. The Neon launch predicates scope every child table
  through `gold.data_center_project`. The `CIVIC_SERVING` test was extended, and the decision page is under
  `web_docs/docs/development/`.

## Findings

### 🔴 Blocking (Critical)

1. **`dbt_project/models/intermediate/int_data_center_project__figure.sql:43`: Epoch IT-power excerpts misquote
   the value.**
   `trim(trailing '.' from trim(trailing '0' from s.it_power_mw::numeric::text))` also strips significant zeros
   from whole numbers, because `'340'` becomes `'34'`.
   - **How it was verified:** `select trim(trailing '.' from trim(trailing '0' from 100::numeric::text))` returns
     `1`. In the locally built `gold.data_center_project_figure`, 7 of the 76 `dataset_row` figures are affected:
     Colossus 1 (340 → "34"), Anthropic Lake Mariner (210 → "21"), Microsoft Project Osmium (190 → "19"), Meta-QTS
     Hillsboro 2 and QTS Richmond 2 (180 → "18"), Meta Sarpy (80 → "8") and Microsoft-Nebius New Jersey (50 → "5").
   - **Where it shows:** the same text appears as `data_center_project.it_mw_source_excerpt` for those projects,
     and both tables are published to `public` and Neon. An excerpt that states a different number than the value
     it sources breaks No Fabricated Data ("every figure must trace to a real value").
   - **Fix:** use `trim_scale(s.it_power_mw::numeric)::text`, which the local PG 16 returns as `340` and `12.5`.
     Add a test that the excerpt ends with the value, for example
     `dbt_utils.expression_is_true: "source_kind <> 'dataset_row' or source_excerpt like '%: ' || trim_scale(value)::text"`.

### 🟡 Should fix (Important, non-blocking)

2. **`dbt_project/seeds/data_center_projects.csv:2`: Polaris Forge 1 duplicates an Epoch site.**
   The curated project "Polaris Forge 1" (Ellendale, ND, leased to CoreWeave) leaves `data_center_site_name` blank,
   so Epoch's "CoreWeave Ellendale ND" (owner CoreWeave, ND; the only Ellendale site in `gold.data_center_site`)
   becomes a second project.
   - **Why it matters:** #531 "Done when" says Epoch sites are folded in with the `data_center_site_id` FK. Right
     now the same campus has two `project_id`s, two sets of governments, and the Epoch IT-power figure is detached
     from the curated project.
   - **How it was verified:** queried `gold.data_center_site` and `gold.data_center_project`.
   - **Fix:** confirm they are the same campus, then set `data_center_site_name = CoreWeave Ellendale ND`. Applied
     Digital's release and Epoch's row both place it in Ellendale with CoreWeave. If they are not the same campus,
     say why on the decision page.

3. **`dbt_project/models/marts/data_center_project_mention.sql:39-43, 86-94`: the `company_and_place` match
   over-links passages to projects.**
   All 27 local rows are `company_and_place`, and none is `project_name`. Three problems show in the data:
   - Five passages are each linked to both Colossus 1 and Colossus 2: one company in one government means every
     project of that company matches.
   - The Google Columbus links are mostly passages that mention Google in general ("contributions from Google",
     "Amazon and Google and Meta").
   - One Google Omaha passage matched "google com" (an email or web address).
   - **Why it matters:** the evidence is verbatim, but it shows the company, not the project. A tile built on this
     table would claim a project link the passage doesn't support (CLAUDE.md, "Show the Match Evidence": "matched
     only on metadata … surface that honestly").
   - **Fix, at least one of these:**
     - add an `n_candidate_projects` / ambiguity column, or skip a `company_and_place` hit when the company has more
       than one project in that government;
     - require a project-specific term (the site's city, road or Epoch "Project" field) near the company name;
     - exclude the `\.?\s?com\M` form after the term.
   - Also document on the decision page that `company_and_place` means "names the company in the project's
     government", not "discusses the project".

4. **`dbt_project/models/marts/_schema_data_center_project.yml:418`: `data_center_project_mention.event_decision_id`
   has no FK assertion.**
   `event_decision` is partitioned with a composite PK, so the repo convention (`_schema_decision_context.yml:7-9`)
   asserts the FK with a `relationships` test. This column has no tests. The Keys rule asks for a declared FK for
   every relationship.
   - **Fix:** add `relationships: {to: ref('event_decision'), field: event_decision_id}` to `event_decision_id`,
     with `where: "record_type = 'decision'"` if needed.

### 🔵 Nits / suggestions (Minor)

5. **`dbt_project/seeds/schema.yml` (the `data_center_projects` block, from line 420): seed link columns aren't
   tested.**
   `developer_key`, `operator_key` and `tenant_key` have no `relationships` test to `data_center_companies.company_key`,
   and `data_center_site_name` has none to `data_center_site.site_name`. A typo silently drops the company link
   (`data_center_project_company` inner-joins) or silently creates a duplicate project (finding 2's failure mode).
   - **Fix:** add the four `relationships` tests (dbt skips blanks only if you add `where`; use
     `where: "developer_key <> ''"` etc.).

6. **`dbt_project/seeds/data_center_projects.csv:2-5`: the developer role is sourced by an excerpt that doesn't name
   the developer.**
   `company_source_excerpt` is shared by every role on the row.
   - For Polaris Forge 1, the `developer = Applied Digital` link is sourced by "Polaris Forge 1 is leased to
     CoreWeave, …". That passage names neither Applied Digital nor any development role, although the row's own
     `source_excerpt` does name Applied Digital.
   - For PF2, PF3 and DF1, the passage says only "the Company has leases …".
   - **Fix:** source each role separately (for example `developer_source_*` / `tenant_source_*`), or fall back to
     the main source for the developer.

7. **`dbt_project/models/staging/stg_schools__org.sql:13-16`: the empty fallback gives no signal.**
   In a warehouse that should have schools, a missing or renamed `bronze_schools_nces` now drops about 102k schools
   from `mdm_organization` with no error.
   - **Fix:** emit `{{ log("stg_schools__org: bronze_schools_nces missing; schools excluded from the org master",
     info=true) }}` (or `exceptions.warn`) in the `else` branch.
   - **Verified:** the source is absent locally, and the compiled view takes the empty branch.

8. **`dbt_project/seeds/data_center_companies.csv:13`: the "Stargate" alias maps to OpenAI only.**
   Stargate is the OpenAI, Oracle and SoftBank venture, and the row's excerpt ("OpenAI Stargate Abilene | Users:
   OpenAI") doesn't state the alias. Through it, `decision_company_mention.master_org_id` and the mention matching
   resolve "Stargate" to OpenAI alone.
   - **Fix:** drop the alias, or source it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | Branch `feat/531-…`; `Closes #531`; the issue has all four parts; the contract change is a dated comment, and the original text is untouched |
| Conventional Commits | ✅ | All 3 commits; each has the co-author trailer |
| No fabricated data | ❌ | The seeds are sourced, but the Epoch excerpts misquote 7 values (finding 1) |
| New Python in `packages/` | ✅ | Only `hosting` constant and test edits; nothing in `scripts/` |
| dbt for transformations | ✅ | All logic is in dbt, layered staging → intermediate → marts |
| Naming | ✅ | `state_code` + `state` on `data_center_project`; `website_url` in the satellite (the master's `website` column predates this PR); no `dim_`/`fact_` |
| Keys | ⚠️ | PK and FKs are enforced on all six; `data_center_project_mention.event_decision_id` lacks its relationships test (finding 4) |
| Calendar years | n/a | Only real `date` columns |
| Scope label matches filter | n/a | No UI |
| Match evidence on filtered tiles | ⚠️ | Evidence is verbatim and `<mark>`ed, but `company_and_place` evidence doesn't show the project (finding 3) |
| Docs | ✅ | `web_docs/docs/development/data-center-companies-projects.md`, kebab-case, frontmatter |
| Telemetry and logging | n/a | No FastAPI or script code |
| Tests | ⚠️ | A unit test covers figure agreement, and the #508 unit test was extended for `master_org_id`; nothing tests that an excerpt matches its value (that test would have caught finding 1) |
| Shared libraries | ✅ | `packages/hosting` and `datamodels` ODCS tests pass |

## Test Coverage
- **Tested in the PR:**
  - the dbt unit test `project_figures_shown_only_when_sources_agree`;
  - the extended `decision_company_mention` unit test (`master_org_id` by name, no alias collision);
  - unique and not_null on every PK, and accepted_values on role, basis, metric, unit and source_kind;
  - seed not_null on `source_url` and `source_excerpt`;
  - `test_neon_sync_data_center_tables.py`, extended for the six tables.
- **Run locally on `d94822d8`:**
  - `dbt parse`: OK.
  - `dbt compile` of all changed models (staging, intermediate, the six marts, `mdm_organization`,
    `decision_company_mention`): OK.
  - `dbt ls --select mdm_organization+ stg_schools__org+`: 24 downstream models.
  - `pytest packages/hosting/tests packages/datamodels/tests/test_odcs.py`: 64 passed, 3 skipped.
  - `python -m models.odcs --check`: 61 contracts current and valid.
  - `ruff check` on the changed Python: 2 errors (`io` unused, E731 lambda). Both are pre-existing on `main` in
    lines this PR doesn't touch.
  - Read-only SELECTs on the local `gold` tables confirmed findings 1 to 3.
- **Not run:** `dbt run`, `build`, `seed` and `test`. They would rebuild shared tables, so the PR's own test run is
  taken as reported.
- **Not covered:**
  - that an excerpt states its figure (finding 1);
  - that the seed link columns resolve (finding 5);
  - precision of the mention match (finding 3).

## Verdict
**request-changes.** Fix finding 1 first: quote Epoch values with `trim_scale` and add an excerpt-matches-value
test, then rebuild `int_data_center_project__figure` → `data_center_project` → `data_center_project_figure`. Findings
2 to 4 (the Polaris Forge 1 / CoreWeave Ellendale duplicate, `company_and_place` over-linking, and the missing
`event_decision` relationships test) should land in this PR or as linked `action-item` issues. Findings 5 to 8 are
optional.

## Resolution (author, 2026-11-17)

1. 🔴 Fixed: the Epoch excerpt now uses `trim_scale(value)::text` (Colossus 1 reads "…: 340"), and a data test on
   `data_center_project_figure` checks that every dataset-row excerpt ends with its value.
2. 🟡 Not folded: no source ties Epoch's "CoreWeave Ellendale ND" address to Polaris Forge 1. Logged as #544.
3. 🟡 Fixed: a company-and-place match is skipped when the company has more than one project in that government
   (Colossus 1/2) or is named as a web address ("google com"). 27 → 16 rows, all Google Columbus. The model
   documents that `company_and_place` means the company is named where the project is, not the project itself.
4. 🟡 Fixed: `relationships` test (warn) from `data_center_project_mention.event_decision_id` to `event_decision`.
5. 🔵 Fixed: `relationships` tests on the projects seed's `developer_key` / `operator_key` / `tenant_key` and
   `data_center_site_name`.
6. 🔵 Fixed: developer/operator links are sourced by a passage that names Applied Digital ("Applied Digital’s HPC
   Hosting Business designs, builds, and operates…"); the tenant gets its own `tenant_source_url` / `_excerpt`.
7. 🔵 Fixed: `stg_schools__org` logs when `bronze_schools_nces` is absent.
8. 🔵 Fixed: the "Stargate" alias is dropped from OpenAI's company row (the #508 operator seed is unchanged).
