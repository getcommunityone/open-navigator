---
sidebar_position: 12
---

# Master Data Management: Person & Address Entity Resolution

Design for normalizing names and addresses across heterogeneous sources so that
name search and address-map search resolve **similar entities to one canonical
record**. Links persons and addresses from OpenStates, GivingTuesday / 990s,
campaign contributions, `bronze_locations`, and the AI-extracted `event_person`
/ `event_place` / `event_organization` marts.

**Status:** partially built. Addresses resolve deterministically and serve from
`mdm_address`; organizations serve from `mdm_organization`. The person pool
(`int_persons__unioned`) is built and now serves at **source-occurrence grain**
from `mdm_person` (PK `person_uid`) — the canonical public person table that
replaced the legacy `contacts_search_ai` model. Probabilistic person clustering
(Splink → `int_persons__clustered` → a deduplicated `master_person_id`) is the
remaining piece; until it lands, `mdm_person` serves the conformed occurrences.
Serving models use the `mdm_` prefix (the `dim_`/`fact_` star-schema naming is
disallowed). Build incrementally in the order in [Build order](#build-order).

## Division of labor

dbt owns the **keys and serving**; Splink owns the **fuzzy matching and
clustering**. The two halves talk through exactly two tables, so neither reaches
into the other's internals.

```
dbt (keys + conformance)          Python / Splink (matching)         dbt (serving)
──────────────────────────        ──────────────────────────         ─────────────────
Layer 0  extensions               Layer 3  Splink model              Layer 5  mdm_person/address
Layer 1  normalization macros  ►  Layer 4  predict + cluster    ►            mdm_bridge_*
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
| OpenStates persons | `bronze_persons_scraped` via `stg_bronze_persons_scraped` (filtered `is_usable_person`) | `name_clean` | `mailing_address` | `ocd_id`, `email`, `phone` |
| Election candidates | `bronze_persons_osf_ledb` (OSF LEDB) | `full_name`, `firstname`, `lastname` | `geo_name`, `state_abb` | `ledb_candid` |
| GivingTuesday / 990 | `bronze.bronze_organizations_nonprofits_nccs` | `org_name_current` | `f990_org_addr_street/city/state/zip`, `org_addr_full`, lat/long | `ein` |
| Campaign contributions | `bronze.bronze_campaigns_contributions` | `contributor_name` | `contributor_city/state/zip` | `contributor_employer`, `committee_id` |
| Locations | `bronze.bronze_locations` | `name` | `address`, `city`, `state`, `zip`, `county`, lat/long | `telephone`, `website` |
| Parcel / property records | `bronze.bronze_addresses` (~598k) | `owner_name` | `street_line1` (number embedded), `street_line2`, `city`, `state_abbr`, `postal_code` | `parcel_number`, `jurisdiction_id` |
| AI persons | `bronze.bronze_persons_from_ai` | `full_name`, `appeared_as` | — | `person_id`, `wikidata_qid` |
| AI places | `bronze.bronze_places_from_ai` | — | `normalized_address`, `street_address`, `city`, `state_code`, lat/long | `geocode_status` (no strong id) |
| AI organizations | `bronze.bronze_organizations_from_ai` | `org_name`, `org_name_normalized` | — | `ein`, `ntee_code`, `wikidata_qid` |

**Read AI sources at bronze, not at the marts.** `event_person` / `event_place` /
`event_organization` are medallion *outputs* (`bronze_*_from_ai` + event/
jurisdiction joins + monthly partitioning). Feeding a mart back into an
intermediate model is a backwards DAG dependency; MDM also doesn't need the event
context to resolve an entity. So conform from `bronze_persons_from_ai`,
`bronze_places_from_ai`, `bronze_organizations_from_ai` directly.

`bronze.bronze_addresses` is the largest address source (~598k) but is **not**
pre-parsed despite its column names: `street_number` is empty (the number is
embedded in `street_line1`) and `situs_full` carries a noisy source prefix, so
the street/number split is done in `stg_parcels__address`. Its `owner_name` is a
parcel owner (person *or* business), so it feeds the name pipeline too under the
right `entity_type`.

**Reference / gazetteer (not resolution inputs):** `bronze.bronze_geo_places`
(Census place gazetteer: name → geoid → state) and
`bronze.bronze_osf_places_geocoded` (place → lat/long → population) are lookups
used to **validate and enrich** `city_norm` / place names and attach geoids —
they are a reference dimension, not entities to dedup.

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

`stg_<source>__person` and `stg_<source>__address` for each resolution source
(OpenStates, 990/NCCS, campaign contributions, `bronze_locations`,
`bronze_addresses`, and the `event_*` marts — not every source feeds both
pipelines: contributions and `event_person` are name-only, `bronze_addresses`
feeds both),
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

## Layer 3–4 — resolution

**Split by data shape (decided after a first Splink run over-merged addresses):**

- **Addresses → deterministic (dbt, not Splink).** Addresses are structured, so
  they resolve on the exact normalized-address key. Probabilistic clustering
  chained whole ZIPs together (a 13,699- then 4,469-member blob of *different*
  houses) because fuzzy `street_number` scoring is too weak against exact
  zip+city+state agreement. `int_addresses__clustered` sets
  `master_address_id = coalesce(address_match_key, address_uid)` — identical
  addresses merge, streetless singletons stay separate. Result: 442,579 →
  **376,337 master addresses**, largest cluster a real shared PO box (551), built
  in seconds, zero chaining. `mdm_address` + `mdm_bridge_address_xref` serve it.
- **Persons → Splink (probabilistic).** Names have no clean key and genuinely
  need fuzzy + phonetic matching; this is where Splink earns its keep.

The Splink design below now applies to the **person** pool.

### Splink (Python, `packages/`)

New Python is a proper library, not a script (`packages/` rule). Record linkage
is explicitly allowed outside dbt (ML / ingestion).

- **Location:** `packages/ingestion/src/ingestion/mdm/` — `person_linker.py`,
  `address_linker.py`, shared `settings.py`, and a CLI so it runs as
  `python -m ingestion.mdm.person_linker` (mirrors `llm.governance`,
  `ingestion.youtube`). Add `splink` to that package via `uv`.
- **Backend:** Splink Postgres backend on `localhost:5433/open_navigator`,
  reading the `intermediate.int_*__unioned` tables; results write back to
  `bronze`. No data leaves the warehouse. (DuckDB backend is the fallback if
  Postgres perf bites.) Two backend constraints, caught via `--dry-run` and
  handled in `ingestion.mdm`: the Postgres dialect has **no Jaro-Winkler** (use
  Levenshtein via `fuzzystrmatch`), and it resolves input tables by **bare name
  only** (engine sets `search_path=intermediate,bronze,public`; schema-qualified
  names fail).
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

- `mdm_person`, `mdm_address` — golden records, built by joining `int_*__unioned`
  to the cluster table plus survivorship logic. **Addresses** are live
  (deterministic clustering). **Persons** currently serve at source-occurrence
  grain (PK `person_uid`) directly off `int_persons__unioned`; the upstream `ref`
  swaps to `int_persons__clustered` once Splink person clustering lands, adding a
  deduplicated `master_person_id` — same evolution `mdm_organization` followed.
- `mdm_bridge_person_address`, `mdm_person_source_link`, `mdm_bridge_address_xref`
  — link the masters to `source_system + source_pk` (and to each other).
- API name-search and address-map-search query the `mdm_` marts; every source
  reaches them through the bridge.
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
                          mdm_person / mdm_address + mdm_bridge_* ◄── API search
```

## Build order

Each step is shippable on its own.

1. Extensions + the five normalization macros.
2. Conformed stagings → `int_persons__unioned` / `int_addresses__unioned`.
   **Validate row counts + key null-rates before continuing.**
3. Splink linker on **addresses first** (smaller comparison space, lat/long is a
   strong signal) as the template.
4. `mdm_address` + `mdm_bridge_address_xref` + API trigram index. Prove search
   end-to-end on one entity. ✅ done.
5. Repeat 3–4 for persons. `mdm_person` already serves at occurrence grain;
   remaining work is the Splink person linker → `int_persons__clustered` →
   `master_person_id`, then repoint `mdm_person`'s upstream `ref`.

## Watch-outs

- **Organizations vs people:** `contributor_name` and 990 `org_name_current` go
  to an organization master, not the person pool.
- **AI-extracted sources are lowest trust:** `bronze_persons_from_ai` /
  `bronze_places_from_ai` have no strong keys and known dirtiness (channel-name
  collisions, promotion gaps).
  Use a conservative match threshold and rank them last in survivorship so a
  hallucinated name never becomes a golden record.
- **Name token order differs across sources** (found via `audit_mdm_keys`):
  campaign `contributor_name` is `LAST, FIRST` (comma-delimited, which
  `normalize_person_name` flips), but parcel `bronze_addresses.owner_name` is
  `LAST FIRST` with **no comma** (`DORROUGH JESSE`) — the macro can't detect
  order, so it does not flip, and a surname-as-last-token phonetic key keys on
  the given name instead. Owner names also carry estate/trust noise
  (`... 1/2 INT & ... TRUST`). **Decision:** do not rely on a single "surname"
  phonetic key. Emit phonetic keys for *both* the first and last token and let
  Splink's name comparison + multiple blocking rules resolve order, rather than
  hard-coding a per-source flip. Low match weight handles the trust/estate noise
  gracefully. See [Layer 1](#layer-1--normalization-macros-dbt) /
  [Layer 3](#layer-34--splink-python-packages).
- **Streetless rows + PO boxes need NULL keys** (found building
  `int_addresses__unioned`): `address_match_key` already returns NULL when the
  street is blank — without that, ~11.7k streetless Selma AL parcels collapsed
  onto one hash. A shared **PO box** is the same trap (`po box 412` = 551
  distinct owners): treat PO-box-only situs as not-a-unique-address and exclude
  it from the exact key too, leaving those rows to Splink's fuzzy comparison.
- **High-volume sources must dedup to distinct entities, not occurrences**
  (found building `int_persons__unioned`): `bronze_campaigns_contributions` has
  **~24.5M transaction rows** — a donor who gave 500 times is one entity, not 500
  pool rows. `stg_contributions__person` collapses to one row per distinct
  contributor identity (`name_norm` + city + state + zip) before the union, with
  `source_pk` = a hash of that identity; the transaction-level link belongs in a
  separate xref, not the person pool. Apply the same rule to any future
  transaction-grained source. Result: 24.5M txns → **1,885,888 distinct
  contributors** (13× collapse); full person pool `int_persons__unioned` =
  2,362,852 rows.
- **Materialize high-volume staging as a table, not a view** (perf, found
  building the above): `stg_contributions__person` is a view, so the regex-heavy
  `normalize_person_name` + `distinct on` over 24.5M rows re-runs on every read —
  the union build took ~21 min, almost all of it here. Switch this one staging
  model to `materialized='table'` (or an incremental int model keyed on the
  append-only contributions) so the normalization runs once. The view default is
  fine for the small sources.
- **Filter non-names at the source, flag the rest** (found via `full_name`/
  `is_probable_person`): scraped pages yield ~12k non-name strings (titles, dates,
  "hours of operation", UI chrome). `stg_openstates__person` reuses the existing
  `is_usable_person` gate from `stg_bronze_persons_scraped` so they never enter
  the pool. For residual junk from other sources, `int_persons__unioned` exposes
  `is_probable_person` (false for orgs, names with digits, 1- or 6+-token strings)
  and `full_name` = `initcap(name_norm)` for display. Filter with
  `where is_probable_person` before serving.
