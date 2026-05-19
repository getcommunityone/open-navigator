-- Track when official_website (P856) was last set from Wikidata enrichment.
-- Applied by load_jurisdictions_wikidata.py and hydrate_municipality_websites_from_wikidata.py.

ALTER TABLE bronze.bronze_jurisdictions_states_wikidata
    ADD COLUMN IF NOT EXISTS official_website_updated_at TIMESTAMP;

ALTER TABLE bronze.bronze_jurisdictions_counties_wikidata
    ADD COLUMN IF NOT EXISTS official_website_updated_at TIMESTAMP;

ALTER TABLE bronze.bronze_jurisdictions_municipalities_wikidata
    ADD COLUMN IF NOT EXISTS official_website_updated_at TIMESTAMP;

ALTER TABLE bronze.bronze_jurisdictions_school_districts_wikidata
    ADD COLUMN IF NOT EXISTS official_website_updated_at TIMESTAMP;
