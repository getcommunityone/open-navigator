{{ config(tags=['data_quality', 'meetings', 'documents']) }}

-- A county meeting document (5-digit county FIPS census_geoid) may only link to
-- a meeting that carries that same county geoid. Canonical county ids drop
-- "County" ('tuscaloosa_01125'), so the mart's state + normalized-name fallback
-- would otherwise attach a county agenda to the same-named city's meeting
-- ('City of Tuscaloosa') on the same day and body. The mart therefore links
-- county documents by geoid only (#392 review). Returns the offending rows.

select
    d.event_meeting_document_id,
    d.jurisdiction_id,
    d.census_geoid,
    d.doc_date,
    d.body_name,
    d.event_meeting_id,
    m.jurisdiction       as meeting_jurisdiction,
    m.jurisdiction_name  as meeting_jurisdiction_name
from {{ ref('event_meeting_document') }} d
join {{ ref('event_meeting') }} m
  on m.event_meeting_id = d.event_meeting_id
where d.census_geoid ~ '^\d{5}$'
  and substring(m.jurisdiction from '(\d{5,7})') is distinct from d.census_geoid
