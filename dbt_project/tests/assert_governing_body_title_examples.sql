-- #1442: the SQL title -> body resolution gives the expected body for every real example title
-- (seeds/governing_body_title_example.csv). pytest checks the Python twin (ingestion.governance.body_titles) on the
-- same seed, so the two cannot drift apart. Returns the examples that disagree.
with example as (
    select
        e.*,
        {{ body_jurisdiction_kind('e.jurisdiction_type') }}                  as kind,
        {{ clean_meeting_title_for_body('e.title', 'e.jurisdiction_name') }} as cleaned
    from {{ ref('governing_body_title_example') }} as e
),

resolved as (
    {{ resolve_governing_body('example') }}
)

select
    e.title,
    e.expected_body_key,
    r.body_key,
    e.expected_body_name,
    r.body_name
from example as e
left join resolved as r on r.cleaned = e.cleaned and r.kind = e.kind
where coalesce(r.body_key, '') <> coalesce(e.expected_body_key, '')
   or coalesce(r.body_name, '') <> coalesce(e.expected_body_name, '')
