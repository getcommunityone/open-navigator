---
sidebar_position: 12
---

# Master Data Management: Person & Address Entity Resolution

Design for normalizing names and addresses across heterogeneous sources so that
name search and address-map search resolve **similar entities to one canonical
record**. Links persons and addresses from OpenStates, GivingTuesday / 990s,
campaign contributions, `bronze_locations`, and the AI-extracted `event_person`
/ `event_place` / `event_organization` marts.

**Status:** design / not yet built. Build incrementally in the order in
[Build order](#build-order).

## Division of labor

dbt owns the **keys and serving**; Splink owns the **fuzzy matching and
clustering**. The two halves talk through exactly two tables, so neither reaches
into the other's internals.

```
dbt (keys + conformance)          Python / Splink (matching)         dbt (serving)
──────────────────────────        ──────────────────────────         ─────────────────
Layer 0  extensions               Layer 3  Splink model              Layer 5  dim_*_master
Layer 1  normalization macros  ►  Layer 4  predict + cluster    ►            bridge_*_xref
Layer 2  conformed stagings       writes clusters → bronze              (reads cluster table)
```

- **dbt → Splink contract:** `int_persons__unioned` / `int_addresses__unioned`
  (the conformed input Splink reads).
- **Splink → dbt contract:** `bronze.entity_person_clusters` /
  `bronze.entity_address_clusters`
  (`source_system, source_pk, master_person_id, match_probability`).

## Why this shape

- Reuses the record-linkage pattern already proven in
  `int_master__crosswalk` (one CTE per strategy, `match_method` +
  `match_confidence`), rather than a bespoke MDM tool.
- Normalization keys live **upstream in dbt** where they are shared and tested —
  Splink's `block_on(...)` clauses reference those same columns.
- Cross-reference **bridge tables** link sources without mutating source data.
- Every step is independently shippable (exact-match first, fuzzy later).

## The sources

| Source | Table | Name field(s) | Address field(s) | Strong keys |
|---|---|---|---|---|
| OpenStates persons | `bronze.bronze_persons_scraped` | `name`, `given_name`, `family_name` | `mailing_address` | `openstates_person_id`, `email`, `phone`, `ocd_id` |
| GivingTuesday / 990 | `bronze.bronze_organizations_nonprofits_nccs` | `org_name_current` | `f990_org_addr_street/city/state/zip`, `org_addr_full`, lat/long | `ein` |
| Campaign contributions | `bronze.bronze_campaigns_contributions` | `contributor_name` | `contributor_city/state/zip` | `contributor_employer`, `committee_id` |
| Locations | `bronze.bronze_locations` | `name` | `address`, `city`, `state`, `zip`, `county`, lat/long | `telephone`, `website` |
| Event extraction | `event_person`, `event_place`, `event_organization` | `full_name` / `display_name` | `event_place.normalized_address`, `street_address`, `place_city`, lat/long | none (AI-extracted) |

:::warning Grain mismatch
`contributor_name` and 990 `org_name_current` are **organizations**, not people.
Route them to an organization resolution pool (or at minimum a separate
`entity_type` partition) — do not link them against `event_person` / OpenStates
humans. Connect person ↔ org via an affiliation edge instead.
:::

## Layer 0 — extensions

One migration / `dbt run-operation`. Used by Splink's Postgres comparison
functions and by the API search trigram indexes.

```sql
create extension if not exists unaccent;
create extension if not exists pg_trgm;
create extension if not exists fuzzystrmatch;
```

## Layer 1 — normalization macros (dbt)

In `dbt_project/macros/`. These produce the blocking keys Splink consumes, so
they must live here, shared, not inside the Splink script. Keep the existing
`normalize_name` for the generic case and add:

- `normalize_person_name(col)` — `unaccent` → lowercase → flip "Last, First" →
  strip titles (`mr|mrs|dr|hon|councilmember|commissioner`) and suffixes
  (`jr|sr|iii`) → collapse whitespace.
- `name_phonetic_key(col)` — `dmetaphone(family_name)` (Double Metaphone, via
  `fuzzystrmatch`) for the fuzzy blocking key; Splink also uses `dmetaphone` as a
  name comparison level.
- `normalize_address(col)` — `unaccent` → lowercase → expand USPS abbreviations
  (`st→street`, `ave→avenue`, `n→north`…) → strip unit/suite → collapse.
- `zip5(col)` — `left(regexp_replace(zip, '\D', '', 'g'), 5)`.
- `address_match_key(...)` —
  `md5(normalized_street || '|' || city_norm || '|' || state_code || '|' || zip5)`.

Address **parsing** (street vs unit vs city) is the one task worth doing outside
dbt — a small `usaddress` / `libpostal` enrichment in `packages/ingestion` that
writes parsed components back to bronze. Start SQL-only (abbreviation expansion
covers ~80%); add the parser only if match recall is poor.

## Layer 2 — conformance staging (dbt)

`stg_<source>__person` and `stg_<source>__address` for each of the six sources,
all emitting one uniform contract, then unioned into
`int_persons__unioned` / `int_addresses__unioned`:

```
source_system, source_pk, entity_type,
-- names
raw_name, name_norm, given_name_norm, family_name_norm,
family_name_initial, name_phonetic_key,   -- initial = left(family_name_norm, 1), for blocking
-- addresses: PARSED INTO COLUMNS, not one string (Splink matches far better this way)
raw_address, address_norm, address_match_key,
street_number, street_name, city_norm, state_code, zip5,
lat, lon,
-- strong keys, nullable
email, phone, ein, external_id
```

:::tip Parse addresses into columns
Splink performs significantly better when an address is split into distinct
columns than when fed one long string — each component gets its own comparison
and term-frequency weighting. Break every source address into `street_number`,
`street_name`, `city_norm`, `state_code`, `zip5` during conformance. SQL
abbreviation expansion covers the easy cases; the `usaddress` / `libpostal`
enrichment (Layer 1) fills `street_number` / `street_name` for the messy tail.
:::

Standardization happens here too, before anything reaches Splink — **garbage in,
garbage out**: lowercase every string, strip leading/trailing and double
whitespace (`normalize_name` / `normalize_address` already do this), `unaccent`,
and null out empties so Splink sees real nulls rather than `''`.

This is the highest-value artifact. **Validate row counts and key null-rates
here before going further** — most of the value and most of the bugs live in
conformance.

## Layer 3–4 — Splink (Python, `packages/`)

New Python is a proper library, not a script (`packages/` rule). Record linkage
is explicitly allowed outside dbt (ML / ingestion).

- **Location:** `packages/ingestion/src/ingestion/mdm/` — `person_linker.py`,
  `address_linker.py`, shared `settings.py`, and a CLI so it runs as
  `python -m ingestion.mdm.person_linker` (mirrors `llm.governance`,
  `ingestion.youtube`). Add `splink` to that package via `uv`.
- **Backend:** Splink Postgres backend on `localhost:5433/open_navigator`,
  reading `public.int_persons__unioned`; results write back to `bronze`. No data
  leaves the warehouse. (DuckDB backend is the fallback if Postgres perf bites.)
- **Blocking rules — run several in sequence** so a typo in one field doesn't
  drop the pair (a record blocked out by a bad zip is still caught by a
  name-based rule). Avoids the `O(N²)` all-pairs blowup. Use the dbt keys:
  - `block_on("zip5")` — exact zip.
  - `block_on("family_name_initial", "state_code")` — first initial of surname + state.
  - `block_on("street_name")` — shared street name.
  - `block_on("email")` / `block_on("external_id")` — strong-key shortcuts.

  Keep `entity_type` as a partition so org rows never block against people.

- **Comparison levels — ordered, most-to-least certain per column.** Mix string
  metrics (Jaro-Winkler / Levenshtein) with phonetics (Double Metaphone).

  **Person name** (`given_name_norm`, `family_name_norm`):
  1. Exact match (`john bowyer` == `john bowyer`).
  2. **Double Metaphone** match — catches `jon`/`john`, `smith`/`smyth`.
  3. **Jaro-Winkler ≥ 0.88** — catches typos `jhon`, `bowyre`.
  4. Else / null.

  **Address** (parsed columns):
  - `street_number` — **exact-or-null only**. A wrong number is a different
    house; do not fuzzy-match it.
  - `street_name`, `city_norm` — Jaro-Winkler / Levenshtein levels (`main st`
    vs `maen st`).
  - `zip5` — **partial credit**: exact = strong; first-3-digits match = a
    positive (weaker) level; total mismatch = penalty. Don't treat zip as
    all-or-nothing.
  - lat/long distance band as a corroborating level when both present.

- **Term-frequency (TF) adjustments — turn these on.** A match on a rare name or
  rare street name is heavier evidence than a match on `Smith` or `Main`. Splink
  down-weights common values and boosts rare ones automatically; enable TF on
  `family_name_norm`, `given_name_norm`, `street_name`, and `city_norm`.

- **Training:** `estimate_u_using_random_sampling` + EM; persist the trained
  model JSON in the package (versioned) for reproducible runs.
- **Clustering:** `cluster_pairwise_predictions_at_threshold(df, threshold=0.9)`
  → `cluster_id` becomes `master_person_id` / `master_address_id`. Tune the
  threshold from Splink's match-weight waterfall charts; log precision/recall on
  a hand-labeled sample.

**Survivorship (golden record) stays in dbt** — pick best-source / most-complete
per cluster in reviewable SQL, not in Python.

## Layer 5 — serving (dbt marts)

- `dim_person_master`, `dim_address_master` — golden records, built by joining
  `int_*__unioned` to the Splink cluster table plus survivorship logic.
- `bridge_person_xref`, `bridge_address_xref` —
  `master_id ↔ source_system + source_pk`.
- API name-search and address-map-search query the dims; every source reaches
  them through the bridge.
- `GIN (name_norm gin_trgm_ops)` and `GIN (address_norm gin_trgm_ops)` indexes
  keep `similarity()` / `%` searches fast.

```
bronze sources ─┐
                ├─► stg_<src>__person/address (conform) ─► int_*__unioned
event_* marts ──┘                                              │
                                                               ▼
                                          Splink: predict + cluster (packages/ingestion)
                                                               │
                                                               ▼
                                          bronze.entity_*_clusters (master_id)
                                                               │
                                                               ▼
                      dim_person_master / dim_address_master + bridge_*_xref ◄── API search
```

## Build order

Each step is shippable on its own.

1. Extensions + the five normalization macros.
2. Conformed stagings → `int_persons__unioned` / `int_addresses__unioned`.
   **Validate row counts + key null-rates before continuing.**
3. Splink linker on **addresses first** (smaller comparison space, lat/long is a
   strong signal) as the template.
4. `dim_address_master` + `bridge_address_xref` + API trigram index. Prove search
   end-to-end on one entity.
5. Repeat 3–4 for persons.

## Watch-outs

- **Organizations vs people:** `contributor_name` and 990 `org_name_current` go
  to an organization master, not the person pool.
- **AI-extracted sources are lowest trust:** `event_person` / `event_place` have
  no strong keys and known dirtiness (channel-name collisions, promotion gaps).
  Use a conservative match threshold and rank them last in survivorship so a
  hallucinated name never becomes a golden record.
