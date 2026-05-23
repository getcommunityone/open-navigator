-- MA pilot verification queries (DuckDB).
--
-- Run from the repo root:
--     duckdb -c ".read scripts/datasources/ma_pilot/verify.sql"
-- Or interactively:
--     duckdb
--     .read scripts/datasources/ma_pilot/verify.sql
--
-- Reads the local parquet files written by
-- ``scripts/datasources/ma_pilot/scrape_ma_jurisdictions.py``.

.print
.print === MA pilot verification ===
.print

-- 1. Row counts by jurisdiction.
.print Contacts per jurisdiction:
SELECT
    jurisdiction_id,
    jurisdiction_name,
    jurisdiction_type,
    COUNT(*)                                    AS contact_rows,
    COUNT(DISTINCT source_page_url)             AS distinct_pages,
    SUM(CASE WHEN is_mayor THEN 1 ELSE 0 END)   AS mayor_rows,
    SUM(CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_email,
    SUM(CASE WHEN phone IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_phone
FROM 'data/bronze/contacts_scraped/ma_pilot_contacts.parquet'
GROUP BY 1, 2, 3
ORDER BY jurisdiction_name;

.print
.print Jurisdictions with NO contact rows (red flag):
SELECT
    j.name                  AS jurisdiction_name,
    j.jurisdiction_id,
    j.homepage
FROM (VALUES
    ('Boston',          'municipality_2507000', 'https://www.boston.gov/'),
    ('Cambridge',       'municipality_2511000', 'https://www.cambridgema.gov/'),
    ('Worcester',       'municipality_2582000', 'https://www.worcesterma.gov/'),
    ('Springfield',     'municipality_2567000', 'https://www.springfield-ma.gov/'),
    ('Lowell',          'municipality_2537000', 'https://www.lowellma.gov/'),
    ('Somerville',      'municipality_2562535', 'https://www.somervillema.gov/'),
    ('Newton',          'municipality_2545560', 'https://www.newtonma.gov/'),
    ('Quincy',          'municipality_2555745', 'https://www.quincyma.gov/'),
    ('Plymouth County', 'county_25023',         'https://www.plymouthcountyma.gov/'),
    ('Norfolk County',  'county_25021',         'http://www.norfolkcounty.org/')
) AS j(name, jurisdiction_id, homepage)
LEFT JOIN (
    SELECT DISTINCT jurisdiction_id
    FROM 'data/bronze/contacts_scraped/ma_pilot_contacts.parquet'
) c USING (jurisdiction_id)
WHERE c.jurisdiction_id IS NULL;

.print
.print Mayor-flagged contacts (these came from mayor-style URLs or had 'Mayor' in the title):
SELECT
    jurisdiction_name,
    person_name,
    title_or_role,
    email,
    phone,
    source_page_url
FROM 'data/bronze/contacts_scraped/ma_pilot_contacts.parquet'
WHERE is_mayor = TRUE
ORDER BY jurisdiction_name, person_name;

.print
.print Contacts WITHOUT person_name (cleanup candidates):
SELECT
    jurisdiction_name,
    source_page_url,
    title_or_role,
    email,
    phone
FROM 'data/bronze/contacts_scraped/ma_pilot_contacts.parquet'
WHERE person_name IS NULL OR TRIM(person_name) = ''
LIMIT 25;

.print
.print Duplicate emails across jurisdictions (often shared portals or generic mailboxes):
SELECT
    email,
    COUNT(DISTINCT jurisdiction_id) AS jurisdiction_count,
    LIST(DISTINCT jurisdiction_name) AS jurisdictions
FROM 'data/bronze/contacts_scraped/ma_pilot_contacts.parquet'
WHERE email IS NOT NULL
GROUP BY email
HAVING COUNT(DISTINCT jurisdiction_id) > 1
ORDER BY jurisdiction_count DESC;

.print
.print === YouTube channels ===
.print

-- The YouTube file may not exist if --skip-youtube was used. Guard with a check.
.print YouTube channels by jurisdiction:
SELECT
    jurisdiction_name,
    channel_url,
    channel_title,
    subscriber_count,
    video_count,
    discovery_method,
    confidence
FROM 'data/bronze/youtube_channels/ma_pilot_youtube_channels.parquet'
ORDER BY jurisdiction_name, confidence DESC;

.print
.print Jurisdictions with NO YouTube channel discovered:
SELECT
    j.name AS jurisdiction_name,
    j.jurisdiction_id
FROM (VALUES
    ('Boston',          'municipality_2507000'),
    ('Cambridge',       'municipality_2511000'),
    ('Worcester',       'municipality_2582000'),
    ('Springfield',     'municipality_2567000'),
    ('Lowell',          'municipality_2537000'),
    ('Somerville',      'municipality_2562535'),
    ('Newton',          'municipality_2545560'),
    ('Quincy',          'municipality_2555745'),
    ('Plymouth County', 'county_25023'),
    ('Norfolk County',  'county_25021')
) AS j(name, jurisdiction_id)
LEFT JOIN (
    SELECT DISTINCT jurisdiction_id
    FROM 'data/bronze/youtube_channels/ma_pilot_youtube_channels.parquet'
) y USING (jurisdiction_id)
WHERE y.jurisdiction_id IS NULL;
