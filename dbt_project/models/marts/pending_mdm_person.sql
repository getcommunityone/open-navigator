{{ config(materialized='table') }}

/*
    Mart (MDM): the human-review queue for person records that should NOT be served
    as-is. Two disjoint quality signals, distinguished by pending_reason:

      - 'not_probable_person': failed the is_probable_person heuristic in
        int_persons__unioned (org acronyms like "HHS", UI chrome, names with digits,
        1- or 6+-token strings). These never reach mdm_person today — surfaced here so
        a reviewer can rescue real people the heuristic over-rejected.

      - 'ambiguous_match': Splink PREDICTED a match (>= predict threshold, 0.9) but the
        strongest incident edge stayed BELOW the 0.99 auto-merge bar, so the record was
        not merged into a cluster. candidate_person_uid points at the most-likely
        counterpart. Empty until the linker is re-run with the confidence-retaining
        build (it populates bronze.entity_person_predictions).

    Grain: one row per person_uid. This is a standalone review table — it intentionally
    has NO FK to mdm_person, because the 'not_probable_person' rows are not in mdm_person
    (flag-in-place: the 'ambiguous_match' rows DO stay in mdm_person, flagged
    review_status='needs_review').
*/

with clustered as (
    -- collapse to one row per person_uid (the pool carries several name occurrences
    -- per key — same dedup rule as mdm_person).
    select distinct on (person_uid)
        person_uid,
        master_person_id,
        match_confidence,
        is_probable_person,
        entity_type,
        full_name,
        source_system,
        source_pk,
        state_code,
        city_norm
    from {{ ref('int_persons__clustered') }}
    where entity_type = 'person'
    order by
        person_uid,
        (full_name is not null) desc,
        (state_code is not null) desc,
        full_name
),

-- symmetric candidate edges -> the single strongest counterpart per person_uid.
edges as (
    select person_uid_l as person_uid, person_uid_r as candidate_person_uid, match_probability
    from {{ source('bronze', 'entity_person_predictions') }}
    union all
    select person_uid_r as person_uid, person_uid_l as candidate_person_uid, match_probability
    from {{ source('bronze', 'entity_person_predictions') }}
),

best_candidate as (
    select distinct on (person_uid)
        person_uid,
        candidate_person_uid,
        match_probability
    from edges
    order by person_uid, match_probability desc
),

not_probable as (
    select
        person_uid,
        full_name,
        source_system,
        source_pk,
        state_code,
        city_norm,
        'not_probable_person'::text as pending_reason,
        null::double precision      as match_confidence,
        null::text                  as candidate_person_uid
    from clustered
    where not is_probable_person
),

ambiguous as (
    select
        c.person_uid,
        c.full_name,
        c.source_system,
        c.source_pk,
        c.state_code,
        c.city_norm,
        'ambiguous_match'::text     as pending_reason,
        b.match_probability         as match_confidence,
        b.candidate_person_uid
    from clustered c
    join best_candidate b on b.person_uid = c.person_uid
    where c.is_probable_person
      and b.match_probability < 0.99   -- predicted but never crossed the auto-merge bar
)

select * from not_probable
union all
select * from ambiguous
