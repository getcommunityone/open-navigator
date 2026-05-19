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