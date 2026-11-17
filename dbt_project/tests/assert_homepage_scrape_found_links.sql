-- Freshness / coverage (context-engineering.md, principle 5).
-- The jurisdiction homepage scrape once saved 6,407 city homepages but no video or
-- social links for any of them (a concurrency bug), and nothing reported it. This
-- fails when fewer than 5% of scraped city homepages have any YouTube link, in
-- `youtube_channels` (website_scrape) or `social_media.youtube`. A healthy scan
-- finds links on roughly a quarter of city sites. Returns a row when it fails.
{{ config(severity='warn', tags=['freshness']) }}

with scraped as (
    select
        count(*) as homepages,
        count(*) filter (
            where jsonb_array_length(coalesce(payload -> 'social_media' -> 'youtube', '[]'::jsonb)) > 0
               or exists (
                    select 1
                    from jsonb_array_elements(coalesce(payload -> 'youtube_channels', '[]'::jsonb)) as c
                    where c ->> 'discovery_method' like '%website_scrape%'
               )
        ) as with_links
    from {{ source('bronze', 'bronze_jurisdictions_municipalities_scraped') }}
    where coalesce(btrim(homepage_url), '') <> ''
)

select homepages, with_links, round(100.0 * with_links / nullif(homepages, 0), 1) as pct_with_links
from scraped
where homepages > 0 and with_links < 0.05 * homepages
