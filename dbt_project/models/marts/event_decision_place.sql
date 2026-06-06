{{
    config(
        materialized='table',
        unique_key='event_decision_place_id',
        tags=['marts', 'event-extraction', 'ai', 'bridge']
    )
}}

/*
public.event_decision_place — bridge linking AI-extracted decisions to the
places they reference.

GRAIN: one row per (decision, place_id). A decision's reference graph carries a
many-to-many set of place slugs (place_refs[]) plus one primary_place_id, so a
bridge — not a single column — is the correct shape.

WHY event_decision (not event_policy_decision):
  public.event_policy_decision is the TEXT/policy pipeline (Pipeline A, sourced
  from bronze.bronze_policy_decisions). That source has NO place_refs and its
  source_event_id is in a different id-space from event_place.analysis_id (only
  26 of ~1,500 ids overlap), so it CANNOT carry this link.
  The decision<->place reference graph lives only in the MULTIMODAL pipeline:
  bronze_events_analysis_ai -> bronze_decisions_from_ai -> public.event_decision,
  which already exposes primary_place_id + place_refs and shares event_place's
  analysis_id id-space. This bridge is therefore anchored on event_decision.

RESOLUTION: place_id slugs are NOT globally unique across analyses (the same
slug recurs in different meetings), so a place_ref is resolved to an event_place
row SCOPED TO THE SAME analysis_id. Refs that have no matching event_place row in
their analysis are orphans (~2.6%) and are intentionally dropped here — a later
backfill pass will land the missing place rows.

SOURCE : public.event_decision (place_refs jsonb, primary_place_id text)
LOOKUP : public.event_place (place_id, analysis_id)
TARGET : public.event_decision_place (plain table; single-column PK so it can be
         contract-enforced — the partitioned event_* parents cannot be FK
         targets, so FKs to them are asserted via relationships tests instead).
*/

with decisions as (
    -- collapse the partitioned source to the latest row per decision
    select
        event_decision_id,
        analysis_id,
        primary_place_id,
        place_refs
    from (
        select
            event_decision_id,
            analysis_id,
            primary_place_id,
            place_refs,
            row_number() over (
                partition by event_decision_id
                order by extracted_at desc
            ) as _rn
        from {{ ref('event_decision') }}
    ) d
    where _rn = 1
),

-- one (decision, place_id) per referenced slug, carrying the is_primary flag
refs as (
    select
        d.event_decision_id,
        d.analysis_id,
        ref_pid.place_id,
        bool_or(ref_pid.place_id = d.primary_place_id) as is_primary
    from decisions d
    cross join lateral (
        -- place_refs[] members ...
        select jsonb_array_elements_text(coalesce(d.place_refs, '[]'::jsonb)) as place_id
        union
        -- ... plus the primary (may not appear in place_refs)
        select d.primary_place_id where d.primary_place_id is not null
    ) ref_pid
    where ref_pid.place_id is not null
      and ref_pid.place_id <> ''
    group by d.event_decision_id, d.analysis_id, ref_pid.place_id
),

-- resolve each slug to an event_place row in the SAME analysis (latest row)
places as (
    select place_id, analysis_id
    from (
        select
            place_id,
            analysis_id,
            row_number() over (
                partition by place_id, analysis_id
                order by extracted_at desc
            ) as _rn
        from {{ ref('event_place') }}
    ) p
    where _rn = 1
)

select
    md5(r.event_decision_id || '|' || r.place_id) as event_decision_place_id,
    r.event_decision_id,
    r.place_id,
    r.is_primary
from refs r
join places p
  on p.place_id = r.place_id
 and p.analysis_id = r.analysis_id
