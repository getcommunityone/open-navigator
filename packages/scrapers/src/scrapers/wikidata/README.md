# Wikidata Data Scripts

Scripts for querying Wikidata (WDQS), enriching Open Navigator bronze tables, and validating YouTube channels.

> ## DECOMPOSED (2026-05): `load_jurisdictions_wikidata.py` no longer runs here
>
> The 4,159-line `load_jurisdictions_wikidata.py` monolith was an
> **enrichment** job (live WDQS/SPARQL + `wbgetentities` -> UPDATE pre-seeded
> `bronze.bronze_jurisdictions_*_wikidata` rows). It has been split into clean
> layers; the happy path is now **FETCH (downloader) + `dbt build`**:
>
> | Layer | Where it lives now |
> |-------|--------------------|
> | **FETCH** — WDQS/SPARQL GET + `wbgetentities` GET, JSON cache to `data/cache/wikidata/<usps>/` | `packages/ingestion/src/ingestion/wikidata/download.py` (`core_lib.http.BaseAsyncClient`). Run `python -m ingestion.wikidata.download --states AL,GA --types county,city`. |
> | **SEED** — copy census `bronze_jurisdictions_*` into the `*_wikidata` base rows | dbt `stg_wikidata__jurisdiction_{counties,municipalities,school_districts}` |
> | **APPLY** — UPDATE `*_wikidata` from cached enrichment, keyed on geoid (now a JOIN) | dbt `stg_wikidata__enrichment` + `int_wikidata__jurisdictions_enriched` |
>
> There is **no clean raw-INSERT LAND** layer — Wikidata was always
> UPDATE-enrichment on pre-seeded census rows, so SEED + APPLY together are the
> land+derive.
>
> The monolith was archived to
> `archive/datasources/wikidata/load_jurisdictions_wikidata.py`. The file at
> this path is now a **thin deprecated shim** that re-exports the irreducible
> helpers (so the scrapers below still import them). Do **not** run its old CLI.
>
> **Still scrapers/utilities here (NOT translatable to dbt — flagged):**
> `hydrate_municipality_websites_from_wikidata.py`,
> `hydrate_county_websites_from_wikidata.py` (live `wbgetentities` hydration of
> QID-but-no-website rows, resume-driven), `discover_municipality_website_gaps.py`
> (Postgres gap discovery), `geography_qid_cache.py` / `parquet_qid_lookup.py`
> (fuzzy / identifier literal->QID resolution), `wikidata_entity_search.py`
> (`wbsearchentities` fuzzy county recovery), and the archived
> `CheckpointManager` / county-gap discovery / bespoke WDQS quota client.
>
> **NEEDS-HUMAN (dbt build):** a small bronze cache-loader
> (`data/cache/wikidata/*.json` -> `bronze.bronze_jurisdiction_wikidata_enrichment`,
> analogous to `ingestion.gsa.domains`) must land before
> `stg_wikidata__enrichment` / `int_wikidata__jurisdictions_enriched` can build;
> the seed staging models build independently.

## Caching (important)

| Layer | What it is |
|-------|------------|
| **JSON files** | `data/cache/wikidata/sparql_<sha256>.json` — keyed by **WDQS endpoint URL + SPARQL body** (SHA-256), TTL `WIKIDATA_CACHE_TTL_SECONDS` (see `wikidata_integration.py`). Not Postgres. |
| **`geography_qid_mapping_v1.json`** | Under `<WIKIDATA_CACHE_DIR>`: incremental literal (FIPS/GNIS/NCES…) → Wikidata Q-id map used when `WIKIDATA_HYBRID_ENRICH=1`. Grows across runs so WDQS stays on thin mapping queries while `wbgetentities` fills claims; optionally warmed from Postgres via `WIKIDATA_QID_CACHE_WARM_DB` (see `geography_qid_cache.py`). |
| **Bronze `*_wikidata` tables** | The durable enriched dataset. **Without** `WIKIDATA_INCREMENTAL_MERGE`, each run **deleted** per-state rows and re-seeded from Census, which forced repeat WDQS traffic even when QIDs were already known. |

### Be nice to `query.wikidata.org` and finish faster today

1. **Incremental merge (strongly recommended for reruns):** set `WIKIDATA_INCREMENTAL_MERGE=1` or pass `--incremental-merge`. Seeding **merges** new Census rows into `*_wikidata` and **keeps** existing `wikidata_id` values; WDQS runs **only** for rows where `wikidata_id` is still NULL (and chunks are restricted to those GEOIDs).
2. **Hybrid mode (when SPARQL is too heavy):** `WIKIDATA_HYBRID_ENRICH=1` uses WDQS only for **identifier → Q-id** rows, then **Wikibase `wbgetentities`** (or optional Pywikibot when `WIKIDATA_ENRICH_USE_PYWIKIBOT=1`) for full claims. Mappings accumulate in `geography_qid_mapping_v1.json` and can be preloaded from Postgres with `WIKIDATA_QID_CACHE_WARM_DB` (default on).
3. **US state row (`state` task):** uses **`wbgetentities`** on the fixed Q-id from `STATE_MAP` (same JSON bundle as [`Special:EntityData/{Q}.json`](https://www.wikidata.org/wiki/Special:EntityData/Q173.json)), plus a tiny second batch for English labels on referenced items (capital, governor, etc.). Avoids WDQS entirely unless `WIKIDATA_STATE_LEGACY_SPARQL=1`. Pywikibot is optional here and buys little, since reads are already plain entity JSON.
4. **File cache:** raise `WIKIDATA_CACHE_TTL_SECONDS` (e.g. 30 days) if you rerun the same queries.
5. **Throttle:** default `WIKIDATA_THROTTLE_SECONDS=6` — increase if you still see 429s (e.g. `8`–`10`).
6. **429 Retry-After:** `WIKIDATA_RETRY_AFTER_MAX_SECONDS` (default `120` in `wikidata_integration.py`) caps post-429 sleep (WDQS often sends Retry-After in the hundreds of seconds). **`≤0` is treated as `120`** so bulk discovery does not stall on ~1000s sleeps; set **`90–180`** explicitly if you want a different cap. **`WIKIDATA_HTTPS_PROXY` / `WIKIDATA_HTTP_PROXY`** optionally send WDQS + `w/api.php` through SOCKS5 (e.g. `socks5://127.0.0.1:1080` forwarded from WARP-in-Docker).
7. **May 2025 WDQS split + quotas:** Wikidata separated the SPARQL service into **[main (`query.wikidata.org`) vs scholarly (`query-scholarly.wikidata.org`)](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/WDQS_graph_split)** — jurisdiction loaders use **main** by default (`WIKIDATA_SPARQL_GRAPH=main` or explicit `WIKIDATA_SPARQL_ENDPOINT`). The client also **serializes WDQS**, uses **rolling time/error budgets**, and switches to **POST** for oversized queries (`WIKIDATA_SPARQL_MAX_GET_QUERY_CHARS`) to align with Wikimedia’s per–(IP, User-Agent) limits and reduce **502** chains.

```bash
WIKIDATA_INCREMENTAL_MERGE=1 WIKIDATA_THROTTLE_SECONDS=8 \
  .venv/bin/python packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py --states AL --types county,city
```

## Bronze tables that hold Wikidata (or Wikidata-derived) data

### Jurisdiction enrichment (`bronze.bronze_jurisdictions_*_wikidata`)

These mirror Census gazetteer rows for a state and add Wikidata entity metadata (QID, websites, social URLs, YouTube, population, etc.). Rows are **seeded from the base gazetteer table**, then enriched from Wikidata via **WDQS** and/or the **Wikibase API** (e.g. `wbgetentities` for known Q-ids, including default US-state loads).

| Bronze table | Seeded from (Census bronze) | Loader |
|--------------|-----------------------------|--------|
| `bronze.bronze_jurisdictions_states_wikidata` | `bronze.bronze_jurisdictions_states` | `load_jurisdictions_wikidata.py` (`state` task) |
| `bronze.bronze_jurisdictions_counties_wikidata` | `bronze.bronze_jurisdictions_counties` | `load_jurisdictions_wikidata.py` (`county` task) |
| `bronze.bronze_jurisdictions_municipalities_wikidata` | `bronze.bronze_jurisdictions_municipalities` | `load_jurisdictions_wikidata.py` (`city` task) |
| `bronze.bronze_jurisdictions_school_districts_wikidata` | `bronze.bronze_jurisdictions_school_districts` | `load_jurisdictions_wikidata.py` (`school_district` task) |

**Prerequisite:** rows in the base **`bronze.bronze_jurisdictions_*`** gazetteer tables. Populate locally **or directly on Neon** with `packages/hosting/scripts/neon/run_bronze_jurisdictions_to_cloud.sh` / `ensure_bronze_jurisdictions_cloud.py` + `load_census_gazetteer.py` (see **`packages/hosting/src/hosting/neon/README.md`** — selective, **no pg_dump**).

**Primary script:** `load_jurisdictions_wikidata.py` — writes directly into the `bronze` `*_wikidata` tables. The legacy `public.jurisdictions_wikidata` table is **not** used.

**Optional rebuild:** `materialize_bronze_jurisdictions_wikidata_tables.py` rebuilds the same four tables with `CREATE TABLE … AS SELECT` joins from base bronze to `jurisdictions_wikidata`. That path only applies if you still maintain a `jurisdictions_wikidata` relation in Postgres; the main loader path is `load_jurisdictions_wikidata.py` above.

### Other bronze columns / tables tied to Wikidata

| Location | Role | How it is loaded / updated |
|----------|------|----------------------------|
| `bronze.bronze_contacts.wikidata_qid` | Person entity QID from extraction/matching | AI extraction and merge pipelines (e.g. `scripts/datasources/gemini/`) |
| `bronze.bronze_organizations_meetings` (if `wikidata_qid` present) | Org QID when matched | Same family of loaders |
| `bronze.bronze_events_channels.in_wikidata` | Channel appears validated against Wikidata | `packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py` and related channel loaders |

### YouTube / search (outside bronze, but Wikidata-related)

| Script | What it touches |
|--------|-----------------|
| `validate_channels_wikidata.py` | Validates channels against Wikidata; updates **`events_channels_search`** (`in_wikidata`-style flags), not bronze |
| `load_channels.py` (this folder) | Docstring points at `packages/scrapers/src/scrapers/youtube/load_channels.py` — enriches/validates using `WikidataQuery` |

### Supporting modules

| File | Purpose |
|------|---------|
| `wikidata_integration.py` | WDQS client (`WikidataQuery`) used by loaders |
| `run_load_jurisdictions_wikidata.sh` | Thin wrapper: forwards all args to `load_jurisdictions_wikidata.py` via `.venv` |
| `run_wikidata_priority_states_background.sh` | **Local / VPS:** priority dev USPS (`PRIORITY_STATES`), all four jurisdiction types, incremental merge + sensible WDQS env; **`nohup`** + log under `data/logs/` (`RUN_FOREGROUND=1` to block) |
| `load_jurisdictions_wikidata_colab.ipynb` | Optional Jupyter driver (defaults match priority states locally) |
| `fix_fips_codes.py`, `cleanup_bad_counties.py` | Data fixes for jurisdiction FIPS / county quality |
| `generate_mapping_report.sql` | Ad hoc reporting |

## Environment

- Database URL: `NEON_DATABASE_URL_DEV` or `NEON_DATABASE_URL` (see `.env.example`).
- Optional tuning: `WIKIDATA_CACHE_DIR`, `WIKIDATA_CITY_IDENTIFIER_BATCH`, `WIKIDATA_SCHOOL_IDENTIFIER_BATCH` (see `.env.example`).

## `fips_gnis_map.parquet` (dump extract) → bronze enrichment

If you built **`data/cache/wikidata/fips_gnis_map.parquet`** from `wikidata_fips_gnis_extract_local.py`, use it **before** re-running heavy WDQS:

```bash
# One-time: warm JSON cache + Postgres lookup table (fast SQL joins)
.venv/bin/python packages/scrapers/src/scrapers/wikidata/warm_geography_cache_from_parquet.py \
  --warm-cache --postgres

# Per state: stamp wikidata_id from parquet (still no official_website)
.venv/bin/python packages/scrapers/src/scrapers/wikidata/warm_geography_cache_from_parquet.py \
  --apply-bronze --states AL --types city

# Hydrate websites via wbgetentities only (skips bulk WDQS — avoids ReadError/429)
WIKIDATA_WARM_FROM_PARQUET=1 WIKIDATA_SKIP_BULK_WDQS=1 WIKIDATA_HYDRATE_MISSING_WEBSITES=1 \
  ./packages/scrapers/src/scrapers/wikidata/run_wikidata_happy_path.sh --states AL --types city --force
```

With `--happy-path`, if `fips_gnis_map.parquet` exists, those three env vars default **on** automatically.

Parquet has **Q-ids only**; `official_website` still comes from the loader’s Wikibase API step.

## County websites only (`official_website`)

Same pattern as municipalities, on `bronze.bronze_jurisdictions_counties_wikidata`.

Optional: stamp Q-ids from parquet first:

```bash
.venv/bin/python packages/scrapers/src/scrapers/wikidata/warm_geography_cache_from_parquet.py \
  --apply-bronze --states AL --types county
```

Run hydration (summary log: `data/logs/county_website_hydrate_<timestamp>.json`):

```bash
./packages/scrapers/src/scrapers/wikidata/run_hydrate_county_websites.sh --states AL
./packages/scrapers/src/scrapers/wikidata/run_hydrate_county_websites.sh --priority-states
./packages/scrapers/src/scrapers/wikidata/run_hydrate_county_websites.sh --all-us-states --force
```

Check progress:

```sql
SELECT usps,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE official_website IS NOT NULL AND BTRIM(official_website) <> '') AS with_url,
       MAX(official_website_updated_at) AS last_website_update
FROM bronze.bronze_jurisdictions_counties_wikidata
GROUP BY usps
ORDER BY usps;
```

## Municipality websites only (`official_website`)

After rows have a `wikidata_id`, hydrate **P856 official website** via Wikibase `wbgetentities` (no bulk WDQS). Timestamps on the bronze table:

| Column | Meaning |
|--------|---------|
| `official_website_updated_at` | Set when `official_website` is newly written or changed |
| `wikidata_last_updated` | Any Wikidata enrichment field updated on that row |
| `wikidata_fetched_at` | Same pass as `wikidata_last_updated` |

One-time DDL (idempotent):

```bash
.venv/bin/python packages/hosting/src/hosting/neon/ensure_bronze_jurisdictions_cloud.py --schema-only
# or migration 036_add_official_website_updated_at_bronze_wikidata.sql on Neon
```

Re-run states with **zero** municipality `*_wikidata` rows (e.g. VT, WA, WV, WY — seeds from Census, parquet Q-ids, then websites):

```bash
./packages/scrapers/src/scrapers/wikidata/run_municipality_websites_gap_states.sh
# or auto-detect from Postgres:
./packages/scrapers/src/scrapers/wikidata/run_municipality_websites_gap_states.sh --discover
```

Run hydration (writes `data/logs/municipality_website_hydrate_<timestamp>.json`):

```bash
./packages/scrapers/src/scrapers/wikidata/run_hydrate_municipality_websites.sh --states AL
./packages/scrapers/src/scrapers/wikidata/run_hydrate_municipality_websites.sh --priority-states
./packages/scrapers/src/scrapers/wikidata/run_hydrate_municipality_websites.sh --all-us-states --force
```

Check progress in SQL:

```sql
SELECT usps,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE official_website IS NOT NULL AND BTRIM(official_website) <> '') AS with_url,
       ROUND(
         100.0 * COUNT(*) FILTER (WHERE official_website IS NOT NULL AND BTRIM(official_website) <> '')
         / NULLIF(COUNT(*), 0),
         1
       ) AS pct_with_url,
       MAX(official_website_updated_at) AS last_website_update
FROM bronze.bronze_jurisdictions_municipalities_wikidata
GROUP BY usps
ORDER BY usps;
```

Municipalities **and** counties — **percent of all Census jurisdictions** (denominator = gazetteer base, not `*_wikidata` row count):

```sql
SELECT
  usps,
  jurisdiction_type,
  total_jurisdictions,
  in_wikidata,
  with_url,
  ROUND(100.0 * in_wikidata / NULLIF(total_jurisdictions, 0), 1) AS pct_in_wikidata,
  ROUND(100.0 * with_url / NULLIF(total_jurisdictions, 0), 1) AS pct_with_url,
  last_website_update
FROM (
  SELECT
    b.usps,
    b.jurisdiction_type::text AS jurisdiction_type,
    COUNT(*)::int AS total_jurisdictions,
    COUNT(w.geoid)::int AS in_wikidata,
    COUNT(*) FILTER (
      WHERE w.official_website IS NOT NULL AND BTRIM(w.official_website::text) <> ''
    )::int AS with_url,
    MAX(w.official_website_updated_at) AS last_website_update
  FROM (
    SELECT usps, geoid, jurisdiction_type
    FROM bronze.bronze_jurisdictions_municipalities
    UNION ALL
    SELECT usps, geoid, jurisdiction_type
    FROM bronze.bronze_jurisdictions_counties
  ) b
  LEFT JOIN (
    SELECT usps, geoid, official_website, official_website_updated_at, jurisdiction_type
    FROM bronze.bronze_jurisdictions_municipalities_wikidata
    UNION ALL
    SELECT usps, geoid, official_website, official_website_updated_at, jurisdiction_type
    FROM bronze.bronze_jurisdictions_counties_wikidata
  ) w
    ON w.usps = b.usps
   AND w.geoid::text = b.geoid::text
   AND w.jurisdiction_type::text = b.jurisdiction_type::text
  GROUP BY b.usps, b.jurisdiction_type
) stats
ORDER BY usps, jurisdiction_type;
```

| Column | Meaning |
|--------|---------|
| `total_jurisdictions` | Rows in Census gazetteer (`bronze_jurisdictions_municipalities` / `_counties`) |
| `in_wikidata` | Base rows with a matching `*_wikidata` shell |
| `with_url` | Base rows whose Wikidata row has `official_website` |
| `pct_in_wikidata` | `in_wikidata / total_jurisdictions × 100` |
| `pct_with_url` | `with_url / total_jurisdictions × 100` (not “% of wikidata rows only”) |

## Main entrypoint (jurisdictions)

Seven **priority development states** in code: **`AL`, `GA`, `IN`, `MA`, `MT`, `WA`, `WI`** (`PRIORITY_STATES` in `load_jurisdictions_wikidata.py`).

**Run and forget (recommended on a workstation or VPS):**

```bash
./packages/scrapers/src/scrapers/wikidata/run_wikidata_priority_states_background.sh
# tail progress:
tail -f data/logs/wikidata_priority_*.log
```

**Foreground equivalent** (logs + stdout):

```bash
RUN_FOREGROUND=1 ./packages/scrapers/src/scrapers/wikidata/run_wikidata_priority_states_background.sh
```

**Direct CLI** (also defaults `--states` CSV to those six when no env / flags narrow it):

```bash
WIKIDATA_INCREMENTAL_MERGE=1 .venv/bin/python packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py --priority-states
```

Defaults: **`--types`** is `city,county,state,school_district` unless `WIKIDATA_LOAD_TYPES` overrides.

See `load_jurisdictions_wikidata.py` for full CLI (checkpoints, county gaps, `--all-us-states`).
