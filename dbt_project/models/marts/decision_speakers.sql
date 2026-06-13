{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'decision', 'ai'],
        contract={'enforced': true}
    )
}}

/*
public.decision_speakers — per-decision attribution of the people who gave named
testimony, extracted from event_decision.human_element->'personal_stories'.

GRAIN: one row per event_decision_id, restricted to decisions that have at least
one personal_story carrying a non-empty person_id slug.

SOURCE : public.event_decision (human_element jsonb). personal_stories is a jsonb
         array whose elements carry person_id (a slug, e.g.
         'jesus_carmona_jr_resident_clayton_county_georgia'), story_headline and
         story_detail. ~2,001 of ~8,886 decisions have >=1 element.

COLUMNS:
  * speaker_ids   — jsonb ARRAY of DISTINCT person_id slugs, in first-appearance
                    order, CAPPED to at most 6 (the card only shows a few). The
                    cap is applied with a row_number() window before aggregating.
  * speaker_count — total DISTINCT person_id slugs (UNCAPPED) so the card can
                    render "+N more".

Honest data only (CLAUDE.md No Fabricated Data): only the real person_id slugs
that exist in the extraction are emitted; no names are synthesized.

KEYS: single-column PK (event_decision_id) so it is contract-enforced. event_decision
is partitioned with a COMPOSITE PK (event_decision_id, extracted_at) and so cannot
be a single-column FK target — following the established event_* family convention
the FK into it is asserted via a relationships data_test, not an enforced constraint.
*/

with decisions as (
    -- collapse the partitioned source to the latest row per decision
    select
        event_decision_id,
        human_element
    from (
        select
            event_decision_id,
            human_element,
            row_number() over (
                partition by event_decision_id
                order by extracted_at desc
            ) as _rn
        from {{ ref('event_decision') }}
    ) d
    where _rn = 1
),

-- unnest personal_stories, keeping ordinality so first-appearance order is stable.
-- jsonb_array_elements only runs where the element is actually an array.
stories as (
    select
        d.event_decision_id,
        nullif(btrim(story.elem ->> 'person_id'), '') as person_id,
        story.ord
    from decisions d
    cross join lateral jsonb_array_elements(d.human_element -> 'personal_stories')
        with ordinality as story(elem, ord)
    where jsonb_typeof(d.human_element -> 'personal_stories') = 'array'
),

-- DISTINCT person_id per decision, carrying that slug's first appearance ordinality
distinct_speakers as (
    select
        event_decision_id,
        person_id,
        min(ord) as first_ord
    from stories
    where person_id is not null
    group by event_decision_id, person_id
),

-- rank by first appearance so we can cap the array to the leading 6 slugs
ranked as (
    select
        event_decision_id,
        person_id,
        first_ord,
        row_number() over (
            partition by event_decision_id
            order by first_ord, person_id
        ) as appearance_rank
    from distinct_speakers
),

-- UNCAPPED count of distinct slugs per decision
counts as (
    select
        event_decision_id,
        count(*)::integer as speaker_count
    from distinct_speakers
    group by event_decision_id
),

-- CAPPED (<=6), ordered array of slugs
capped as (
    select
        event_decision_id,
        jsonb_agg(to_jsonb(person_id) order by appearance_rank) as speaker_ids
    from ranked
    where appearance_rank <= 6
    group by event_decision_id
)

select
    c.event_decision_id,
    cap.speaker_ids,
    c.speaker_count
from counts c
join capped cap
    on cap.event_decision_id = c.event_decision_id
