{{ config(materialized='table') }}

/*
    Intermediate (MDM): the conformed person pool with its Splink resolution attached.

    Mirrors int_organizations__clustered / int_addresses__clustered (which cluster
    deterministically) but the person pool resolves PROBABILISTICALLY: Splink writes
    bronze.entity_person_clusters (run via `python -m ingestion.mdm person`), and this
    model joins those clusters + the per-occurrence match_confidence back onto the
    conformed pool so the marts can serve master_person_id and flag weak matches.

    Grain: one row per source person occurrence (person_uid), unchanged from
    int_persons__unioned.

    Resilience: left join + coalesce(master_person_id, person_uid) keeps every row
    valid even before the next linker run — until Splink is re-run with the new linker
    (which now retains match_confidence), the cluster table may lack confidence and a
    row falls back to a singleton master id with NULL confidence.
*/

select
    i.*,
    coalesce(c.master_person_id, i.person_uid) as master_person_id,
    -- per-occurrence merge confidence (max incident Splink edge probability):
    --   >= cluster_threshold -> auto-merged; [match,cluster) -> borderline candidate;
    --   NULL -> no candidate edge (isolated) OR clusters not yet recomputed.
    c.match_confidence
from {{ ref('int_persons__unioned') }} i
left join {{ source('bronze', 'entity_person_clusters') }} c
    on c.person_uid = i.person_uid
