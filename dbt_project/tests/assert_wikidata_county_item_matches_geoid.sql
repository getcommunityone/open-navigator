{{ config(tags=['data_quality', 'wikidata', 'websites']) }}

-- A county's Wikidata website must come from that county's own Wikidata item:
-- the item's FIPS (P882, stored as wikidata_fips_code) must equal the row's
-- 5-digit GEOID, state prefix included. An earlier hydration matched items on
-- the bare 3-digit county code, so Allen County, IN (18003) carried Baldwin
-- County, AL's item (P882 01003) and its website (#461). The wikidata leg of
-- int_jurisdiction_websites reads exactly these rows (official_website set).
-- Repair: python -m scrapers.wikidata.rehydrate_county_qids --apply
-- Returns the offending rows.

select
    w.geoid,
    w.usps,
    w.name,
    w.wikidata_id,
    w.wikidata_fips_code,
    w.official_website
from {{ source('bronze', 'bronze_jurisdictions_counties_wikidata') }} w
where w.official_website is not null
  and btrim(w.official_website) <> ''
  and replace(btrim(coalesce(w.wikidata_fips_code, '')), '-', '')
      is distinct from replace(btrim(w.geoid::text), '-', '')
