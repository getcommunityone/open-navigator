# `scripts/datasources/` Reconciliation Report

_Generated 2026-05-28. Purpose: determine which `scripts/datasources/<source>/`
trees are safe to retire now that the core-lib refactor ported sources into
`packages/ingestion/src/ingestion/`._

## Method

For each source that exists in **both** `packages/ingestion` and
`scripts/datasources`, we measured:

1. **LOC** still living under `scripts/datasources/<source>/`.
2. **Live code dependencies** — actual `from/import scripts.datasources.<source>`
   statements in `packages/`, `api/`, `pipeline/`, `agents/`, `tests/`, and
   shell/Makefile entrypoints that invoke the scripts directly.

Path mentions inside docstrings / `.md` / `.sql` comments (provenance notes)
were treated as **noise**, not dependencies — the already-shimmed `bls` and
`tpc` set that baseline (they each show 1–2 such mentions and nothing more).

## Headline

This is **not** simply "cleanup was skipped." For several sources the port is
**incomplete**: the new `packages/ingestion/<source>` module exists, but live
`api/` / `pipeline/` code — and in one case the new package itself — still
imports the old `scripts/` implementation. Those cannot be archived without
finishing the port.

---

## Category A — DONE: migrated to the new `packages/scrapers` library

These were **LAND-ported but not FETCH-ported**: the `ingestion.<source>` module
reads a `data/cache/<source>/` that a **scraper** still living in `scripts/`
produced. Web-crawling (httpx / BeautifulSoup / Playwright) does not fit the
`DataSourcePipeline` cache->bronze contract, so per the project decision the
scrapers moved into a new workspace package **`packages/scrapers`** (`scrapers.<source>`),
not into `archive/`. The `scripts/datasources/<source>/` trees are now empty.

| source | scraper now at | external importer repointed |
|---|---|---|
| ballotpedia | `scrapers.ballotpedia` | `jurisdiction_pilot/county_municipality_websites.py` → `scrapers.ballotpedia` |
| dot | `scrapers.dot` | — |
| google_civic | `scrapers.google_civic` | — |
| leagueofcities | `scrapers.leagueofcities` | (intra-source only) |
| naco | `scrapers.naco` | runner → `packages/scrapers/scripts/run_naco.sh` |
| uscm | `scrapers.uscm` | `vendorsearch/vendor_meeting_portal_search.py` → `scrapers.uscm` |

All migrated modules import cleanly; ingestion docstrings updated to the
`scrapers.<source>` (FETCH) + `ingestion.<source>` (LAND) two-step.

### Category A.2 — renamed ports also migrated (per maintainer correction)

Two sources mis-classified as "never ported" in the first pass were actually
**ported under a different package name**. Their scrapers were migrated too:

| scripts source | LAND ported to | scraper now at |
|---|---|---|
| `parcels` | `ingestion.arcgis` (`data/cache/parcels` → `bronze.bronze_addresses`) | `scrapers.parcels` |
| `powerbi_ballot_measures` | `ingestion.ncls` (`data/cache/ncls` → `bronze.bronze_ballot_measures_powerbi`) | `scrapers.powerbi_ballot_measures` |

Note: `scrapers.parcels.batch_state_parcels` was a combined FETCH+LAND
orchestrator; its inline `load_csv_to_bronze` (now ported to
`ingestion.arcgis.addresses`) was removed — it is FETCH/extract-only now and
raises a clear pointer to `python -m ingestion.arcgis.addresses` if invoked
with loading enabled. **TODO:** add a thin LAND adapter if the per-county batch
load is still wanted in one command.

---

## Category B — Port INCOMPLETE, do NOT archive yet

Live code still depends on the `scripts/` version. Finish the port (move the
imported symbols into `packages/ingestion`, repoint callers) before retiring.

| source | blocking dependency |
|---|---|
| **nces** | `packages/ingestion/.../nces/school_districts.py` imports `scripts.datasources.nces.download_nces.NCESSchoolDistrictIngestion` — the *new* module wraps the *old* one |
| **irs** | `api/app.py`, `api/main.py`, `pipeline/create_nonprofits_gold_tables.py` import `scripts.datasources.irs.nonprofit_discovery.NonprofitDiscovery` |
| **youtube** | `api/routes/batch_jobs.py` imports many `api.batch_jobs.batch_job_*` modules; 17 test files import youtube scripts (18,450 LOC — largest) |
| **openstates** | `pipeline/create_contacts_gold_tables.py` imports `scripts.datasources.openstates.openstates_sources`; several `.sh` runners + tests |
| **census** | operator entrypoint `scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh` invokes `load_census_gazetteer.py` |
| **fec** | `scripts/datasources/fec/run_bulk_download.sh` invokes `load_fec_bulk.py` |
| **wikidata** | `scripts/deployment/neon/run_jurisdiction_id_migration.sh` invokes `materialize_bronze_jurisdictions_wikidata_tables.py` |

---

## Category C — Never ported, never archived (separate triage)

`scripts/datasources/` subdirs with no `packages/ingestion` counterpart:

- **Load-bearing** (live `api/` + tests import them, despite no package):
  `jurisdictions` (`api/routes/jurisdiction_mapping.py` + tests),
  `jurisdiction_pilot` (many tests).
- **Renamed ports** (LAND lives in `packages/ingestion` under a different name;
  scrapers migrated in Category A.2 above): `parcels` → `ingestion.arcgis`,
  `powerbi_ballot_measures` → `ingestion.ncls`.
- **Still to triage** (no live refs found; may yet be renamed ports —
  maintainer to confirm): `cityscrapers`, `data_gov`, `dbpedia`,
  `google_data_commons`, `govwebsites`, `grants_gov`, `ma_pilot`,
  `meetingbank`, `netronline`, `social_media`, `vendorsearch`, `voter_data`.

Caveat learned this pass: "no same-name `packages/ingestion` dir" does **not**
mean "never ported" — match by cache dir / bronze table, not by name. The only
`ingestion` modules with no same-name scripts dir are `arcgis`, `everyorg`,
`ncls`, `ntee`, `wikimedia`; of those, `arcgis`↔`parcels` and `ncls`↔`powerbi_ballot_measures`
are the Category-C renames, while `everyorg` (HuggingFace parquet), `wikimedia`
(`scripts/wikimedia/`), and `ntee` (already archived) do not come from a
remaining Category-C dir.

---

## Already clean (for reference)

- **Thin shims** (correct end state): `bls` (22 LOC), `tpc` (25 LOC).
- **Fully removed** from `scripts/`: `gsa`, `hifld`, `hud`, `nccs`, `osf`,
  `wikicommons`.

## On `archive/`

Only 12 sources have an `archive/datasources/<source>/` entry, and several
(`census`, `fec`, `nccs`, `nces`, `wikidata`) **also** still have a `scripts/`
copy — so "archived" did not imply "removed from scripts". Archiving was
applied ad hoc rather than as the closing step of each port.
