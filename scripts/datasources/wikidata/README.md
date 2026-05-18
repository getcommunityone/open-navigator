# Wikidata Data Scripts

Scripts for querying Wikidata (WDQS), enriching Open Navigator bronze tables, and validating YouTube channels.

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
  .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states AL --types county,city
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

**Prerequisite:** rows in the base **`bronze.bronze_jurisdictions_*`** gazetteer tables. Populate locally **or directly on Neon** with `scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh` / `ensure_bronze_jurisdictions_cloud.py` + `load_census_gazetteer.py` (see **`scripts/deployment/neon/README.md`** — selective, **no pg_dump**).

**Primary script:** `load_jurisdictions_wikidata.py` — writes directly into the `bronze` `*_wikidata` tables. The legacy `public.jurisdictions_wikidata` table is **not** used.

**Optional rebuild:** `materialize_bronze_jurisdictions_wikidata_tables.py` rebuilds the same four tables with `CREATE TABLE … AS SELECT` joins from base bronze to `jurisdictions_wikidata`. That path only applies if you still maintain a `jurisdictions_wikidata` relation in Postgres; the main loader path is `load_jurisdictions_wikidata.py` above.

### Other bronze columns / tables tied to Wikidata

| Location | Role | How it is loaded / updated |
|----------|------|----------------------------|
| `bronze.bronze_contacts.wikidata_qid` | Person entity QID from extraction/matching | AI extraction and merge pipelines (e.g. `scripts/datasources/gemini/`) |
| `bronze.bronze_organizations_meetings` (if `wikidata_qid` present) | Org QID when matched | Same family of loaders |
| `bronze.bronze_events_channels.in_wikidata` | Channel appears validated against Wikidata | `scripts/datasources/youtube/load_youtube_channels_bronze.py` and related channel loaders |

### YouTube / search (outside bronze, but Wikidata-related)

| Script | What it touches |
|--------|-----------------|
| `validate_channels_wikidata.py` | Validates channels against Wikidata; updates **`events_channels_search`** (`in_wikidata`-style flags), not bronze |
| `load_channels.py` (this folder) | Docstring points at `scripts/datasources/youtube/load_channels.py` — enriches/validates using `WikidataQuery` |

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
.venv/bin/python scripts/datasources/wikidata/warm_geography_cache_from_parquet.py \
  --warm-cache --postgres

# Per state: stamp wikidata_id from parquet (still no official_website)
.venv/bin/python scripts/datasources/wikidata/warm_geography_cache_from_parquet.py \
  --apply-bronze --states AL --types city

# Hydrate websites via wbgetentities only (skips bulk WDQS — avoids ReadError/429)
WIKIDATA_WARM_FROM_PARQUET=1 WIKIDATA_SKIP_BULK_WDQS=1 WIKIDATA_HYDRATE_MISSING_WEBSITES=1 \
  ./scripts/datasources/wikidata/run_wikidata_happy_path.sh --states AL --types city --force
```

With `--happy-path`, if `fips_gnis_map.parquet` exists, those three env vars default **on** automatically.

Parquet has **Q-ids only**; `official_website` still comes from the loader’s Wikibase API step.

## Main entrypoint (jurisdictions)

Seven **priority development states** in code: **`AL`, `GA`, `IN`, `MA`, `MT`, `WA`, `WI`** (`PRIORITY_STATES` in `load_jurisdictions_wikidata.py`).

**Run and forget (recommended on a workstation or VPS):**

```bash
./scripts/datasources/wikidata/run_wikidata_priority_states_background.sh
# tail progress:
tail -f data/logs/wikidata_priority_*.log
```

**Foreground equivalent** (logs + stdout):

```bash
RUN_FOREGROUND=1 ./scripts/datasources/wikidata/run_wikidata_priority_states_background.sh
```

**Direct CLI** (also defaults `--states` CSV to those six when no env / flags narrow it):

```bash
WIKIDATA_INCREMENTAL_MERGE=1 .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --priority-states
```

Defaults: **`--types`** is `city,county,state,school_district` unless `WIKIDATA_LOAD_TYPES` overrides.

See `load_jurisdictions_wikidata.py` for full CLI (checkpoints, county gaps, `--all-us-states`).
