# Plan: repoint leaders/officials search onto MDM (retire `contact_official`)

Status: **approved, not yet executed** (2026-06-05). Execute as one PR against a
**quiet warehouse** (the heavy step is a 13.8M-row `mdm_person` rebuild) — see
"Why not done yet". Goal: officials served from MDM, `public.contact_official`
dropped, per the "everything uses MDM" rule.

## Background / why

`public.contact_official` (34,296 rows, mart `dbt_project/models/marts/contact_official.sql`,
re-created in commit `6b958e68` after migration 052 dropped the empty legacy
table) is the ONLY model of government office (mayor/councilor/legislator +
title/district/jurisdiction). The leaders search (`api/routes/search_postgres.py`
→ `search_officials_pg`) reads it directly. It must be replaced by an MDM bridge.

## Validated findings (these shaped the design — verified against the dev warehouse)

1. **Officials' identity is NOT in MDM yet.** `bronze_officials_openstates`
   persons are keyed `ocd-person/<uuid>`; **0 of 21,548** join to `mdm_person`
   (`ocd-person` UUIDs are never a `source_pk`; the `bronze_persons_osf_ledb`
   feed uses *integer* ids — a different OpenStates feed). So officials must be
   *added* as an MDM person source.
2. **`person_uid` is deterministic**: in `int_persons__unioned`,
   `person_uid = md5(source_system || '|' || source_pk)`. So once officials are a
   source, every join is exact — **no fuzzy matching, ever**.
3. `int_persons__unioned` unions: `stg_openstates__person`, `stg_osf_ledb__person`,
   `stg_persons_ai__person`, `stg_contributions__person`, `stg_parcels__person`,
   `stg_990_officers__person`, `stg_openstates_legislators__person`.
4. **`bronze.bronze_persons_scraped` already carries office data** on an existing
   MDM source: `role`, `jurisdiction_id`, `state_code`, `ocd_id`, `image`,
   `primary_party`, `openstates_person_id`. Municipal officials (Maddox, Tyner…)
   already live here — it's the right home for scraped council members (NOT the
   interim `bronze_officials_scraped` built this session).
5. `mdm_person`: 13.78M rows, 13.19M master_person_id (Splink clustering is ~1:1
   today — weak dedup).
6. API leaders result shape to preserve: `id, full_name, title, jurisdiction,
   state_code, state, party, district, office, email, phone, photo_url, is_current`.

## Steps

### Step 1 — make officials an MDM person source (low risk, file work)
- New `dbt_project/models/staging/stg_officials_openstates__person.sql` projecting
  `bronze.bronze_officials_openstates` into the `int_persons__unioned` column
  shape, with `source_system = 'bronze_officials_openstates'`,
  `source_pk = ocd_person_id` → `person_uid = md5('bronze_officials_openstates'||'|'||ocd_person_id)`.
  Match the existing person-staging column contract (full_name, name_norm,
  given/family norm, email, phone, city_norm, state_code, zip5, image→ wherever
  photo lands, party). De-dupe to one row per `ocd_person_id`.
- Add it as the 8th source in `dbt_project/models/intermediate/int_persons__unioned.sql`.
- **Reroute the council scraper** (`ingestion.municipal.load_council_officials`)
  to write into `bronze.bronze_persons_scraped` (role, jurisdiction_id, ocd_id,
  image, name, state_code) instead of the interim `bronze_officials_scraped`.
  Then the council members ride the existing scraped-persons MDM source.

### Step 2 — rebuild `mdm_person` (HEAVY — needs a quiet warehouse)
- Rebuild `mdm_person` + `mdm_person_source_link` to absorb the new source.
- Re-run Splink clustering (`ingestion.mdm`) so officials dedupe against existing
  people. The `person_uid` works without it; clustering is the quality layer.

### Step 3 — `mdm_person_office` bridge (the new MDM model)
- `dbt_project/models/marts/mdm_person_office.sql`, grain one row per
  (person, office-holding). Columns: `person_office_id` (PK = md5 natural key),
  `person_uid` (FK→`mdm_person`), `master_person_id`, `jurisdiction_id`,
  `jurisdiction_name`, `state_code`, `state`, `title`, `district`, `office`,
  `party`, `email`, `phone`, `photo_url`, `is_current`, `source_system`.
- UNION two sources, joined to `mdm_person` on the deterministic `person_uid`:
  - **OpenStates**: `bronze_officials_openstates` →
    `person_uid = md5('bronze_officials_openstates'||'|'||ocd_person_id)`;
    title=initcap(role), district, jurisdiction=organization_name,
    office=organization_classification, photo_url=image, is_current per term.
  - **Scraped municipal**: `bronze_persons_scraped` where `role` + `jurisdiction_id`
    present → `person_uid = md5('bronze_persons_scraped'||'|'||<source_pk>)`.
- Declare PK + FK(person_uid→mdm_person) in `_schema_*.yml` per the mdm_* convention.

### Step 4 — repoint the API
- `api/routes/search_postgres.py::search_officials_pg`: read
  `mdm_person ⋈ mdm_person_office` instead of `contact_official`, preserving the
  result shape (esp. `photo_url`) and the city filter
  (`jurisdiction ILIKE '%city%' AND NOT '%county%'`).

### Step 5 — decommission `contact_official`
- Delete mart model `dbt_project/models/marts/contact_official.sql` + remove the
  interim UNION; drop `stg_scraped__official.sql`; drop the table via a
  `packages/hosting/scripts/neon/migrations/` migration (dev only).
- Remove the interim `bronze.bronze_officials_scraped` table + the
  `bronze_officials_scraped` source registration in `_staging.yml`.

## Verify
- `select full_name,title,district from mdm_person_office o join mdm_person p
  on p.person_uid=o.person_uid where o.state_code='AL' and
  o.jurisdiction_name ilike '%tuscaloosa%' and o.jurisdiction_name not ilike '%county%';`
  → Mayor Maddox + 7 council districts.
- Coverage vs the 34,296 contact_official rows; deterministic-join rate (should be
  100% by construction).
- `/search?types=leaders&state=AL&city=Tuscaloosa` returns them with photos.

## Why not done yet (2026-06-05)
- The warehouse is **contended** by a parallel policy-analysis dbt job that held
  `bronze_event_youtube` ~1 hr; heavy rebuilds (Step 2 = 13.8M rows) get
  blocked/slow.
- Subagents died 4× on socket errors this session — couldn't parallelize safely.

## Interim state (safe, in working tree, uncommitted)
- Leaders search works **now** via `contact_official` + the 7 Tuscaloosa
  councilors I loaded (the county-leak + photo-render fixes are also in).
- Scraper/loader (`scrapers.municipal`, `ingestion.municipal`) built + tested;
  reroute to `bronze_persons_scraped` is Step 1.
- See memory `project-leaders-contact-official`, `project-decisions-map-pipeline`.
